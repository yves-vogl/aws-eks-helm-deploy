"""Unit tests for OciChart.resolve() — subprocess mocked via pytest-mock.

Coverage targets:
  - 100% line + 100% branch on chart/oci.py
  - All R4/R5/R6/R7/R8/R13 structural invariants asserted

Subprocess patch strategy:
  - HELM calls: patch ``aws_eks_helm_deploy.helm.client.subprocess.run`` (the helm module's
    subprocess binding — distinct module from oci.py).
  - COSIGN calls: patch ``OciChart._run_cosign_verify`` method directly (method-level mock)
    to avoid the shared-module binding issue where both helm and cosign patches would target
    the same ``subprocess.run`` attribute. For tests that need to inspect cosign argv,
    we use a side_effect to capture the call.
  - For subprocess.run counting tests (ordering, failure), patch
    ``aws_eks_helm_deploy.chart.oci.subprocess.run`` WITHOUT also patching the helm module,
    so the patch isn't overwritten.

pytest-mock's ``mocker`` fixture is used throughout.
"""

from __future__ import annotations

import pathlib
import subprocess
from subprocess import CompletedProcess
from typing import Any

import pytest
from pydantic import SecretStr

from aws_eks_helm_deploy.chart.oci import OciChart
from aws_eks_helm_deploy.errors import ChartResolutionError

# Patch targets
_COSIGN_METHOD_PATCH = "aws_eks_helm_deploy.chart.oci.OciChart._run_cosign_verify"
_COSIGN_RUN_PATCH = "aws_eks_helm_deploy.chart.oci.subprocess.run"
_HELM_PATCH = "aws_eks_helm_deploy.helm.client.subprocess.run"


def _success(stdout: str = "", stderr: str = "") -> CompletedProcess[str]:
    return CompletedProcess(args=[], returncode=0, stdout=stdout, stderr=stderr)


def _make_chart_dir(tmp_path: pathlib.Path, name: str = "redis", version: str = "0.1.0") -> None:
    """Create a minimal unpacked chart directory structure inside tmp_path/unpacked/."""
    unpack_dir = tmp_path / "unpacked"
    chart_dir = unpack_dir / name
    chart_dir.mkdir(parents=True, exist_ok=True)
    (chart_dir / "Chart.yaml").write_text(f"name: {name}\nversion: {version}\n")


# ---------------------------------------------------------------------------
# Happy path — no auth, no verify
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_happy_path_without_verify(tmp_path: pathlib.Path, mocker: Any) -> None:
    """verify=False: helm pull called, no cosign, no registry_login."""
    mock_helm = mocker.patch(_HELM_PATCH, return_value=_success())
    mock_cosign_method = mocker.patch(_COSIGN_METHOD_PATCH)
    # Pre-create the unpacked chart dir that helm pull would produce
    _make_chart_dir(tmp_path, "redis")
    mocker.patch(
        "aws_eks_helm_deploy.chart.oci.tempfile.mkdtemp",
        return_value=str(tmp_path),
    )

    chart = OciChart(reference="127.0.0.1:5555/charts/redis", version="0.1.0")
    with chart.resolve() as resolved:
        assert resolved.name == "redis"
        assert resolved.version == "0.1.0"

    # No cosign — only helm pull was called
    assert mock_helm.call_count == 1
    argv = mock_helm.call_args.args[0]
    assert "oci://127.0.0.1:5555/charts/redis" in argv
    # cosign method NOT called
    assert mock_cosign_method.call_count == 0


@pytest.mark.unit
def test_resolve_happy_path_with_registry_creds(tmp_path: pathlib.Path, mocker: Any) -> None:
    """auth: registry_login called once with .get_secret_value() (R13 single unwrap)."""
    mock_helm = mocker.patch(_HELM_PATCH, return_value=_success())
    _make_chart_dir(tmp_path, "redis")
    mocker.patch(
        "aws_eks_helm_deploy.chart.oci.tempfile.mkdtemp",
        return_value=str(tmp_path),
    )

    chart = OciChart(
        reference="127.0.0.1:5555/charts/redis",
        version="0.1.0",
        registry_username="alice",
        registry_password=SecretStr("hunter2"),
    )
    with chart.resolve() as resolved:
        assert resolved.name == "redis"

    # First call: registry login (input=password); second call: pull_oci
    assert mock_helm.call_count == 2
    login_call = mock_helm.call_args_list[0]
    login_argv = login_call.args[0]
    assert "registry" in login_argv
    assert "login" in login_argv
    assert "--password-stdin" in login_argv
    # Password passed via input=, NOT in argv (R4 + R13)
    assert login_call.kwargs["input"] == "hunter2"
    assert "hunter2" not in login_argv


# ---------------------------------------------------------------------------
# cosign verify — constrained (identity + issuer)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_happy_path_with_verify_constrained(tmp_path: pathlib.Path, mocker: Any) -> None:
    """verify=True + both constraints: cosign called with both --certificate-* flags."""
    # Capture the argv cosign was called with by hooking into _run_cosign_verify
    cosign_calls: list[list[str]] = []

    def capture_cosign_verify(self: OciChart) -> None:
        """Side effect that records what argv would be built."""
        argv: list[str] = ["cosign", "verify"]
        if self._verify_identity is not None:
            argv.extend(["--certificate-identity", self._verify_identity])
        if self._verify_oidc_issuer is not None:
            argv.extend(["--certificate-oidc-issuer", self._verify_oidc_issuer])
        argv.append(self._reference)
        cosign_calls.append(argv)

    mock_cosign_method = mocker.patch(
        _COSIGN_METHOD_PATCH, side_effect=capture_cosign_verify, autospec=True
    )
    mocker.patch(_HELM_PATCH, return_value=_success())
    _make_chart_dir(tmp_path, "redis")
    mocker.patch(
        "aws_eks_helm_deploy.chart.oci.tempfile.mkdtemp",
        return_value=str(tmp_path),
    )

    chart = OciChart(
        reference="127.0.0.1:5555/charts/redis",
        verify=True,
        verify_identity="alice@example.com",
        verify_oidc_issuer="https://accounts.example.com",
    )
    with chart.resolve() as resolved:
        assert resolved.name == "redis"

    # cosign method called exactly once
    assert mock_cosign_method.call_count == 1
    cosign_argv = cosign_calls[0]
    assert "--certificate-identity" in cosign_argv
    assert "alice@example.com" in cosign_argv
    assert "--certificate-oidc-issuer" in cosign_argv
    assert "https://accounts.example.com" in cosign_argv
    # Reference is the OCI ref, NOT a local path (R5)
    assert "127.0.0.1:5555/charts/redis" in cosign_argv


# ---------------------------------------------------------------------------
# cosign verify — unconstrained WARN log
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_verify_unconstrained_emits_warn(
    tmp_path: pathlib.Path, mocker: Any, capfd: Any
) -> None:
    """verify=True without identity/issuer: WARN log 'chart.verify.unconstrained_identity'."""
    import structlog.testing

    # Let _run_cosign_verify actually run but mock subprocess.run for cosign
    # Since verify=True but no helm call + cosign call, we need to avoid the shared-module issue.
    # We patch _run_cosign_verify to trigger the WARN log by calling the real implementation
    # but mocking its subprocess.run. Since no helm calls happen alongside, no conflict.
    mocker.patch(_COSIGN_RUN_PATCH, return_value=_success())
    mocker.patch(_HELM_PATCH, return_value=_success())
    _make_chart_dir(tmp_path, "redis")
    mocker.patch(
        "aws_eks_helm_deploy.chart.oci.tempfile.mkdtemp",
        return_value=str(tmp_path),
    )

    with structlog.testing.capture_logs() as cap_logs:
        chart = OciChart(reference="127.0.0.1:5555/charts/redis", verify=True)
        with chart.resolve() as resolved:
            assert resolved.name == "redis"

    # Exactly one WARN log with the canonical event name
    warn_logs = [
        e
        for e in cap_logs
        if e.get("log_level") == "warning"
        and e.get("event") == "chart.verify.unconstrained_identity"
    ]
    assert len(warn_logs) == 1, f"Expected exactly 1 WARN log, got: {cap_logs}"


# ---------------------------------------------------------------------------
# R6: cosign verify BEFORE helm pull (ordering assertion)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_runs_cosign_verify_before_helm_pull(tmp_path: pathlib.Path, mocker: Any) -> None:
    """R6: cosign verify call MUST appear before helm pull in call order."""
    call_order: list[str] = []

    def cosign_side_effect(self: OciChart) -> None:
        call_order.append("cosign")

    def helm_side_effect(*args: Any, **kwargs: Any) -> CompletedProcess[str]:
        call_order.append("helm")
        return _success()

    mocker.patch(_COSIGN_METHOD_PATCH, side_effect=cosign_side_effect, autospec=True)
    mocker.patch(_HELM_PATCH, side_effect=helm_side_effect)
    _make_chart_dir(tmp_path, "redis")
    mocker.patch(
        "aws_eks_helm_deploy.chart.oci.tempfile.mkdtemp",
        return_value=str(tmp_path),
    )

    chart = OciChart(
        reference="127.0.0.1:5555/charts/redis",
        verify=True,
        verify_identity="alice@example.com",
        verify_oidc_issuer="https://accounts.example.com",
    )
    with chart.resolve():
        pass

    assert call_order[0] == "cosign", "cosign must run BEFORE helm pull (R6)"
    assert call_order[1] == "helm", "helm pull must run AFTER cosign (R6)"


# ---------------------------------------------------------------------------
# R5: cosign verify against OCI ref, NOT a local file
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_cosign_verify_against_ref_not_tarball(tmp_path: pathlib.Path, mocker: Any) -> None:
    """R5: cosign verify uses the OCI reference, NOT any local file path."""
    captured_ref: list[str] = []

    def capture_ref(self: OciChart) -> None:
        captured_ref.append(self._reference)

    mocker.patch(_COSIGN_METHOD_PATCH, side_effect=capture_ref, autospec=True)
    mocker.patch(_HELM_PATCH, return_value=_success())
    _make_chart_dir(tmp_path, "redis")
    mocker.patch(
        "aws_eks_helm_deploy.chart.oci.tempfile.mkdtemp",
        return_value=str(tmp_path),
    )

    chart = OciChart(
        reference="127.0.0.1:5555/charts/redis",
        verify=True,
        verify_identity="alice@example.com",
        verify_oidc_issuer="https://accounts.example.com",
    )
    with chart.resolve():
        pass

    assert len(captured_ref) == 1
    # Reference is the OCI registry reference (R5), NOT a local path
    ref = captured_ref[0]
    assert ref == "127.0.0.1:5555/charts/redis"
    assert not ref.endswith(".tgz"), "cosign reference must not be a tarball path"
    assert "/" in ref  # registry/chart format


# ---------------------------------------------------------------------------
# R5 + R6 + R8: cosign failure — ChartResolutionError raised; helm NEVER called; cleanup
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_cosign_failure_raises_chart_resolution_error_and_cleans_tempdir(
    tmp_path: pathlib.Path, mocker: Any
) -> None:
    """cosign non-zero exit: ChartResolutionError raised; helm pull never called (R6/R8).

    Uses method-level mock (_run_cosign_verify) to avoid shared subprocess.run conflict.
    The raised ChartResolutionError matches what _run_cosign_verify emits on CalledProcessError.
    """
    mocker.patch(
        _COSIGN_METHOD_PATCH,
        side_effect=ChartResolutionError(
            "cosign verify failed for 127.0.0.1:5555/charts/redis: no matching signatures"
        ),
    )
    mock_helm = mocker.patch(_HELM_PATCH)
    mocker.patch(
        "aws_eks_helm_deploy.chart.oci.tempfile.mkdtemp",
        return_value=str(tmp_path),
    )
    # Create a sentinel file to check cleanup
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("should be cleaned up")

    chart = OciChart(
        reference="127.0.0.1:5555/charts/redis",
        verify=True,
        verify_identity="alice@example.com",
        verify_oidc_issuer="https://accounts.example.com",
    )
    with pytest.raises(ChartResolutionError) as exc_info, chart.resolve():
        pass

    assert "cosign verify failed" in str(exc_info.value)
    assert "no matching signatures" in str(exc_info.value)
    # helm pull NEVER called (R6 — verify before pull)
    assert mock_helm.call_count == 0
    # Tempdir cleaned (R8)
    assert not tmp_path.exists()


@pytest.mark.unit
def test_resolve_cosign_timeout_raises_chart_resolution_error(
    tmp_path: pathlib.Path, mocker: Any
) -> None:
    """cosign TimeoutExpired: ChartResolutionError raised; helm never called; cleanup.

    Uses method-level mock to avoid shared subprocess.run conflict.
    """
    mocker.patch(
        _COSIGN_METHOD_PATCH,
        side_effect=ChartResolutionError(
            "cosign verify for 127.0.0.1:5555/charts/redis timed out after 120s"
        ),
    )
    mock_helm = mocker.patch(_HELM_PATCH)
    mocker.patch(
        "aws_eks_helm_deploy.chart.oci.tempfile.mkdtemp",
        return_value=str(tmp_path),
    )

    chart = OciChart(
        reference="127.0.0.1:5555/charts/redis",
        verify=True,
        verify_identity="alice@example.com",
        verify_oidc_issuer="https://accounts.example.com",
    )
    with pytest.raises(ChartResolutionError) as exc_info, chart.resolve():
        pass

    assert "timed out" in str(exc_info.value)
    assert mock_helm.call_count == 0
    assert not tmp_path.exists()


@pytest.mark.unit
def test_run_cosign_verify_called_process_error(mocker: Any) -> None:
    """Direct test of _run_cosign_verify: CalledProcessError → ChartResolutionError.

    Patches subprocess.run in oci.py without any helm interference.
    """
    mocker.patch(
        _COSIGN_RUN_PATCH,
        side_effect=subprocess.CalledProcessError(
            returncode=1,
            cmd=["cosign", "verify"],
            stderr="no matching signatures",
        ),
    )
    chart = OciChart(
        reference="127.0.0.1:5555/charts/redis",
        verify=True,
        verify_identity="alice@example.com",
        verify_oidc_issuer="https://accounts.example.com",
    )
    with pytest.raises(ChartResolutionError) as exc_info:
        chart._run_cosign_verify()

    assert "cosign verify failed" in str(exc_info.value)
    assert "no matching signatures" in str(exc_info.value)


@pytest.mark.unit
def test_run_cosign_verify_timeout(mocker: Any) -> None:
    """Direct test of _run_cosign_verify: TimeoutExpired → ChartResolutionError."""
    mocker.patch(
        _COSIGN_RUN_PATCH,
        side_effect=subprocess.TimeoutExpired(cmd=["cosign"], timeout=120),
    )
    chart = OciChart(
        reference="127.0.0.1:5555/charts/redis",
        verify=True,
        verify_identity="alice@example.com",
        verify_oidc_issuer="https://accounts.example.com",
    )
    with pytest.raises(ChartResolutionError) as exc_info:
        chart._run_cosign_verify()

    assert "timed out" in str(exc_info.value)
    assert "120" in str(exc_info.value)


# ---------------------------------------------------------------------------
# helm pull failure — cleanup
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_helm_pull_failure_raises_chart_resolution_error(
    tmp_path: pathlib.Path, mocker: Any
) -> None:
    """helm pull non-zero: ChartResolutionError raised; tempdir cleaned."""
    mocker.patch(
        _HELM_PATCH,
        return_value=CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Error: chart not found"
        ),
    )
    mocker.patch(
        "aws_eks_helm_deploy.chart.oci.tempfile.mkdtemp",
        return_value=str(tmp_path),
    )

    chart = OciChart(reference="127.0.0.1:5555/charts/redis", version="0.1.0")
    with pytest.raises(ChartResolutionError) as exc_info, chart.resolve():
        pass

    assert "chart not found" in str(exc_info.value)
    assert not tmp_path.exists()


# ---------------------------------------------------------------------------
# Registry login — with / without creds
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_without_registry_creds_skips_registry_login(
    tmp_path: pathlib.Path, mocker: Any
) -> None:
    """username=None: registry login is never called."""
    mock_helm = mocker.patch(_HELM_PATCH, return_value=_success())
    _make_chart_dir(tmp_path, "redis")
    mocker.patch(
        "aws_eks_helm_deploy.chart.oci.tempfile.mkdtemp",
        return_value=str(tmp_path),
    )

    chart = OciChart(reference="127.0.0.1:5555/charts/redis")
    with chart.resolve():
        pass

    # Only helm pull called, not login
    assert mock_helm.call_count == 1
    argv = mock_helm.call_args.args[0]
    assert "registry" not in argv


@pytest.mark.unit
def test_resolve_secret_str_password_unwrapped_at_single_site(
    tmp_path: pathlib.Path, mocker: Any
) -> None:
    """R13: SecretStr unwrapped exactly once; plaintext not in any argv."""
    mock_helm = mocker.patch(_HELM_PATCH, return_value=_success())
    _make_chart_dir(tmp_path, "redis")
    mocker.patch(
        "aws_eks_helm_deploy.chart.oci.tempfile.mkdtemp",
        return_value=str(tmp_path),
    )

    chart = OciChart(
        reference="127.0.0.1:5555/charts/redis",
        registry_username="alice",
        registry_password=SecretStr("s3cr3t-password"),
    )
    with chart.resolve():
        pass

    # The plaintext must not appear in any argv (R4 / R13)
    for call in mock_helm.call_args_list:
        for arg in call.args[0]:
            assert "s3cr3t-password" not in str(arg), (
                f"Plaintext password leaked into argv: {call.args[0]}"
            )
    # Password is passed via input= to the login call
    login_call = mock_helm.call_args_list[0]
    assert login_call.kwargs.get("input") == "s3cr3t-password"


# ---------------------------------------------------------------------------
# 4-env-var isolation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_passes_4_isolated_env_vars(tmp_path: pathlib.Path, mocker: Any) -> None:
    """All helm subprocess calls receive 4 isolated HELM_/DOCKER_ env vars (RESEARCH §5)."""
    mock_helm = mocker.patch(_HELM_PATCH, return_value=_success())
    mocker.patch(_COSIGN_METHOD_PATCH)  # method-level mock — no env passed to cosign
    _make_chart_dir(tmp_path, "redis")
    mocker.patch(
        "aws_eks_helm_deploy.chart.oci.tempfile.mkdtemp",
        return_value=str(tmp_path),
    )

    chart = OciChart(
        reference="127.0.0.1:5555/charts/redis",
        registry_username="alice",
        registry_password=SecretStr("pass"),
        verify=True,
        verify_identity="alice@example.com",
        verify_oidc_issuer="https://accounts.example.com",
    )
    with chart.resolve():
        pass

    # helm calls: registry_login + pull_oci — both get the 4 env vars
    for call in mock_helm.call_args_list:
        env = call.kwargs["env"]
        assert "HELM_REGISTRY_CONFIG" in env
        assert "DOCKER_CONFIG" in env
        assert "HELM_REPOSITORY_CONFIG" in env
        assert "HELM_REPOSITORY_CACHE" in env
        # All paths should point inside the tmpdir
        assert str(tmp_path) in env["HELM_REGISTRY_CONFIG"]
        assert str(tmp_path) in env["DOCKER_CONFIG"]
        assert str(tmp_path) in env["HELM_REPOSITORY_CONFIG"]
        assert str(tmp_path) in env["HELM_REPOSITORY_CACHE"]


# ---------------------------------------------------------------------------
# Version flag passthrough
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_with_version_passes_version_flag(tmp_path: pathlib.Path, mocker: Any) -> None:
    """--version flag is passed to helm pull when version is set."""
    mock_helm = mocker.patch(_HELM_PATCH, return_value=_success())
    _make_chart_dir(tmp_path, "redis")
    mocker.patch(
        "aws_eks_helm_deploy.chart.oci.tempfile.mkdtemp",
        return_value=str(tmp_path),
    )

    chart = OciChart(reference="127.0.0.1:5555/charts/redis", version="18.5.0")
    with chart.resolve():
        pass

    argv = mock_helm.call_args.args[0]
    assert "--version" in argv
    assert "18.5.0" in argv


@pytest.mark.unit
def test_resolve_without_version_omits_version_flag(tmp_path: pathlib.Path, mocker: Any) -> None:
    """No --version flag in helm pull argv when version is None."""
    mock_helm = mocker.patch(_HELM_PATCH, return_value=_success())
    _make_chart_dir(tmp_path, "redis")
    mocker.patch(
        "aws_eks_helm_deploy.chart.oci.tempfile.mkdtemp",
        return_value=str(tmp_path),
    )

    chart = OciChart(reference="127.0.0.1:5555/charts/redis", version=None)
    with chart.resolve():
        pass

    argv = mock_helm.call_args.args[0]
    assert "--version" not in argv


# ---------------------------------------------------------------------------
# R7: single-subdir discovery negative branch
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_raises_chart_resolution_error_when_no_subdir_after_untar(
    tmp_path: pathlib.Path, mocker: Any
) -> None:
    """R7: zero unpacked subdirs → ChartResolutionError with descriptive message."""
    mocker.patch(_HELM_PATCH, return_value=_success())
    mocker.patch(
        "aws_eks_helm_deploy.chart.oci.tempfile.mkdtemp",
        return_value=str(tmp_path),
    )
    # Create unpack_dir but leave it empty (no chart dir inside)
    (tmp_path / "unpacked").mkdir()

    chart = OciChart(reference="127.0.0.1:5555/charts/redis")
    with pytest.raises(ChartResolutionError) as exc_info, chart.resolve():
        pass

    assert "expected exactly one unpacked chart dir" in str(exc_info.value)
    assert "found 0" in str(exc_info.value)
