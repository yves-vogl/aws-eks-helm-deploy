"""Unit tests for aws_eks_helm_deploy.actions.rollback (RollbackAction).

Requirements traceability:
    PIPE-04:  RollbackAction.run orchestrates ACTION=rollback with pre-flight check
    PIPE-05:  Pre-flight uses SAFE_UPGRADE_DESCRIPTION to detect safe-upgraded revisions
"""

from __future__ import annotations

import pathlib
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from aws_eks_helm_deploy.errors import (
    ChartResolutionError,
    ConfigurationError,
    HelmExecutionError,
)
from aws_eks_helm_deploy.helm.client import HelmRevision
from aws_eks_helm_deploy.settings import Settings

# ---------------------------------------------------------------------------
# Helpers + fixtures
# ---------------------------------------------------------------------------


def _make_settings(**overrides: Any) -> Settings:
    """Construct Settings with all required fields pre-set for rollback."""
    defaults: dict[str, Any] = dict(
        action="rollback",
        aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
        aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        aws_region="eu-central-1",
        cluster_name="test-cluster",
        release_name="test-release",
        namespace="default",
        revision=1,
    )
    return Settings(**(defaults | overrides))


def _revisions_with_marker() -> list[HelmRevision]:
    """Return a history list where revision 1 and 2 both have the safe-upgrade marker."""
    return [
        HelmRevision(
            revision=1,
            status="superseded",
            chart="x-0.1.0",
            description="Install complete pipe:safe-upgrade",
        ),
        HelmRevision(
            revision=2,
            status="deployed",
            chart="x-0.1.0",
            description="Upgrade complete pipe:safe-upgrade",
        ),
    ]


def _revisions_without_marker() -> list[HelmRevision]:
    """Return a history list where revision 1 was NOT deployed with SAFE_UPGRADE."""
    return [
        HelmRevision(
            revision=1,
            status="superseded",
            chart="x-0.1.0",
            description="Install complete",
        ),
        HelmRevision(
            revision=2,
            status="deployed",
            chart="x-0.1.0",
            description="Upgrade complete",
        ),
    ]


@contextmanager  # type: ignore[arg-type]
def _kubeconfig_ctx(*_args: Any, **_kwargs: Any):  # type: ignore[no-untyped-def]
    """Fake write_kubeconfig context manager yielding a test Path."""
    yield pathlib.Path("/tmp/test-kubeconfig.yaml")


def _patch_all_happy(
    mocker: MockerFixture, history: list[HelmRevision] | None = None
) -> dict[str, MagicMock]:
    """Patch all external dependencies for happy-path rollback tests."""
    if history is None:
        history = _revisions_with_marker()

    fake_strategy = mocker.MagicMock()
    fake_strategy.get_credentials.return_value = mocker.MagicMock(
        to_boto3_kwargs=mocker.MagicMock(return_value={})
    )

    mocks = {
        "select_strategy": mocker.patch(
            "aws_eks_helm_deploy.actions.rollback.select_strategy",
            return_value=fake_strategy,
        ),
        "boto3_session": mocker.patch(
            "aws_eks_helm_deploy.actions.rollback.boto3.session.Session",
            return_value=mocker.MagicMock(),
        ),
        "get_cluster_access": mocker.patch(
            "aws_eks_helm_deploy.actions.rollback.get_cluster_access",
            return_value=MagicMock(name="test-cluster"),
        ),
        "generate_eks_token": mocker.patch(
            "aws_eks_helm_deploy.actions.rollback.generate_eks_token",
            return_value="k8s-aws-v1.test-token",
        ),
        "write_kubeconfig": mocker.patch(
            "aws_eks_helm_deploy.actions.rollback.write_kubeconfig",
            side_effect=_kubeconfig_ctx,
        ),
        "helm_client_cls": mocker.patch(
            "aws_eks_helm_deploy.actions.rollback.HelmClient",
        ),
    }
    mocks["helm_client_cls"].return_value.history.return_value = history
    mocks["helm_client_cls"].return_value.rollback.return_value = None
    mocks["strategy"] = fake_strategy
    return mocks


# ---------------------------------------------------------------------------
# Required-field guard tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_rollback_action_requires_cluster_name(mocker: MockerFixture) -> None:
    """RollbackAction.run raises ConfigurationError when CLUSTER_NAME is missing."""
    from aws_eks_helm_deploy.actions.rollback import RollbackAction

    mock_pipe = mocker.MagicMock()
    settings = _make_settings(cluster_name=None)
    action = RollbackAction(settings)

    with pytest.raises(ConfigurationError) as exc_info:
        action.run(mock_pipe)

    assert exc_info.value.exit_code == 1
    assert "CLUSTER_NAME" in str(exc_info.value)


@pytest.mark.unit
def test_rollback_action_requires_release_name(mocker: MockerFixture) -> None:
    """RollbackAction.run raises ConfigurationError when RELEASE_NAME is missing."""
    from aws_eks_helm_deploy.actions.rollback import RollbackAction

    mock_pipe = mocker.MagicMock()
    settings = _make_settings(release_name=None)
    action = RollbackAction(settings)

    with pytest.raises(ConfigurationError) as exc_info:
        action.run(mock_pipe)

    assert exc_info.value.exit_code == 1
    assert "RELEASE_NAME" in str(exc_info.value)


@pytest.mark.unit
def test_rollback_action_requires_revision(mocker: MockerFixture) -> None:
    """RollbackAction.run raises ConfigurationError when REVISION is None (not set)."""
    from aws_eks_helm_deploy.actions.rollback import RollbackAction

    mock_pipe = mocker.MagicMock()
    settings = _make_settings(revision=None)
    action = RollbackAction(settings)

    with pytest.raises(ConfigurationError) as exc_info:
        action.run(mock_pipe)

    assert exc_info.value.exit_code == 1
    assert "REVISION" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Pre-flight check tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_rollback_action_preflight_passes_when_target_revision_has_safe_marker(
    mocker: MockerFixture,
) -> None:
    """Pre-flight passes when target revision description contains pipe:safe-upgrade."""
    from aws_eks_helm_deploy.actions.rollback import RollbackAction

    mocks = _patch_all_happy(mocker, history=_revisions_with_marker())
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(revision=1)
    action = RollbackAction(settings)

    result = action.run(mock_pipe)

    assert result == 0
    mocks["helm_client_cls"].return_value.rollback.assert_called_once_with(
        release="test-release", revision=1, namespace="default", timeout="600s"
    )


@pytest.mark.unit
def test_rollback_action_preflight_raises_when_target_revision_lacks_safe_marker(
    mocker: MockerFixture,
) -> None:
    """Pre-flight raises ChartResolutionError when target revision lacks pipe:safe-upgrade."""
    from aws_eks_helm_deploy.actions.rollback import RollbackAction

    mocks = _patch_all_happy(mocker, history=_revisions_without_marker())
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(revision=1)
    action = RollbackAction(settings)

    with pytest.raises(ChartResolutionError) as exc_info:
        action.run(mock_pipe)

    assert exc_info.value.exit_code == 4
    # Error message must name SAFE_UPGRADE=true as the remedy (consumer-facing UX)
    assert "SAFE_UPGRADE=true" in str(exc_info.value)
    # helm rollback must NOT have been called
    mocks["helm_client_cls"].return_value.rollback.assert_not_called()


@pytest.mark.unit
def test_rollback_action_preflight_raises_when_revision_not_in_history(
    mocker: MockerFixture,
) -> None:
    """Pre-flight raises ChartResolutionError when REVISION=99 not found in history."""
    from aws_eks_helm_deploy.actions.rollback import RollbackAction

    mocks = _patch_all_happy(mocker, history=_revisions_with_marker())
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(revision=99)
    action = RollbackAction(settings)

    with pytest.raises(ChartResolutionError) as exc_info:
        action.run(mock_pipe)

    error_msg = str(exc_info.value)
    assert "99" in error_msg
    # Message should list the available revisions
    assert "1" in error_msg
    assert "2" in error_msg
    mocks["helm_client_cls"].return_value.rollback.assert_not_called()


# ---------------------------------------------------------------------------
# Error propagation tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_rollback_action_propagates_helm_execution_error(
    mocker: MockerFixture,
) -> None:
    """HelmExecutionError from client.rollback() propagates through run()."""
    from aws_eks_helm_deploy.actions.rollback import RollbackAction

    mocks = _patch_all_happy(mocker, history=_revisions_with_marker())
    mocks["helm_client_cls"].return_value.rollback.side_effect = HelmExecutionError(
        "helm rollback returned 1"
    )
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(revision=1)
    action = RollbackAction(settings)

    with pytest.raises(HelmExecutionError):
        action.run(mock_pipe)


# ---------------------------------------------------------------------------
# Design invariant: no chart resolution in rollback
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_rollback_action_kubeconfig_override_skips_cluster_and_token(
    mocker: MockerFixture,
) -> None:
    """kubeconfig_override kwarg skips steps 4+5 (cluster_access, token, write_kubeconfig)."""
    from aws_eks_helm_deploy.actions.rollback import RollbackAction

    mocks = _patch_all_happy(mocker, history=_revisions_with_marker())
    override_path = pathlib.Path("/tmp/kind-kubeconfig.yaml")
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(revision=1)
    action = RollbackAction(settings, kubeconfig_override=override_path)

    result = action.run(mock_pipe)

    assert result == 0
    mocks["get_cluster_access"].assert_not_called()
    mocks["generate_eks_token"].assert_not_called()
    mocks["write_kubeconfig"].assert_not_called()
    # HelmClient should be instantiated with the override path
    mocks["helm_client_cls"].assert_called_once_with(override_path)


@pytest.mark.unit
def test_rollback_action_wraps_oserror_as_kubeconfig_error(
    mocker: MockerFixture,
) -> None:
    """OSError from write_kubeconfig raises KubeconfigError(exit_code=7)."""
    from contextlib import contextmanager

    from aws_eks_helm_deploy.actions.rollback import RollbackAction
    from aws_eks_helm_deploy.errors import KubeconfigError

    _patch_all_happy(mocker, history=_revisions_with_marker())

    @contextmanager  # type: ignore[arg-type]
    def _raising_ctx(*_args: Any, **_kwargs: Any):  # type: ignore[no-untyped-def]
        raise OSError("disk full")
        yield  # pragma: no cover

    mocker.patch(
        "aws_eks_helm_deploy.actions.rollback.write_kubeconfig",
        side_effect=_raising_ctx,
    )
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(revision=1)
    action = RollbackAction(settings)

    with pytest.raises(KubeconfigError) as exc_info:
        action.run(mock_pipe)

    assert exc_info.value.exit_code == 7
    assert isinstance(exc_info.value.__cause__, OSError)
    assert "disk full" in str(exc_info.value.__cause__)


@pytest.mark.unit
def test_rollback_action_does_not_call_select_chart_source(
    mocker: MockerFixture,
) -> None:
    """RollbackAction.run never calls select_chart_source (rollback is cluster-native).

    Patches select_chart_source at the chart module level and verifies it is never called.
    rollback.py intentionally does NOT import select_chart_source — this test guards
    against future accidental imports.
    """
    from aws_eks_helm_deploy.actions.rollback import RollbackAction

    _patch_all_happy(mocker, history=_revisions_with_marker())
    # Patch at the chart module source so any accidental import would be intercepted
    mock_select_chart = mocker.patch(
        "aws_eks_helm_deploy.chart.select_chart_source",
        side_effect=AssertionError("select_chart_source must NOT be called in rollback"),
    )
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(revision=1)
    action = RollbackAction(settings)

    # Should succeed without hitting select_chart_source
    result = action.run(mock_pipe)

    assert result == 0
    mock_select_chart.assert_not_called()
