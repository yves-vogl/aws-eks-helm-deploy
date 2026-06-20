"""Unit tests for aws_eks_helm_deploy.actions.diff (DiffAction).

Requirements traceability:
    PIPE-02:  DiffAction.run invokes HelmClient.diff (read-only, no cluster mutation)
    SEC-06:   diff output flows through HelmClient.diff's redactor; DiffAction emits
              only the redacted return value (T-05-01 per-task gate)
    META-01:  inject_bitbucket_metadata opt-in guard carried forward from UpgradeAction
"""

from __future__ import annotations

import contextlib
import pathlib
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from aws_eks_helm_deploy.actions.diff import DiffAction
from aws_eks_helm_deploy.chart import ChartSource
from aws_eks_helm_deploy.chart.base import ResolvedChart
from aws_eks_helm_deploy.eks.cluster import ClusterAccess
from aws_eks_helm_deploy.errors import ConfigurationError, HelmExecutionError
from aws_eks_helm_deploy.settings import Settings

# ---------------------------------------------------------------------------
# Helpers + fixtures
# ---------------------------------------------------------------------------


def _make_settings(**overrides: Any) -> Settings:
    """Construct Settings with all required fields pre-set."""
    defaults: dict[str, Any] = dict(
        action="diff",
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


def _make_fake_source(resolved: ResolvedChart) -> Any:
    """Build a fake ChartSource whose .resolve() yields the given ResolvedChart."""
    return MagicMock(spec=ChartSource, resolve=lambda: contextlib.nullcontext(resolved))


def _cluster_access() -> ClusterAccess:
    return ClusterAccess(
        name="test-cluster",
        endpoint="https://test-cluster.example.com",
        ca_data="dGVzdA==",
        region="eu-central-1",
    )


@contextmanager  # type: ignore[arg-type]
def _kubeconfig_ctx(*_args: Any, **_kwargs: Any):  # type: ignore[no-untyped-def]
    """Fake write_kubeconfig context manager yielding a test Path."""
    yield pathlib.Path("/tmp/test-kubeconfig.yaml")


def _patch_all_happy(mocker: MockerFixture) -> dict[str, MagicMock]:
    """Patch all external dependencies for happy-path tests. Returns mocks dict."""
    fake_strategy = mocker.MagicMock()
    fake_strategy.get_credentials.return_value = mocker.MagicMock(
        to_boto3_kwargs=mocker.MagicMock(return_value={})
    )

    mocks = {
        "select_strategy": mocker.patch(
            "aws_eks_helm_deploy.actions.diff.select_strategy",
            return_value=fake_strategy,
        ),
        "boto3_session": mocker.patch(
            "aws_eks_helm_deploy.actions.diff.boto3.session.Session",
            return_value=mocker.MagicMock(),
        ),
        "get_cluster_access": mocker.patch(
            "aws_eks_helm_deploy.actions.diff.get_cluster_access",
            return_value=_cluster_access(),
        ),
        "generate_eks_token": mocker.patch(
            "aws_eks_helm_deploy.actions.diff.generate_eks_token",
            return_value="k8s-aws-v1.test-token",
        ),
        "write_kubeconfig": mocker.patch(
            "aws_eks_helm_deploy.actions.diff.write_kubeconfig",
            side_effect=_kubeconfig_ctx,
        ),
        "select_chart_source": mocker.patch(
            "aws_eks_helm_deploy.actions.diff.select_chart_source",
            return_value=_make_fake_source(_resolved_chart()),
        ),
        "helm_client_cls": mocker.patch(
            "aws_eks_helm_deploy.actions.diff.HelmClient",
        ),
    }
    mocks["helm_client_cls"].return_value.diff.return_value = "--- a\n+++ b\n"
    mocks["strategy"] = fake_strategy
    return mocks


# ---------------------------------------------------------------------------
# Required-field defensive checks
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_diff_action_requires_cluster_name(mocker: MockerFixture) -> None:
    """run() raises ConfigurationError before any AWS call when cluster_name is None."""
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(cluster_name=None)
    action = DiffAction(settings, strategy=mocker.MagicMock())

    with pytest.raises(ConfigurationError) as exc_info:
        action.run(mock_pipe)

    assert exc_info.value.exit_code == 1
    assert "CLUSTER_NAME" in str(exc_info.value)


@pytest.mark.unit
def test_diff_action_requires_chart(mocker: MockerFixture) -> None:
    """run() raises ConfigurationError before any AWS call when chart is None."""
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(chart=None)
    action = DiffAction(settings, strategy=mocker.MagicMock())

    with pytest.raises(ConfigurationError) as exc_info:
        action.run(mock_pipe)

    assert exc_info.value.exit_code == 1
    assert "CHART" in str(exc_info.value)


@pytest.mark.unit
def test_diff_action_requires_release_name(mocker: MockerFixture) -> None:
    """run() raises ConfigurationError before any AWS call when release_name is None."""
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(release_name=None)
    action = DiffAction(settings, strategy=mocker.MagicMock())

    with pytest.raises(ConfigurationError) as exc_info:
        action.run(mock_pipe)

    assert exc_info.value.exit_code == 1
    assert "RELEASE_NAME" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_diff_action_happy_path_calls_helm_client_diff(mocker: MockerFixture) -> None:
    """run() calls HelmClient.diff exactly once with the correct kwargs."""
    mocks = _patch_all_happy(mocker)
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(
        namespace="prod",
        timeout="300s",
        values_files=["base.yaml"],
        set_values=["key=val"],
    )
    action = DiffAction(settings, kubeconfig_override=pathlib.Path("/tmp/test-kubeconfig.yaml"))
    mocks["select_chart_source"].return_value = _make_fake_source(_resolved_chart())

    result = action.run(mock_pipe)

    assert result == 0
    mocks["helm_client_cls"].return_value.diff.assert_called_once_with(
        release=settings.release_name,
        chart=_resolved_chart(),
        namespace="prod",
        values_files=["base.yaml"],
        set_args=settings.set_values,
        timeout="300s",
    )


@pytest.mark.unit
def test_diff_action_returns_zero_on_success(mocker: MockerFixture) -> None:
    """DiffAction.run returns 0 on success."""
    _patch_all_happy(mocker)
    mock_pipe = mocker.MagicMock()
    action = DiffAction(
        _make_settings(), kubeconfig_override=pathlib.Path("/tmp/test-kubeconfig.yaml")
    )

    result = action.run(mock_pipe)

    assert result == 0


@pytest.mark.unit
def test_diff_action_writes_redacted_diff_to_pipe(mocker: MockerFixture) -> None:
    """run() emits the redacted diff text via pipe.success."""
    mocks = _patch_all_happy(mocker)
    diff_output = "+++ added\n--- removed\n"
    mocks["helm_client_cls"].return_value.diff.return_value = diff_output
    mock_pipe = mocker.MagicMock()
    action = DiffAction(
        _make_settings(), kubeconfig_override=pathlib.Path("/tmp/test-kubeconfig.yaml")
    )

    action.run(mock_pipe)

    # pipe.success must have been called with a message containing the diff text
    call_args = mock_pipe.success.call_args
    assert call_args is not None
    message = call_args.args[0]
    assert diff_output in message


@pytest.mark.unit
def test_diff_action_propagates_helm_execution_error(mocker: MockerFixture) -> None:
    """HelmExecutionError from HelmClient.diff bubbles up to the caller (cli.py handles it)."""
    mocks = _patch_all_happy(mocker)
    mocks["helm_client_cls"].return_value.diff.side_effect = HelmExecutionError("helm failed")
    mock_pipe = mocker.MagicMock()
    action = DiffAction(
        _make_settings(), kubeconfig_override=pathlib.Path("/tmp/test-kubeconfig.yaml")
    )

    with pytest.raises(HelmExecutionError):
        action.run(mock_pipe)


@pytest.mark.unit
def test_diff_action_skips_bitbucket_metadata_when_inject_metadata_is_none(
    mocker: MockerFixture,
) -> None:
    """When inject_bitbucket_metadata is None, no bitbucket.* entries in set_args to HelmClient.

    META-02 default behaviour preview — None means do not inject.
    """
    mocks = _patch_all_happy(mocker)
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(inject_bitbucket_metadata=None)
    action = DiffAction(settings, kubeconfig_override=pathlib.Path("/tmp/test-kubeconfig.yaml"))

    action.run(mock_pipe)

    call_kwargs = mocks["helm_client_cls"].return_value.diff.call_args.kwargs
    set_args_passed = call_kwargs["set_args"]
    assert not any("bitbucket." in sa for sa in set_args_passed), (
        f"Expected no bitbucket.* in set_args but got: {set_args_passed}"
    )


@pytest.mark.unit
def test_diff_action_skips_bitbucket_metadata_when_inject_metadata_is_false(
    mocker: MockerFixture,
) -> None:
    """When inject_bitbucket_metadata is False, no bitbucket.* entries in set_args."""
    mocks = _patch_all_happy(mocker)
    mock_pipe = mocker.MagicMock()
    settings = _make_settings(inject_bitbucket_metadata=False)
    action = DiffAction(settings, kubeconfig_override=pathlib.Path("/tmp/test-kubeconfig.yaml"))

    action.run(mock_pipe)

    call_kwargs = mocks["helm_client_cls"].return_value.diff.call_args.kwargs
    set_args_passed = call_kwargs["set_args"]
    assert not any("bitbucket." in sa for sa in set_args_passed)


# ---------------------------------------------------------------------------
# Full EKS path tests (no kubeconfig_override — exercises lines 99-141)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_diff_action_full_eks_path_calls_helm_client_diff(mocker: MockerFixture) -> None:
    """run() without kubeconfig_override exercises EKS + kubeconfig write path."""
    mocks = _patch_all_happy(mocker)
    mock_pipe = mocker.MagicMock()
    settings = _make_settings()
    action = DiffAction(settings)  # no kubeconfig_override

    result = action.run(mock_pipe)

    assert result == 0
    mocks["get_cluster_access"].assert_called_once()
    mocks["generate_eks_token"].assert_called_once()
    mocks["write_kubeconfig"].assert_called_once()
    mocks["helm_client_cls"].return_value.diff.assert_called_once()


@pytest.mark.unit
def test_diff_action_full_eks_path_wraps_os_error_as_kubeconfig_error(
    mocker: MockerFixture,
) -> None:
    """OSError from write_kubeconfig is wrapped as KubeconfigError."""
    from aws_eks_helm_deploy.errors import KubeconfigError

    _patch_all_happy(mocker)
    mocker.patch(
        "aws_eks_helm_deploy.actions.diff.write_kubeconfig",
        side_effect=OSError("permission denied"),
    )
    mock_pipe = mocker.MagicMock()
    settings = _make_settings()
    action = DiffAction(settings)  # no kubeconfig_override

    with pytest.raises(KubeconfigError) as exc_info:
        action.run(mock_pipe)

    assert "permission denied" in str(exc_info.value)
