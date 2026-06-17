"""Unit tests for auth/base.py — AuthStrategy Protocol + AwsCredentials dataclass.

Requirements traceability:
  - AUTH-01: typed AuthStrategy Protocol + AwsCredentials value object
  - OBS-02: credential blocklist enforced — to_boto3_kwargs() keys collide with CREDENTIAL_BLOCKLIST
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest
from aws_eks_helm_deploy.auth.base import AuthStrategy, AwsCredentials

# ---------------------------------------------------------------------------
# Well-known AWS docs example keys used throughout (not real credentials)
# ---------------------------------------------------------------------------

_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"  # noqa: S105 — AWS docs example key
_SESSION_TOKEN = "test-session-token"  # noqa: S105 — synthetic test value, not a real token
_DUMMY_SECRET = "supersecret"  # noqa: S105 — sentinel value for repr masking tests

# ---------------------------------------------------------------------------
# AwsCredentials — field defaults
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_aws_credentials_default_session_token_is_none() -> None:
    """session_token defaults to None for long-term key pairs."""
    creds = AwsCredentials(_ACCESS_KEY, _SECRET_KEY)
    assert creds.session_token is None


@pytest.mark.unit
def test_aws_credentials_default_expiration_is_none() -> None:
    """expiration defaults to None for long-term key pairs."""
    creds = AwsCredentials(_ACCESS_KEY, _SECRET_KEY)
    assert creds.expiration is None


@pytest.mark.unit
def test_aws_credentials_with_session_token() -> None:
    """session_token field stores the provided value."""
    creds = AwsCredentials(_ACCESS_KEY, _SECRET_KEY, session_token=_SESSION_TOKEN)
    assert creds.session_token == _SESSION_TOKEN


@pytest.mark.unit
def test_aws_credentials_with_expiration() -> None:
    """expiration field stores a datetime value."""
    exp = datetime(2026, 1, 1, tzinfo=UTC)
    creds = AwsCredentials(_ACCESS_KEY, _SECRET_KEY, expiration=exp)
    assert creds.expiration == exp


# ---------------------------------------------------------------------------
# AwsCredentials — frozen (immutability)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_aws_credentials_is_frozen_access_key() -> None:
    """Assigning to access_key_id raises FrozenInstanceError (frozen=True)."""
    creds = AwsCredentials(_ACCESS_KEY, _SECRET_KEY)
    with pytest.raises(dataclasses.FrozenInstanceError):
        creds.access_key_id = "NEWKEY"  # type: ignore[misc]


@pytest.mark.unit
def test_aws_credentials_is_frozen_secret() -> None:
    """Assigning to secret_access_key raises FrozenInstanceError (frozen=True)."""
    creds = AwsCredentials(_ACCESS_KEY, _SECRET_KEY)
    with pytest.raises(dataclasses.FrozenInstanceError):
        creds.secret_access_key = "NEWSECRET"  # type: ignore[misc]  # noqa: S105


# ---------------------------------------------------------------------------
# AwsCredentials — __repr__ masking (STRIDE T-02-02-01)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_aws_credentials_repr_masks_secret() -> None:
    """__repr__ must not include the raw secret value; must include <redacted>."""
    creds = AwsCredentials(_ACCESS_KEY, _DUMMY_SECRET)
    r = repr(creds)
    assert _DUMMY_SECRET not in r
    assert "<redacted>" in r


@pytest.mark.unit
def test_aws_credentials_repr_shows_last_four_of_access_key() -> None:
    """__repr__ shows only the last 4 chars of access_key_id prefixed with ..."""
    creds = AwsCredentials(_ACCESS_KEY, _SECRET_KEY)
    r = repr(creds)
    # Last 4 chars of "AKIAIOSFODNN7EXAMPLE" are "MPLE"
    assert "...MPLE" in r
    # Full key must NOT appear
    assert _ACCESS_KEY not in r


@pytest.mark.unit
def test_aws_credentials_repr_short_access_key() -> None:
    """Short access_key_id (len < 4) is replaced with **** in __repr__ (no value leak)."""
    short_key = "AKI"
    creds = AwsCredentials(short_key, _SECRET_KEY)
    r = repr(creds)
    assert "****" in r
    assert short_key not in r


@pytest.mark.unit
def test_aws_credentials_repr_includes_session_token_marker_when_set() -> None:
    """__repr__ appends session_token=<redacted> when session_token is set."""
    creds = AwsCredentials(_ACCESS_KEY, _SECRET_KEY, session_token=_SESSION_TOKEN)
    assert "session_token=<redacted>" in repr(creds)


@pytest.mark.unit
def test_aws_credentials_repr_omits_session_token_marker_when_none() -> None:
    """__repr__ omits session_token entirely when it is None."""
    creds = AwsCredentials(_ACCESS_KEY, _SECRET_KEY)
    assert "session_token" not in repr(creds)


# ---------------------------------------------------------------------------
# AwsCredentials — to_boto3_kwargs()
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_to_boto3_kwargs_without_session_token() -> None:
    """to_boto3_kwargs() returns only access + secret keys when session_token is None."""
    creds = AwsCredentials(_ACCESS_KEY, _SECRET_KEY)
    kwargs = creds.to_boto3_kwargs()
    assert kwargs == {
        "aws_access_key_id": _ACCESS_KEY,
        "aws_secret_access_key": _SECRET_KEY,
    }


@pytest.mark.unit
def test_to_boto3_kwargs_with_session_token() -> None:
    """to_boto3_kwargs() includes aws_session_token when session_token is set."""
    creds = AwsCredentials(_ACCESS_KEY, _SECRET_KEY, session_token=_SESSION_TOKEN)
    kwargs = creds.to_boto3_kwargs()
    assert kwargs == {
        "aws_access_key_id": _ACCESS_KEY,
        "aws_secret_access_key": _SECRET_KEY,
        "aws_session_token": _SESSION_TOKEN,
    }


@pytest.mark.unit
def test_to_boto3_kwargs_omits_expiration() -> None:
    """to_boto3_kwargs() never includes 'expiration' — it is not a boto3 Session kwarg."""
    exp = datetime(2026, 1, 1, tzinfo=UTC)
    creds = AwsCredentials(_ACCESS_KEY, _SECRET_KEY, expiration=exp)
    kwargs = creds.to_boto3_kwargs()
    assert "expiration" not in kwargs


# ---------------------------------------------------------------------------
# AwsCredentials — equality and hashability
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_aws_credentials_equality() -> None:
    """Frozen dataclass auto-generates __eq__; identical instances are equal."""
    a = AwsCredentials(_ACCESS_KEY, _SECRET_KEY)
    b = AwsCredentials(_ACCESS_KEY, _SECRET_KEY)
    c = AwsCredentials("DIFFERENTKEY12345678", _SECRET_KEY)
    assert a == b
    assert a != c


@pytest.mark.unit
def test_aws_credentials_hashable() -> None:
    """Frozen dataclasses are hashable; can be used as dict keys."""
    creds = AwsCredentials(_ACCESS_KEY, _SECRET_KEY)
    cache: dict[AwsCredentials, str] = {creds: "cached"}
    assert cache[creds] == "cached"


# ---------------------------------------------------------------------------
# AuthStrategy — runtime-checkable Protocol
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_auth_strategy_is_runtime_checkable_positive() -> None:
    """An object with get_credentials() passes isinstance(obj, AuthStrategy)."""

    class _Conformant:
        def get_credentials(self) -> AwsCredentials:
            return AwsCredentials(_ACCESS_KEY, _SECRET_KEY)

    assert isinstance(_Conformant(), AuthStrategy) is True


@pytest.mark.unit
def test_auth_strategy_is_runtime_checkable_negative() -> None:
    """A plain object with no get_credentials() method fails isinstance check."""
    assert isinstance(object(), AuthStrategy) is False


# ---------------------------------------------------------------------------
# Integration: to_boto3_kwargs() keys collide with CREDENTIAL_BLOCKLIST (OBS-02)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_aws_credentials_to_boto3_kwargs_collides_with_blocklist() -> None:
    """CONTRACT: bind_safe_context(**creds.to_boto3_kwargs()) MUST raise ValueError.

    This test enforces the credential-blocklist contract documented in RESEARCH
    Section B "Integration with CREDENTIAL_BLOCKLIST". Callers MUST NOT spread
    raw creds into structlog context. The ValueError is the intended behavior,
    not a bug.
    """
    from aws_eks_helm_deploy.logging import bind_safe_context

    creds = AwsCredentials(_ACCESS_KEY, _SECRET_KEY)
    with pytest.raises(ValueError, match="blocklisted"):
        bind_safe_context(**creds.to_boto3_kwargs())
