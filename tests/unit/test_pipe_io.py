"""Unit tests for aws_eks_helm_deploy.pipe_io.

Tests cover:
  - success() delegates to the bitbucket-pipes-toolkit Pipe success channel
  - fail() delegates to the bitbucket-pipes-toolkit Pipe fail channel
  - Pipe instance is lazily constructed on first call

The bitbucket_pipes_toolkit.Pipe constructor is patched via pytest-mock to
avoid any real toolkit I/O or filesystem access.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pytest_mock import MockerFixture

from aws_eks_helm_deploy.pipe_io import PipeIO


@pytest.mark.unit
def test_success_delegates_to_toolkit(mocker: MockerFixture) -> None:
    """PipeIO.success() calls the toolkit Pipe.success() with the correct message."""
    mock_pipe_instance = MagicMock()
    mocker.patch(
        "aws_eks_helm_deploy.pipe_io.Pipe",
        return_value=mock_pipe_instance,
    )

    pio = PipeIO()
    pio.success("deploy succeeded")

    mock_pipe_instance.success.assert_called_once_with(message="deploy succeeded")


@pytest.mark.unit
def test_fail_delegates_to_toolkit(mocker: MockerFixture) -> None:
    """PipeIO.fail() calls the toolkit Pipe.fail() with the correct message."""
    mock_pipe_instance = MagicMock()
    mocker.patch(
        "aws_eks_helm_deploy.pipe_io.Pipe",
        return_value=mock_pipe_instance,
    )

    pio = PipeIO()
    pio.fail("CLUSTER_NAME is required")

    mock_pipe_instance.fail.assert_called_once_with(message="CLUSTER_NAME is required")


@pytest.mark.unit
def test_pipe_lazy_init() -> None:
    """Pipe is only instantiated on first call, not at PipeIO.__init__."""
    with patch("aws_eks_helm_deploy.pipe_io.Pipe") as mock_pipe_cls:
        mock_pipe_cls.return_value = MagicMock()
        pio = PipeIO()
        mock_pipe_cls.assert_not_called()  # not yet constructed

        pio.success("hello")
        mock_pipe_cls.assert_called_once()  # constructed on first use

        pio.fail("bye")
        mock_pipe_cls.assert_called_once()  # not constructed again
