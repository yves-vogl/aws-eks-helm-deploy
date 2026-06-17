"""Unit tests for aws_eks_helm_deploy.cli.

Tests cover:
  - main() returns 0 on the Phase 1 placeholder success path
  - main() catches PipeError and returns exc.exit_code; calls pipe.fail()
  - main() catches bare Exception and returns 99; calls pipe.fail()
  - __main__ module is runnable via runpy.run_module (SystemExit.code is int)
"""

from __future__ import annotations

import runpy

import pytest
from pytest_mock import MockerFixture

from aws_eks_helm_deploy.errors import ConfigurationError
from aws_eks_helm_deploy.settings import Settings


@pytest.mark.unit
def test_main_placeholder_success(mocker: MockerFixture) -> None:
    """main() returns 0 on the Phase 1 placeholder success path."""
    mock_pipe = mocker.MagicMock()
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO", return_value=mock_pipe)

    from aws_eks_helm_deploy.cli import main

    result = main()

    assert result == 0
    mock_pipe.success.assert_called_once_with("Phase 1 skeleton — no action executed")


@pytest.mark.unit
def test_main_catches_pipe_error(mocker: MockerFixture) -> None:
    """main() catches PipeError, calls pipe.fail(), and returns exc.exit_code."""
    mock_pipe = mocker.MagicMock()
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO", return_value=mock_pipe)
    # Make pipe.success raise ConfigurationError to exercise the except branch
    mock_pipe.success.side_effect = ConfigurationError("CLUSTER_NAME is required")

    from aws_eks_helm_deploy.cli import main

    result = main()

    assert result == 1
    mock_pipe.fail.assert_called_once_with("CLUSTER_NAME is required")


@pytest.mark.unit
def test_main_catches_bare_exception(mocker: MockerFixture) -> None:
    """main() catches bare Exception, calls pipe.fail(), and returns 99."""
    mock_pipe = mocker.MagicMock()
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO", return_value=mock_pipe)
    mock_pipe.success.side_effect = RuntimeError("something unexpected")

    from aws_eks_helm_deploy.cli import main

    result = main()

    assert result == 99
    mock_pipe.fail.assert_called_once_with("Unexpected error — see logs")


@pytest.mark.unit
def test_main_module_runs(mocker: MockerFixture) -> None:
    """python -m aws_eks_helm_deploy runs main() and exits with an integer code."""
    mock_pipe = mocker.MagicMock()
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO", return_value=mock_pipe)
    mocker.patch("aws_eks_helm_deploy.cli.configure_logging")

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("aws_eks_helm_deploy", run_name="__main__", alter_sys=True)

    assert isinstance(exc_info.value.code, int)
    assert exc_info.value.code == 0


@pytest.mark.unit
def test_main_calls_configure_logging(mocker: MockerFixture) -> None:
    """main() calls configure_logging(settings) exactly once after Settings()."""
    mock_cfg = mocker.patch("aws_eks_helm_deploy.cli.configure_logging")
    mocker.patch("aws_eks_helm_deploy.cli.PipeIO")

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
