"""Unit tests for AssumeRoleStrategy.

Requirements traceability:
  - AUTH-02: AssumeRoleStrategy wraps any base AuthStrategy, calls STS AssumeRole
    against the regional endpoint, and returns AwsCredentials with session_token
    and expiration. Maps ClientError -> AuthenticationError, NoCredentialsError ->
    ConfigurationError.

Mocking strategy (per 02-PLAN-CHECK Warning 3):
  - Pattern 1 (no @mock_aws): patch boto3.session.Session.client directly to capture
    endpoint_url kwarg and to inject errors. Used for:
    test_assume_role_uses_regional_sts_endpoint,
    test_assume_role_uses_supplied_region_in_endpoint,
    test_assume_role_client_error_raises_authentication_error,
    test_assume_role_no_credentials_error_raises_configuration_error.
  - Pattern 2 (@mock_aws + mocker.patch.object spy): moto provides the STS backend;
    spy on sts.assume_role to assert call kwargs. Used for:
    test_assume_role_passes_role_arn_and_session_name,
    test_assume_role_does_not_pass_duration_seconds,
    test_assume_role_does_not_pass_external_id.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import boto3
import boto3.session
import botocore.exceptions
import pytest
from moto import mock_aws

from aws_eks_helm_deploy.auth.assume_role import AssumeRoleStrategy
from aws_eks_helm_deploy.auth.base import AuthStrategy, AwsCredentials
from aws_eks_helm_deploy.auth.static_keys import StaticKeysStrategy
from aws_eks_helm_deploy.errors import AuthenticationError, ConfigurationError

# Synthetic credential constants — not real AWS values
_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"  # noqa: S105 — AWS docs example
_SESSION_TOKEN = "test-session-token"  # noqa: S105 — synthetic value
_ROLE_ARN = "arn:aws:iam::123456789012:role/TestRole"
_SESSION_NAME = "test-session"
_REGION = "eu-central-1"

# Synthetic STS AssumeRole response for Pattern 1 tests
_SYNTHETIC_STS_RESPONSE: dict[str, object] = {
    "Credentials": {
        "AccessKeyId": "ASIA-FAKE-ACCESS-KEY",
        "SecretAccessKey": "fake-secret-key",
        "SessionToken": "fake-session-token",
        "Expiration": datetime(2026, 6, 17, 12, 0, 0),
    },
    "AssumedRoleUser": {
        "AssumedRoleId": "AROA123:test-session",
        "Arn": "arn:aws:sts::123456789012:assumed-role/TestRole/test-session",
    },
    "ResponseMetadata": {"RequestId": "fake-request-id", "HTTPStatusCode": 200},
}


def _make_strategy(
    region: str = _REGION,
    role_arn: str = _ROLE_ARN,
    session_name: str = _SESSION_NAME,
    session_token: str | None = None,
) -> AssumeRoleStrategy:
    """Build an AssumeRoleStrategy backed by a StaticKeysStrategy."""
    base = StaticKeysStrategy(_ACCESS_KEY, _SECRET_KEY, session_token=session_token)
    return AssumeRoleStrategy(base, role_arn, session_name, region)


# ---------------------------------------------------------------------------
# Pattern 1 tests — patch Session.client (no @mock_aws)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_assume_role_uses_regional_sts_endpoint(
    mocker: pytest.fixture,  # type: ignore[type-arg]
) -> None:
    """STS client is constructed with the regional endpoint_url, not the global one.

    Pattern 1: patch boto3.session.Session.client to capture kwargs; inject a
    synthetic MagicMock STS client. Do NOT combine with @mock_aws.
    """
    mock_sts = MagicMock()
    mock_sts.assume_role.return_value = _SYNTHETIC_STS_RESPONSE
    mock_client = mocker.patch.object(boto3.session.Session, "client", return_value=mock_sts)

    _make_strategy(region=_REGION).get_credentials()

    mock_client.assert_called_once()
    _, kwargs = mock_client.call_args
    assert kwargs["endpoint_url"] == f"https://sts.{_REGION}.amazonaws.com"


@pytest.mark.unit
def test_assume_role_uses_supplied_region_in_endpoint(
    mocker: pytest.fixture,  # type: ignore[type-arg]
) -> None:
    """endpoint_url contains the constructor-supplied region (not hardcoded).

    Pattern 1: same approach with a different region to prove the string is dynamic.
    """
    region = "us-west-2"
    mock_sts = MagicMock()
    mock_sts.assume_role.return_value = _SYNTHETIC_STS_RESPONSE
    mock_client = mocker.patch.object(boto3.session.Session, "client", return_value=mock_sts)

    _make_strategy(region=region).get_credentials()

    _, kwargs = mock_client.call_args
    assert "us-west-2" in kwargs["endpoint_url"]


@pytest.mark.unit
def test_assume_role_client_error_raises_authentication_error(
    mocker: pytest.fixture,  # type: ignore[type-arg]
) -> None:
    """ClientError from assume_role is caught and re-raised as AuthenticationError (exit 2).

    Pattern 1: inject ClientError via MagicMock so the error path is exercised without
    a real STS call. The Code appears in the AuthenticationError message.
    """
    mock_sts = MagicMock()
    mock_sts.assume_role.side_effect = botocore.exceptions.ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "No trust relationship"}},
        "AssumeRole",
    )
    mocker.patch.object(boto3.session.Session, "client", return_value=mock_sts)

    with pytest.raises(AuthenticationError) as exc_info:
        _make_strategy().get_credentials()

    assert exc_info.value.exit_code == 2
    assert "AccessDenied" in str(exc_info.value)


@pytest.mark.unit
def test_assume_role_no_credentials_error_raises_configuration_error(
    mocker: pytest.fixture,  # type: ignore[type-arg]
) -> None:
    """NoCredentialsError from assume_role is re-raised as ConfigurationError (exit 1)."""
    mock_sts = MagicMock()
    mock_sts.assume_role.side_effect = botocore.exceptions.NoCredentialsError()
    mocker.patch.object(boto3.session.Session, "client", return_value=mock_sts)

    with pytest.raises(ConfigurationError) as exc_info:
        _make_strategy().get_credentials()

    assert exc_info.value.exit_code == 1


# ---------------------------------------------------------------------------
# Pattern 2 tests — @mock_aws + mocker.patch.object / spy
# ---------------------------------------------------------------------------


@pytest.mark.unit
@mock_aws
def test_assume_role_happy_path() -> None:
    """Under @mock_aws, get_credentials() returns AwsCredentials with session_token set."""
    creds = _make_strategy().get_credentials()
    assert creds.session_token is not None
    assert creds.expiration is not None


@pytest.mark.unit
@mock_aws
def test_assume_role_delegates_to_base(mocker: pytest.fixture) -> None:  # type: ignore[type-arg]
    """get_credentials() calls the base strategy's get_credentials exactly once."""
    mock_base = MagicMock(spec=AuthStrategy)
    mock_base.get_credentials.return_value = AwsCredentials(
        access_key_id=_ACCESS_KEY,
        secret_access_key=_SECRET_KEY,
    )
    strategy = AssumeRoleStrategy(mock_base, _ROLE_ARN, _SESSION_NAME, _REGION)
    strategy.get_credentials()
    mock_base.get_credentials.assert_called_once()


@pytest.mark.unit
@mock_aws
def test_assume_role_passes_role_arn_and_session_name(
    mocker: pytest.fixture,  # type: ignore[type-arg]
) -> None:
    """assume_role is called with the exact role_arn and session_name from the constructor.

    Pattern 2: @mock_aws provides the STS backend; we spy on the sts client's
    assume_role to capture call kwargs while moto returns a real synthetic response.
    """
    strategy = _make_strategy(role_arn=_ROLE_ARN, session_name=_SESSION_NAME)
    captured: dict[str, object] = {}

    original_session_client = boto3.session.Session.client

    def spy_session_client(self: boto3.session.Session, service: str, **kwargs: object) -> object:
        client = original_session_client(self, service, **kwargs)
        if service == "sts":
            original_assume = client.assume_role

            def spy_assume_role(**ar_kwargs: object) -> object:
                captured.update(ar_kwargs)
                return original_assume(**ar_kwargs)

            client.assume_role = spy_assume_role  # type: ignore[method-assign]
        return client

    mocker.patch.object(boto3.session.Session, "client", spy_session_client)
    strategy.get_credentials()

    assert captured.get("RoleArn") == _ROLE_ARN
    assert captured.get("RoleSessionName") == _SESSION_NAME


@pytest.mark.unit
@mock_aws
def test_assume_role_does_not_pass_duration_seconds(
    mocker: pytest.fixture,  # type: ignore[type-arg]
) -> None:
    """assume_role is called WITHOUT DurationSeconds — accepts AWS default of 3600s."""
    strategy = _make_strategy()
    captured: dict[str, object] = {}
    original_session_client = boto3.session.Session.client

    def spy_session_client(self: boto3.session.Session, service: str, **kwargs: object) -> object:
        client = original_session_client(self, service, **kwargs)
        if service == "sts":
            original_assume = client.assume_role

            def spy_assume_role(**ar_kwargs: object) -> object:
                captured.update(ar_kwargs)
                return original_assume(**ar_kwargs)

            client.assume_role = spy_assume_role  # type: ignore[method-assign]
        return client

    mocker.patch.object(boto3.session.Session, "client", spy_session_client)
    strategy.get_credentials()

    assert "DurationSeconds" not in captured


@pytest.mark.unit
@mock_aws
def test_assume_role_does_not_pass_external_id(
    mocker: pytest.fixture,  # type: ignore[type-arg]
) -> None:
    """assume_role is called WITHOUT ExternalId — Phase 4 deferred per RESEARCH Section E."""
    strategy = _make_strategy()
    captured: dict[str, object] = {}
    original_session_client = boto3.session.Session.client

    def spy_session_client(self: boto3.session.Session, service: str, **kwargs: object) -> object:
        client = original_session_client(self, service, **kwargs)
        if service == "sts":
            original_assume = client.assume_role

            def spy_assume_role(**ar_kwargs: object) -> object:
                captured.update(ar_kwargs)
                return original_assume(**ar_kwargs)

            client.assume_role = spy_assume_role  # type: ignore[method-assign]
        return client

    mocker.patch.object(boto3.session.Session, "client", spy_session_client)
    strategy.get_credentials()

    assert "ExternalId" not in captured


@pytest.mark.unit
@mock_aws
def test_assume_role_returns_credentials_with_expiration() -> None:
    """Under @mock_aws, AwsCredentials.expiration is a non-None datetime."""
    creds = _make_strategy().get_credentials()
    assert creds.expiration is not None
    assert isinstance(creds.expiration, datetime)


@pytest.mark.unit
def test_assume_role_is_auth_strategy_protocol() -> None:
    """AssumeRoleStrategy satisfies the runtime-checkable AuthStrategy Protocol."""
    base = StaticKeysStrategy("a", "b")
    strategy = AssumeRoleStrategy(base, _ROLE_ARN, _SESSION_NAME, _REGION)
    assert isinstance(strategy, AuthStrategy)


@pytest.mark.unit
@mock_aws
def test_assume_role_propagates_base_session_token() -> None:
    """A base StaticKeysStrategy with a session_token is accepted by STS AssumeRole.

    moto 5.2.x does not validate session_token format for assume_role — it accepts
    any kwargs and returns a synthetic response. This test verifies that the boto3
    Session construction does not raise when a session_token is supplied.
    """
    creds = _make_strategy(session_token=_SESSION_TOKEN).get_credentials()
    # The returned credentials are the moto-synthesised assumed-role creds
    assert creds.session_token is not None
    assert creds.expiration is not None
