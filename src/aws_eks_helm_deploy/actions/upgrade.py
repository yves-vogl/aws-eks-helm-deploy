"""UpgradeAction — orchestration root for helm upgrade --install.

Requirements traceability:
    CHART-01:  end-to-end: resolve_local_chart -> HelmClient.upgrade_install
    CHART-05:  pipe.success emits exact format per CONTEXT D7
    PIPE-01:   full chain (auth -> token -> kubeconfig -> chart -> helm) wired
    PIPE-06:   every failure maps to a typed PipeError; OSError wrapped as KubeconfigError
    HISTORY-01: Settings.history_max field (closes #17)
    HISTORY-02: settings.history_max flows through to HelmClient.upgrade_install(history_max=...)
    META-01:   INJECT_BITBUCKET_METADATA opt-in; 5 BITBUCKET_* env vars; missing-var warn

Architecture (CONTEXT D1):
    - This module is < 50 LOC in UpgradeAction.run body.
    - No subprocess. No file I/O beyond kubeconfig context-manager use.
    - subprocess lives exclusively in helm/client.py.

BITBUCKET_* env vars are read directly (documented exception to the
"no os.environ outside settings.py" rule). These are Bitbucket-platform-supplied
variables, not consumer-supplied pipe.yml vars. Mirrors the same exception in
auth/__init__.py::_derive_session_name. See CONTEXT D5 + RESEARCH Section G.
"""

from __future__ import annotations

import os
import pathlib
import time
from typing import TYPE_CHECKING, Final

import boto3.session
import structlog

from aws_eks_helm_deploy.auth import select_strategy
from aws_eks_helm_deploy.aws.eks_token import generate_eks_token
from aws_eks_helm_deploy.chart.local import resolve_local_chart
from aws_eks_helm_deploy.eks.cluster import get_cluster_access
from aws_eks_helm_deploy.errors import ConfigurationError, KubeconfigError
from aws_eks_helm_deploy.helm.client import HelmClient
from aws_eks_helm_deploy.kube.kubeconfig import write_kubeconfig
from aws_eks_helm_deploy.logging import get_logger

if TYPE_CHECKING:
    from aws_eks_helm_deploy.auth.base import AuthStrategy
    from aws_eks_helm_deploy.pipe_io import PipeIO
    from aws_eks_helm_deploy.settings import Settings

__all__: list[str] = ["BITBUCKET_META_VARS", "UpgradeAction", "build_bitbucket_set_args"]

logger = get_logger(__name__)

# 5 BITBUCKET_* env vars -> helm key mappings. Order-stable per RESEARCH Section G.
BITBUCKET_META_VARS: Final[list[tuple[str, str]]] = [
    ("BITBUCKET_BUILD_NUMBER", "bitbucket.bitbucket_build_number"),
    ("BITBUCKET_REPO_SLUG", "bitbucket.bitbucket_repo_slug"),
    ("BITBUCKET_COMMIT", "bitbucket.bitbucket_commit"),
    ("BITBUCKET_TAG", "bitbucket.bitbucket_tag"),
    ("BITBUCKET_STEP_TRIGGERER_UUID", "bitbucket.bitbucket_step_triggerer_uuid"),
]


def build_bitbucket_set_args(log: structlog.BoundLogger) -> list[str]:
    """Build --set-string-formatted args for all present BITBUCKET_* env vars.

    For each (env_var, helm_key) in BITBUCKET_META_VARS:
      - If env_var is absent or empty: emit structlog warning + skip.
      - Otherwise: append "helm_key=value" to result.

    The returned list is consumed by HelmClient.upgrade_install(set_args=...)
    which renders each entry as --set-string helm_key=value (RESEARCH G /
    corrections #4 / Pitfall 4).

    Args:
        log: Bound structlog logger (injected to allow capture_logs in tests).

    Returns:
        List of "helm_key=value" strings for present BITBUCKET_* vars.
    """
    result: list[str] = []
    for env_var, helm_key in BITBUCKET_META_VARS:
        value = os.environ.get(env_var)
        if not value:  # None or empty string (CONTEXT D5)
            log.warning("missing_metadata_key", key=env_var)
            continue
        result.append(f"{helm_key}={value}")
    return result


class UpgradeAction:
    """Orchestrates the full helm upgrade --install chain (CONTEXT D1 layering).

    This class is the composition root for Phase 3: wires auth -> EKS -> kubeconfig
    -> chart resolution -> helm in a typed, testable sequence. All I/O is delegated
    to typed primitives from Plans 03-01..03. No subprocess calls here.

    The kubeconfig_override kwarg is a test-only scaffold for Plan 03-05 integration
    tests (kind admin kubeconfig path bypasses EKS token and kubeconfig-write steps).
    Production code MUST NOT use this kwarg.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        strategy: AuthStrategy | None = None,
        kubeconfig_override: pathlib.Path | None = None,  # test-only
    ) -> None:
        self._settings = settings
        self._strategy = strategy
        self._kubeconfig_override = kubeconfig_override

    def run(self, pipe: PipeIO) -> int:
        """Execute the upgrade chain. Returns 0 on success, exc.exit_code on PipeError.

        Only OSError is caught here (wrapped as KubeconfigError). All other typed
        PipeErrors propagate to cli.py's except PipeError handler.
        """
        s = self._settings

        # Step 1: required-field defensive checks
        if s.cluster_name is None:
            raise ConfigurationError("CLUSTER_NAME env var is required for ACTION=upgrade")
        if s.chart is None:
            raise ConfigurationError("CHART env var is required for ACTION=upgrade")
        if s.release_name is None:
            raise ConfigurationError("RELEASE_NAME env var is required for ACTION=upgrade")

        # Step 2: auth strategy + credentials
        strategy = self._strategy if self._strategy is not None else select_strategy(s)
        creds = strategy.get_credentials()

        # Step 3: boto3 session (Plan 02-04 pattern)
        session = boto3.session.Session(region_name=s.aws_region, **creds.to_boto3_kwargs())  # type: ignore[arg-type]

        # Steps 4+5: EKS cluster metadata + bearer token (SKIPPED when kubeconfig_override set)
        if self._kubeconfig_override is None:
            cluster = get_cluster_access(session, s.cluster_name, s.aws_region)
            token = generate_eks_token(session, s.cluster_name, s.aws_region)

        # Step 6: chart resolution
        resolved = resolve_local_chart(s.chart)

        # Step 7: Bitbucket metadata args (opt-in per CONTEXT D5 / META-01)
        bitbucket_args: list[str] = (
            build_bitbucket_set_args(logger) if s.inject_bitbucket_metadata else []
        )
        set_args = bitbucket_args + s.set_values  # user-supplied AFTER bitbucket (last-wins)

        # Step 8: kubeconfig write + helm upgrade
        start = time.monotonic()
        if self._kubeconfig_override is not None:
            client = HelmClient(self._kubeconfig_override)
            result = client.upgrade_install(
                release=s.release_name,
                chart=resolved,
                namespace=s.namespace,
                values_files=s.values_files,
                set_args=set_args,
                history_max=s.history_max,
                timeout=s.timeout,
            )
            cluster_name = s.cluster_name
        else:
            try:
                with write_kubeconfig(cluster, token) as kubeconfig_path:
                    client = HelmClient(kubeconfig_path)
                    result = client.upgrade_install(
                        release=s.release_name,
                        chart=resolved,
                        namespace=s.namespace,
                        values_files=s.values_files,
                        set_args=set_args,
                        history_max=s.history_max,
                        timeout=s.timeout,
                    )
            except OSError as exc:
                raise KubeconfigError(f"Failed to write kubeconfig: {exc}") from exc
            cluster_name = cluster.name
        duration_ms = int((time.monotonic() - start) * 1000)

        # Step 9: success message + structlog (CHART-05 + D7 + OBS-01)
        message = (
            f"Deployed chart {resolved.name} ({resolved.version})"
            f" to release {s.release_name}"
            f" in namespace {s.namespace}"
            f" on cluster {cluster_name}"
        )
        logger.info(
            "upgrade complete",
            action="upgrade",
            release=s.release_name,
            namespace=s.namespace,
            chart_source=s.chart,
            chart_name=resolved.name,
            chart_version=resolved.version,
            cluster=cluster_name,
            helm_revision=result.revision,
            duration_ms=duration_ms,
        )
        pipe.success(message)
        return 0
