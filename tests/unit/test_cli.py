"""Unit tests for aws_eks_helm_deploy.cli.

Tests cover:
  - main() dispatches ACTION=upgrade to UpgradeAction (Phase 3)
  - main() passes strategy from select_strategy to UpgradeAction constructor
  - main() returns UpgradeAction.run return code (passthrough)
  - main() catches PipeError from UpgradeAction.run, calls pipe.fail(), returns exc.exit_code
  - main() catches bare Exception from UpgradeAction.run and returns 99
  - main() catches PipeError from select_strategy and returns exc.exit_code
  - __main__ module is runnable via runpy.run_module (SystemExit.code is int)
  - main() calls configure_logging(settings) exactly once
  - main() returns non-zero and writes to stderr when Settings() raises
  - main() calls select_strategy(settings) and binds auth_strategy to structlog context
  - Credentials are never passed to bind_safe_context
  - MIG-02: _warn_on_v1_env_vars emits WARN for SET/VALUES env vars at startup (D4)
"""

from __future__ import annotations

import runpy
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture
from structlog.testing import capture_logs

from aws_eks_helm_deploy.auth.base import AuthStrategy
from aws_eks_helm_deploy.cli import _warn_on_v1_env_vars
from aws_eks_helm_deploy.errors import ConfigurationError, HelmExecutionError
from aws_eks_helm_deploy.settings import Settings

# ---------------------------------------------------------------------------
# Shared fixture: short-circuit select_strategy for Phase-1-style cli tests
# ---------------------------------------------------------------------------


@pytest.fixture
def _fake_strategy(mocker: MockerFixture) -> object:
    """Patch select_strategy to return a MagicMock AuthStrategy.

    Existing Phase 1 cli tests use this fixture to isolate cli flow from auth
    env-var coverage. The mock satisfies the AuthStrategy Protocol structurally.
    """
    fake = mocker.MagicMock(spec=AuthStrategy)
    fake.__class__.__name__ = "StaticKeysStrategy"
    mocker.patch("aws_eks_helm_deploy.cli.select_strategy", return_value=fake)
    return fake


# ---------------------------------------------------------------------------
# Phase 3 UpgradeAction dispatch tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_main_dispatches_upgrade_action_on_default_action(
    _fake_strategy: object, mocker: MockerFixture
) -> None:
    """main() instantiates UpgradeAction(settings, strategy=...) and calls .run(pipe)."""
    mock_pipe = mocker.MagicMock()
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO", return_value=mock_pipe)
    mock_upgrade_cls = mocker.patch("aws_eks_helm_deploy.cli.UpgradeAction")
    mock_upgrade_cls.return_value.run.return_value = 0

    from aws_eks_helm_deploy.cli import main

    result = main()

    assert result == 0
    # UpgradeAction was instantiated (settings as positional, strategy as kwarg)
    mock_upgrade_cls.assert_called_once()
    call_args = mock_upgrade_cls.call_args
    assert isinstance(call_args.args[0], Settings)
    assert call_args.kwargs["strategy"] is _fake_strategy
    mock_upgrade_cls.return_value.run.assert_called_once_with(mock_pipe)


@pytest.mark.unit
def test_main_returns_upgrade_action_run_return_code(
    _fake_strategy: object, mocker: MockerFixture
) -> None:
    """main() passes through UpgradeAction.run return code (0 or non-zero)."""
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO")
    mock_upgrade_cls = mocker.patch("aws_eks_helm_deploy.cli.UpgradeAction")

    from aws_eks_helm_deploy.cli import main

    mock_upgrade_cls.return_value.run.return_value = 0
    assert main() == 0

    mock_upgrade_cls.return_value.run.return_value = 5
    assert main() == 5


@pytest.mark.unit
def test_main_catches_pipe_error_from_upgrade_action(
    _fake_strategy: object, mocker: MockerFixture
) -> None:
    """main() catches PipeError from UpgradeAction.run -> pipe.fail + exit_code."""
    mock_pipe = mocker.MagicMock()
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO", return_value=mock_pipe)
    mock_upgrade_cls = mocker.patch("aws_eks_helm_deploy.cli.UpgradeAction")
    mock_upgrade_cls.return_value.run.side_effect = HelmExecutionError("helm failed")

    from aws_eks_helm_deploy.cli import main

    result = main()

    assert result == 5  # HelmExecutionError.exit_code
    mock_pipe.fail.assert_called_once_with("helm failed")


@pytest.mark.unit
def test_main_catches_unexpected_exception_returns_99(
    _fake_strategy: object, mocker: MockerFixture
) -> None:
    """main() catches bare Exception from UpgradeAction.run -> pipe.fail + 99."""
    mock_pipe = mocker.MagicMock()
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO", return_value=mock_pipe)
    mock_upgrade_cls = mocker.patch("aws_eks_helm_deploy.cli.UpgradeAction")
    mock_upgrade_cls.return_value.run.side_effect = RuntimeError("unexpected")

    from aws_eks_helm_deploy.cli import main

    result = main()

    assert result == 99
    mock_pipe.fail.assert_called_once_with("Unexpected error — see logs")


# ---------------------------------------------------------------------------
# Phase 1-style cli flow tests (kept for regression + bare exception path)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_main_catches_bare_exception(_fake_strategy: object, mocker: MockerFixture) -> None:
    """main() catches bare Exception from dispatch, calls pipe.fail(), and returns 99."""
    mock_pipe = mocker.MagicMock()
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO", return_value=mock_pipe)
    mock_upgrade_cls = mocker.patch("aws_eks_helm_deploy.cli.UpgradeAction")
    mock_upgrade_cls.return_value.run.side_effect = RuntimeError("something unexpected")

    from aws_eks_helm_deploy.cli import main

    result = main()

    assert result == 99
    mock_pipe.fail.assert_called_once_with("Unexpected error — see logs")


@pytest.mark.unit
def test_main_module_runs(_fake_strategy: object, mocker: MockerFixture) -> None:
    """python -m aws_eks_helm_deploy runs main() and exits with an integer code."""
    mock_pipe = mocker.MagicMock()
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO", return_value=mock_pipe)
    mocker.patch("aws_eks_helm_deploy.cli.configure_logging")
    mock_upgrade_cls = mocker.patch("aws_eks_helm_deploy.cli.UpgradeAction")
    mock_upgrade_cls.return_value.run.return_value = 0

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("aws_eks_helm_deploy", run_name="__main__", alter_sys=True)

    assert isinstance(exc_info.value.code, int)
    assert exc_info.value.code == 0


@pytest.mark.unit
def test_main_calls_configure_logging(_fake_strategy: object, mocker: MockerFixture) -> None:
    """main() calls configure_logging(settings) exactly once after Settings()."""
    mock_cfg = mocker.patch("aws_eks_helm_deploy.cli.configure_logging")
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO")
    mock_upgrade_cls = mocker.patch("aws_eks_helm_deploy.cli.UpgradeAction")
    mock_upgrade_cls.return_value.run.return_value = 0

    from aws_eks_helm_deploy.cli import main

    assert main() == 0
    assert mock_cfg.call_count == 1
    assert isinstance(mock_cfg.call_args.args[0], Settings)


@pytest.mark.unit
def test_main_settings_error_returns_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    """main() returns non-zero and writes to stderr when Settings() raises."""
    from unittest.mock import patch

    from aws_eks_helm_deploy.cli import main

    with patch("aws_eks_helm_deploy.cli.Settings", side_effect=RuntimeError("bad env")):
        result = main()

    assert result != 0
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err


# ---------------------------------------------------------------------------
# Phase 2 auth wire-in tests (new in Plan 02-04)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_main_selects_static_keys_strategy(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    """main() calls select_strategy; with valid static keys, returns 0."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")

    mock_upgrade_cls = mocker.patch("aws_eks_helm_deploy.cli.UpgradeAction")
    mock_upgrade_cls.return_value.run.return_value = 0

    from aws_eks_helm_deploy.cli import main

    result = main()
    assert result == 0


@pytest.mark.unit
def test_main_selects_assume_role_strategy(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    """main() selects AssumeRoleStrategy when ROLE_ARN is set alongside access keys."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    monkeypatch.setenv("ROLE_ARN", "arn:aws:iam::123456789012:role/TestRole")
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO")
    mock_upgrade_cls = mocker.patch("aws_eks_helm_deploy.cli.UpgradeAction")
    mock_upgrade_cls.return_value.run.return_value = 0

    mock_bind = mocker.patch("aws_eks_helm_deploy.cli.bind_safe_context")

    from aws_eks_helm_deploy.cli import main

    result = main()

    assert result == 0
    mock_bind.assert_called_once_with(auth_strategy="AssumeRoleStrategy")


@pytest.mark.unit
def test_main_configuration_error_from_select_strategy_returns_1(
    mocker: MockerFixture,
) -> None:
    """main() returns 1 and calls pipe.fail() when select_strategy raises ConfigurationError."""
    mock_pipe = mocker.MagicMock()
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO", return_value=mock_pipe)
    mocker.patch(
        "aws_eks_helm_deploy.cli.select_strategy",
        side_effect=ConfigurationError("No valid credential configuration"),
    )

    from aws_eks_helm_deploy.cli import main

    result = main()

    assert result == 1
    mock_pipe.fail.assert_called_once_with("No valid credential configuration")


@pytest.mark.unit
def test_main_bind_safe_context_called_with_auth_strategy(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    """main() calls bind_safe_context(auth_strategy=<class name>) after strategy selection."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO")
    mock_upgrade_cls = mocker.patch("aws_eks_helm_deploy.cli.UpgradeAction")
    mock_upgrade_cls.return_value.run.return_value = 0

    mock_bind = mocker.patch("aws_eks_helm_deploy.cli.bind_safe_context")

    from aws_eks_helm_deploy.cli import main

    main()

    mock_bind.assert_called_once_with(auth_strategy="StaticKeysStrategy")


@pytest.mark.unit
def test_main_credentials_never_passed_to_bind_safe_context(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    """bind_safe_context is never called with credential keys — Phase 02-02 contract holds."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "some-token")
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO")
    mock_upgrade_cls = mocker.patch("aws_eks_helm_deploy.cli.UpgradeAction")
    mock_upgrade_cls.return_value.run.return_value = 0

    mock_bind = mocker.patch("aws_eks_helm_deploy.cli.bind_safe_context")

    from aws_eks_helm_deploy.cli import main

    main()

    credential_keys = {"aws_access_key_id", "aws_secret_access_key", "aws_session_token"}
    for call in mock_bind.call_args_list:
        bound_keys = set(call.kwargs.keys())
        assert not bound_keys & credential_keys, (
            f"Credential key(s) {bound_keys & credential_keys!r} passed to bind_safe_context"
        )


# ---------------------------------------------------------------------------
# Phase 5 DiffAction dispatch tests (Plan 05-03)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cli_dispatches_action_diff_to_diff_action(
    _fake_strategy: object, mocker: MockerFixture
) -> None:
    """main() routes ACTION=diff to DiffAction (not UpgradeAction)."""
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO")
    mock_diff_cls = mocker.patch("aws_eks_helm_deploy.cli.DiffAction")
    mock_diff_cls.return_value.run.return_value = 0
    mock_upgrade_cls = mocker.patch("aws_eks_helm_deploy.cli.UpgradeAction")

    from aws_eks_helm_deploy.cli import main

    with mocker.patch(
        "aws_eks_helm_deploy.cli.Settings",
        return_value=mocker.MagicMock(
            action="diff",
            dry_run=False,
            log_format="human",
            debug=False,
        ),
    ):
        result = main()

    assert result == 0
    mock_diff_cls.assert_called_once()
    mock_diff_cls.return_value.run.assert_called_once()
    mock_upgrade_cls.assert_not_called()


@pytest.mark.unit
def test_cli_dispatches_action_upgrade_with_dry_run_true_to_diff_action(
    _fake_strategy: object, mocker: MockerFixture
) -> None:
    """main() routes ACTION=upgrade + DRY_RUN=true to DiffAction (R7 routing)."""
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO")
    mock_diff_cls = mocker.patch("aws_eks_helm_deploy.cli.DiffAction")
    mock_diff_cls.return_value.run.return_value = 0
    mock_upgrade_cls = mocker.patch("aws_eks_helm_deploy.cli.UpgradeAction")

    from aws_eks_helm_deploy.cli import main

    with mocker.patch(
        "aws_eks_helm_deploy.cli.Settings",
        return_value=mocker.MagicMock(
            action="upgrade",
            dry_run=True,
            log_format="human",
            debug=False,
        ),
    ):
        result = main()

    assert result == 0
    mock_diff_cls.assert_called_once()
    mock_upgrade_cls.assert_not_called()


@pytest.mark.unit
def test_cli_dispatches_action_upgrade_with_dry_run_false_to_upgrade_action(
    _fake_strategy: object, mocker: MockerFixture
) -> None:
    """main() routes ACTION=upgrade + DRY_RUN=false to UpgradeAction (regression guard)."""
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO")
    mock_diff_cls = mocker.patch("aws_eks_helm_deploy.cli.DiffAction")
    mock_upgrade_cls = mocker.patch("aws_eks_helm_deploy.cli.UpgradeAction")
    mock_upgrade_cls.return_value.run.return_value = 0

    from aws_eks_helm_deploy.cli import main

    with mocker.patch(
        "aws_eks_helm_deploy.cli.Settings",
        return_value=mocker.MagicMock(
            action="upgrade",
            dry_run=False,
            log_format="human",
            debug=False,
        ),
    ):
        result = main()

    assert result == 0
    mock_upgrade_cls.assert_called_once()
    mock_diff_cls.assert_not_called()


@pytest.mark.unit
def test_cli_dispatches_action_upgrade_default_to_upgrade_action(
    _fake_strategy: object, mocker: MockerFixture
) -> None:
    """main() defaults to UpgradeAction when ACTION and DRY_RUN are unset (preserved)."""
    mock_pipe = mocker.MagicMock()
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO", return_value=mock_pipe)
    mock_upgrade_cls = mocker.patch("aws_eks_helm_deploy.cli.UpgradeAction")
    mock_upgrade_cls.return_value.run.return_value = 0

    from aws_eks_helm_deploy.cli import main

    # Default settings: action="upgrade", dry_run=False
    result = main()

    assert result == 0
    mock_upgrade_cls.assert_called_once()


# ---------------------------------------------------------------------------
# Phase 5 RollbackAction dispatch tests (Plan 05-05)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cli_dispatches_action_rollback_to_rollback_action(
    _fake_strategy: object, mocker: MockerFixture
) -> None:
    """main() routes ACTION=rollback to RollbackAction (not UpgradeAction or DiffAction)."""
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO")
    mock_rollback_cls = mocker.patch("aws_eks_helm_deploy.cli.RollbackAction")
    mock_rollback_cls.return_value.run.return_value = 0
    mock_diff_cls = mocker.patch("aws_eks_helm_deploy.cli.DiffAction")
    mock_upgrade_cls = mocker.patch("aws_eks_helm_deploy.cli.UpgradeAction")

    from aws_eks_helm_deploy.cli import main

    with mocker.patch(
        "aws_eks_helm_deploy.cli.Settings",
        return_value=mocker.MagicMock(
            action="rollback",
            dry_run=False,
            log_format="human",
            debug=False,
        ),
    ):
        result = main()

    assert result == 0
    mock_rollback_cls.assert_called_once()
    mock_rollback_cls.return_value.run.assert_called_once()
    mock_diff_cls.assert_not_called()
    mock_upgrade_cls.assert_not_called()


@pytest.mark.unit
def test_cli_action_rollback_with_dry_run_true_still_uses_rollback_action(
    _fake_strategy: object, mocker: MockerFixture
) -> None:
    """ACTION=rollback + DRY_RUN=true still routes to RollbackAction (R7 only affects upgrade)."""
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO")
    mock_rollback_cls = mocker.patch("aws_eks_helm_deploy.cli.RollbackAction")
    mock_rollback_cls.return_value.run.return_value = 0
    mock_diff_cls = mocker.patch("aws_eks_helm_deploy.cli.DiffAction")

    from aws_eks_helm_deploy.cli import main

    with mocker.patch(
        "aws_eks_helm_deploy.cli.Settings",
        return_value=mocker.MagicMock(
            action="rollback",
            dry_run=True,
            log_format="human",
            debug=False,
        ),
    ):
        result = main()

    assert result == 0
    mock_rollback_cls.assert_called_once()
    mock_diff_cls.assert_not_called()


# ---------------------------------------------------------------------------
# MIG-02: _warn_on_v1_env_vars startup scan (CONTEXT D4)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_warn_on_v1_env_vars_emits_warn_when_set_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_warn_on_v1_env_vars emits one WARN with name='SET' when SET env var is present."""
    monkeypatch.setenv("SET", "oldvalue")
    mock_log = MagicMock()

    _warn_on_v1_env_vars(mock_log)

    mock_log.warning.assert_called_once_with("mig.v1_env_var_detected", name="SET")


@pytest.mark.unit
def test_warn_on_v1_env_vars_emits_warn_when_values_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_warn_on_v1_env_vars emits one WARN with name='VALUES' when VALUES env var is present."""
    monkeypatch.setenv("VALUES", "values.yaml,extra.yaml")
    mock_log = MagicMock()

    _warn_on_v1_env_vars(mock_log)

    mock_log.warning.assert_called_once_with("mig.v1_env_var_detected", name="VALUES")


@pytest.mark.unit
def test_warn_on_v1_env_vars_emits_two_warns_when_both_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_warn_on_v1_env_vars emits two WARNs when both SET and VALUES are present."""
    monkeypatch.setenv("SET", "key1=val1")
    monkeypatch.setenv("VALUES", "values.yaml")
    mock_log = MagicMock()

    _warn_on_v1_env_vars(mock_log)

    assert mock_log.warning.call_count == 2
    calls = [call.kwargs["name"] for call in mock_log.warning.call_args_list]
    assert "SET" in calls
    assert "VALUES" in calls


@pytest.mark.unit
def test_warn_on_v1_env_vars_silent_when_neither_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_warn_on_v1_env_vars emits no WARNs when neither SET nor VALUES is in os.environ."""
    monkeypatch.delenv("SET", raising=False)
    monkeypatch.delenv("VALUES", raising=False)
    mock_log = MagicMock()

    _warn_on_v1_env_vars(mock_log)

    mock_log.warning.assert_not_called()


@pytest.mark.unit
def test_warn_on_v1_env_vars_silent_when_set_is_empty_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_warn_on_v1_env_vars treats empty-string SET as unset — no WARN emitted."""
    monkeypatch.setenv("SET", "")
    mock_log = MagicMock()

    _warn_on_v1_env_vars(mock_log)

    mock_log.warning.assert_not_called()


@pytest.mark.unit
def test_main_calls_warn_on_v1_env_vars_after_configure_logging_and_before_dispatch(
    _fake_strategy: object,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """main() emits mig.v1_env_var_detected WARN before auth strategy selected INFO.

    configure_logging() is mocked so it does not reconfigure the structlog pipeline
    (which would discard the capture_logs() processor installed by the test harness).
    """
    monkeypatch.setenv("SET", "key=value")
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO")
    mocker.patch("aws_eks_helm_deploy.cli.configure_logging")  # prevent pipeline clobber
    mock_upgrade_cls = mocker.patch("aws_eks_helm_deploy.cli.UpgradeAction")
    mock_upgrade_cls.return_value.run.return_value = 0

    from aws_eks_helm_deploy.cli import main

    with capture_logs() as logs:
        result = main()

    assert result == 0
    warn_events = [e for e in logs if e.get("event") == "mig.v1_env_var_detected"]
    assert len(warn_events) == 1
    assert warn_events[0]["name"] == "SET"
    assert warn_events[0]["log_level"] == "warning"
    # Verify WARN comes before the auth strategy info log
    auth_events = [e for e in logs if e.get("event") == "auth strategy selected"]
    warn_idx = logs.index(warn_events[0])
    auth_idx = logs.index(auth_events[0])
    assert warn_idx < auth_idx
