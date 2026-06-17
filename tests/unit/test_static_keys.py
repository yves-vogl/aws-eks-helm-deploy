"""Unit tests for StaticKeysStrategy.

Requirements traceability:
  - AUTH-01: StaticKeysStrategy satisfies the AuthStrategy Protocol and produces
    AwsCredentials from explicitly-supplied key material without any AWS API calls.
"""

from __future__ import annotations

import pytest

from aws_eks_helm_deploy.auth.base import AuthStrategy, AwsCredentials
from aws_eks_helm_deploy.auth.static_keys import StaticKeysStrategy

_ACCESS_KEY_ID = "AKIA-X"
_SECRET_ACCESS_KEY = "secret-Y"  # noqa: S105 — synthetic test value, not a real secret
_SESSION_TOKEN = "T-X"  # noqa: S105 — synthetic test value, not a real token


@pytest.mark.unit
def test_static_keys_get_credentials_returns_expected_values() -> None:
    """Happy path: get_credentials() returns AwsCredentials with the supplied values."""
    strategy = StaticKeysStrategy(_ACCESS_KEY_ID, _SECRET_ACCESS_KEY)
    creds = strategy.get_credentials()
    assert creds == AwsCredentials(_ACCESS_KEY_ID, _SECRET_ACCESS_KEY, None)


@pytest.mark.unit
def test_static_keys_session_token_default_is_none() -> None:
    """session_token parameter defaults to None when not supplied."""
    strategy = StaticKeysStrategy(_ACCESS_KEY_ID, _SECRET_ACCESS_KEY)
    creds = strategy.get_credentials()
    assert creds.session_token is None


@pytest.mark.unit
def test_static_keys_propagates_session_token_when_set() -> None:
    """session_token is propagated to AwsCredentials when explicitly set."""
    strategy = StaticKeysStrategy(_ACCESS_KEY_ID, _SECRET_ACCESS_KEY, session_token=_SESSION_TOKEN)
    creds = strategy.get_credentials()
    assert creds.session_token == _SESSION_TOKEN


@pytest.mark.unit
def test_static_keys_get_credentials_returns_same_values_on_repeat_calls() -> None:
    """Repeated calls to get_credentials() return equal AwsCredentials (stateless)."""
    strategy = StaticKeysStrategy(_ACCESS_KEY_ID, _SECRET_ACCESS_KEY)
    first = strategy.get_credentials()
    second = strategy.get_credentials()
    assert first == second


@pytest.mark.unit
def test_static_keys_no_expiration() -> None:
    """expiration is always None — long-term keys have no expiration."""
    strategy = StaticKeysStrategy(_ACCESS_KEY_ID, _SECRET_ACCESS_KEY)
    creds = strategy.get_credentials()
    assert creds.expiration is None


@pytest.mark.unit
def test_static_keys_is_auth_strategy_protocol() -> None:
    """StaticKeysStrategy satisfies the runtime-checkable AuthStrategy Protocol."""
    strategy = StaticKeysStrategy("a", "b")
    assert isinstance(strategy, AuthStrategy)


@pytest.mark.unit
def test_static_keys_constructor_signature_keyword_only_friendly() -> None:
    """Keyword arguments work as documented (the canonical consumer usage)."""
    strategy = StaticKeysStrategy(
        access_key_id=_ACCESS_KEY_ID,
        secret_access_key=_SECRET_ACCESS_KEY,
        session_token=_SESSION_TOKEN,
    )
    creds = strategy.get_credentials()
    assert creds.access_key_id == _ACCESS_KEY_ID
    assert creds.secret_access_key == _SECRET_ACCESS_KEY
    assert creds.session_token == _SESSION_TOKEN
