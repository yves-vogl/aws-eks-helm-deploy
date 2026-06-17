"""Structural-equivalence test suite for generate_eks_token (AUTH-07).

The ROADMAP's 'byte-equal' wording is replaced with structural equivalence per
RESEARCH Section A — see 02-01-PLAN.md <deviations> for the documented departure.
Two consecutive calls with identical credentials produce different timestamps and
HMAC signatures; byte-equality would always be flaky.
"""

from __future__ import annotations

import base64
import urllib.parse

import boto3
import botocore.exceptions
import pytest
from moto import mock_aws
from pytest_mock import MockerFixture

from aws_eks_helm_deploy.aws.eks_token import (
    K8S_AWS_ID_HEADER,
    TOKEN_PREFIX,
    URL_TIMEOUT,
    generate_eks_token,
)
from aws_eks_helm_deploy.errors import EksTokenError, PipeError

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

_REGION = "eu-central-1"
_CLUSTER = "my-test-cluster"

_DUMMY_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
_DUMMY_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"  # noqa: S105 — well-known AWS docs example key


def _make_session(region: str = _REGION) -> boto3.Session:
    """Return a boto3.Session with dummy credentials (safe under @mock_aws)."""
    return boto3.Session(
        region_name=region,
        aws_access_key_id=_DUMMY_ACCESS_KEY,
        aws_secret_access_key=_DUMMY_SECRET_KEY,
    )


def _decode_token_payload(token: str) -> dict[str, str]:
    """Strip prefix, restore padding, base64url-decode, parse query string."""
    encoded = token[len(TOKEN_PREFIX) :]
    # Restore the stripped '=' padding
    padded = encoded + "=" * (-len(encoded) % 4)
    url = base64.urlsafe_b64decode(padded).decode("utf-8")
    return dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))


# ---------------------------------------------------------------------------
# Structural token tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@mock_aws
def test_token_starts_with_v1_prefix() -> None:
    """Generated token must begin with the k8s-aws-v1. literal prefix."""
    token = generate_eks_token(_make_session(), _CLUSTER, _REGION)
    assert token.startswith(TOKEN_PREFIX)


@pytest.mark.unit
@mock_aws
def test_token_contains_no_base64_padding() -> None:
    """Generated token must contain no '=' padding (base64url-no-padding spec)."""
    token = generate_eks_token(_make_session(), _CLUSTER, _REGION)
    assert "=" not in token


@pytest.mark.unit
@mock_aws
def test_decoded_url_has_x_amz_expires_60() -> None:
    """Decoded URL must have X-Amz-Expires=60 (URL_TIMEOUT constant)."""
    token = generate_eks_token(_make_session(), _CLUSTER, _REGION)
    params = _decode_token_payload(token)
    assert params.get("X-Amz-Expires") == str(URL_TIMEOUT)


@pytest.mark.unit
@mock_aws
def test_decoded_url_signs_cluster_name_header() -> None:
    """Decoded URL must list x-k8s-aws-id in X-Amz-SignedHeaders."""
    token = generate_eks_token(_make_session(), _CLUSTER, _REGION)
    params = _decode_token_payload(token)
    signed_headers = params.get("X-Amz-SignedHeaders", "")
    assert K8S_AWS_ID_HEADER in signed_headers


@pytest.mark.unit
@mock_aws
def test_decoded_url_action_is_get_caller_identity() -> None:
    """Decoded URL Action param must be GetCallerIdentity."""
    token = generate_eks_token(_make_session(), _CLUSTER, _REGION)
    params = _decode_token_payload(token)
    assert params.get("Action") == "GetCallerIdentity"


@pytest.mark.unit
@mock_aws
def test_decoded_url_uses_regional_sts_endpoint() -> None:
    """Decoded URL hostname must be the regional STS endpoint (not global)."""
    token = generate_eks_token(_make_session(), _CLUSTER, _REGION)
    encoded = token[len(TOKEN_PREFIX) :]
    padded = encoded + "=" * (-len(encoded) % 4)
    url = base64.urlsafe_b64decode(padded).decode("utf-8")
    parsed = urllib.parse.urlparse(url)
    assert parsed.hostname == f"sts.{_REGION}.amazonaws.com"


@pytest.mark.unit
@mock_aws
def test_different_cluster_names_produce_different_tokens() -> None:
    """Different cluster names must yield different tokens (cluster name is signed)."""
    session = _make_session()
    token_a = generate_eks_token(session, "cluster-a", _REGION)
    token_b = generate_eks_token(session, "cluster-b", _REGION)
    assert token_a != token_b


@pytest.mark.unit
@mock_aws
def test_different_regions_produce_different_endpoints() -> None:
    """Different regions must produce different STS endpoint hostnames in the token."""
    token = generate_eks_token(_make_session(region="us-east-1"), _CLUSTER, "us-east-1")
    encoded = token[len(TOKEN_PREFIX) :]
    padded = encoded + "=" * (-len(encoded) % 4)
    url = base64.urlsafe_b64decode(padded).decode("utf-8")
    parsed = urllib.parse.urlparse(url)
    assert parsed.hostname == "sts.us-east-1.amazonaws.com"


@pytest.mark.unit
@mock_aws
def test_algorithm_is_sigv4() -> None:
    """Decoded URL must specify AWS4-HMAC-SHA256 as the signing algorithm."""
    token = generate_eks_token(_make_session(), _CLUSTER, _REGION)
    params = _decode_token_payload(token)
    assert params.get("X-Amz-Algorithm") == "AWS4-HMAC-SHA256"


# ---------------------------------------------------------------------------
# Error branch tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@mock_aws
def test_client_error_raises_eks_token_error(mocker: MockerFixture) -> None:
    """ClientError from generate_presigned_url must be wrapped as EksTokenError.

    We patch botocore.signers.generate_presigned_url (the module-level function
    that botocore injects as the client method via add_generate_presigned_url).
    botocore.client.BaseClient does NOT have generate_presigned_url in its
    __dict__ — it is added dynamically to service-specific subclasses via
    botocore.signers.add_generate_presigned_url during client creation.
    Patching the signers module-level function is the stable injection point
    that works regardless of @mock_aws intercepting the underlying HTTP calls.
    """
    mocker.patch(
        "botocore.signers.generate_presigned_url",
        side_effect=botocore.exceptions.ClientError(
            {"Error": {"Code": "InvalidClientTokenId", "Message": "Bad token"}},
            "GetCallerIdentity",
        ),
    )
    session = _make_session()
    with pytest.raises(EksTokenError) as exc_info:
        generate_eks_token(session, _CLUSTER, _REGION)
    assert exc_info.value.exit_code == 3
    assert isinstance(exc_info.value, PipeError)


@pytest.mark.unit
@mock_aws
def test_no_credentials_error_raises_eks_token_error(mocker: MockerFixture) -> None:
    """NoCredentialsError from generate_presigned_url must be wrapped as EksTokenError.

    Same patching rationale as test_client_error_raises_eks_token_error.
    botocore.signers.generate_presigned_url is the module-level function
    injected as the STS client's method via add_generate_presigned_url.
    """
    mocker.patch(
        "botocore.signers.generate_presigned_url",
        side_effect=botocore.exceptions.NoCredentialsError(),
    )
    session = _make_session()
    with pytest.raises(EksTokenError) as exc_info:
        generate_eks_token(session, _CLUSTER, _REGION)
    assert exc_info.value.exit_code == 3
    assert isinstance(exc_info.value, PipeError)
