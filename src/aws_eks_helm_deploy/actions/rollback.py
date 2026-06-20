"""RollbackAction — orchestration root for helm rollback (ACTION=rollback).

Requirements traceability:
    PIPE-04:   RollbackAction.run orchestrates ACTION=rollback with pre-flight check
    PIPE-05:   pre-flight uses SAFE_UPGRADE_DESCRIPTION to detect revisions deployed
               with --wait --atomic (CONTEXT D5 / 05-RESEARCH CONTRADICTION 2 workaround)

Architecture (CONTEXT D1):
    - This module is < 50 LOC in RollbackAction.run body.
    - No subprocess. No file I/O beyond kubeconfig context-manager use.
    - subprocess lives exclusively in helm/client.py (D6 invariant).
    - No chart resolution — rollback operates on the cluster's stored release.
      select_chart_source is intentionally NOT imported here.

Rollback safety contract (CONTEXT D5):
    helm 3.x does NOT record --wait in the history description by default.
    The pipe works around this by explicitly setting --description "pipe:safe-upgrade"
    on upgrade (PIPE-05). The pre-flight check here searches for that substring in
    HelmRevision.description before authorising rollback. If absent, the action raises
    ChartResolutionError (exit=4) with a consumer-friendly error message.
"""

from __future__ import annotations

import pathlib
import time
from typing import TYPE_CHECKING

import boto3.session

from aws_eks_helm_deploy.auth import select_strategy
from aws_eks_helm_deploy.aws.eks_token import generate_eks_token
from aws_eks_helm_deploy.eks.cluster import get_cluster_access
from aws_eks_helm_deploy.errors import ChartResolutionError, ConfigurationError, KubeconfigError
from aws_eks_helm_deploy.helm.client import SAFE_UPGRADE_DESCRIPTION, HelmClient
from aws_eks_helm_deploy.kube.kubeconfig import write_kubeconfig
from aws_eks_helm_deploy.logging import get_logger

if TYPE_CHECKING:
    from aws_eks_helm_deploy.auth.base import AuthStrategy
    from aws_eks_helm_deploy.pipe_io import PipeIO
    from aws_eks_helm_deploy.settings import Settings

__all__: list[str] = ["RollbackAction"]

logger = get_logger(__name__)


class RollbackAction:
    """Orchestrates the helm rollback chain with pre-flight safety check (CONTEXT D1 layering).

    Mirrors UpgradeAction structure: auth -> EKS -> kubeconfig -> pre-flight -> rollback.
    No subprocess calls here; all I/O is delegated to typed primitives.

    Pre-flight contract (PIPE-05 / CONTEXT D5):
        Reads ``helm history`` and refuses rollback unless the target revision's
        ``description`` field contains ``SAFE_UPGRADE_DESCRIPTION`` (``"pipe:safe-upgrade"``).
        This prevents rolling back to revisions deployed without ``--wait/--atomic``.

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
        """Execute the rollback chain. Returns 0 on success, exc.exit_code on PipeError.

        Only OSError is caught here (wrapped as KubeconfigError). All other typed
        PipeErrors propagate to cli.py's except PipeError handler.
        """
        s = self._settings

        # Step 1: required-field defensive checks
        if s.cluster_name is None:
            raise ConfigurationError("CLUSTER_NAME env var is required for ACTION=rollback")
        if s.release_name is None:
            raise ConfigurationError("RELEASE_NAME env var is required for ACTION=rollback")
        if s.revision is None:
            raise ConfigurationError("REVISION env var is required for ACTION=rollback")

        # Step 2: auth strategy + credentials
        strategy = self._strategy if self._strategy is not None else select_strategy(s)
        creds = strategy.get_credentials()

        # Step 3: boto3 session
        session = boto3.session.Session(region_name=s.aws_region, **creds.to_boto3_kwargs())  # type: ignore[arg-type]

        # Steps 4+5: EKS cluster metadata + bearer token (SKIPPED when kubeconfig_override set)
        if self._kubeconfig_override is None:
            cluster = get_cluster_access(session, s.cluster_name, s.aws_region)
            token = generate_eks_token(session, s.cluster_name, s.aws_region)

        # Validated required fields (guards above ensure these are not None).
        # Explicit narrowing for mypy strict: Settings fields are Optional[str/int] but the
        # guards above guarantee non-None at this point.
        assert s.release_name is not None
        assert s.revision is not None
        release: str = s.release_name
        revision: int = s.revision

        # Step 6: kubeconfig write + pre-flight + rollback
        start = time.monotonic()
        if self._kubeconfig_override is not None:
            client = HelmClient(self._kubeconfig_override)
            cluster_name = s.cluster_name
            self._run_rollback(client, release, revision, s.namespace, s.timeout)
        else:
            try:
                with write_kubeconfig(cluster, token) as kubeconfig_path:
                    client = HelmClient(kubeconfig_path)
                    self._run_rollback(client, release, revision, s.namespace, s.timeout)
            except OSError as exc:
                raise KubeconfigError(f"Failed to write kubeconfig: {exc}") from exc
            cluster_name = cluster.name

        duration_ms = int((time.monotonic() - start) * 1000)

        # Step 7: emit structured INFO log + pipe success
        message = (
            f"Rolled back release {release}"
            f" to revision {revision}"
            f" in namespace {s.namespace}"
            f" on cluster {cluster_name}"
        )
        logger.info(
            "rollback complete",
            action="rollback",
            release=release,
            namespace=s.namespace,
            revision=revision,
            cluster=cluster_name,
            duration_ms=duration_ms,
        )
        pipe.success(message)
        return 0

    def _run_rollback(
        self,
        client: HelmClient,
        release: str,
        revision: int,
        namespace: str,
        timeout: str,
    ) -> None:
        """Execute pre-flight check then helm rollback. Raises on pre-flight failure."""
        # Pre-flight: fetch history and validate target revision
        history = client.history(release=release, namespace=namespace)

        target = next((r for r in history if r.revision == revision), None)
        if target is None:
            available = [r.revision for r in history]
            raise ChartResolutionError(
                f"Revision {revision} not found in release {release!r} history. "
                f"Available revisions: {available}."
            )

        if SAFE_UPGRADE_DESCRIPTION not in target.description:
            raise ChartResolutionError(
                f"Refusing rollback to revision {revision} of release {release!r} "
                f"— that revision was NOT deployed with SAFE_UPGRADE=true "
                f"(no --wait/--atomic guarantee). "
                f"Re-deploy with SAFE_UPGRADE=true first, then retry rollback."
            )

        # Pre-flight passed — execute rollback
        client.rollback(
            release=release,
            revision=revision,
            namespace=namespace,
            timeout=timeout,
        )
