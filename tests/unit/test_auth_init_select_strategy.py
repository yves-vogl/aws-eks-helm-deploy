"""Unit tests for select_strategy OIDC integration (AUTH-03/04/06).

Tests the Phase 4 extensions to auth/__init__.py::select_strategy:
  - AUTH-03: OIDC branch returns OidcWebIdentityStrategy when BITBUCKET_STEP_OIDC_TOKEN
    + ROLE_ARN + OIDC_AUDIENCE are all set and no static keys are present.
  - AUTH-04 (revised): static keys take precedence over OIDC token;
    a WARN log is emitted when both are present.
  - AUTH-06: ConfigurationError raised for misconfig:
    - OIDC token present without ROLE_ARN
    - OIDC token + ROLE_ARN present without OIDC_AUDIENCE
    - ROLE_ARN set without any base credentials (message updated to mention OIDC)
    - No credentials at all

These tests APPEND Phase 4 coverage alongside the existing Phase 2 tests in
test_auth_select.py. Existing Phase 2 tests are NOT modified here.

Requirements traceability:
  - AUTH-03, AUTH-04 (revised), AUTH-06
"""

from __future__ import annotations

import pytest
from structlog.testing import capture_logs

from aws_eks_helm_deploy.auth import select_strategy
from aws_eks_helm_deploy.auth.assume_role import AssumeRoleStrategy
from aws_eks_helm_deploy.auth.oidc import OidcWebIdentityStrategy
from aws_eks_helm_deploy.auth.static_keys import StaticKeysStrategy
from aws_eks_helm_deploy.errors import ConfigurationError
from aws_eks_helm_deploy.settings import Settings

# ---------------------------------------------------------------------------
# Shared fixture: wipe all credential-related env vars for test isolation
# ---------------------------------------------------------------------------

_ALL_CRED_VARS = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "ROLE_ARN",
    "OIDC_AUDIENCE",
    "SESSION_NAME",
    "BITBUCKET_STEP_OIDC_TOKEN",
    "BITBUCKET_PIPELINE_UUID",
    "BITBUCKET_BUILD_NUMBER",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all credential-related env vars before each test."""
    for var in _ALL_CRED_VARS:
        monkeypatch.delenv(var, raising=False)


# ---------------------------------------------------------------------------
# AUTH-03: OIDC happy path
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_select_strategy_returns_oidc_when_token_and_role_arn_and_audience_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OIDC happy path: token + ROLE_ARN + OIDC_AUDIENCE → OidcWebIdentityStrategy.

    No static keys are present; no WARN log should be emitted.
    """
    monkeypatch.setenv("BITBUCKET_STEP_OIDC_TOKEN", "dummy.jwt.token")

    settings = Settings(
        ROLE_ARN="arn:aws:iam::123456789012:role/MyOidcRole",  # type: ignore[call-arg]
        OIDC_AUDIENCE="ari:cloud:bitbucket::workspace/abc",  # type: ignore[call-arg]
    )

    with capture_logs() as logs:
        strategy = select_strategy(settings)

    assert isinstance(strategy, OidcWebIdentityStrategy)
    # No WARN log should be emitted in the OIDC-only path
    precedence_logs = [
        lg for lg in logs if lg.get("event") == "auth.precedence.static_keys_won_over_oidc"
    ]
    assert len(precedence_logs) == 0


# ---------------------------------------------------------------------------
# AUTH-04 revised: static keys win over OIDC token + WARN log
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_select_strategy_static_keys_win_over_oidc_and_emits_warn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Static keys + OIDC token both present → static keys win; WARN log emitted (AUTH-04).

    Verifies: strategy is AssumeRoleStrategy (keys + role_arn), exactly one
    auth.precedence.static_keys_won_over_oidc WARN log with reason + hint fields.
    """
    monkeypatch.setenv("BITBUCKET_STEP_OIDC_TOKEN", "dummy.jwt.token")

    settings = Settings(
        AWS_ACCESS_KEY_ID="AKIAIOSFODNN7EXAMPLE",  # type: ignore[call-arg]
        AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",  # type: ignore[call-arg]
        ROLE_ARN="arn:aws:iam::123456789012:role/MyOidcRole",  # type: ignore[call-arg]
        OIDC_AUDIENCE="ari:cloud:bitbucket::workspace/abc",  # type: ignore[call-arg]
    )

    with capture_logs() as logs:
        strategy = select_strategy(settings)

    # Static keys win — result is AssumeRoleStrategy (role_arn is set)
    assert isinstance(strategy, AssumeRoleStrategy)

    # Exactly one WARN log for the precedence event
    precedence_logs = [
        lg for lg in logs if lg.get("event") == "auth.precedence.static_keys_won_over_oidc"
    ]
    assert len(precedence_logs) == 1
    log_entry = precedence_logs[0]
    assert log_entry.get("log_level") == "warning"
    assert "reason" in log_entry
    assert "hint" in log_entry


@pytest.mark.unit
def test_select_strategy_static_keys_without_oidc_token_does_not_emit_warn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Static keys only (no OIDC token) → no WARN log emitted."""
    # BITBUCKET_STEP_OIDC_TOKEN is absent (cleaned by autouse fixture)
    settings = Settings(
        AWS_ACCESS_KEY_ID="AKIAIOSFODNN7EXAMPLE",  # type: ignore[call-arg]
        AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",  # type: ignore[call-arg]
    )

    with capture_logs() as logs:
        strategy = select_strategy(settings)

    assert isinstance(strategy, StaticKeysStrategy)
    precedence_logs = [
        lg for lg in logs if lg.get("event") == "auth.precedence.static_keys_won_over_oidc"
    ]
    assert len(precedence_logs) == 0


# ---------------------------------------------------------------------------
# AUTH-06: misconfig error branches
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_select_strategy_oidc_token_without_role_arn_raises_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BITBUCKET_STEP_OIDC_TOKEN set but no ROLE_ARN → ConfigurationError (AUTH-06)."""
    monkeypatch.setenv("BITBUCKET_STEP_OIDC_TOKEN", "dummy.jwt.token")

    settings = Settings(
        OIDC_AUDIENCE="ari:cloud:bitbucket::workspace/abc",  # type: ignore[call-arg]
        # NO ROLE_ARN
    )

    with pytest.raises(ConfigurationError) as exc_info:
        select_strategy(settings)

    assert exc_info.value.exit_code == 1
    assert "OIDC requires ROLE_ARN" in str(exc_info.value)


@pytest.mark.unit
def test_select_strategy_token_and_role_arn_without_audience_raises_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Token + ROLE_ARN set but no OIDC_AUDIENCE → ConfigurationError (AUTH-06)."""
    monkeypatch.setenv("BITBUCKET_STEP_OIDC_TOKEN", "dummy.jwt.token")

    settings = Settings(
        ROLE_ARN="arn:aws:iam::123456789012:role/MyOidcRole",  # type: ignore[call-arg]
        # NO OIDC_AUDIENCE
    )

    with pytest.raises(ConfigurationError) as exc_info:
        select_strategy(settings)

    assert exc_info.value.exit_code == 1
    assert "OIDC_AUDIENCE is missing" in str(exc_info.value)
    assert "set OIDC_AUDIENCE to the Bitbucket workspace ARI" in str(exc_info.value)


@pytest.mark.unit
def test_select_strategy_role_arn_without_creds_error_message_mentions_oidc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ROLE_ARN set but no static keys and no OIDC token → updated AUTH-06 message mentions OIDC."""
    # No BITBUCKET_STEP_OIDC_TOKEN (cleaned by autouse fixture)
    settings = Settings(
        ROLE_ARN="arn:aws:iam::123456789012:role/X",  # type: ignore[call-arg]
        # No static keys, no OIDC token
    )

    with pytest.raises(ConfigurationError) as exc_info:
        select_strategy(settings)

    assert exc_info.value.exit_code == 1
    msg = str(exc_info.value)
    # Updated Phase 4 message — must mention OIDC as an alternative (AUTH-06)
    assert "ROLE_ARN requires AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY" in msg
    assert "BITBUCKET_STEP_OIDC_TOKEN + OIDC_AUDIENCE" in msg


@pytest.mark.unit
def test_select_strategy_no_credentials_at_all_raises_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No credentials set at all → ConfigurationError with no-creds message."""
    settings = Settings()  # all vars wiped by autouse fixture

    with pytest.raises(ConfigurationError) as exc_info:
        select_strategy(settings)

    assert exc_info.value.exit_code == 1
    assert "No valid credential configuration" in str(exc_info.value)
    assert "BITBUCKET_STEP_OIDC_TOKEN" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AUTH-03: OIDC strategy construction — session name, region, audience
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_select_strategy_oidc_strategy_receives_correct_session_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OIDC branch reuses _derive_session_name; session_name starts with 'aws-eks-helm-deploy-'."""
    monkeypatch.setenv("BITBUCKET_STEP_OIDC_TOKEN", "dummy.jwt.token")
    # Set a recognisable BITBUCKET_PIPELINE_UUID so we can assert the UUID is embedded
    monkeypatch.setenv("BITBUCKET_PIPELINE_UUID", "{xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}")

    settings = Settings(
        ROLE_ARN="arn:aws:iam::123456789012:role/MyOidcRole",  # type: ignore[call-arg]
        OIDC_AUDIENCE="ari:cloud:bitbucket::workspace/abc",  # type: ignore[call-arg]
    )
    strategy = select_strategy(settings)

    assert isinstance(strategy, OidcWebIdentityStrategy)
    # _derive_session_name strips braces and prepends the prefix
    assert strategy._session_name.startswith("aws-eks-helm-deploy-")
    assert "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" in strategy._session_name


@pytest.mark.unit
def test_select_strategy_oidc_strategy_receives_correct_region_and_audience(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OIDC strategy receives correct region and audience from settings."""
    monkeypatch.setenv("BITBUCKET_STEP_OIDC_TOKEN", "x")

    settings = Settings(
        AWS_REGION="us-east-1",  # type: ignore[call-arg]
        ROLE_ARN="arn:aws:iam::123456789012:role/MyOidcRole",  # type: ignore[call-arg]
        OIDC_AUDIENCE="ari:cloud:bitbucket::workspace/abc",  # type: ignore[call-arg]
    )
    strategy = select_strategy(settings)

    assert isinstance(strategy, OidcWebIdentityStrategy)
    assert strategy._region == "us-east-1"
    assert strategy._audience == "ari:cloud:bitbucket::workspace/abc"


@pytest.mark.unit
def test_select_strategy_oidc_strategy_oidc_token_matches_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OIDC strategy receives the exact token from BITBUCKET_STEP_OIDC_TOKEN."""
    monkeypatch.setenv("BITBUCKET_STEP_OIDC_TOKEN", "eyJhbGciOiJSUzI1NiJ9.payload.sig")

    settings = Settings(
        ROLE_ARN="arn:aws:iam::123456789012:role/MyOidcRole",  # type: ignore[call-arg]
        OIDC_AUDIENCE="ari:cloud:bitbucket::workspace/abc",  # type: ignore[call-arg]
    )
    strategy = select_strategy(settings)

    assert isinstance(strategy, OidcWebIdentityStrategy)
    assert strategy._oidc_token == "eyJhbGciOiJSUzI1NiJ9.payload.sig"  # noqa: S105


# ---------------------------------------------------------------------------
# Phase 2 regression: static-keys + AssumeRoleStrategy composition preserved
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_select_strategy_phase2_static_keys_plus_role_arn_regression(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 2 regression: static keys + ROLE_ARN still returns AssumeRoleStrategy."""
    # Ensure OIDC token is absent
    settings = Settings(
        AWS_ACCESS_KEY_ID="AKIAIOSFODNN7EXAMPLE",  # type: ignore[call-arg]
        AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",  # type: ignore[call-arg]
        ROLE_ARN="arn:aws:iam::123456789012:role/TestRole",  # type: ignore[call-arg]
    )

    with capture_logs() as logs:
        strategy = select_strategy(settings)

    assert isinstance(strategy, AssumeRoleStrategy)
    # Private-attr access: intentional (no public introspection API)
    assert isinstance(strategy._base, StaticKeysStrategy)
    # No WARN log — OIDC token is absent
    precedence_logs = [
        lg for lg in logs if lg.get("event") == "auth.precedence.static_keys_won_over_oidc"
    ]
    assert len(precedence_logs) == 0
