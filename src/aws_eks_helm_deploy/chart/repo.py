"""RepoChart — Helm repository chart source.

Requirements traceability:
  - CHART-02 (Phase 4): consumer sets CHART=repo://<name>/<chart> + REPO_URL +
    optional CHART_VERSION; this module runs `helm repo add` + `helm repo update` +
    `helm pull <name>/<chart>` into a tempdir and yields a ResolvedChart whose
    source_path points at the unpacked chart directory.

Architecture:
  - All subprocess.run calls go through HelmClient (Phase 3 D1 invariant preserved).
    This module constructs a HelmClient internally (with kubeconfig_path=None — none
    needed for repo ops) and calls helm_client.repo_add/repo_update/pull_repo.
    The HelmClient routes each through subprocess.run from helm/client.py only.
  - Tempdir lifecycle mirrors kube/kubeconfig.py (CONTEXT D6): mkdtemp ->
    try/yield/finally(rmtree).
  - Env isolation: HELM_REPOSITORY_CONFIG + HELM_REPOSITORY_CACHE point at the
    tempdir so nothing leaks to ~/.config/helm/.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager

from aws_eks_helm_deploy.chart.base import ResolvedChart
from aws_eks_helm_deploy.chart.local import _parse_chart_yaml
from aws_eks_helm_deploy.errors import ChartResolutionError
from aws_eks_helm_deploy.helm.client import HelmClient

__all__: list[str] = ["RepoChart"]


class RepoChart:
    """Resolves a chart from a Helm HTTP/HTTPS repository.

    Constructor stores args only — no I/O. The actual helm subprocess calls happen
    inside resolve() under the context-manager scope.

    Args:
        name: Helm repository alias (e.g. ``"bitnami"``). Used in
            ``helm repo add <name> <url>`` and ``helm pull <name>/<chart>``.
        chart: Chart name within the repository (e.g. ``"redis"``).
        repo_url: HTTPS URL of the helm repository index
            (e.g. ``"https://charts.bitnami.com/bitnami"``).
        version: Chart version pin (e.g. ``"18.5.0"``), or ``None`` to pull
            the latest version available.
    """

    def __init__(
        self,
        name: str,
        chart: str,
        repo_url: str,
        version: str | None = None,
    ) -> None:
        self._name = name
        self._chart = chart
        self._repo_url = repo_url
        self._version = version

    @contextmanager
    def resolve(self) -> Iterator[ResolvedChart]:
        """Yield a ResolvedChart with source_path inside a tempdir.

        Lifecycle (mirrors kube/kubeconfig.py CONTEXT D6):
          1. Create a tempdir with prefix ``aws-eks-helm-deploy-chart-``.
          2. Set HELM_REPOSITORY_CONFIG + HELM_REPOSITORY_CACHE in a scoped env
             dict so helm writes repo config + cache only inside the tempdir.
          3. helm repo add <name> <repo_url>
          4. helm repo update <name>
          5. helm pull <name>/<chart> --destination <tmpdir>
                --untar --untar-dir <tmpdir>/unpacked [--version <version>]
          6. Discover the single unpacked subdirectory (R7: chart name from
             Chart.yaml, NOT the tarball filename or repo ref path component).
          7. Parse Chart.yaml, build and yield ResolvedChart.
          8. finally: shutil.rmtree(tmpdir, ignore_errors=True) — fires on
             both normal exit AND exception (CONTEXT D6).

        Raises:
            ChartResolutionError: If helm commands fail, or the unpacked
                directory contains anything other than exactly one chart dir.
        """
        tmpdir = pathlib.Path(tempfile.mkdtemp(prefix="aws-eks-helm-deploy-chart-"))
        try:
            unpack_dir = tmpdir / "unpacked"
            unpack_dir.mkdir(exist_ok=True)

            # Isolated env — nothing leaks to ~/.config/helm/ (RESEARCH §5 + R7)
            env: dict[str, str] = os.environ.copy()
            env["HELM_REPOSITORY_CONFIG"] = str(tmpdir / "repositories.yaml")
            env["HELM_REPOSITORY_CACHE"] = str(tmpdir / "cache")

            # HelmClient with a placeholder kubeconfig_path — repo ops don't need it,
            # but the constructor requires a Path argument (Deviation 2 from 04-06 PLAN).
            # The placeholder path is never created or read by repo_add/update/pull_repo.
            helm_client = HelmClient(kubeconfig_path=tmpdir / "unused-kubeconfig.yaml")

            # 1. helm repo add <name> <repo_url>
            helm_client.repo_add(self._name, self._repo_url, env)
            # 2. helm repo update <name>
            helm_client.repo_update(self._name, env)
            # 3. helm pull <name>/<chart> --destination <tmp> --untar --untar-dir <tmp/unpacked>
            repo_chart = f"{self._name}/{self._chart}"
            helm_client.pull_repo(repo_chart, tmpdir, unpack_dir, self._version, env)

            # 4. Single-subdir discovery (R7) — chart name from Chart.yaml,
            # NOT the tgz filename or repo ref path component.
            candidates = [p for p in unpack_dir.iterdir() if p.is_dir()]
            if len(candidates) != 1:
                raise ChartResolutionError(
                    f"expected exactly one unpacked chart dir in {unpack_dir}, "
                    f"found {len(candidates)}"
                )
            chart_dir = candidates[0]

            # 5. Parse Chart.yaml for name + version (reuses helper from chart/local.py
            #    per Plan 04-05 Deviation 2).
            data = _parse_chart_yaml(chart_dir)
            yield ResolvedChart(
                name=str(data.get("name", chart_dir.name)),
                version=str(data.get("version", "")),
                source_path=chart_dir,
            )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
