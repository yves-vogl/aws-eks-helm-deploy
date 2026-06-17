"""Unit tests for aws_eks_helm_deploy.errors.

Tests cover:
  - All seven exit codes in the PipeError hierarchy
  - user_message property
  - Custom exit_code constructor argument
  - EksTokenError (exit code 3, PipeError subclass)
"""

from __future__ import annotations

import pytest

from aws_eks_helm_deploy.errors import (
    AuthenticationError,
    ChartResolutionError,
    ClusterAccessError,
    ConfigurationError,
    EksTokenError,
    HelmError,
    HelmTimeoutError,
    KubeconfigError,
    PipeError,
)


@pytest.mark.unit
def test_pipe_error_exit_codes() -> None:
    """All seven exception classes carry the correct default exit codes."""
    assert PipeError("x").exit_code == 1
    assert ConfigurationError("x").exit_code == 1
    assert AuthenticationError("x").exit_code == 2
    assert ClusterAccessError("x").exit_code == 3
    assert ChartResolutionError("x").exit_code == 4
    assert HelmError("x").exit_code == 5
    assert HelmTimeoutError("x").exit_code == 6


@pytest.mark.unit
def test_pipe_error_user_message() -> None:
    """user_message property returns the string representation of the error."""
    e = ConfigurationError("CLUSTER_NAME is required")
    assert e.user_message == "CLUSTER_NAME is required"


@pytest.mark.unit
def test_pipe_error_custom_exit_code() -> None:
    """A custom exit_code passed to the constructor overrides the class default."""
    e = PipeError("custom error", exit_code=42)
    assert e.exit_code == 42


@pytest.mark.unit
def test_eks_token_error_exit_code() -> None:
    """EksTokenError carries exit code 3 and is a PipeError subclass."""
    assert EksTokenError("x").exit_code == 3
    assert isinstance(EksTokenError("x"), PipeError)


@pytest.mark.unit
def test_eks_token_error_custom_exit_code() -> None:
    """A custom exit_code passed to EksTokenError overrides the class default."""
    assert EksTokenError("x", exit_code=42).exit_code == 42


@pytest.mark.unit
def test_kubeconfig_error_exit_code() -> None:
    """KubeconfigError carries exit code 7 and is a PipeError subclass."""
    assert KubeconfigError("x").exit_code == 7
    assert isinstance(KubeconfigError("x"), PipeError)


@pytest.mark.unit
def test_kubeconfig_error_custom_exit_code() -> None:
    """A custom exit_code passed to KubeconfigError overrides the class default."""
    assert KubeconfigError("x", exit_code=42).exit_code == 42
