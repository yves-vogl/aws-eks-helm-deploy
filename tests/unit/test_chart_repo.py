"""Unit tests for RepoChart.resolve() — subprocess-mocked via HelmClient patch target.

All subprocess.run calls go through HelmClient; the patch target is:
    ``aws_eks_helm_deploy.helm.client.subprocess.run``

Requirements traceability:
    CHART-02 (Phase 4): RepoChart resolves helm-repo charts via
    helm repo add + repo update + helm pull into an isolated tempdir.

Coverage targets: 100% line + branch on chart/repo.py.
"""

from __future__ import annotations

import pathlib
from subprocess import CompletedProcess
from typing import Any

import pytest

from aws_eks_helm_deploy.chart.base import ResolvedChart
from aws_eks_helm_deploy.chart.repo import RepoChart
from aws_eks_helm_deploy.errors import ChartResolutionError

_PATCH_TARGET = "aws_eks_helm_deploy.helm.client.subprocess.run"


def _success(stdout: str = "", stderr: str = "") -> CompletedProcess[str]:
    """Return a CompletedProcess with returncode=0."""
    return CompletedProcess(args=[], returncode=0, stdout=stdout, stderr=stderr)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chart_yaml(path: pathlib.Path, name: str = "redis", version: str = "18.5.0") -> None:
    """Create a minimal Chart.yaml in the given directory."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "Chart.yaml").write_text(f"apiVersion: v2\nname: {name}\nversion: {version}\n")


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_happy_path_yields_resolved_chart(tmp_path: pathlib.Path, mocker: Any) -> None:
    """Happy path: RepoChart.resolve() yields ResolvedChart with correct name + version."""
    # Pre-create the unpacked chart directory that HelmClient.pull_repo would produce
    chart_dir = tmp_path / "unpacked" / "redis"
    _make_chart_yaml(chart_dir, name="redis", version="18.5.0")

    mocker.patch("tempfile.mkdtemp", return_value=str(tmp_path))
    mocker.patch(_PATCH_TARGET, return_value=_success())

    chart_source = RepoChart("bitnami", "redis", "https://charts.bitnami.com/bitnami", "18.5.0")
    with chart_source.resolve() as resolved:
        assert isinstance(resolved, ResolvedChart)
        assert resolved.name == "redis"
        assert resolved.version == "18.5.0"
        assert resolved.source_path.is_dir()


@pytest.mark.unit
def test_resolve_yields_inside_with_block_path_valid(tmp_path: pathlib.Path, mocker: Any) -> None:
    """Inside the with block, resolved.source_path.is_dir() returns True."""
    chart_dir = tmp_path / "unpacked" / "redis"
    _make_chart_yaml(chart_dir)

    mocker.patch("tempfile.mkdtemp", return_value=str(tmp_path))
    mocker.patch(_PATCH_TARGET, return_value=_success())

    with RepoChart("bitnami", "redis", "https://charts.bitnami.com/bitnami").resolve() as r:
        assert r.source_path.is_dir()
        assert (r.source_path / "Chart.yaml").exists()


# ---------------------------------------------------------------------------
# Call order + env isolation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_calls_helm_client_in_order(tmp_path: pathlib.Path, mocker: Any) -> None:
    """repo_add, then repo_update, then pull_repo — strict call order."""
    chart_dir = tmp_path / "unpacked" / "redis"
    _make_chart_yaml(chart_dir)

    mocker.patch("tempfile.mkdtemp", return_value=str(tmp_path))
    mock_run = mocker.patch(_PATCH_TARGET, return_value=_success())

    with RepoChart("bitnami", "redis", "https://charts.bitnami.com/bitnami").resolve():
        pass

    calls = mock_run.call_args_list
    assert len(calls) == 3

    # First call: helm repo add
    assert calls[0].args[0] == [
        "helm",
        "repo",
        "add",
        "bitnami",
        "https://charts.bitnami.com/bitnami",
    ]
    # Second call: helm repo update
    assert calls[1].args[0] == ["helm", "repo", "update", "bitnami"]
    # Third call: helm pull
    assert calls[2].args[0][0:3] == ["helm", "pull", "bitnami/redis"]


@pytest.mark.unit
def test_resolve_passes_isolated_env_vars(tmp_path: pathlib.Path, mocker: Any) -> None:
    """Every subprocess call receives HELM_REPOSITORY_CONFIG + HELM_REPOSITORY_CACHE env vars."""
    chart_dir = tmp_path / "unpacked" / "redis"
    _make_chart_yaml(chart_dir)

    mocker.patch("tempfile.mkdtemp", return_value=str(tmp_path))
    mock_run = mocker.patch(_PATCH_TARGET, return_value=_success())

    with RepoChart("bitnami", "redis", "https://charts.bitnami.com/bitnami").resolve():
        pass

    expected_config = str(tmp_path / "repositories.yaml")
    expected_cache = str(tmp_path / "cache")

    for c in mock_run.call_args_list:
        env = c.kwargs["env"]
        assert env["HELM_REPOSITORY_CONFIG"] == expected_config
        assert env["HELM_REPOSITORY_CACHE"] == expected_cache


# ---------------------------------------------------------------------------
# Tempdir cleanup
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_cleans_tempdir_on_normal_exit(tmp_path: pathlib.Path, mocker: Any) -> None:
    """After the with block, the tempdir is removed (rmtree fired in finally)."""
    chart_dir = tmp_path / "unpacked" / "redis"
    _make_chart_yaml(chart_dir)

    mocker.patch("tempfile.mkdtemp", return_value=str(tmp_path))
    mocker.patch(_PATCH_TARGET, return_value=_success())

    with RepoChart("bitnami", "redis", "https://charts.bitnami.com/bitnami").resolve():
        assert tmp_path.exists()  # inside: tmpdir still present

    assert not tmp_path.exists()  # outside: cleaned up


@pytest.mark.unit
def test_resolve_cleans_tempdir_on_exception(tmp_path: pathlib.Path, mocker: Any) -> None:
    """Tempdir is cleaned up even when the with block raises an exception."""
    chart_dir = tmp_path / "unpacked" / "redis"
    _make_chart_yaml(chart_dir)

    mocker.patch("tempfile.mkdtemp", return_value=str(tmp_path))
    mocker.patch(_PATCH_TARGET, return_value=_success())

    with (
        pytest.raises(RuntimeError, match="boom"),
        RepoChart("bitnami", "redis", "https://charts.bitnami.com/bitnami").resolve(),
    ):
        raise RuntimeError("boom")

    assert not tmp_path.exists()


# ---------------------------------------------------------------------------
# Version flag
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_with_version_passes_version_flag(tmp_path: pathlib.Path, mocker: Any) -> None:
    """When version is set, the helm pull argv contains --version <version>."""
    chart_dir = tmp_path / "unpacked" / "redis"
    _make_chart_yaml(chart_dir, version="18.5.0")

    mocker.patch("tempfile.mkdtemp", return_value=str(tmp_path))
    mock_run = mocker.patch(_PATCH_TARGET, return_value=_success())

    with RepoChart("bitnami", "redis", "https://charts.bitnami.com/bitnami", "18.5.0").resolve():
        pass

    pull_argv = mock_run.call_args_list[2].args[0]
    assert "--version" in pull_argv
    assert "18.5.0" in pull_argv


@pytest.mark.unit
def test_resolve_without_version_omits_version_flag(tmp_path: pathlib.Path, mocker: Any) -> None:
    """When version is None, the helm pull argv does NOT contain --version."""
    chart_dir = tmp_path / "unpacked" / "redis"
    _make_chart_yaml(chart_dir)

    mocker.patch("tempfile.mkdtemp", return_value=str(tmp_path))
    mock_run = mocker.patch(_PATCH_TARGET, return_value=_success())

    with RepoChart("bitnami", "redis", "https://charts.bitnami.com/bitnami").resolve():
        pass

    pull_argv = mock_run.call_args_list[2].args[0]
    assert "--version" not in pull_argv


# ---------------------------------------------------------------------------
# Error: no subdir after untar
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_raises_chart_resolution_error_when_no_subdir_after_untar(
    tmp_path: pathlib.Path, mocker: Any
) -> None:
    """When untar produces no subdir, ChartResolutionError is raised + tempdir cleaned."""
    # Create the unpacked dir but leave it empty (no subdirectory)
    (tmp_path / "unpacked").mkdir()

    mocker.patch("tempfile.mkdtemp", return_value=str(tmp_path))
    mocker.patch(_PATCH_TARGET, return_value=_success())

    with (
        pytest.raises(ChartResolutionError) as exc_info,
        RepoChart("bitnami", "redis", "https://charts.bitnami.com/bitnami").resolve(),
    ):
        pass

    assert "expected exactly one unpacked chart dir" in str(exc_info.value)
    assert exc_info.value.exit_code == 4
    assert not tmp_path.exists()  # cleanup still fired


# ---------------------------------------------------------------------------
# Error: helm subprocess non-zero returncode
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_raises_chart_resolution_error_on_repo_add_failure(
    mocker: Any,
    tmp_path: pathlib.Path,
) -> None:
    """helm repo add non-zero returncode bubbles up as ChartResolutionError; tmpdir cleaned."""
    mocker.patch("tempfile.mkdtemp", return_value=str(tmp_path))
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Error: unauthorized"
        ),
    )

    with (
        pytest.raises(ChartResolutionError) as exc_info,
        RepoChart("bitnami", "redis", "https://charts.bitnami.com/bitnami").resolve(),
    ):
        pass

    assert "helm repo add bitnami returned 1" in str(exc_info.value)
    assert "unauthorized" in str(exc_info.value)
    assert exc_info.value.exit_code == 4
    assert not tmp_path.exists()  # finally cleanup fired
