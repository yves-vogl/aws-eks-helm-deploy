"""Local-path chart resolver for aws-eks-helm-deploy.

Requirements traceability:
  - CHART-01: validates a local-path Helm chart directory and produces a
    ResolvedChart value object consumed by HelmClient.upgrade_install().
  - CHART-05: ResolvedChart.name + .version surface in the success message
    emitted by actions/upgrade.py.

Phase 4 refactor: resolve_local_chart() was removed; LocalChart class with
.resolve() context-manager replaces it (CONTEXT D3 + RESEARCH §7.5).

Security note (T-03-03-01):
  - yaml.safe_load is used exclusively. NEVER yaml.load — it executes
    arbitrary Python via YAML constructor tags (e.g. !!python/object/apply).
"""

from __future__ import annotations

import pathlib
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import yaml  # PyYAML

from aws_eks_helm_deploy.chart.base import ResolvedChart
from aws_eks_helm_deploy.errors import ChartResolutionError
from aws_eks_helm_deploy.logging import get_logger

__all__: list[str] = ["LocalChart"]

logger = get_logger(__name__)


def _resolve_chart_path(
    chart_spec: str,
    repo_root: pathlib.Path | None,
) -> pathlib.Path:
    """Resolve chart_spec to an absolute, canonicalized Path.

    Relative specs are resolved against *repo_root* when supplied, otherwise
    against ``pathlib.Path.cwd()``.
    """
    raw_path = pathlib.Path(chart_spec)
    if raw_path.is_absolute():
        return raw_path.resolve()
    base = repo_root if repo_root is not None else pathlib.Path.cwd()
    return (base / raw_path).resolve()


def _parse_chart_yaml(path: pathlib.Path) -> dict[str, Any]:
    """Read and parse Chart.yaml inside *path*, returning its data as a dict.

    Raises:
        ChartResolutionError: If Chart.yaml is missing, contains invalid YAML,
            is empty, or is not a YAML mapping at top level.
    """
    chart_yaml_path = path / "Chart.yaml"
    if not chart_yaml_path.exists():
        raise ChartResolutionError(
            f"Chart.yaml not found at {chart_yaml_path} — is {path} a valid Helm chart?"
        )

    text = chart_yaml_path.read_text()
    try:
        data: Any = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ChartResolutionError(
            f"Chart.yaml at {chart_yaml_path} is not valid YAML: {exc}"
        ) from exc

    if data is None:
        raise ChartResolutionError(f"Chart.yaml at {chart_yaml_path} is empty or malformed")
    if not isinstance(data, dict):
        raise ChartResolutionError(
            f"Chart.yaml at {chart_yaml_path} must be a YAML mapping at top level,"
            f" got {type(data).__name__}"
        )
    return data


class LocalChart:
    """Local-path chart source — satisfies ChartSource Protocol.

    The resolve() context-manager is degenerate: it yields the on-disk
    path that already exists; no tempdir creation; no cleanup. Unlike
    RepoChart / OciChart which manage tempdir lifecycle, LocalChart's
    resolve() is a yield-and-return.
    """

    def __init__(self, chart_spec: str, repo_root: pathlib.Path | None = None) -> None:
        self._chart_spec = chart_spec
        self._repo_root = repo_root

    @contextmanager
    def resolve(self) -> Iterator[ResolvedChart]:
        """Yield a ResolvedChart for the local chart directory.

        Raises:
            ChartResolutionError: On any of the following conditions —
                - chart_spec starts with ``repo://`` or ``oci://`` (handled by
                  RepoChart / OciChart via select_chart_source())
                - resolved path does not exist
                - resolved path is not a directory
                - Chart.yaml is missing from the directory
                - Chart.yaml contains invalid YAML
                - Chart.yaml is empty or not a YAML mapping at top level
        """
        # 1. Source prefix rejection — select_chart_source() routes by prefix
        if self._chart_spec.startswith("repo://"):
            raise ChartResolutionError(
                "repo:// chart sources are handled by RepoChart (CHART-02) — "
                "select_chart_source() routes by prefix"
            )
        if self._chart_spec.startswith("oci://"):
            raise ChartResolutionError(
                "oci:// chart sources are handled by OciChart (CHART-03) — "
                "select_chart_source() routes by prefix"
            )

        # 2. Path resolution
        path = _resolve_chart_path(self._chart_spec, self._repo_root)

        # 3. Path existence + type validation
        if not path.exists():
            raise ChartResolutionError(f"Chart path does not exist: {path}")
        if not path.is_dir():
            raise ChartResolutionError(f"Chart path is not a directory: {path}")

        # 4-6. Chart.yaml parse + shape validation
        data = _parse_chart_yaml(path)

        # 7. Field extraction with fallbacks and non-fatal warnings
        name_raw: Any = data.get("name")
        name: str = str(name_raw) if name_raw is not None else path.name

        version_raw: Any = data.get("version")
        version: str = str(version_raw) if version_raw is not None else ""
        if not version:
            logger.warning("chart_yaml_missing_version", chart_path=str(path), chart_name=name)

        api_version: str = str(data.get("apiVersion", "v2"))
        if api_version == "v1":
            # Helm 3 reads v1 charts in compatibility mode — warn but proceed.
            logger.warning(
                "chart_yaml_legacy_v1_api_version", chart_path=str(path), chart_name=name
            )

        # 8. Yield the fully-resolved, immutable descriptor.
        # No finally — degenerate context-manager; nothing to clean up.
        yield ResolvedChart(name=name, version=version, source_path=path)
