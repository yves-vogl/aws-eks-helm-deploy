"""Phase 2 integration smoke — end-to-end auth wire-in shape verification.

Real EKS webhook validation is out of scope per RESEARCH Section G.
These tests verify the structural shape of the auth wire (Settings → select_strategy →
AwsCredentials shape, and boto3.Session → generate_eks_token → k8s-aws-v1. token prefix).

Test 1 (test_static_keys_produce_credentials): runs without kind — pure Python only.
Test 2 (test_eks_token_is_structurally_valid): uses the kind_cluster fixture for a
realistic cluster name; skips cleanly when kind is absent.
"""

from __future__ import annotations

import base64
import urllib.parse

import boto3
import pytest

from aws_eks_helm_deploy.auth import select_strategy
from aws_eks_helm_deploy.auth.static_keys import StaticKeysStrategy
from aws_eks_helm_deploy.aws.eks_token import generate_eks_token
from aws_eks_helm_deploy.settings import Settings

# AWS-documented test key material (NOT real credentials — cannot sign real API calls).
# Reference: https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp_request.html
_TEST_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
_TEST_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"  # noqa: S105
_TEST_REGION = "eu-central-1"


def _decode_token_payload(token: str) -> dict[str, list[str]]:
    """Decode the base64url payload of a k8s-aws-v1. token into a query-string dict.

    Adds back the stripped '=' padding before decoding. The payload is the
    presigned STS GetCallerIdentity URL with x-k8s-aws-id signed in.
    """
    prefix = "k8s-aws-v1."
    encoded = token[len(prefix) :]
    # Add back padding stripped by upstream spec
    padding = 4 - len(encoded) % 4
    if padding != 4:
        encoded += "=" * padding
    url = base64.urlsafe_b64decode(encoded).decode("utf-8")
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.parse_qs(parsed.query)


@pytest.mark.integration
def test_static_keys_produce_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end: Settings → select_strategy → StaticKeysStrategy → AwsCredentials shape.

    Does not require a kind cluster — pure Python, no network calls.
    Verifies:
    - select_strategy returns a StaticKeysStrategy instance.
    - get_credentials() returns an AwsCredentials with the expected access_key_id.
    - repr() does not expose the secret value (Phase 02-02 contract crossover).
    """
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", _TEST_ACCESS_KEY_ID)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", _TEST_SECRET_ACCESS_KEY)

    settings = Settings()
    strategy = select_strategy(settings)

    assert isinstance(strategy, StaticKeysStrategy)

    creds = strategy.get_credentials()
    assert creds.access_key_id == _TEST_ACCESS_KEY_ID
    # repr() must not expose secret VALUE (Phase 02-02 AwsCredentials masked repr contract).
    # The field name "secret_access_key" appears as text; only the VALUE is redacted.
    assert _TEST_SECRET_ACCESS_KEY not in repr(creds)
    assert "<redacted>" in repr(creds)


@pytest.mark.integration
def test_eks_token_is_structurally_valid(
    kind_cluster: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: boto3.Session → generate_eks_token → k8s-aws-v1. token shape.

    Uses the kind_cluster fixture for a realistic cluster name (skips if kind absent).
    The token is EVALUATED for shape only — never sent to a kube-apiserver.
    Real EKS webhook validation is explicitly out of scope per RESEARCH Section G.

    Verifies:
    - Token starts with "k8s-aws-v1."
    - Token has no "=" padding (base64url-no-padding per upstream spec).
    - Decoded payload contains X-Amz-Expires=60.
    - x-k8s-aws-id is in X-Amz-SignedHeaders.
    - Hostname is sts.eu-central-1.amazonaws.com.
    """
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", _TEST_ACCESS_KEY_ID)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", _TEST_SECRET_ACCESS_KEY)

    # Build boto3.Session directly — isolates token-generation surface from select_strategy.
    session = boto3.Session(
        region_name=_TEST_REGION,
        aws_access_key_id=_TEST_ACCESS_KEY_ID,
        aws_secret_access_key=_TEST_SECRET_ACCESS_KEY,
    )

    token = generate_eks_token(session, kind_cluster, _TEST_REGION)

    # Token prefix
    assert token.startswith("k8s-aws-v1."), f"Token does not start with k8s-aws-v1.: {token[:30]!r}"
    # No base64 padding in the token itself (stripped by generate_eks_token)
    assert "=" not in token, f"Token contains unexpected '=' padding: {token[:60]!r}"

    # Decode and inspect the presigned URL payload
    params = _decode_token_payload(token)

    # X-Amz-Expires must be 60 (URL_TIMEOUT constant from eks_token.py)
    assert params.get("X-Amz-Expires") == ["60"], (
        f"Expected X-Amz-Expires=60, got: {params.get('X-Amz-Expires')}"
    )

    # x-k8s-aws-id must appear in X-Amz-SignedHeaders
    signed_headers_list = params.get("X-Amz-SignedHeaders", [""])
    signed_headers = signed_headers_list[0].split(";")
    assert "x-k8s-aws-id" in signed_headers, (
        f"x-k8s-aws-id not in X-Amz-SignedHeaders: {signed_headers}"
    )

    # Hostname must be the regional STS endpoint
    encoded = token[len("k8s-aws-v1.") :]
    padding = 4 - len(encoded) % 4
    if padding != 4:
        encoded += "=" * padding
    url = base64.urlsafe_b64decode(encoded).decode("utf-8")
    parsed = urllib.parse.urlparse(url)
    assert parsed.hostname == f"sts.{_TEST_REGION}.amazonaws.com", (
        f"Expected sts.{_TEST_REGION}.amazonaws.com, got: {parsed.hostname}"
    )
