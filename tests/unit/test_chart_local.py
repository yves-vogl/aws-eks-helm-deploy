"""Unit tests for ResolvedChart + resolve_local_chart (CHART-01 + CHART-05).

Uses pytest's tmp_path fixture for filesystem fixtures and
structlog.testing.capture_logs() for warning assertions.
Note: capture_logs() works regardless of configure_logging() state — it
intercepts structlog's pipeline before the configured renderer.
"""

from __future__ import annotations

import pathlib

import pytest
from structlog.testing import capture_logs

from aws_eks_helm_deploy.chart.local import ResolvedChart, resolve_local_chart
from aws_eks_helm_deploy.errors import ChartResolutionError

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _write_chart(
    tmp_path: pathlib.Path,
    name: str = "test-chart",
    *,
    content: str | None = None,
    dir_name: str | None = None,
) -> pathlib.Path:
    """Write a Chart.yaml into tmp_path/<dir_name or name>/ and return the chart dir path.

    If *content* is None, writes a minimal valid Chart.yaml:
        apiVersion: v2
        name: <name>
        version: 0.1.0
    """
    chart_dir = tmp_path / (dir_name or name)
    chart_dir.mkdir(parents=True, exist_ok=True)
    if content is None:
        content = f"apiVersion: v2\nname: {name}\nversion: 0.1.0\n"
    (chart_dir / "Chart.yaml").write_text(content)
    return chart_dir


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_happy_path_full_chart_yaml(tmp_path: pathlib.Path) -> None:
    """resolve_local_chart returns a populated ResolvedChart from a valid chart dir."""
    chart_dir = tmp_path / "mychart"
    chart_dir.mkdir()
    (chart_dir / "Chart.yaml").write_text(
        "apiVersion: v2\nname: mychart\nversion: 1.2.3\ntype: application\n"
    )

    result = resolve_local_chart(str(chart_dir))

    assert result.name == "mychart"
    assert result.version == "1.2.3"
    assert result.source_path == chart_dir.resolve()


# ---------------------------------------------------------------------------
# Source prefix rejection (repo:// + oci://)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_repo_prefix_raises_chart_resolution_error() -> None:
    """resolve_local_chart raises ChartResolutionError for repo:// prefixed specs."""
    with pytest.raises(ChartResolutionError) as exc_info:
        resolve_local_chart("repo://stable/postgres")

    assert exc_info.value.exit_code == 4
    assert "repo://" in str(exc_info.value)
    assert "Phase 4" in str(exc_info.value)


@pytest.mark.unit
def test_oci_prefix_raises_chart_resolution_error() -> None:
    """resolve_local_chart raises ChartResolutionError for oci:// prefixed specs."""
    with pytest.raises(ChartResolutionError) as exc_info:
        resolve_local_chart("oci://ghcr.io/x/y")

    assert exc_info.value.exit_code == 4
    assert "oci://" in str(exc_info.value)
    assert "Phase 4" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_relative_path_resolved_against_repo_root(tmp_path: pathlib.Path) -> None:
    """Relative chart_spec is resolved against repo_root when supplied."""
    chart_dir = tmp_path / "charts" / "minimal"
    chart_dir.mkdir(parents=True)
    (chart_dir / "Chart.yaml").write_text("apiVersion: v2\nname: minimal\nversion: 0.1.0\n")

    result = resolve_local_chart("charts/minimal", repo_root=tmp_path)

    assert result.source_path == (tmp_path / "charts" / "minimal").resolve()


@pytest.mark.unit
def test_relative_path_resolved_against_cwd_when_no_repo_root(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Relative chart_spec without repo_root is resolved against Path.cwd()."""
    monkeypatch.chdir(tmp_path)
    chart_dir = tmp_path / "minimal"
    chart_dir.mkdir()
    (chart_dir / "Chart.yaml").write_text("apiVersion: v2\nname: minimal\nversion: 0.1.0\n")

    result = resolve_local_chart("minimal")

    assert result.source_path == chart_dir.resolve()
    assert result.name == "minimal"


@pytest.mark.unit
def test_absolute_path_used_directly(tmp_path: pathlib.Path) -> None:
    """An absolute chart_spec is used directly without repo_root resolution."""
    abs_chart = tmp_path / "abs_chart"
    abs_chart.mkdir()
    (abs_chart / "Chart.yaml").write_text("apiVersion: v2\nname: abs_chart\nversion: 2.0.0\n")

    result = resolve_local_chart(str(abs_chart))

    assert result.source_path == abs_chart.resolve()
    assert result.name == "abs_chart"
    assert result.version == "2.0.0"


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_missing_directory_raises(tmp_path: pathlib.Path) -> None:
    """resolve_local_chart raises ChartResolutionError when path does not exist."""
    missing = tmp_path / "does-not-exist"

    with pytest.raises(ChartResolutionError) as exc_info:
        resolve_local_chart(str(missing))

    assert "does not exist" in str(exc_info.value)
    assert exc_info.value.exit_code == 4


@pytest.mark.unit
def test_path_is_file_not_directory_raises(tmp_path: pathlib.Path) -> None:
    """resolve_local_chart raises ChartResolutionError when path is a file, not a directory."""
    afile = tmp_path / "afile"
    afile.write_text("x")

    with pytest.raises(ChartResolutionError) as exc_info:
        resolve_local_chart(str(afile))

    assert "not a directory" in str(exc_info.value)
    assert exc_info.value.exit_code == 4


@pytest.mark.unit
def test_missing_chart_yaml_raises(tmp_path: pathlib.Path) -> None:
    """resolve_local_chart raises ChartResolutionError when Chart.yaml is missing."""
    empty_dir = tmp_path / "empty-dir"
    empty_dir.mkdir()

    with pytest.raises(ChartResolutionError) as exc_info:
        resolve_local_chart(str(empty_dir))

    assert "Chart.yaml not found" in str(exc_info.value)
    assert exc_info.value.exit_code == 4


@pytest.mark.unit
def test_invalid_yaml_raises(tmp_path: pathlib.Path) -> None:
    """resolve_local_chart raises ChartResolutionError when Chart.yaml has invalid YAML."""
    chart_dir = tmp_path / "bad-yaml-chart"
    chart_dir.mkdir()
    # Deliberately malformed YAML
    (chart_dir / "Chart.yaml").write_text("name: : :\nver bad:[\n")

    with pytest.raises(ChartResolutionError) as exc_info:
        resolve_local_chart(str(chart_dir))

    # Should contain the underlying YAML error text
    assert exc_info.value.exit_code == 4
    error_msg = str(exc_info.value)
    assert "not valid YAML" in error_msg


@pytest.mark.unit
def test_empty_chart_yaml_raises(tmp_path: pathlib.Path) -> None:
    """resolve_local_chart raises ChartResolutionError when Chart.yaml is empty."""
    chart_dir = tmp_path / "empty-yaml-chart"
    chart_dir.mkdir()
    (chart_dir / "Chart.yaml").write_text("")

    with pytest.raises(ChartResolutionError) as exc_info:
        resolve_local_chart(str(chart_dir))

    assert "empty or malformed" in str(exc_info.value)
    assert exc_info.value.exit_code == 4


@pytest.mark.unit
def test_non_mapping_chart_yaml_raises(tmp_path: pathlib.Path) -> None:
    """resolve_local_chart raises ChartResolutionError for non-mapping Chart.yaml top level."""
    chart_dir = tmp_path / "list-yaml-chart"
    chart_dir.mkdir()
    # YAML list at top level — not a mapping
    (chart_dir / "Chart.yaml").write_text("- name\n- mychart\n")

    with pytest.raises(ChartResolutionError) as exc_info:
        resolve_local_chart(str(chart_dir))

    assert "must be a YAML mapping" in str(exc_info.value)
    assert exc_info.value.exit_code == 4


# ---------------------------------------------------------------------------
# Field fallbacks and warnings
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_missing_name_falls_back_to_dir_name(tmp_path: pathlib.Path) -> None:
    """When Chart.yaml has no 'name' key, result.name falls back to the directory name."""
    chart_dir = tmp_path / "dirname"
    chart_dir.mkdir()
    (chart_dir / "Chart.yaml").write_text("apiVersion: v2\nversion: 0.1.0\n")

    result = resolve_local_chart(str(chart_dir))

    assert result.name == "dirname"


@pytest.mark.unit
def test_missing_version_falls_back_to_empty_string_and_warns(tmp_path: pathlib.Path) -> None:
    """When Chart.yaml has no 'version' key, result.version == '' and a warning is emitted."""
    chart_dir = tmp_path / "no-version-chart"
    chart_dir.mkdir()
    (chart_dir / "Chart.yaml").write_text("apiVersion: v2\nname: x\n")

    with capture_logs() as captured:
        result = resolve_local_chart(str(chart_dir))

    assert result.version == ""
    assert any(event["event"] == "chart_yaml_missing_version" for event in captured), (
        f"Expected 'chart_yaml_missing_version' warning, got: {captured}"
    )


@pytest.mark.unit
def test_v1_api_version_warns_but_proceeds(tmp_path: pathlib.Path) -> None:
    """When apiVersion is v1 (Helm 2 legacy), a warning is emitted but ResolvedChart is returned."""
    chart_dir = tmp_path / "v1-chart"
    chart_dir.mkdir()
    (chart_dir / "Chart.yaml").write_text("apiVersion: v1\nname: x\nversion: 0.1.0\n")

    with capture_logs() as captured:
        result = resolve_local_chart(str(chart_dir))

    assert result.name == "x"
    assert result.version == "0.1.0"
    assert any(event["event"] == "chart_yaml_legacy_v1_api_version" for event in captured), (
        f"Expected 'chart_yaml_legacy_v1_api_version' warning, got: {captured}"
    )


# ---------------------------------------------------------------------------
# ResolvedChart dataclass properties
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolved_chart_is_frozen(tmp_path: pathlib.Path) -> None:
    """ResolvedChart is frozen — mutation raises FrozenInstanceError."""
    import dataclasses

    chart = ResolvedChart(name="x", version="1.0.0", source_path=pathlib.Path("/tmp/x"))

    with pytest.raises(dataclasses.FrozenInstanceError):
        chart.name = "y"  # type: ignore[misc]


@pytest.mark.unit
def test_resolved_chart_fields_order() -> None:
    """ResolvedChart has exactly three fields: name, version, source_path (in that order)."""
    import dataclasses

    fields = [f.name for f in dataclasses.fields(ResolvedChart)]
    assert fields == ["name", "version", "source_path"]
