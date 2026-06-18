"""Local-path chart resolver for aws-eks-helm-deploy.

Requirements traceability:
  - CHART-01: validates a local-path Helm chart directory and produces a
    ResolvedChart value object consumed by HelmClient.upgrade_install().
  - CHART-05: ResolvedChart.name + .version surface in the success message
    emitted by actions/upgrade.py.

Scope (Phase 3):
  - Only local-path chart sources are supported (CONTEXT D6).
  - repo:// and oci:// chart sources are explicitly rejected with
    ChartResolutionError; they ship in Phase 4 (CHART-02, CHART-03).

Security note (T-03-03-01):
  - yaml.safe_load is used exclusively. NEVER yaml.load — it executes
    arbitrary Python via YAML constructor tags (e.g. !!python/object/apply).
"""

from __future__ import annotations

import dataclasses
import pathlib
from typing import Any

import yaml  # PyYAML

from aws_eks_helm_deploy.errors import ChartResolutionError
from aws_eks_helm_deploy.logging import get_logger

__all__: list[str] = ["ResolvedChart", "resolve_local_chart"]

logger = get_logger(__name__)


@dataclasses.dataclass(frozen=True)
class ResolvedChart:
    """Immutable resolved local chart descriptor.

    Phase 4 refactors this to a ChartSource Protocol when repo:// and oci://
    sources are added (CHART-02, CHART-03). Phase 3 keeps it as a concrete
    frozen dataclass — YAGNI; one implementation does not warrant a Protocol.

    Fields:
        name: Chart name from Chart.yaml, or the directory name as fallback.
        version: Chart version from Chart.yaml, or "" if missing (warns).
        source_path: Absolute resolved path to the chart directory.
    """

    name: str
    version: str
    source_path: pathlib.Path


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


def resolve_local_chart(
    chart_spec: str,
    repo_root: pathlib.Path | None = None,
) -> ResolvedChart:
    """Resolve a local-path chart spec to a ResolvedChart.

    Validates that *chart_spec* points to an existing directory containing a
    parseable Chart.yaml, then returns a ResolvedChart with the chart's name,
    version, and absolute source path.

    Args:
        chart_spec: A local path (absolute or relative) to a Helm chart
            directory. Strings starting with ``repo://`` or ``oci://`` are
            explicitly rejected — those resolvers ship in Phase 4.
        repo_root: Base directory for relative paths. When None, relative
            paths are resolved against ``pathlib.Path.cwd()``. Useful in
            tests and CI to avoid monkeypatching the working directory.

    Returns:
        A frozen ResolvedChart with ``name``, ``version``, and
        ``source_path`` (always absolute).

    Raises:
        ChartResolutionError: On any of the following conditions —
            - chart_spec starts with ``repo://`` or ``oci://`` (Phase 4 scope)
            - resolved path does not exist
            - resolved path is not a directory
            - Chart.yaml is missing from the directory
            - Chart.yaml contains invalid YAML
            - Chart.yaml is empty or not a YAML mapping at top level
    """
    # 1. Source prefix rejection (Phase 3 scope boundary)
    if chart_spec.startswith("repo://"):
        raise ChartResolutionError(
            "repo:// chart sources are not supported in Phase 3 (ship in Phase 4 — CHART-02)"
        )
    if chart_spec.startswith("oci://"):
        raise ChartResolutionError(
            "oci:// chart sources are not supported in Phase 3 (ship in Phase 4 — CHART-03)"
        )

    # 2. Path resolution
    path = _resolve_chart_path(chart_spec, repo_root)

    # 3. Path existence + type validation
    if not path.exists():
        raise ChartResolutionError(f"Chart path does not exist: {path}")
    if not path.is_dir():
        raise ChartResolutionError(f"Chart path is not a directory: {path}")

    # 4-6. Chart.yaml parse + shape validation (delegated to helper)
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
        # Raising here would break existing Helm 2-era charts unnecessarily.
        logger.warning("chart_yaml_legacy_v1_api_version", chart_path=str(path), chart_name=name)

    # 8. Return the fully-resolved, immutable descriptor
    return ResolvedChart(name=name, version=version, source_path=path)
