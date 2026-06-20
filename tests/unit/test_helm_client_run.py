"""subprocess-mocked tests for HelmClient.upgrade_install + HelmClient.history.

Covers exit-code mapping (HelmExecutionError exit=5, HelmTimeoutError exit=6),
32 KB stderr truncation, REVISION:\\s*(\\d+) parsing, helm history JSON parsing,
and subprocess argv contract. Uses pytest-mock's ``mocker`` fixture.

Patch target: ``aws_eks_helm_deploy.helm.client.subprocess.run`` — patches the
subprocess module as imported inside helm/client.py (more reliable than patching
the global ``subprocess.run``).
"""

from __future__ import annotations

import pathlib
import subprocess
from subprocess import CompletedProcess
from types import SimpleNamespace
from typing import Any

import pytest

from aws_eks_helm_deploy.errors import ChartResolutionError, HelmExecutionError, HelmTimeoutError
from aws_eks_helm_deploy.helm.client import (
    STDERR_MAX_BYTES,
    TRUNCATION_MARKER,
    HelmClient,
    HelmRevision,
    _parse_timeout,
)

_PATCH_TARGET = "aws_eks_helm_deploy.helm.client.subprocess.run"


def _client() -> HelmClient:
    return HelmClient(kubeconfig_path=pathlib.Path("/tmp/test-kubeconfig.yaml"))


def _stub_chart(source_path: str = "/charts/minimal") -> Any:
    """Duck-typed substitute for ResolvedChart (lands in Plan 03-03)."""
    return SimpleNamespace(
        name="minimal",
        version="0.1.0",
        source_path=pathlib.Path(source_path),
    )


# ---------------------------------------------------------------------------
# upgrade_install — happy path + revision parsing
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_upgrade_install_returns_helm_result_with_revision(mocker: Any) -> None:
    """Happy path: returncode=0 parses REVISION from stdout into HelmResult."""
    stdout = (
        'Release "r" has been upgraded. Happy Helming!\n'
        "NAME: r\n"
        "NAMESPACE: default\n"
        "REVISION: 3\n"
        "STATUS: deployed"
    )
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=0, stdout=stdout, stderr=""),
    )
    result = _client().upgrade_install("r", _stub_chart(), "default", [], [], None, "600s")
    assert result.returncode == 0
    assert result.revision == 3
    assert "Release" in result.stdout
    assert result.stderr == ""


@pytest.mark.unit
def test_upgrade_install_revision_none_when_not_in_stdout(mocker: Any) -> None:
    """If stdout has no REVISION: line, HelmResult.revision is None."""
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(
            args=[], returncode=0, stdout="some output without REVISION line", stderr=""
        ),
    )
    result = _client().upgrade_install("r", _stub_chart(), "default", [], [], None, "600s")
    assert result.revision is None


# ---------------------------------------------------------------------------
# upgrade_install — non-zero returncode
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_upgrade_install_non_zero_returncode_raises_helm_execution_error(mocker: Any) -> None:
    """returncode=1 raises HelmExecutionError with exit_code=5 and message details."""
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="Error: UPGRADE FAILED: template error",
        ),
    )
    with pytest.raises(HelmExecutionError) as exc_info:
        _client().upgrade_install("r", _stub_chart(), "default", [], [], None, "600s")
    assert exc_info.value.exit_code == 5
    assert "returned 1" in str(exc_info.value)
    assert "template error" in str(exc_info.value)


@pytest.mark.unit
def test_upgrade_install_returncode_2_also_raises(mocker: Any) -> None:
    """Any non-zero returncode raises HelmExecutionError (covers the branch broadly)."""
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=2, stdout="", stderr="Error: bad"),
    )
    with pytest.raises(HelmExecutionError):
        _client().upgrade_install("r", _stub_chart(), "default", [], [], None, "600s")


# ---------------------------------------------------------------------------
# upgrade_install — timeout
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_upgrade_install_timeout_raises_helm_timeout_error(mocker: Any) -> None:
    """subprocess.TimeoutExpired maps to HelmTimeoutError with exit_code=6."""
    mocker.patch(
        _PATCH_TARGET,
        side_effect=subprocess.TimeoutExpired(cmd=["helm"], timeout=600),
    )
    with pytest.raises(HelmTimeoutError) as exc_info:
        _client().upgrade_install("r", _stub_chart(), "default", [], [], None, "600s")
    assert exc_info.value.exit_code == 6
    assert "600" in str(exc_info.value)


@pytest.mark.unit
def test_upgrade_install_timeout_includes_partial_stderr_when_present(mocker: Any) -> None:
    """When TimeoutExpired.stderr has bytes, they appear in the HelmTimeoutError message."""
    mocker.patch(
        _PATCH_TARGET,
        side_effect=subprocess.TimeoutExpired(
            cmd=["helm"],
            timeout=60,
            output=None,
            stderr=b"partial error log line",
        ),
    )
    with pytest.raises(HelmTimeoutError) as exc_info:
        _client().upgrade_install("r", _stub_chart(), "default", [], [], None, "60s")
    assert "partial error log line" in str(exc_info.value)


@pytest.mark.unit
def test_upgrade_install_timeout_with_none_stderr_does_not_crash(mocker: Any) -> None:
    """TimeoutExpired with stderr=None raises HelmTimeoutError without secondary exception."""
    mocker.patch(
        _PATCH_TARGET,
        side_effect=subprocess.TimeoutExpired(cmd=["helm"], timeout=600, stderr=None),
    )
    with pytest.raises(HelmTimeoutError):
        _client().upgrade_install("r", _stub_chart(), "default", [], [], None, "600s")


# ---------------------------------------------------------------------------
# upgrade_install — 32 KB stderr truncation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_upgrade_install_truncates_stderr_when_over_32kb(mocker: Any) -> None:
    """stderr > 32 KB is truncated to last 32 KB with TRUNCATION_MARKER prefix."""
    big_stderr = "x" * (33 * 1024)
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(
            args=[],
            returncode=0,
            stdout="OK\nREVISION: 1",
            stderr=big_stderr,
        ),
    )
    result = _client().upgrade_install("r", _stub_chart(), "default", [], [], None, "600s")
    assert result.stderr.startswith(TRUNCATION_MARKER)
    assert len(result.stderr) <= STDERR_MAX_BYTES + len(TRUNCATION_MARKER)


@pytest.mark.unit
def test_upgrade_install_does_not_truncate_when_stderr_under_32kb(mocker: Any) -> None:
    """Short stderr is returned unchanged (no TRUNCATION_MARKER)."""
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(
            args=[], returncode=0, stdout="OK\nREVISION: 2", stderr="short"
        ),
    )
    result = _client().upgrade_install("r", _stub_chart(), "default", [], [], None, "600s")
    assert result.stderr == "short"


@pytest.mark.unit
def test_upgrade_install_truncates_stderr_on_error_path_too(mocker: Any) -> None:
    """Truncation applies on failure path too (returncode=1 with big stderr)."""
    big_stderr = "y" * (33 * 1024)
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=1, stdout="", stderr=big_stderr),
    )
    with pytest.raises(HelmExecutionError) as exc_info:
        _client().upgrade_install("r", _stub_chart(), "default", [], [], None, "600s")
    assert TRUNCATION_MARKER in str(exc_info.value)


# ---------------------------------------------------------------------------
# upgrade_install — subprocess argv contract
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_upgrade_install_invokes_subprocess_run_with_correct_argv(mocker: Any) -> None:
    """subprocess.run is called with the exact argv, timeout, and flags."""
    mock_run = mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=0, stdout="REVISION: 1", stderr=""),
    )
    _client().upgrade_install("rel", _stub_chart(), "ns", ["v.yaml"], ["k=v"], 5, "300s")
    expected_argv = [
        "helm",
        "upgrade",
        "rel",
        "/charts/minimal",
        "--install",
        "--namespace",
        "ns",
        "--kubeconfig",
        "/tmp/test-kubeconfig.yaml",
        "--timeout",
        "300s",
        "--values",
        "v.yaml",
        "--set-string",
        "k=v",
        "--history-max",
        "5",
    ]
    assert mock_run.call_args.args[0] == expected_argv
    assert mock_run.call_args.kwargs["timeout"] == 300
    assert mock_run.call_args.kwargs["check"] is False
    assert mock_run.call_args.kwargs["capture_output"] is True
    assert mock_run.call_args.kwargs["text"] is True


@pytest.mark.unit
def test_upgrade_install_passes_env_os_environ_copy(
    mocker: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """subprocess.run receives env=os.environ.copy() including test-injected vars."""
    monkeypatch.setenv("MY_TEST_VAR", "testvalue42")
    mock_run = mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=0, stdout="REVISION: 1", stderr=""),
    )
    _client().upgrade_install("r", _stub_chart(), "default", [], [], None, "600s")
    env_passed = mock_run.call_args.kwargs["env"]
    assert isinstance(env_passed, dict)
    assert "MY_TEST_VAR" in env_passed
    assert env_passed["MY_TEST_VAR"] == "testvalue42"


# ---------------------------------------------------------------------------
# _parse_timeout helper
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_parse_timeout_seconds_only() -> None:
    assert _parse_timeout("600s") == 600


@pytest.mark.unit
def test_parse_timeout_minutes_only() -> None:
    assert _parse_timeout("10m") == 600


@pytest.mark.unit
def test_parse_timeout_hours_only() -> None:
    assert _parse_timeout("1h") == 3600


@pytest.mark.unit
def test_parse_timeout_combined() -> None:
    assert _parse_timeout("5m30s") == 330


@pytest.mark.unit
def test_parse_timeout_hours_minutes() -> None:
    assert _parse_timeout("1h30m") == 5400


@pytest.mark.unit
def test_parse_timeout_invalid_raises_value_error() -> None:
    with pytest.raises(ValueError, match="invalid timeout"):
        _parse_timeout("garbage")


@pytest.mark.unit
def test_parse_timeout_empty_raises_value_error() -> None:
    with pytest.raises(ValueError, match="invalid timeout"):
        _parse_timeout("")


@pytest.mark.unit
def test_parse_timeout_zero_raises_value_error() -> None:
    """A duration that sums to zero seconds is invalid (e.g. "0s")."""
    with pytest.raises(ValueError, match="invalid timeout"):
        _parse_timeout("0s")


# ---------------------------------------------------------------------------
# history method
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_history_parses_json_into_helm_revision_list(mocker: Any) -> None:
    """helm history -o json is parsed into a list[HelmRevision]."""
    json_stdout = (
        '[{"revision": 1, "status": "superseded", "chart": "minimal-0.1.0", '
        '"description": "Install", "updated": "2026-01-01T00:00:00Z", "app_version": ""},'
        ' {"revision": 2, "status": "deployed", "chart": "minimal-0.1.0", '
        '"description": "Upgrade", "updated": "2026-01-02T00:00:00Z", "app_version": ""}]'
    )
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=0, stdout=json_stdout, stderr=""),
    )
    result = _client().history("rel", "ns")
    assert len(result) == 2
    assert result[0].revision == 1
    assert result[0].status == "superseded"
    assert result[1].status == "deployed"


@pytest.mark.unit
def test_history_invokes_correct_argv(mocker: Any) -> None:
    """helm history is called with the exact argv."""
    mock_run = mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=0, stdout="[]", stderr=""),
    )
    _client().history("rel", "ns")
    expected_argv = [
        "helm",
        "history",
        "rel",
        "-n",
        "ns",
        "-o",
        "json",
        "--kubeconfig",
        "/tmp/test-kubeconfig.yaml",
    ]
    assert mock_run.call_args.args[0] == expected_argv


@pytest.mark.unit
def test_history_non_zero_returncode_raises_helm_execution_error(mocker: Any) -> None:
    """returncode=1 from helm history raises HelmExecutionError with exit_code=5."""
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Error: release: not found"
        ),
    )
    with pytest.raises(HelmExecutionError) as exc_info:
        _client().history("rel", "ns")
    assert exc_info.value.exit_code == 5


@pytest.mark.unit
def test_history_empty_list(mocker: Any) -> None:
    """stdout=[] returns an empty list without error."""
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=0, stdout="[]", stderr=""),
    )
    result = _client().history("rel", "ns")
    assert result == []


@pytest.mark.unit
def test_history_returns_helm_revision_instances(mocker: Any) -> None:
    """Each item in the returned list is a HelmRevision frozen dataclass instance."""
    json_stdout = (
        '[{"revision": 5, "status": "deployed", "chart": "app-1.2.3",'
        ' "description": "Upgrade complete", "updated": "2026-01-01T00:00:00Z",'
        ' "app_version": "1.0"}]'
    )
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=0, stdout=json_stdout, stderr=""),
    )
    result = _client().history("rel", "default")
    assert len(result) == 1
    assert isinstance(result[0], HelmRevision)
    assert result[0].revision == 5
    assert result[0].chart == "app-1.2.3"
    assert result[0].description == "Upgrade complete"


# ---------------------------------------------------------------------------
# repo_add — new method (Plan 04-06)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_repo_add_happy_path(mocker: Any) -> None:
    """repo_add happy path: subprocess.run returns 0, no exception raised."""
    mock_run = mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
    )
    env = {"HELM_REPOSITORY_CONFIG": "/tmp/repos.yaml", "MARKER": "x"}
    _client().repo_add("bitnami", "https://charts.bitnami.com/bitnami", env)
    assert mock_run.call_count == 1
    assert mock_run.call_args.args[0] == [
        "helm",
        "repo",
        "add",
        "bitnami",
        "https://charts.bitnami.com/bitnami",
    ]
    assert mock_run.call_args.kwargs["env"] == env
    assert mock_run.call_args.kwargs["check"] is False
    assert mock_run.call_args.kwargs["timeout"] == 60


@pytest.mark.unit
def test_repo_add_non_zero_returncode_raises_chart_resolution_error(mocker: Any) -> None:
    """repo_add non-zero returncode raises ChartResolutionError (exit_code=4)."""
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Error: unauthorized"
        ),
    )
    with pytest.raises(ChartResolutionError) as exc_info:
        _client().repo_add("bitnami", "https://charts.bitnami.com/bitnami", {})
    assert exc_info.value.exit_code == 4
    assert "helm repo add bitnami returned 1" in str(exc_info.value)
    assert "unauthorized" in str(exc_info.value)


@pytest.mark.unit
def test_repo_add_timeout_raises_chart_resolution_error(mocker: Any) -> None:
    """repo_add TimeoutExpired raises ChartResolutionError with timeout info."""
    mocker.patch(
        _PATCH_TARGET,
        side_effect=subprocess.TimeoutExpired(cmd=["helm"], timeout=60),
    )
    with pytest.raises(ChartResolutionError) as exc_info:
        _client().repo_add("bitnami", "https://charts.bitnami.com/bitnami", {})
    assert exc_info.value.exit_code == 4
    assert "60" in str(exc_info.value)


@pytest.mark.unit
def test_repo_add_timeout_with_stderr_includes_partial_stderr(mocker: Any) -> None:
    """repo_add TimeoutExpired with stderr bytes surfaces them in the error message."""
    mocker.patch(
        _PATCH_TARGET,
        side_effect=subprocess.TimeoutExpired(
            cmd=["helm"], timeout=60, output=None, stderr=b"partial output here"
        ),
    )
    with pytest.raises(ChartResolutionError) as exc_info:
        _client().repo_add("bitnami", "https://charts.bitnami.com/bitnami", {})
    assert "partial output here" in str(exc_info.value)


# ---------------------------------------------------------------------------
# repo_update — new method (Plan 04-06)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_repo_update_happy_path(mocker: Any) -> None:
    """repo_update happy path: subprocess.run returns 0, no exception raised."""
    mock_run = mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
    )
    env = {"HELM_REPOSITORY_CACHE": "/tmp/cache", "MARKER": "y"}
    _client().repo_update("bitnami", env)
    assert mock_run.call_count == 1
    assert mock_run.call_args.args[0] == ["helm", "repo", "update", "bitnami"]
    assert mock_run.call_args.kwargs["env"] == env
    assert mock_run.call_args.kwargs["check"] is False
    assert mock_run.call_args.kwargs["timeout"] == 120


@pytest.mark.unit
def test_repo_update_non_zero_returncode_raises_chart_resolution_error(mocker: Any) -> None:
    """repo_update non-zero returncode raises ChartResolutionError (exit_code=4)."""
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Error: no repositories"
        ),
    )
    with pytest.raises(ChartResolutionError) as exc_info:
        _client().repo_update("bitnami", {})
    assert exc_info.value.exit_code == 4
    assert "helm repo update bitnami returned 1" in str(exc_info.value)


@pytest.mark.unit
def test_repo_update_timeout_raises_chart_resolution_error(mocker: Any) -> None:
    """repo_update TimeoutExpired raises ChartResolutionError."""
    mocker.patch(
        _PATCH_TARGET,
        side_effect=subprocess.TimeoutExpired(cmd=["helm"], timeout=120),
    )
    with pytest.raises(ChartResolutionError) as exc_info:
        _client().repo_update("bitnami", {})
    assert exc_info.value.exit_code == 4
    assert "120" in str(exc_info.value)


@pytest.mark.unit
def test_repo_update_timeout_with_stderr_bytes(mocker: Any) -> None:
    """repo_update TimeoutExpired with stderr bytes includes them in the error."""
    mocker.patch(
        _PATCH_TARGET,
        side_effect=subprocess.TimeoutExpired(
            cmd=["helm"], timeout=120, output=None, stderr=b"network timeout partial"
        ),
    )
    with pytest.raises(ChartResolutionError) as exc_info:
        _client().repo_update("bitnami", {})
    assert "network timeout partial" in str(exc_info.value)


# ---------------------------------------------------------------------------
# pull_repo — new method (Plan 04-06)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pull_repo_happy_path_with_version(mocker: Any) -> None:
    """pull_repo happy path with version: subprocess.run returns 0, no exception."""
    mock_run = mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
    )
    env = {"HELM_REPOSITORY_CONFIG": "/tmp/repos.yaml", "MARKER": "z"}
    dest = pathlib.Path("/tmp/dest")
    untar_dir = pathlib.Path("/tmp/unpacked")
    _client().pull_repo("bitnami/redis", dest, untar_dir, "18.5.0", env)
    assert mock_run.call_count == 1
    assert mock_run.call_args.args[0] == [
        "helm",
        "pull",
        "bitnami/redis",
        "--destination",
        "/tmp/dest",
        "--untar",
        "--untar-dir",
        "/tmp/unpacked",
        "--version",
        "18.5.0",
    ]
    assert mock_run.call_args.kwargs["env"] == env
    assert mock_run.call_args.kwargs["check"] is False
    assert mock_run.call_args.kwargs["timeout"] == 600


@pytest.mark.unit
def test_pull_repo_happy_path_without_version(mocker: Any) -> None:
    """pull_repo without version: no --version flag in argv."""
    mock_run = mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
    )
    dest = pathlib.Path("/tmp/dest")
    untar_dir = pathlib.Path("/tmp/unpacked")
    _client().pull_repo("bitnami/redis", dest, untar_dir, None, {})
    argv = mock_run.call_args.args[0]
    assert "--version" not in argv
    assert argv == [
        "helm",
        "pull",
        "bitnami/redis",
        "--destination",
        "/tmp/dest",
        "--untar",
        "--untar-dir",
        "/tmp/unpacked",
    ]


@pytest.mark.unit
def test_pull_repo_non_zero_returncode_raises_chart_resolution_error(mocker: Any) -> None:
    """pull_repo non-zero returncode raises ChartResolutionError (exit_code=4)."""
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Error: chart not found"
        ),
    )
    with pytest.raises(ChartResolutionError) as exc_info:
        _client().pull_repo(
            "bitnami/redis", pathlib.Path("/tmp/dest"), pathlib.Path("/tmp/up"), "18.5.0", {}
        )
    assert exc_info.value.exit_code == 4
    assert "helm pull bitnami/redis returned 1" in str(exc_info.value)
    assert "chart not found" in str(exc_info.value)


@pytest.mark.unit
def test_pull_repo_timeout_raises_chart_resolution_error(mocker: Any) -> None:
    """pull_repo TimeoutExpired raises ChartResolutionError."""
    mocker.patch(
        _PATCH_TARGET,
        side_effect=subprocess.TimeoutExpired(cmd=["helm"], timeout=600),
    )
    with pytest.raises(ChartResolutionError) as exc_info:
        _client().pull_repo(
            "bitnami/redis", pathlib.Path("/tmp/dest"), pathlib.Path("/tmp/up"), None, {}
        )
    assert exc_info.value.exit_code == 4
    assert "600" in str(exc_info.value)


# ---------------------------------------------------------------------------
# registry_login — new method (Plan 04-07)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_registry_login_happy_path_password_via_input_not_argv(mocker: Any) -> None:
    """registry_login passes password via input=, NEVER in argv (R4).

    Verifies:
    - subprocess.run receives input="hunter2"
    - argv does NOT contain "hunter2" anywhere
    - timeout=60
    """
    mock_run = mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=0, stdout="Login Succeeded", stderr=""),
    )
    env = {"HELM_REGISTRY_CONFIG": "/tmp/reg.json", "DOCKER_CONFIG": "/tmp/docker"}
    _client().registry_login("127.0.0.1:5555", "alice", "hunter2", env)
    assert mock_run.call_count == 1
    # Password must appear in input=, NOT in argv
    assert mock_run.call_args.kwargs["input"] == "hunter2"
    assert "hunter2" not in mock_run.call_args.args[0]  # argv does not contain password
    # Timeout and env passthrough
    assert mock_run.call_args.kwargs["timeout"] == 60
    assert mock_run.call_args.kwargs["env"] == env


@pytest.mark.unit
def test_registry_login_argv_contains_password_stdin_flag(mocker: Any) -> None:
    """registry_login argv includes --password-stdin (not --password <value>)."""
    mock_run = mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
    )
    _client().registry_login("ghcr.io", "bob", "s3cr3t", {})
    argv = mock_run.call_args.args[0]
    assert "--password-stdin" in argv
    # Negative: the literal form '--password' followed by value must NOT appear
    # (--password-stdin is OK, but '--password' with a space + value is forbidden)
    assert "s3cr3t" not in argv


@pytest.mark.unit
def test_registry_login_non_zero_returncode_raises_chart_resolution_error(mocker: Any) -> None:
    """registry_login non-zero returncode raises ChartResolutionError (exit_code=4)."""
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Error: unauthorized"
        ),
    )
    with pytest.raises(ChartResolutionError) as exc_info:
        _client().registry_login("ghcr.io", "alice", "bad-pass", {})
    assert exc_info.value.exit_code == 4
    assert "registry login ghcr.io returned 1" in str(exc_info.value)
    assert "unauthorized" in str(exc_info.value)


@pytest.mark.unit
def test_registry_login_timeout_raises_chart_resolution_error(mocker: Any) -> None:
    """registry_login TimeoutExpired raises ChartResolutionError."""
    mocker.patch(
        _PATCH_TARGET,
        side_effect=subprocess.TimeoutExpired(cmd=["helm"], timeout=60),
    )
    with pytest.raises(ChartResolutionError) as exc_info:
        _client().registry_login("ghcr.io", "alice", "pass", {})
    assert exc_info.value.exit_code == 4
    assert "60" in str(exc_info.value)


# ---------------------------------------------------------------------------
# pull_oci — new method (Plan 04-07)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pull_oci_happy_path_with_version(mocker: Any) -> None:
    """pull_oci happy path with version: subprocess.run returns 0, no exception."""
    mock_run = mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
    )
    env = {
        "HELM_REGISTRY_CONFIG": "/tmp/reg.json",
        "DOCKER_CONFIG": "/tmp/docker",
        "MARKER": "oci",
    }
    dest = pathlib.Path("/tmp/dest")
    untar_dir = pathlib.Path("/tmp/unpacked")
    _client().pull_oci("127.0.0.1:5555/charts/redis", dest, untar_dir, "18.5.0", env)
    assert mock_run.call_count == 1
    assert mock_run.call_args.args[0] == [
        "helm",
        "pull",
        "oci://127.0.0.1:5555/charts/redis",
        "--destination",
        "/tmp/dest",
        "--untar",
        "--untar-dir",
        "/tmp/unpacked",
        "--version",
        "18.5.0",
    ]
    assert mock_run.call_args.kwargs["env"] == env
    assert mock_run.call_args.kwargs["check"] is False
    assert mock_run.call_args.kwargs["timeout"] == 600


@pytest.mark.unit
def test_pull_oci_happy_path_without_version(mocker: Any) -> None:
    """pull_oci without version: no --version flag in argv."""
    mock_run = mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
    )
    dest = pathlib.Path("/tmp/dest")
    untar_dir = pathlib.Path("/tmp/unpacked")
    _client().pull_oci("127.0.0.1:5555/charts/redis", dest, untar_dir, None, {})
    argv = mock_run.call_args.args[0]
    assert "--version" not in argv
    assert "oci://127.0.0.1:5555/charts/redis" in argv
    assert "--untar" in argv


@pytest.mark.unit
def test_pull_oci_non_zero_returncode_raises_chart_resolution_error(mocker: Any) -> None:
    """pull_oci non-zero returncode raises ChartResolutionError (exit_code=4)."""
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Error: chart not found in registry"
        ),
    )
    with pytest.raises(ChartResolutionError) as exc_info:
        _client().pull_oci(
            "ghcr.io/org/chart",
            pathlib.Path("/tmp/dest"),
            pathlib.Path("/tmp/up"),
            "1.0.0",
            {},
        )
    assert exc_info.value.exit_code == 4
    assert "helm pull oci://ghcr.io/org/chart returned 1" in str(exc_info.value)
    assert "chart not found" in str(exc_info.value)


@pytest.mark.unit
def test_pull_oci_timeout_raises_chart_resolution_error(mocker: Any) -> None:
    """pull_oci TimeoutExpired raises ChartResolutionError."""
    mocker.patch(
        _PATCH_TARGET,
        side_effect=subprocess.TimeoutExpired(cmd=["helm"], timeout=600),
    )
    with pytest.raises(ChartResolutionError) as exc_info:
        _client().pull_oci(
            "ghcr.io/org/chart", pathlib.Path("/tmp/dest"), pathlib.Path("/tmp/up"), None, {}
        )
    assert exc_info.value.exit_code == 4
    assert "600" in str(exc_info.value)


@pytest.mark.unit
def test_pull_oci_env_passthrough(mocker: Any) -> None:
    """pull_oci passes env dict to subprocess.run (env isolation assertion)."""
    mock_run = mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
    )
    env = {
        "HELM_REGISTRY_CONFIG": "/tmp/reg.json",
        "DOCKER_CONFIG": "/tmp/docker",
        "HELM_REPOSITORY_CONFIG": "/tmp/repos.yaml",
        "HELM_REPOSITORY_CACHE": "/tmp/cache",
    }
    _client().pull_oci(
        "127.0.0.1:5555/charts/redis",
        pathlib.Path("/tmp/dest"),
        pathlib.Path("/tmp/up"),
        None,
        env,
    )
    assert mock_run.call_args.kwargs["env"] == env


# ---------------------------------------------------------------------------
# Redactor wiring — SEC-06 / CONTEXT D1 (Plan 05-02)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_upgrade_install_routes_stdout_and_stderr_through_redactor(mocker: Any) -> None:
    """upgrade_install delegates both stdout and stderr through the injected redactor.

    Uses a tracking redactor (closure) to verify the delegation — proving the wiring,
    not the redactor's correctness (that lives in test_helm_redact.py).
    """
    calls: list[str] = []

    def tracking_redactor(text: str) -> str:
        calls.append(text)
        return text

    raw_stdout = (
        "REVISION: 1\napiVersion: v1\nkind: Secret\nmetadata:\n  name: x\ndata:\n  pw: dGVzdA==\n"
    )
    raw_stderr = "some stderr text\n"
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=0, stdout=raw_stdout, stderr=raw_stderr),
    )
    client = HelmClient(
        kubeconfig_path=pathlib.Path("/tmp/test-kubeconfig.yaml"),
        redactor=tracking_redactor,
    )
    client.upgrade_install("r", _stub_chart(), "default", [], [], None, "600s")
    # Redactor must have been called with the raw stdout AND raw stderr at least once each.
    assert raw_stdout in calls, "tracking_redactor was not called with raw stdout"
    assert raw_stderr in calls, "tracking_redactor was not called with raw stderr"


@pytest.mark.unit
def test_history_routes_stdout_and_stderr_through_redactor(mocker: Any) -> None:
    """history delegates stdout through redactor on success and stderr on error path.

    Two sub-cases are verified using the tracking redactor:
    - Happy path: stdout (json.loads path) is passed through the redactor.
    - Error path: stderr is passed through the redactor (via HelmExecutionError).
    """
    stdout_calls: list[str] = []
    stderr_calls: list[str] = []

    def tracking_redactor(text: str) -> str:
        # Distinguish stdout vs stderr by format heuristic: JSON starts with '['
        if text.startswith("[") or text == "":
            stdout_calls.append(text)
        else:
            stderr_calls.append(text)
        return text

    # Sub-case 1: happy path — redactor receives stdout.
    json_stdout = (
        '[{"revision": 1, "status": "deployed", "chart": "app-1.0.0",'
        ' "description": "Install complete", "updated": "2026-01-01T00:00:00Z",'
        ' "app_version": "1.0"}]'
    )
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=0, stdout=json_stdout, stderr=""),
    )
    client = HelmClient(
        kubeconfig_path=pathlib.Path("/tmp/test-kubeconfig.yaml"),
        redactor=tracking_redactor,
    )
    client.history("rel", "ns")
    assert json_stdout in stdout_calls, "tracking_redactor was not called with raw stdout"

    # Sub-case 2: error path — redactor receives stderr.
    raw_stderr = "Error: release not found\n"
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=1, stdout="", stderr=raw_stderr),
    )
    with pytest.raises(HelmExecutionError):
        client.history("rel", "ns")
    assert raw_stderr in stderr_calls, "tracking_redactor was not called with raw stderr"


@pytest.mark.unit
def test_default_redactor_redacts_secret_in_upgrade_install_stdout(mocker: Any) -> None:
    """Default redact_helm_output scrubs kind: Secret from upgrade_install stdout end-to-end.

    Constructs HelmClient WITHOUT explicit redactor= to prove the default wiring.
    Verifies that the sentinel appears and the raw base64 bytes do not.
    """
    helm_stdout = "apiVersion: v1\nkind: Secret\nmetadata:\n  name: x\ndata:\n  pw: dGVzdA==\n"
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=0, stdout=helm_stdout, stderr=""),
    )
    # No explicit redactor= — default redact_helm_output is used.
    result = HelmClient(kubeconfig_path=pathlib.Path("/tmp/test-kubeconfig.yaml")).upgrade_install(
        "r", _stub_chart(), "default", [], [], None, "600s"
    )
    assert "<redacted>" in result.stdout
    assert "dGVzdA==" not in result.stdout


# ---------------------------------------------------------------------------
# diff method — PIPE-02 / SEC-06 (Plan 05-03)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_diff_success_exit_0_returns_redacted_stdout(mocker: Any) -> None:
    """returncode=0 (no diff) returns the redacted stdout string."""
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=0, stdout="no changes\n", stderr=""),
    )
    result = _client().diff("r", _stub_chart(), "default", [], [], "600s")
    assert result == "no changes\n"


@pytest.mark.unit
def test_diff_success_exit_1_returns_redacted_stdout(mocker: Any) -> None:
    """returncode=1 (differences exist) is SUCCESS — returns the redacted diff text."""
    diff_text = "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n"
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=1, stdout=diff_text, stderr=""),
    )
    # Must NOT raise; must return the diff content
    result = _client().diff("r", _stub_chart(), "default", [], [], "600s")
    assert result == diff_text


@pytest.mark.unit
def test_diff_failure_exit_2_raises_helm_execution_error(mocker: Any) -> None:
    """returncode=2 (error) raises HelmExecutionError with exit_code=5."""
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(
            args=[], returncode=2, stdout="", stderr="something went wrong"
        ),
    )
    with pytest.raises(HelmExecutionError) as exc_info:
        _client().diff("r", _stub_chart(), "default", [], [], "600s")
    assert exc_info.value.exit_code == 5
    assert "returned 2" in str(exc_info.value)


@pytest.mark.unit
def test_diff_routes_stdout_and_stderr_through_redactor(mocker: Any) -> None:
    """diff() routes stdout through the injected redactor (SEC-06 / T-05-01 gate).

    Uses a tracking redactor to verify delegation — proving the wiring, not the
    redactor's correctness (that lives in test_helm_redact.py).
    """
    calls: list[str] = []

    def tracking_redactor(text: str) -> str:
        calls.append(text)
        return text.replace("dGVzdA==", "<redacted>")

    raw_stdout = "apiVersion: v1\nkind: Secret\ndata:\n  pw: dGVzdA==\n"
    mocker.patch(
        _PATCH_TARGET,
        return_value=CompletedProcess(args=[], returncode=0, stdout=raw_stdout, stderr=""),
    )
    client = HelmClient(
        kubeconfig_path=pathlib.Path("/tmp/test-kubeconfig.yaml"),
        redactor=tracking_redactor,
    )
    result = client.diff("r", _stub_chart(), "default", [], [], "600s")
    # Redactor must have been called with the raw stdout
    assert raw_stdout in calls, "tracking_redactor was not called with raw stdout"
    # Returned text must reflect redaction
    assert "<redacted>" in result
    assert "dGVzdA==" not in result


@pytest.mark.unit
def test_diff_timeout_raises_helm_timeout_error(mocker: Any) -> None:
    """subprocess.TimeoutExpired raises HelmTimeoutError with exit_code=6."""
    mocker.patch(
        _PATCH_TARGET,
        side_effect=subprocess.TimeoutExpired(cmd=["helm"], timeout=600),
    )
    with pytest.raises(HelmTimeoutError) as exc_info:
        _client().diff("r", _stub_chart(), "default", [], [], "600s")
    assert exc_info.value.exit_code == 6
    assert "600" in str(exc_info.value)
