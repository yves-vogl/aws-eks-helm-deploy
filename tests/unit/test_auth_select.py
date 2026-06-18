"""Unit tests for aws_eks_helm_deploy.auth.select_strategy + _derive_session_name.

Requirements traceability:
  - AUTH-01: select_strategy() returns the correct concrete strategy for each
    decision-tree branch.
  - AUTH-02: AssumeRoleStrategy wraps StaticKeysStrategy when ROLE_ARN is present.

Coverage target: 100% line + 100% branch on auth/__init__.py.
"""

from __future__ import annotations

import re

import pytest

from aws_eks_helm_deploy.auth import _derive_session_name, select_strategy
from aws_eks_helm_deploy.auth.assume_role import AssumeRoleStrategy
from aws_eks_helm_deploy.auth.base import AwsCredentials
from aws_eks_helm_deploy.auth.static_keys import StaticKeysStrategy
from aws_eks_helm_deploy.errors import ConfigurationError
from aws_eks_helm_deploy.settings import Settings

# ---------------------------------------------------------------------------
# Shared fixture: wipe all credential-related env vars for test isolation
# ---------------------------------------------------------------------------

_CREDENTIAL_VARS = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "ROLE_ARN",
    "SESSION_NAME",
    "BITBUCKET_PIPELINE_UUID",
    "BITBUCKET_BUILD_NUMBER",
)


@pytest.fixture(autouse=True)
def _clean_aws_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all credential-related env vars before each test."""
    for var in _CREDENTIAL_VARS:
        monkeypatch.delenv(var, raising=False)


# ---------------------------------------------------------------------------
# select_strategy — decision-tree branch tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_select_static_keys_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """select_strategy returns StaticKeysStrategy when only access key + secret are set."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")

    settings = Settings()
    strategy = select_strategy(settings)

    assert isinstance(strategy, StaticKeysStrategy)
    creds = strategy.get_credentials()
    assert creds.access_key_id == "AKIAIOSFODNN7EXAMPLE"
    assert creds.secret_access_key == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"  # noqa: S105


@pytest.mark.unit
def test_select_static_keys_plus_role_arn_returns_assume_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """select_strategy returns AssumeRoleStrategy wrapping StaticKeysStrategy when ROLE_ARN set.

    Private-attr access (_base) is intentional here — Phase 2 has no public
    introspection API for the wrapped base strategy. The comment acknowledges this.
    """
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    monkeypatch.setenv("ROLE_ARN", "arn:aws:iam::123456789012:role/TestRole")

    settings = Settings()
    strategy = select_strategy(settings)

    assert isinstance(strategy, AssumeRoleStrategy)
    # Private-attr access: intentional (no public introspection API in Phase 2)
    assert isinstance(strategy._base, StaticKeysStrategy)


@pytest.mark.unit
def test_select_role_arn_without_base_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """select_strategy raises ConfigurationError with exit_code=1 when ROLE_ARN set without keys.

    The error message must mention both static-keys AND OIDC as alternatives (AUTH-06 revised).
    """
    monkeypatch.setenv("ROLE_ARN", "arn:aws:iam::123456789012:role/TestRole")

    settings = Settings()

    with pytest.raises(ConfigurationError) as exc_info:
        select_strategy(settings)

    assert exc_info.value.exit_code == 1
    assert "ROLE_ARN requires" in str(exc_info.value)
    assert "BITBUCKET_STEP_OIDC_TOKEN" in str(exc_info.value)


@pytest.mark.unit
def test_select_no_credentials_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """select_strategy raises ConfigurationError when no credentials are configured at all."""
    settings = Settings()  # all creds are None (env vars wiped by autouse fixture)

    with pytest.raises(ConfigurationError) as exc_info:
        select_strategy(settings)

    assert exc_info.value.exit_code == 1
    assert "AWS_ACCESS_KEY_ID" in str(exc_info.value)


@pytest.mark.unit
def test_select_with_aws_session_token_passes_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """StaticKeysStrategy propagates session_token when AWS_SESSION_TOKEN is set."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "token-value-for-test")

    settings = Settings()
    strategy = select_strategy(settings)

    assert isinstance(strategy, StaticKeysStrategy)
    creds: AwsCredentials = strategy.get_credentials()
    assert creds.session_token == "token-value-for-test"  # noqa: S105


@pytest.mark.unit
def test_select_with_session_token_and_role_arn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AssumeRoleStrategy wraps a StaticKeysStrategy that itself has session_token set."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "token-value-for-test")
    monkeypatch.setenv("ROLE_ARN", "arn:aws:iam::123456789012:role/TestRole")

    settings = Settings()
    strategy = select_strategy(settings)

    assert isinstance(strategy, AssumeRoleStrategy)
    # Private-attr access: intentional (no public introspection API in Phase 2)
    assert isinstance(strategy._base, StaticKeysStrategy)
    base_creds: AwsCredentials = strategy._base.get_credentials()
    assert base_creds.session_token == "token-value-for-test"  # noqa: S105


# ---------------------------------------------------------------------------
# _derive_session_name — helper function tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_derive_session_name_explicit_session_name_honored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit SESSION_NAME (non-default) is returned as-is (up to 64 chars)."""
    monkeypatch.setenv("SESSION_NAME", "custom-name")

    settings = Settings()
    name = _derive_session_name(settings)

    assert name == "custom-name"


@pytest.mark.unit
def test_derive_session_name_explicit_session_name_truncated_to_64(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SESSION_NAME longer than 64 chars is truncated to exactly 64 chars."""
    long_name = "a" * 80
    monkeypatch.setenv("SESSION_NAME", long_name)

    settings = Settings()
    name = _derive_session_name(settings)

    assert len(name) == 64
    assert name == "a" * 64


@pytest.mark.unit
def test_derive_session_name_bitbucket_pipeline_uuid_used_when_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BITBUCKET_PIPELINE_UUID is used when SESSION_NAME is the default."""
    monkeypatch.setenv("BITBUCKET_PIPELINE_UUID", "{1234-5678-abcd-ef01}")
    # SESSION_NAME left at default ("BitbucketPipe") by not setting it

    settings = Settings()
    name = _derive_session_name(settings)

    assert name.startswith("aws-eks-helm-deploy-1234-5678")


@pytest.mark.unit
def test_derive_session_name_bitbucket_pipeline_uuid_strips_braces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Surrounding braces are stripped from BITBUCKET_PIPELINE_UUID."""
    monkeypatch.setenv("BITBUCKET_PIPELINE_UUID", "{abc-uuid}")

    settings = Settings()
    name = _derive_session_name(settings)

    assert "{" not in name
    assert "}" not in name


@pytest.mark.unit
def test_derive_session_name_bitbucket_build_number_used_as_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BITBUCKET_BUILD_NUMBER is used when PIPELINE_UUID is not set."""
    monkeypatch.delenv("BITBUCKET_PIPELINE_UUID", raising=False)
    monkeypatch.setenv("BITBUCKET_BUILD_NUMBER", "42")

    settings = Settings()
    name = _derive_session_name(settings)

    assert name == "aws-eks-helm-deploy-42"


@pytest.mark.unit
def test_derive_session_name_uuid_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UUID4 fallback is used when no Bitbucket env vars and SESSION_NAME is default."""
    monkeypatch.delenv("BITBUCKET_PIPELINE_UUID", raising=False)
    monkeypatch.delenv("BITBUCKET_BUILD_NUMBER", raising=False)

    settings = Settings()
    name = _derive_session_name(settings)

    assert name.startswith("aws-eks-helm-deploy-")
    suffix = name[len("aws-eks-helm-deploy-") :]
    # UUID4 hex chars + hyphens
    assert re.fullmatch(r"[0-9a-f-]+", suffix) is not None


@pytest.mark.unit
def test_derive_session_name_truncated_to_64_chars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All four derivation paths produce names <= 64 characters."""
    settings = Settings()

    # Path 1: explicit (long) name
    monkeypatch.setenv("SESSION_NAME", "a" * 80)
    assert len(_derive_session_name(settings)) <= 64
    monkeypatch.delenv("SESSION_NAME", raising=False)

    # Path 2: pipeline UUID (long)
    monkeypatch.setenv("BITBUCKET_PIPELINE_UUID", "{" + "x" * 60 + "}")
    assert len(_derive_session_name(settings)) <= 64
    monkeypatch.delenv("BITBUCKET_PIPELINE_UUID", raising=False)

    # Path 3: build number (long)
    monkeypatch.setenv("BITBUCKET_BUILD_NUMBER", "9" * 60)
    assert len(_derive_session_name(settings)) <= 64
    monkeypatch.delenv("BITBUCKET_BUILD_NUMBER", raising=False)

    # Path 4: UUID fallback
    assert len(_derive_session_name(settings)) <= 64


@pytest.mark.unit
def test_derive_session_name_matches_iam_pattern(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All four derivation paths produce names matching [\\w+=,.@-]+."""
    iam_pattern = re.compile(r"[\w+=,.@-]+")
    settings = Settings()

    # Path 1: explicit valid name
    monkeypatch.setenv("SESSION_NAME", "my-session.name@1")
    name = _derive_session_name(settings)
    assert iam_pattern.fullmatch(name) is not None, f"Path 1 failed: {name!r}"
    monkeypatch.delenv("SESSION_NAME", raising=False)

    # Path 2: pipeline UUID
    monkeypatch.setenv("BITBUCKET_PIPELINE_UUID", "{abc-1234}")
    name = _derive_session_name(settings)
    assert iam_pattern.fullmatch(name) is not None, f"Path 2 failed: {name!r}"
    monkeypatch.delenv("BITBUCKET_PIPELINE_UUID", raising=False)

    # Path 3: build number
    monkeypatch.setenv("BITBUCKET_BUILD_NUMBER", "99")
    name = _derive_session_name(settings)
    assert iam_pattern.fullmatch(name) is not None, f"Path 3 failed: {name!r}"
    monkeypatch.delenv("BITBUCKET_BUILD_NUMBER", raising=False)

    # Path 4: UUID fallback
    name = _derive_session_name(settings)
    assert iam_pattern.fullmatch(name) is not None, f"Path 4 failed: {name!r}"


@pytest.mark.unit
def test_derive_session_name_explicit_session_name_invalid_chars_falls_through_to_uuid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SESSION_NAME with invalid IAM characters silently falls through to UUID fallback.

    Design choice: graceful degradation, not an error. The consumer's custom name is
    replaced with a UUID-based name without raising an exception. This avoids breaking
    runs in environments where SESSION_NAME might contain shell-expanded values with
    spaces or other problematic chars.

    Re-evaluation hook: Phase 2.1 could elevate this to a ConfigurationError if
    consumer-supplied invalid SESSION_NAME values turn out to be a real problem.
    """
    monkeypatch.setenv("SESSION_NAME", "has spaces here")  # invalid: spaces not in IAM pattern
    monkeypatch.delenv("BITBUCKET_PIPELINE_UUID", raising=False)
    monkeypatch.delenv("BITBUCKET_BUILD_NUMBER", raising=False)

    settings = Settings()
    name = _derive_session_name(settings)

    # Must NOT contain spaces (fell through to UUID)
    assert " " not in name
    assert name.startswith("aws-eks-helm-deploy-")
