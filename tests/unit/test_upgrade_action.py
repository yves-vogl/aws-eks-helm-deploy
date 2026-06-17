"""Unit tests for aws_eks_helm_deploy.actions.upgrade.

Requirements traceability:
    CHART-01: UpgradeAction.run invokes resolve_local_chart -> HelmClient.upgrade_install
    CHART-05: pipe.success emits exact 'Deployed chart ...' format per CONTEXT D7
    PIPE-01:  Full chain (auth -> token -> kubeconfig -> chart -> helm upgrade --install) wired
    PIPE-06:  Every failure mode raises a typed PipeError subclass; cli.py catches PipeError
    HISTORY-01: Settings.history_max with ge=0 validator (closes #17)
    HISTORY-02: settings.history_max flows through to HelmClient.upgrade_install(history_max=...)
    META-01:  INJECT_BITBUCKET_METADATA opt-in; 5 BITBUCKET_* vars; missing-var warn
"""

from __future__ import annotations

import pathlib
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest
from aws_eks_helm_deploy.actions.upgrade import (
    BITBUCKET_META_VARS,
    UpgradeAction,
    build_bitbucket_set_args,
)
from pytest_mock import MockerFixture
from structlog.testing import capture_logs

from aws_eks_helm_deploy.chart.local import ResolvedChart
from aws_eks_helm_deploy.eks.cluster import ClusterAccess
from aws_eks_helm_deploy.errors import (
    AuthenticationError,
    ChartResolutionError,
    ClusterAccessError,
    ConfigurationError,
    EksTokenError,
    HelmExecutionError,
    HelmTimeoutError,
    KubeconfigError,
)
from aws_eks_helm_deploy.helm.client import HelmResult
from aws_eks_helm_deploy.settings import Settings

# ---------------------------------------------------------------------------
# Helpers + fixtures
# ---------------------------------------------------------------------------


def _make_settings(**overrides: Any) -> Settings:
    """Construct a Settings with all required env vars pre-set via kwargs."""
    defaults: dict[str, Any] = dict(
        aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
        aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        aws_region="eu-central-1",
        cluster_name="test-cluster",
        chart="/tmp/chart-fixture",
        release_name="test-release",
        namespace="default",
    )
    return Settings(**(defaults | overrides))


def _resolved_chart() -> ResolvedChart:
    return ResolvedChart(
        name="minimal",
        version="0.1.0",
        source_path=pathlib.Path("/tmp/chart-fixture"),
    )


def _cluster_access() -> ClusterAccess:
    return ClusterAccess(
        name="test-cluster",
        endpoint="https://test-cluster.example.com",
        ca_data="dGVzdA==",
        region="eu-central-1",
    )


def _helm_result() -> HelmResult:
    return HelmResult(
        stdout="Release 'test-release' has been upgraded. Happy Helming!\nREVISION: 3",
        stderr="",
        returncode=0,
        revision=3,
    )


@contextmanager  # type: ignore[arg-type]
def _kubeconfig_ctx(*_args: Any, **_kwargs: Any):  # type: ignore[no-untyped-def]
    """Fake write_kubeconfig context manager yielding a test Path."""
    yield pathlib.Path("/tmp/test-kubeconfig.yaml")


def _patch_all_happy(mocker: MockerFixture) -> dict[str, MagicMock]:
    """Patch all external dependencies for the happy-path tests.

    Returns a dict of all mock objects keyed by the dependency name.
    """
    fake_strategy = mocker.MagicMock()
    fake_strategy.get_credentials.return_value = mocker.MagicMock(
        to_boto3_kwargs=mocker.MagicMock(return_value={})
    )

    mocks = {
        "select_strategy": mocker.patch(
            "aws_eks_helm_deploy.actions.upgrade.select_strategy",
            return_value=fake_strategy,
        ),
        "boto3_session": mocker.patch(
            "aws_eks_helm_deploy.actions.upgrade.boto3.session.Session",
            return_value=mocker.MagicMock(),
        ),
        "get_cluster_access": mocker.patch(
            "aws_eks_helm_deploy.actions.upgrade.get_cluster_access",
            return_value=_cluster_access(),
        ),
        "generate_eks_token": mocker.patch(
            "aws_eks_helm_deploy.actions.upgrade.generate_eks_token",
            return_value="k8s-aws-v1.test-token",
        ),
        "write_kubeconfig": mocker.patch(
            "aws_eks_helm_deploy.actions.upgrade.write_kubeconfig",
            side_effect=_kubeconfig_ctx,
        ),
        "resolve_local_chart": mocker.patch(
            "aws_eks_helm_deploy.actions.upgrade.resolve_local_chart",
            return_value=_resolved_chart(),
        ),
        "helm_client_cls": mocker.patch(
            "aws_eks_helm_deploy.actions.upgrade.HelmClient",
        ),
    }
    mocks["helm_client_cls"].return_value.upgrade_install.return_value = _helm_result()
    mocks["strategy"] = fake_strategy
    return mocks


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_returns_0_on_success(mocker: MockerFixture) -> None:
    """UpgradeAction.run returns 0 on success and calls pipe.success with the exact message."""
    mocks = _patch_all_happy(mocker)
    mock_pipe = mocker.MagicMock()
    settings = _make_settings()
    action = UpgradeAction(settings)

    result = action.run(mock_pipe)

    assert result == 0
    mock_pipe.success.assert_called_once_with(
        "Deployed chart minimal (0.1.0) to release test-release"
        " in namespace default on cluster test-cluster"
    )
    _ = mocks  # mocks used for side-effects


@pytest.mark.unit
def test_run_emits_structlog_info_with_all_obs01_fields(mocker: MockerFixture) -> None:
    """UpgradeAction.run emits a structlog info event with all 9 OBS-01 stable fields."""
    _patch_all_happy(mocker)
    mock_pipe = mocker.MagicMock()
    settings = _make_settings()
    action = UpgradeAction(settings)

    with capture_logs() as logs:
        action.run(mock_pipe)

    upgrade_logs = [e for e in logs if e.get("event") == "upgrade complete"]
    assert len(upgrade_logs) == 1
    event = upgrade_logs[0]

    assert event["action"] == "upgrade"
    assert event["release"] == "test-release"
    assert event["namespace"] == "default"
    assert event["chart_source"] == "/tmp/chart-fixture"
    assert event["chart_name"] == "minimal"
    assert event["chart_version"] == "0.1.0"
    assert event["cluster"] == "test-cluster"
    assert event["helm_revision"] == 3
    assert isinstance(event["duration_ms"], int)


# ---------------------------------------------------------------------------
# Required-env-var checks
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_raises_configuration_error_when_cluster_name_missing(
    mocker: MockerFixture,
) -> None:
    """run() raises ConfigurationError(exit_code=1) when cluster_name is None."""
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(cluster_name=None)
    action = UpgradeAction(settings)

    with pytest.raises(ConfigurationError) as exc_info:
        action.run(mock_pipe)

    assert exc_info.value.exit_code == 1
    assert "CLUSTER_NAME" in str(exc_info.value)


@pytest.mark.unit
def test_run_raises_configuration_error_when_chart_missing(
    mocker: MockerFixture,
) -> None:
    """run() raises ConfigurationError(exit_code=1) when chart is None."""
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(chart=None)
    action = UpgradeAction(settings)

    with pytest.raises(ConfigurationError) as exc_info:
        action.run(mock_pipe)

    assert exc_info.value.exit_code == 1
    assert "CHART" in str(exc_info.value)


@pytest.mark.unit
def test_run_raises_configuration_error_when_release_name_missing(
    mocker: MockerFixture,
) -> None:
    """run() raises ConfigurationError(exit_code=1) when release_name is None."""
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(release_name=None)
    action = UpgradeAction(settings)

    with pytest.raises(ConfigurationError) as exc_info:
        action.run(mock_pipe)

    assert exc_info.value.exit_code == 1
    assert "RELEASE_NAME" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Error-branch propagation tests (PIPE-06)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_propagates_authentication_error_from_credentials(
    mocker: MockerFixture,
) -> None:
    """AuthenticationError from strategy.get_credentials() propagates through run()."""
    mocks = _patch_all_happy(mocker)
    mocks["strategy"].get_credentials.side_effect = AuthenticationError("STS denied")
    mock_pipe = mocker.MagicMock()
    action = UpgradeAction(_make_settings())

    with pytest.raises(AuthenticationError):
        action.run(mock_pipe)


@pytest.mark.unit
def test_run_propagates_cluster_access_error(mocker: MockerFixture) -> None:
    """ClusterAccessError from get_cluster_access() propagates through run()."""
    _patch_all_happy(mocker)
    mocker.patch(
        "aws_eks_helm_deploy.actions.upgrade.get_cluster_access",
        side_effect=ClusterAccessError("describe-cluster failed"),
    )
    mock_pipe = mocker.MagicMock()
    action = UpgradeAction(_make_settings())

    with pytest.raises(ClusterAccessError):
        action.run(mock_pipe)


@pytest.mark.unit
def test_run_propagates_eks_token_error(mocker: MockerFixture) -> None:
    """EksTokenError from generate_eks_token() propagates through run()."""
    _patch_all_happy(mocker)
    mocker.patch(
        "aws_eks_helm_deploy.actions.upgrade.generate_eks_token",
        side_effect=EksTokenError("presign failed"),
    )
    mock_pipe = mocker.MagicMock()
    action = UpgradeAction(_make_settings())

    with pytest.raises(EksTokenError):
        action.run(mock_pipe)


@pytest.mark.unit
def test_run_propagates_chart_resolution_error(mocker: MockerFixture) -> None:
    """ChartResolutionError from resolve_local_chart() propagates through run()."""
    _patch_all_happy(mocker)
    mocker.patch(
        "aws_eks_helm_deploy.actions.upgrade.resolve_local_chart",
        side_effect=ChartResolutionError("chart not found"),
    )
    mock_pipe = mocker.MagicMock()
    action = UpgradeAction(_make_settings())

    with pytest.raises(ChartResolutionError):
        action.run(mock_pipe)


@pytest.mark.unit
def test_run_wraps_oserror_as_kubeconfig_error(mocker: MockerFixture) -> None:
    """OSError from write_kubeconfig raises KubeconfigError(exit_code=7) with __cause__ set."""
    _patch_all_happy(mocker)

    @contextmanager  # type: ignore[arg-type]
    def _raising_ctx(*_args: Any, **_kwargs: Any):  # type: ignore[no-untyped-def]
        raise OSError("disk full")
        yield  # pragma: no cover

    mocker.patch(
        "aws_eks_helm_deploy.actions.upgrade.write_kubeconfig",
        side_effect=_raising_ctx,
    )
    mock_pipe = mocker.MagicMock()
    action = UpgradeAction(_make_settings())

    with pytest.raises(KubeconfigError) as exc_info:
        action.run(mock_pipe)

    assert exc_info.value.exit_code == 7
    assert isinstance(exc_info.value.__cause__, OSError)
    assert "disk full" in str(exc_info.value.__cause__)


@pytest.mark.unit
def test_run_propagates_helm_execution_error(mocker: MockerFixture) -> None:
    """HelmExecutionError from upgrade_install() propagates through run()."""
    mocks = _patch_all_happy(mocker)
    mocks["helm_client_cls"].return_value.upgrade_install.side_effect = HelmExecutionError(
        "helm returned 1"
    )
    mock_pipe = mocker.MagicMock()
    action = UpgradeAction(_make_settings())

    with pytest.raises(HelmExecutionError):
        action.run(mock_pipe)


@pytest.mark.unit
def test_run_propagates_helm_timeout_error(mocker: MockerFixture) -> None:
    """HelmTimeoutError from upgrade_install() propagates through run()."""
    mocks = _patch_all_happy(mocker)
    mocks["helm_client_cls"].return_value.upgrade_install.side_effect = HelmTimeoutError(
        "timed out"
    )
    mock_pipe = mocker.MagicMock()
    action = UpgradeAction(_make_settings())

    with pytest.raises(HelmTimeoutError):
        action.run(mock_pipe)


# ---------------------------------------------------------------------------
# Bitbucket metadata injection tests (META-01 + D5)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_inject_false_omits_bitbucket_set_args(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When inject_bitbucket_metadata=False, no bitbucket.* entries appear in set_args."""
    monkeypatch.setenv("BITBUCKET_BUILD_NUMBER", "42")
    mocks = _patch_all_happy(mocker)
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(inject_bitbucket_metadata=False)
    action = UpgradeAction(settings)

    action.run(mock_pipe)

    call_kwargs = mocks["helm_client_cls"].return_value.upgrade_install.call_args.kwargs
    set_args: list[str] = call_kwargs["set_args"]
    assert not any("bitbucket" in arg for arg in set_args)


@pytest.mark.unit
def test_inject_true_with_all_5_vars_adds_5_set_args(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """All 5 BITBUCKET_* vars present -> 5 set_args entries in documented order."""
    monkeypatch.setenv("BITBUCKET_BUILD_NUMBER", "99")
    monkeypatch.setenv("BITBUCKET_REPO_SLUG", "my-repo")
    monkeypatch.setenv("BITBUCKET_COMMIT", "abc123def456")
    monkeypatch.setenv("BITBUCKET_TAG", "v1.2.3")
    monkeypatch.setenv("BITBUCKET_STEP_TRIGGERER_UUID", "{deadbeef-cafe-1234}")
    mocks = _patch_all_happy(mocker)
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(inject_bitbucket_metadata=True)
    action = UpgradeAction(settings)

    action.run(mock_pipe)

    call_kwargs = mocks["helm_client_cls"].return_value.upgrade_install.call_args.kwargs
    set_args: list[str] = call_kwargs["set_args"]
    bitbucket_args = [a for a in set_args if "bitbucket." in a]
    assert len(bitbucket_args) == 5
    assert bitbucket_args[0] == "bitbucket.bitbucket_build_number=99"
    assert bitbucket_args[1] == "bitbucket.bitbucket_repo_slug=my-repo"
    assert bitbucket_args[2] == "bitbucket.bitbucket_commit=abc123def456"
    assert bitbucket_args[3] == "bitbucket.bitbucket_tag=v1.2.3"
    assert bitbucket_args[4] == "bitbucket.bitbucket_step_triggerer_uuid={deadbeef-cafe-1234}"


@pytest.mark.unit
def test_inject_true_with_uuid_curly_braces_passes_through_verbatim(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Curly braces in BITBUCKET_STEP_TRIGGERER_UUID survive verbatim (T-03-04-01)."""
    monkeypatch.setenv("BITBUCKET_BUILD_NUMBER", "1")
    monkeypatch.setenv("BITBUCKET_REPO_SLUG", "repo")
    monkeypatch.setenv("BITBUCKET_COMMIT", "abc")
    monkeypatch.setenv("BITBUCKET_TAG", "tag")
    monkeypatch.setenv("BITBUCKET_STEP_TRIGGERER_UUID", "{deadbeef-cafe-1234-5678-abcdef012345}")
    mocks = _patch_all_happy(mocker)
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(inject_bitbucket_metadata=True)
    action = UpgradeAction(settings)

    action.run(mock_pipe)

    call_kwargs = mocks["helm_client_cls"].return_value.upgrade_install.call_args.kwargs
    set_args: list[str] = call_kwargs["set_args"]
    uuid_arg = next(a for a in set_args if "triggerer" in a)
    assert (
        uuid_arg == "bitbucket.bitbucket_step_triggerer_uuid={deadbeef-cafe-1234-5678-abcdef012345}"
    )


@pytest.mark.unit
def test_inject_true_with_missing_var_warns_and_omits_that_arg(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """inject=True with only BUILD_NUMBER set -> 4 warnings + 1 set_arg (CONTEXT D5)."""
    monkeypatch.setenv("BITBUCKET_BUILD_NUMBER", "42")
    # Leave all other 4 BITBUCKET_* vars unset
    for env_var, _ in BITBUCKET_META_VARS[1:]:
        monkeypatch.delenv(env_var, raising=False)

    mocks = _patch_all_happy(mocker)
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(inject_bitbucket_metadata=True)
    action = UpgradeAction(settings)

    with capture_logs() as logs:
        action.run(mock_pipe)

    warning_logs = [e for e in logs if e.get("log_level") == "warning"]
    missing_key_warns = [e for e in warning_logs if e.get("event") == "missing_metadata_key"]
    assert len(missing_key_warns) == 4

    call_kwargs = mocks["helm_client_cls"].return_value.upgrade_install.call_args.kwargs
    set_args: list[str] = call_kwargs["set_args"]
    bitbucket_args = [a for a in set_args if "bitbucket." in a]
    assert bitbucket_args == ["bitbucket.bitbucket_build_number=42"]


@pytest.mark.unit
def test_inject_true_with_empty_string_treated_as_missing(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Empty-string BITBUCKET_TAG is treated as missing (warn + omit) per CONTEXT D5."""
    monkeypatch.setenv("BITBUCKET_BUILD_NUMBER", "1")
    monkeypatch.setenv("BITBUCKET_REPO_SLUG", "repo")
    monkeypatch.setenv("BITBUCKET_COMMIT", "abc")
    monkeypatch.setenv("BITBUCKET_TAG", "")  # empty string
    monkeypatch.setenv("BITBUCKET_STEP_TRIGGERER_UUID", "{uuid}")

    mocks = _patch_all_happy(mocker)
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(inject_bitbucket_metadata=True)
    action = UpgradeAction(settings)

    with capture_logs() as logs:
        action.run(mock_pipe)

    missing_warns = [
        e
        for e in logs
        if e.get("log_level") == "warning" and e.get("event") == "missing_metadata_key"
    ]
    assert len(missing_warns) == 1
    assert missing_warns[0]["key"] == "BITBUCKET_TAG"

    call_kwargs = mocks["helm_client_cls"].return_value.upgrade_install.call_args.kwargs
    set_args: list[str] = call_kwargs["set_args"]
    assert not any("bitbucket_tag" in a for a in set_args)


@pytest.mark.unit
def test_user_supplied_set_values_come_after_bitbucket_in_set_args(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """User-supplied set_values appear AFTER bitbucket args (helm last-wins semantics)."""
    monkeypatch.setenv("BITBUCKET_BUILD_NUMBER", "1")
    monkeypatch.setenv("BITBUCKET_REPO_SLUG", "repo")
    monkeypatch.setenv("BITBUCKET_COMMIT", "abc")
    monkeypatch.setenv("BITBUCKET_TAG", "v1")
    monkeypatch.setenv("BITBUCKET_STEP_TRIGGERER_UUID", "{uuid}")

    mocks = _patch_all_happy(mocker)
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(inject_bitbucket_metadata=True, set_values=["my.key=value"])
    action = UpgradeAction(settings)

    action.run(mock_pipe)

    call_kwargs = mocks["helm_client_cls"].return_value.upgrade_install.call_args.kwargs
    set_args: list[str] = call_kwargs["set_args"]
    bb_indices = [i for i, a in enumerate(set_args) if "bitbucket." in a]
    user_indices = [i for i, a in enumerate(set_args) if a == "my.key=value"]
    assert len(bb_indices) == 5
    assert len(user_indices) == 1
    # All bitbucket entries come before user-supplied entries
    assert max(bb_indices) < user_indices[0]


# ---------------------------------------------------------------------------
# HISTORY_MAX wire-through tests (HISTORY-02)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_history_max_none_passes_none_to_helm_client(mocker: MockerFixture) -> None:
    """settings.history_max=None -> HelmClient.upgrade_install(history_max=None)."""
    mocks = _patch_all_happy(mocker)
    mock_pipe = mocker.MagicMock()
    settings = _make_settings()  # history_max default is None
    action = UpgradeAction(settings)

    action.run(mock_pipe)

    call_kwargs = mocks["helm_client_cls"].return_value.upgrade_install.call_args.kwargs
    assert call_kwargs["history_max"] is None


@pytest.mark.unit
def test_history_max_5_passes_5_to_helm_client(mocker: MockerFixture) -> None:
    """settings.history_max=5 -> HelmClient.upgrade_install(history_max=5)."""
    mocks = _patch_all_happy(mocker)
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(history_max=5)
    action = UpgradeAction(settings)

    action.run(mock_pipe)

    call_kwargs = mocks["helm_client_cls"].return_value.upgrade_install.call_args.kwargs
    assert call_kwargs["history_max"] == 5


@pytest.mark.unit
def test_history_max_0_passes_0_to_helm_client(mocker: MockerFixture) -> None:
    """settings.history_max=0 -> HelmClient.upgrade_install(history_max=0) (unlimited)."""
    mocks = _patch_all_happy(mocker)
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(history_max=0)
    action = UpgradeAction(settings)

    action.run(mock_pipe)

    call_kwargs = mocks["helm_client_cls"].return_value.upgrade_install.call_args.kwargs
    assert call_kwargs["history_max"] == 0


# ---------------------------------------------------------------------------
# Settings.timeout wire-through
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_settings_timeout_passes_to_helm_client(mocker: MockerFixture) -> None:
    """settings.timeout is passed verbatim to HelmClient.upgrade_install(timeout=...)."""
    mocks = _patch_all_happy(mocker)
    mock_pipe = mocker.MagicMock()
    settings = _make_settings()  # default timeout is "600s" after Task 03-4-01
    action = UpgradeAction(settings)

    action.run(mock_pipe)

    call_kwargs = mocks["helm_client_cls"].return_value.upgrade_install.call_args.kwargs
    assert call_kwargs["timeout"] == settings.timeout


# ---------------------------------------------------------------------------
# kubeconfig_override scaffold (Plan 03-05 integration test hook)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_kubeconfig_override_skips_cluster_access_and_token_generation(
    mocker: MockerFixture,
) -> None:
    """kubeconfig_override kwarg skips steps 4+5 (cluster_access, eks_token, write_kubeconfig)."""
    mocks = _patch_all_happy(mocker)
    mock_pipe = mocker.MagicMock()
    override_path = pathlib.Path("/tmp/kind-kubeconfig.yaml")
    settings = _make_settings()
    action = UpgradeAction(settings, kubeconfig_override=override_path)

    result = action.run(mock_pipe)

    assert result == 0
    mocks["get_cluster_access"].assert_not_called()
    mocks["generate_eks_token"].assert_not_called()
    mocks["write_kubeconfig"].assert_not_called()
    # HelmClient should be instantiated with the override path
    mocks["helm_client_cls"].assert_called_once_with(override_path)
    mock_pipe.success.assert_called_once()


# ---------------------------------------------------------------------------
# build_bitbucket_set_args standalone tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_bitbucket_set_args_returns_empty_when_all_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build_bitbucket_set_args returns [] + 5 warnings when all BITBUCKET_* vars absent."""
    for env_var, _ in BITBUCKET_META_VARS:
        monkeypatch.delenv(env_var, raising=False)

    mock_logger = MagicMock()
    result = build_bitbucket_set_args(mock_logger)

    assert result == []
    assert mock_logger.warning.call_count == 5


@pytest.mark.unit
def test_build_bitbucket_set_args_meta_vars_order() -> None:
    """BITBUCKET_META_VARS has exactly 5 entries in documented order."""
    assert len(BITBUCKET_META_VARS) == 5
    env_var_names = [e for e, _ in BITBUCKET_META_VARS]
    assert env_var_names[0] == "BITBUCKET_BUILD_NUMBER"
    assert env_var_names[1] == "BITBUCKET_REPO_SLUG"
    assert env_var_names[2] == "BITBUCKET_COMMIT"
    assert env_var_names[3] == "BITBUCKET_TAG"
    assert env_var_names[4] == "BITBUCKET_STEP_TRIGGERER_UUID"
