"""OciChart — OCI-registry chart source + optional Cosign keyless verification.

Requirements traceability:
  - CHART-03 (Phase 4): consumer sets CHART=oci://<registry>/<chart> + optional CHART_VERSION
    + REGISTRY_USERNAME/PASSWORD. The module logs in (if creds set) + pulls the chart into a
    tempdir and yields a ResolvedChart.
  - CHART-04 (Phase 4): consumer sets CHART_VERIFY=true + (optional)
    CHART_VERIFY_CERTIFICATE_IDENTITY + CHART_VERIFY_CERTIFICATE_OIDC_ISSUER. The module
    invokes cosign verify <ref> BEFORE helm pull.

Architecture exception (CONTEXT D5, RESEARCH §R9):
  - helm subprocess calls go through HelmClient (Phase 3 D1 invariant preserved for HELM).
  - cosign is a SEPARATE binary (not a helm command). subprocess.run for cosign lives in
    THIS MODULE — explicit scoped exception to the Phase 3 invariant per CONTEXT D5.

# This module is the scoped exception to the "only helm/client.py shells out" invariant
# — cosign is a separate binary owned end-to-end by the chart source.

Security:
  - registry_password is SecretStr | None (Plan 04-02 type — R13). Unwrapped via
    .get_secret_value() ONLY at the call site that invokes helm_client.registry_login.
    That call uses --password-stdin (R4) so the password NEVER appears in argv.
  - cosign verify runs against the OCI REFERENCE (R5), NOT against the pulled tarball.
    Different cosign subcommand (`verify-blob`) would verify a local file, but the registry
    signature is what we want to trust.
  - cosign verify runs BEFORE helm pull (R6) — if verify fails, the chart is never downloaded.
  - tempdir cleanup fires even on cosign verify failure (R8) via the try/finally.

Env isolation (RESEARCH §5):
  - HELM_REGISTRY_CONFIG = <tmp>/registry-config.json
  - DOCKER_CONFIG = <tmp>/docker-config (belt-and-braces against helm's fallback to docker creds —
        helm v3 and v4 both consult $DOCKER_CONFIG for OCI registry credentials when
        HELM_REGISTRY_CONFIG does not carry the requested host)
  - HELM_REPOSITORY_CONFIG = <tmp>/repositories.yaml
  - HELM_REPOSITORY_CACHE = <tmp>/cache
  All four point at the tempdir; nothing leaks past the context-manager scope.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess  # CONTEXT D5 scoped exception; for cosign only.
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager

from pydantic import SecretStr

from aws_eks_helm_deploy.chart.base import ResolvedChart
from aws_eks_helm_deploy.chart.local import _parse_chart_yaml
from aws_eks_helm_deploy.errors import ChartResolutionError
from aws_eks_helm_deploy.helm.client import HelmClient, _truncate_stderr
from aws_eks_helm_deploy.logging import get_logger

logger = get_logger(__name__)

__all__: list[str] = ["OciChart"]


class OciChart:
    """OCI-registry chart source with optional Cosign keyless verification.

    Constructor stores args (no I/O). resolve() runs the full lifecycle
    inside the context-manager scope.

    Args:
        reference: Already-stripped OCI reference without the ``oci://`` prefix
            (e.g. ``"127.0.0.1:5555/charts/redis"`` or ``"ghcr.io/org/chart"``).
        version: Chart version pin, or ``None`` to pull the latest.
        registry_username: Registry username for authenticated registries, or ``None``
            for public registries.
        registry_password: Registry password as ``SecretStr`` (Plan 04-02 type) for
            authenticated registries, or ``None``. The single ``.get_secret_value()``
            unwrap site is in ``_run_helm_registry_login`` (R13).
        verify: When ``True``, invoke ``cosign verify <ref>`` BEFORE ``helm pull`` (R6).
        verify_identity: Exact-match ``--certificate-identity`` constraint for cosign,
            or ``None`` to skip identity pinning (emits a WARN log when ``verify=True``).
        verify_oidc_issuer: Exact-match ``--certificate-oidc-issuer`` constraint for
            cosign, or ``None`` to skip OIDC issuer pinning.
    """

    def __init__(
        self,
        reference: str,
        version: str | None = None,
        registry_username: str | None = None,
        registry_password: SecretStr | None = None,  # R13 — SecretStr from Plan 04-02
        verify: bool = False,
        verify_identity: str | None = None,  # CHART_VERIFY_CERTIFICATE_IDENTITY
        verify_oidc_issuer: str | None = None,  # CHART_VERIFY_CERTIFICATE_OIDC_ISSUER
    ) -> None:
        self._reference = reference
        self._version = version
        self._registry_username = registry_username
        self._registry_password = registry_password
        self._verify = verify
        self._verify_identity = verify_identity
        self._verify_oidc_issuer = verify_oidc_issuer

    @contextmanager
    def resolve(self) -> Iterator[ResolvedChart]:
        """Yield a ResolvedChart with source_path inside a tempdir.

        Lifecycle (mirrors kube/kubeconfig.py CONTEXT D6):
          1. Create a tempdir with prefix ``aws-eks-helm-deploy-chart-``.
          2. Set 4 isolated env vars pointing at the tempdir (RESEARCH §5):
             HELM_REGISTRY_CONFIG, DOCKER_CONFIG, HELM_REPOSITORY_CONFIG,
             HELM_REPOSITORY_CACHE.
          3. IF registry_username AND registry_password are set: invoke
             ``helm registry login`` via HelmClient (R4 — --password-stdin).
             SecretStr is unwrapped exactly ONCE here (R13).
          4. IF verify=True: invoke ``cosign verify <ref>`` subprocess BEFORE
             helm pull (R6 ordering — if verify fails, helm pull never runs).
             cosign runs from THIS module per CONTEXT D5 scoped exception.
          5. Invoke ``helm pull oci://<ref>`` via HelmClient (D1 preserved).
          6. Discover exactly-one unpacked subdirectory (R6 single-subdir).
          7. Parse Chart.yaml, build and yield ResolvedChart.
          8. finally: shutil.rmtree(tmpdir, ignore_errors=True) — fires even on
             cosign failure (R8 — cleanup on verify failure).

        Raises:
            ChartResolutionError: If registry login, cosign verify, helm pull,
                or subdir discovery fails.
        """
        tmpdir = pathlib.Path(tempfile.mkdtemp(prefix="aws-eks-helm-deploy-chart-"))
        try:
            unpack_dir = tmpdir / "unpacked"
            unpack_dir.mkdir(exist_ok=True)

            # 4-env-var isolation (RESEARCH §5) — nothing leaks to ~/.config/helm/ or ~/.docker/
            env: dict[str, str] = os.environ.copy()
            env["HELM_REGISTRY_CONFIG"] = str(tmpdir / "registry-config.json")
            env["DOCKER_CONFIG"] = str(tmpdir / "docker-config")
            env["HELM_REPOSITORY_CONFIG"] = str(tmpdir / "repositories.yaml")
            env["HELM_REPOSITORY_CACHE"] = str(tmpdir / "cache")

            # HelmClient with placeholder kubeconfig_path — OCI ops don't need it;
            # the constructor requires a Path argument (mirrors Deviation 2 from 04-06 PLAN).
            helm_client = HelmClient(kubeconfig_path=tmpdir / "unused-kubeconfig.yaml")

            # 1. Optional registry login — R4 (--password-stdin in HelmClient);
            #    R13 (SecretStr unwrap at SINGLE site below via _run_helm_registry_login)
            if self._registry_username is not None and self._registry_password is not None:
                self._run_helm_registry_login(helm_client, env)

            # 2. Optional Cosign verify — R6 (BEFORE helm pull); R5 (against ref, not tarball);
            #    R9 (subprocess for cosign lives in THIS module per CONTEXT D5)
            if self._verify:
                self._run_cosign_verify()

            # 3. helm pull oci://<ref> --destination tmp --untar --untar-dir tmp/unpacked
            helm_client.pull_oci(
                reference=self._reference,
                destination=tmpdir,
                untar_dir=unpack_dir,
                version=self._version,
                env=env,
            )

            # 4. Single-subdir discovery (R6 — chart name from Chart.yaml, NOT OCI ref)
            candidates = [p for p in unpack_dir.iterdir() if p.is_dir()]
            if len(candidates) != 1:
                raise ChartResolutionError(
                    f"expected exactly one unpacked chart dir in {unpack_dir}, "
                    f"found {len(candidates)}"
                )
            chart_dir = candidates[0]

            # 5. Parse Chart.yaml for name + version (reuses helper from chart/local.py)
            data = _parse_chart_yaml(chart_dir)
            yield ResolvedChart(
                name=str(data.get("name", chart_dir.name)),
                version=str(data.get("version", "")),
                source_path=chart_dir,
            )
        finally:
            # R8 — cleanup fires even when cosign verify raises ChartResolutionError
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _run_helm_registry_login(
        self,
        helm_client: HelmClient,
        env: dict[str, str],
    ) -> None:
        """Invoke helm registry login — SINGLE SecretStr unwrap site (R13).

        The registry host is derived from the first path component of the reference
        (e.g. ``"ghcr.io"`` from ``"ghcr.io/org/chart"``).
        """
        assert self._registry_username is not None  # guarded by caller
        assert self._registry_password is not None  # guarded by caller
        registry_host = self._reference.split("/", 1)[0]
        helm_client.registry_login(
            registry_host=registry_host,
            username=self._registry_username,
            password=self._registry_password.get_secret_value(),  # SINGLE unwrap site (R13)
            env=env,
        )

    def _run_cosign_verify(self) -> None:
        """Invoke ``cosign verify <ref>`` — CONTEXT D5 scoped subprocess exception.

        WARN if running unconstrained (no identity / no oidc issuer): consumer is only
        verifying signature validity, not signer identity (RESEARCH §3 / R5).

        The reference is the OCI REGISTRY reference (R5), NOT a local file path.
        cosign verify runs BEFORE helm pull (R6 — this method is called first in resolve()).
        On failure, ChartResolutionError is raised and the tempdir is cleaned by finally (R8).
        """
        if self._verify_identity is None and self._verify_oidc_issuer is None:
            logger.warning(
                "chart.verify.unconstrained_identity",
                reason="cosign verify will succeed for ANY valid Sigstore signature",
                hint=(
                    "Set CHART_VERIFY_CERTIFICATE_IDENTITY and"
                    " CHART_VERIFY_CERTIFICATE_OIDC_ISSUER to pin the trusted signer"
                ),
            )

        argv: list[str] = ["cosign", "verify"]
        if self._verify_identity is not None:
            argv.extend(["--certificate-identity", self._verify_identity])
        if self._verify_oidc_issuer is not None:
            argv.extend(["--certificate-oidc-issuer", self._verify_oidc_issuer])
        # Verify against the REGISTRY REFERENCE (R5), NOT a local file path
        argv.append(self._reference)

        try:
            subprocess.run(  # noqa: S603 — CONTEXT D5 scoped exception
                argv,
                capture_output=True,
                text=True,
                check=True,
                timeout=120,
            )
        except subprocess.CalledProcessError as exc:
            raise ChartResolutionError(
                f"cosign verify failed for {self._reference}: "
                f"{_truncate_stderr(exc.stderr if exc.stderr else '')}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ChartResolutionError(
                f"cosign verify for {self._reference} timed out after {exc.timeout}s"
            ) from exc
