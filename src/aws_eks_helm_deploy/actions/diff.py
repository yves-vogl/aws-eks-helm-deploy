"""DiffAction — orchestration root for helm diff upgrade (ACTION=diff / DRY_RUN=true).

Requirements traceability:
    PIPE-02:   DiffAction.run orchestrates ACTION=diff and DRY_RUN=true routing (CONTEXT D2)
    SEC-06:    diff output flows through HelmClient.diff's redactor (CONTEXT D1); DiffAction
               emits only the redacted return value — never raw helm stdout (T-05-01 guard)

Architecture (CONTEXT D1):
    - This module is < 50 LOC in DiffAction.run body.
    - No subprocess. No file I/O beyond kubeconfig context-manager use.
    - subprocess lives exclusively in helm/client.py (D6 invariant).

DRY_RUN routing (R7 from 05-RESEARCH):
    cli.py dispatches to DiffAction when ``settings.action == "diff"`` OR when
    ``settings.action == "upgrade" and settings.dry_run`` (DRY_RUN=true shortcut).
    DiffAction does NOT mutate cluster state — HelmClient.diff() is read-only.

BITBUCKET_* env vars:
    When inject_bitbucket_metadata is True, the same build_bitbucket_set_args()
    helper from upgrade.py is reused. When None or False, no injection occurs
    (META-02 default-flip: None is the new sentinel meaning "unset").
"""

from __future__ import annotations

import pathlib
import time
from typing import TYPE_CHECKING

import boto3.session

from aws_eks_helm_deploy.auth import select_strategy
from aws_eks_helm_deploy.aws.eks_token import generate_eks_token
from aws_eks_helm_deploy.chart import select_chart_source
from aws_eks_helm_deploy.eks.cluster import get_cluster_access
from aws_eks_helm_deploy.errors import ConfigurationError, KubeconfigError
from aws_eks_helm_deploy.helm.client import HelmClient
from aws_eks_helm_deploy.kube.kubeconfig import write_kubeconfig
from aws_eks_helm_deploy.logging import get_logger

if TYPE_CHECKING:
    from aws_eks_helm_deploy.auth.base import AuthStrategy
    from aws_eks_helm_deploy.pipe_io import PipeIO
    from aws_eks_helm_deploy.settings import Settings

__all__: list[str] = ["DiffAction"]

logger = get_logger(__name__)


class DiffAction:
    """Orchestrates the full helm diff upgrade chain (CONTEXT D1 layering).

    Mirrors UpgradeAction structure: auth -> EKS -> kubeconfig -> chart resolution
    -> helm diff (read-only). No subprocess calls here; all I/O is delegated to
    typed primitives.

    The kubeconfig_override kwarg is a test-only scaffold — bypasses EKS token and
    kubeconfig-write steps. Production code MUST NOT use this kwarg.
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
        """Execute the diff chain. Returns 0 on success, exc.exit_code on PipeError.

        Only OSError is caught here (wrapped as KubeconfigError). All other typed
        PipeErrors propagate to cli.py's except PipeError handler.
        """
        s = self._settings

        # Step 1: required-field defensive checks (R8 — same guards as UpgradeAction)
        if s.cluster_name is None:
            raise ConfigurationError("CLUSTER_NAME env var is required for ACTION=diff")
        if s.chart is None:
            raise ConfigurationError("CHART env var is required for ACTION=diff")
        if s.release_name is None:
            raise ConfigurationError("RELEASE_NAME env var is required for ACTION=diff")

        # Step 2: auth strategy + credentials
        strategy = self._strategy if self._strategy is not None else select_strategy(s)
        creds = strategy.get_credentials()

        # Step 3: boto3 session
        session = boto3.session.Session(region_name=s.aws_region, **creds.to_boto3_kwargs())  # type: ignore[arg-type]

        # Steps 4+5: EKS cluster metadata + bearer token (SKIPPED when kubeconfig_override set)
        if self._kubeconfig_override is None:
            cluster = get_cluster_access(session, s.cluster_name, s.aws_region)
            token = generate_eks_token(session, s.cluster_name, s.aws_region)

        # Step 6: chart source factory
        chart_source = select_chart_source(s)

        # Step 7: Bitbucket metadata args (opt-in per META-01; None/False = skip)
        from aws_eks_helm_deploy.actions.upgrade import build_bitbucket_set_args

        bitbucket_args: list[str] = (
            build_bitbucket_set_args(logger) if s.inject_bitbucket_metadata else []
        )
        set_args = bitbucket_args + s.set_values  # user-supplied AFTER bitbucket (last-wins)

        # Step 8: chart resolve + kubeconfig write + helm diff (read-only)
        start = time.monotonic()
        with chart_source.resolve() as resolved:
            if self._kubeconfig_override is not None:
                client = HelmClient(self._kubeconfig_override)
                diff_text = client.diff(
                    release=s.release_name,
                    chart=resolved,
                    namespace=s.namespace,
                    values_files=s.values_files,
                    set_args=set_args,
                    timeout=s.timeout,
                )
                cluster_name = s.cluster_name
            else:
                try:
                    with write_kubeconfig(cluster, token) as kubeconfig_path:
                        client = HelmClient(kubeconfig_path)
                        diff_text = client.diff(
                            release=s.release_name,
                            chart=resolved,
                            namespace=s.namespace,
                            values_files=s.values_files,
                            set_args=set_args,
                            timeout=s.timeout,
                        )
                except OSError as exc:
                    raise KubeconfigError(f"Failed to write kubeconfig: {exc}") from exc
                cluster_name = cluster.name
            duration_ms = int((time.monotonic() - start) * 1000)

            # Step 9: emit redacted diff + structlog (SEC-06: diff_text is already redacted)
            header = f"helm diff complete for release {s.release_name} on cluster {cluster_name}"
            logger.info(
                "diff complete",
                action="diff",
                release=s.release_name,
                namespace=s.namespace,
                cluster=cluster_name,
                duration_ms=duration_ms,
            )
            pipe.success(f"{header}\n\n{diff_text}")
        return 0
