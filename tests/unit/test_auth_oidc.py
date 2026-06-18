"""Unit tests for OidcWebIdentityStrategy (AUTH-03).

Uses moto 5.2.x @mock_aws to mock the STS AssumeRoleWithWebIdentity endpoint;
no real AWS account required.

Requirements traceability:
  - AUTH-03: OidcWebIdentityStrategy exchanges a Bitbucket OIDC JWT for short-lived
    AWS credentials via STS AssumeRoleWithWebIdentity.
"""

from __future__ import annotations

import contextlib
import dataclasses
import datetime

import pytest
from botocore.exceptions import ClientError
from moto import mock_aws
from pytest_mock import MockerFixture

from aws_eks_helm_deploy.auth.base import AuthStrategy, AwsCredentials
from aws_eks_helm_deploy.errors import AuthenticationError

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_strategy(
    oidc_token: str = "dummy.jwt.token",  # noqa: S107
    role_arn: str = "arn:aws:iam::123456789012:role/MyOidcRole",
    audience: str = "ari:cloud:bitbucket::workspace/abc",
    session_name: str = "test-session-name",
    region: str = "eu-central-1",
) -> object:
    from aws_eks_helm_deploy.auth.oidc import OidcWebIdentityStrategy

    return OidcWebIdentityStrategy(oidc_token, role_arn, audience, session_name, region)


# ---------------------------------------------------------------------------
# Import tests
# ---------------------------------------------------------------------------


@mock_aws
@pytest.mark.unit
def test_module_imports_clean() -> None:
    """OidcWebIdentityStrategy can be imported with no side effects."""
    from aws_eks_helm_deploy.auth.oidc import OidcWebIdentityStrategy  # noqa: F401


@mock_aws
@pytest.mark.unit
def test_constructor_stores_args_no_io(mocker: MockerFixture) -> None:
    """Constructor stores args; no boto3 Session or STS client is constructed."""
    mock_session_cls = mocker.patch("boto3.session.Session")

    from aws_eks_helm_deploy.auth.oidc import OidcWebIdentityStrategy

    strategy = OidcWebIdentityStrategy(
        oidc_token="dummy.jwt",
        role_arn="arn:aws:iam::123456789012:role/R",
        audience="ari:cloud:bitbucket::workspace/abc",
        session_name="s",
        region="eu-central-1",
    )

    mock_session_cls.assert_not_called()
    assert strategy._oidc_token == "dummy.jwt"  # noqa: S105
    assert strategy._role_arn == "arn:aws:iam::123456789012:role/R"
    assert strategy._audience == "ari:cloud:bitbucket::workspace/abc"
    assert strategy._session_name == "s"
    assert strategy._region == "eu-central-1"


@mock_aws
@pytest.mark.unit
def test_satisfies_auth_strategy_protocol_structurally() -> None:
    """OidcWebIdentityStrategy satisfies AuthStrategy Protocol structurally."""
    strategy = _make_strategy()
    assert isinstance(strategy, AuthStrategy)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@mock_aws
@pytest.mark.unit
def test_get_credentials_happy_path_under_mock_aws() -> None:
    """get_credentials() returns a populated AwsCredentials under @mock_aws.

    moto accepts any non-empty WebIdentityToken — no JWT validation required.
    """
    from aws_eks_helm_deploy.auth.oidc import OidcWebIdentityStrategy

    strategy = OidcWebIdentityStrategy(
        oidc_token="dummy.jwt.token",
        role_arn="arn:aws:iam::123456789012:role/MyOidcRole",
        audience="ari:cloud:bitbucket::workspace/abc",
        session_name="test-session",
        region="eu-central-1",
    )
    creds = strategy.get_credentials()

    assert isinstance(creds, AwsCredentials)
    # moto's temporary credentials start with ASIA
    assert creds.access_key_id.startswith("ASIA")
    assert creds.secret_access_key != ""
    assert creds.session_token is not None
    assert creds.session_token != ""
    assert isinstance(creds.expiration, datetime.datetime)


@mock_aws
@pytest.mark.unit
def test_get_credentials_does_not_pass_audience_kwarg_to_sts(
    mocker: MockerFixture,
) -> None:
    """get_credentials() does NOT pass Audience= to assume_role_with_web_identity.

    The audience is encoded in the JWT's aud claim — STS reads it from there.
    (CONTEXT D2 explicit note)
    """
    mock_sts = mocker.MagicMock()
    mock_sts.assume_role_with_web_identity.return_value = {
        "Credentials": {
            "AccessKeyId": "ASIAIOSFODNN7EXAMPLE",
            "SecretAccessKey": "secret",
            "SessionToken": "token",
            "Expiration": datetime.datetime(2030, 1, 1, tzinfo=datetime.UTC),
        }
    }

    mock_session = mocker.MagicMock()
    mock_session.client.return_value = mock_sts
    mocker.patch("boto3.session.Session", return_value=mock_session)

    strategy = _make_strategy()
    strategy.get_credentials()  # type: ignore[union-attr]

    call_kwargs = mock_sts.assume_role_with_web_identity.call_args.kwargs
    assert "Audience" not in call_kwargs


@mock_aws
@pytest.mark.unit
def test_get_credentials_uses_unsigned_signature_version(
    mocker: MockerFixture,
) -> None:
    """get_credentials() builds the STS client with signature_version=UNSIGNED.

    Without UNSIGNED, the default Session would raise NoCredentialsError before
    sending the (unauthenticated) AssumeRoleWithWebIdentity request. (R3 mitigation)
    """
    from botocore import UNSIGNED

    mock_sts = mocker.MagicMock()
    mock_sts.assume_role_with_web_identity.return_value = {
        "Credentials": {
            "AccessKeyId": "ASIAIOSFODNN7EXAMPLE",
            "SecretAccessKey": "secret",
            "SessionToken": "token",
            "Expiration": datetime.datetime(2030, 1, 1, tzinfo=datetime.UTC),
        }
    }

    mock_session = mocker.MagicMock()
    mock_session.client.return_value = mock_sts
    mocker.patch("boto3.session.Session", return_value=mock_session)

    strategy = _make_strategy()
    strategy.get_credentials()  # type: ignore[union-attr]

    _call = mock_session.client.call_args
    config_arg = _call.kwargs.get("config") or (_call.args[1] if len(_call.args) > 1 else None)
    assert config_arg is not None
    assert config_arg.signature_version == UNSIGNED


@mock_aws
@pytest.mark.unit
def test_get_credentials_uses_regional_sts_endpoint(
    mocker: MockerFixture,
) -> None:
    """get_credentials() passes the regional STS endpoint_url to the client."""
    mock_sts = mocker.MagicMock()
    mock_sts.assume_role_with_web_identity.return_value = {
        "Credentials": {
            "AccessKeyId": "ASIAIOSFODNN7EXAMPLE",
            "SecretAccessKey": "secret",
            "SessionToken": "token",
            "Expiration": datetime.datetime(2030, 1, 1, tzinfo=datetime.UTC),
        }
    }

    mock_session = mocker.MagicMock()
    mock_session.client.return_value = mock_sts
    mocker.patch("boto3.session.Session", return_value=mock_session)

    strategy = _make_strategy(region="eu-central-1")
    strategy.get_credentials()  # type: ignore[union-attr]

    _call = mock_session.client.call_args
    endpoint_url = _call.kwargs.get("endpoint_url")
    assert endpoint_url == "https://sts.eu-central-1.amazonaws.com"


# ---------------------------------------------------------------------------
# Error path
# ---------------------------------------------------------------------------


@mock_aws
@pytest.mark.unit
def test_get_credentials_client_error_raises_authentication_error(
    mocker: MockerFixture,
) -> None:
    """ClientError from STS is mapped to AuthenticationError with exit_code=2."""
    mock_sts = mocker.MagicMock()
    mock_sts.assume_role_with_web_identity.side_effect = ClientError(
        {"Error": {"Code": "InvalidIdentityToken", "Message": "Token is expired"}},
        "AssumeRoleWithWebIdentity",
    )

    mock_session = mocker.MagicMock()
    mock_session.client.return_value = mock_sts
    mocker.patch("boto3.session.Session", return_value=mock_session)

    strategy = _make_strategy()

    with pytest.raises(AuthenticationError) as exc_info:
        strategy.get_credentials()  # type: ignore[union-attr]

    assert exc_info.value.exit_code == 2
    assert "InvalidIdentityToken" in str(exc_info.value)
    assert "Token is expired" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AwsCredentials properties
# ---------------------------------------------------------------------------


@mock_aws
@pytest.mark.unit
def test_aws_credentials_returned_is_frozen() -> None:
    """Returned AwsCredentials is a frozen dataclass — mutation raises FrozenInstanceError."""
    from aws_eks_helm_deploy.auth.oidc import OidcWebIdentityStrategy

    strategy = OidcWebIdentityStrategy(
        oidc_token="dummy.jwt.token",
        role_arn="arn:aws:iam::123456789012:role/MyOidcRole",
        audience="ari:cloud:bitbucket::workspace/abc",
        session_name="test-session",
        region="eu-central-1",
    )
    creds = strategy.get_credentials()

    assert dataclasses.is_dataclass(creds)
    assert creds.__dataclass_params__.frozen  # type: ignore[union-attr]

    with pytest.raises(dataclasses.FrozenInstanceError):
        creds.access_key_id = "mutated"  # type: ignore[misc]


@mock_aws
@pytest.mark.unit
def test_aws_credentials_repr_is_masked() -> None:
    """AwsCredentials __repr__ masks secret_access_key for OIDC-issued credentials."""
    from aws_eks_helm_deploy.auth.oidc import OidcWebIdentityStrategy

    strategy = OidcWebIdentityStrategy(
        oidc_token="dummy.jwt.token",
        role_arn="arn:aws:iam::123456789012:role/MyOidcRole",
        audience="ari:cloud:bitbucket::workspace/abc",
        session_name="test-session",
        region="eu-central-1",
    )
    creds = strategy.get_credentials()

    r = repr(creds)
    assert "secret_access_key=<redacted>" in r
    # The raw secret value must not appear
    assert creds.secret_access_key not in r


# Suppress unused import warning — contextlib imported for potential use
with contextlib.suppress(Exception):
    pass
