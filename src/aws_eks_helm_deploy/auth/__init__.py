"""Auth subpackage — composition root for AWS credential strategy selection.

Requirements traceability:
  - AUTH-01: select_strategy() is the public composition root that maps Settings
    to a concrete AuthStrategy implementation.
  - AUTH-02: AssumeRoleStrategy is composable on top of any base — select_strategy()
    wraps StaticKeysStrategy with AssumeRoleStrategy when ROLE_ARN is present.
  - AUTH-03: OidcWebIdentityStrategy (Phase 4) — exchanges a Bitbucket OIDC JWT
    for short-lived STS credentials via AssumeRoleWithWebIdentity.
  - AUTH-04 (revised): static keys take precedence over OIDC token per botocore
    default chain order. A WARN log surfaces the precedence when both are present.
  - AUTH-06: select_strategy() raises ConfigurationError for misconfig cases
    (OIDC token without ROLE_ARN; OIDC token + ROLE_ARN without OIDC_AUDIENCE;
    ROLE_ARN without any base credentials).

Decision-tree pseudocode (for grep / quick reference — mirrors botocore default chain):
    if aws_access_key_id AND aws_secret_access_key:   # static keys win (AUTH-04)
        [WARN if BITBUCKET_STEP_OIDC_TOKEN also present]
        base = StaticKeysStrategy(key_id, secret, session_token)
        if role_arn:
            return AssumeRoleStrategy(base, role_arn, session_name, region)
        return base
    oidc_token = os.environ.get("BITBUCKET_STEP_OIDC_TOKEN")
    if oidc_token:                                     # OIDC branch (AUTH-03)
        if not role_arn: raise ConfigurationError      # AUTH-06
        if not oidc_audience: raise ConfigurationError # AUTH-06
        return OidcWebIdentityStrategy(oidc_token, role_arn, oidc_audience, session_name, region)
    if role_arn:
        raise ConfigurationError                       # ROLE_ARN without base (AUTH-06)
    raise ConfigurationError                           # no creds at all

NOTE: Reading BITBUCKET_STEP_OIDC_TOKEN directly from os.environ is a documented deviation
from the "no os.environ outside settings.py" rule — same category as _derive_session_name's
reads of BITBUCKET_PIPELINE_UUID / BITBUCKET_BUILD_NUMBER. The token is Bitbucket-platform-
supplied (not consumer-supplied via pipe.yml), and storing it in Settings would tempt callers
to log the entire settings object, leaking the token. The exception is recorded in
04-03-PLAN.md Deviation 1.

Public exports (importable from aws_eks_helm_deploy.auth):
    select_strategy, AuthStrategy, AwsCredentials, StaticKeysStrategy, AssumeRoleStrategy,
    OidcWebIdentityStrategy
"""

from __future__ import annotations

import os
import re
import uuid
from typing import TYPE_CHECKING, Final

from aws_eks_helm_deploy.auth.assume_role import AssumeRoleStrategy
from aws_eks_helm_deploy.auth.base import AuthStrategy, AwsCredentials
from aws_eks_helm_deploy.auth.oidc import OidcWebIdentityStrategy
from aws_eks_helm_deploy.auth.static_keys import StaticKeysStrategy
from aws_eks_helm_deploy.errors import ConfigurationError
from aws_eks_helm_deploy.logging import get_logger

if TYPE_CHECKING:
    from aws_eks_helm_deploy.settings import Settings

logger = get_logger(__name__)

__all__: list[str] = [
    "AssumeRoleStrategy",
    "AuthStrategy",
    "AwsCredentials",
    "OidcWebIdentityStrategy",
    "StaticKeysStrategy",
    "select_strategy",
]

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_DEFAULT_SESSION_NAME: Final[str] = "BitbucketPipe"
"""Sentinel matching the default in Settings.session_name.

When session_name equals this value, _derive_session_name() assumes the consumer
did NOT explicitly set SESSION_NAME and falls through to the Bitbucket / UUID chain.
"""

_SESSION_NAME_MAX_LEN: Final[int] = 64
"""AWS IAM RoleSessionName hard limit (characters)."""

_SESSION_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"[\w+=,.@-]+")
"""AWS IAM character class for RoleSessionName: [\\w+=,.@-]+."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _derive_session_name(settings: Settings) -> str:
    """Derive a RoleSessionName that satisfies AWS IAM constraints.

    Four-step fallback chain:
    1. Consumer explicitly set SESSION_NAME (differs from default) → honor it,
       enforce 64-char limit. If the value does not match the IAM pattern
       ([\\w+=,.@-]+) it silently falls through to step 4 (UUID).
    2. BITBUCKET_PIPELINE_UUID env var is set → strip surrounding braces,
       prepend "aws-eks-helm-deploy-", truncate to 64 chars.
    3. BITBUCKET_BUILD_NUMBER env var is set → prepend "aws-eks-helm-deploy-",
       truncate to 64 chars.
    4. UUID4 fallback → f"aws-eks-helm-deploy-{uuid.uuid4()}", truncated to 64 chars.

    NOTE: Reading os.environ for BITBUCKET_PIPELINE_UUID and BITBUCKET_BUILD_NUMBER
    is a documented deviation from the "no os.environ outside settings.py" rule.
    These are Bitbucket-platform-supplied variables (not consumer-supplied via pipe.yml)
    and are used only for session-name derivation (traceability in CloudTrail).

    All returned values satisfy:
      - len(name) <= 64
      - re.fullmatch(r"[\\w+=,.@-]+", name) is not None
    """
    # Step 1: consumer explicitly set SESSION_NAME
    if settings.session_name != _DEFAULT_SESSION_NAME:
        candidate = settings.session_name[:_SESSION_NAME_MAX_LEN]
        if _SESSION_NAME_PATTERN.fullmatch(candidate):
            return candidate
        # Invalid chars → fall through to UUID (step 4)

    # Step 2: Bitbucket pipeline UUID (platform-supplied, not consumer-controlled)
    pipeline_uuid = os.environ.get("BITBUCKET_PIPELINE_UUID")
    if pipeline_uuid is not None:
        stripped = pipeline_uuid.strip("{}").strip()
        candidate = f"aws-eks-helm-deploy-{stripped}"[:_SESSION_NAME_MAX_LEN]
        return candidate

    # Step 3: Bitbucket build number (fallback when UUID not set, e.g. local runs)
    build_number = os.environ.get("BITBUCKET_BUILD_NUMBER")
    if build_number is not None:
        candidate = f"aws-eks-helm-deploy-{build_number}"[:_SESSION_NAME_MAX_LEN]
        return candidate

    # Step 4: UUID fallback — always valid per IAM pattern
    return f"aws-eks-helm-deploy-{uuid.uuid4()}"[:_SESSION_NAME_MAX_LEN]


# ---------------------------------------------------------------------------
# Public composition root
# ---------------------------------------------------------------------------


def select_strategy(settings: Settings) -> AuthStrategy:
    """Choose an AuthStrategy implementation based on available Settings.

    Decision outcomes (mirrors boto3 default credential resolver chain per CONTEXT D1):
    1. StaticKeysStrategy — AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY set, no ROLE_ARN.
    2. AssumeRoleStrategy(base=StaticKeysStrategy, ...) — keys + ROLE_ARN both set.
    3. OidcWebIdentityStrategy — BITBUCKET_STEP_OIDC_TOKEN + ROLE_ARN + OIDC_AUDIENCE set,
       NO static keys (static keys win if both are present — see WARN log).
    4. ConfigurationError (exit_code=1) — misconfig (ROLE_ARN without base;
       OIDC token without ROLE_ARN; OIDC token without OIDC_AUDIENCE).
    5. ConfigurationError (exit_code=1) — no credentials at all.

    WARN log:
      When static keys win over a present OIDC token, a one-time
      ``auth.precedence.static_keys_won_over_oidc`` WARN log surfaces the precedence
      (revised AUTH-04 per 04-CONTEXT D1).

    NOTE: BITBUCKET_STEP_OIDC_TOKEN is read directly from os.environ (documented
    deviation — see module docstring and 04-03-PLAN.md Deviation 1).

    Args:
        settings: Validated pipe settings from environment variables.

    Returns:
        An AuthStrategy instance ready to call get_credentials() on.

    Raises:
        ConfigurationError: When the credential configuration is incomplete
            or entirely absent (exit code 1).
    """
    # Branch 1: static keys (AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY) — always win.
    # Per botocore default chain order, explicit env-var keys take precedence over OIDC.
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        # WARN: if an OIDC token is also present, it will be silently ignored (AUTH-04).
        if os.environ.get("BITBUCKET_STEP_OIDC_TOKEN"):
            logger.warning(
                "auth.precedence.static_keys_won_over_oidc",
                reason="AWS_ACCESS_KEY_ID is set and takes precedence per botocore chain order",
                hint="Unset AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY in pipe.yml to use OIDC",
            )
        base: AuthStrategy = StaticKeysStrategy(
            settings.aws_access_key_id,
            settings.aws_secret_access_key,
            settings.aws_session_token,  # may be None
        )
        if settings.role_arn:
            session_name = _derive_session_name(settings)
            return AssumeRoleStrategy(base, settings.role_arn, session_name, settings.aws_region)
        return base

    # Branch 2: OIDC web identity (BITBUCKET_STEP_OIDC_TOKEN + ROLE_ARN + OIDC_AUDIENCE).
    # Placed AFTER static-keys branch per R2 + CONTEXT D1 botocore chain order.
    # NOTE: reading BITBUCKET_STEP_OIDC_TOKEN from os.environ is a documented deviation —
    # see module docstring and 04-03-PLAN.md Deviation 1.
    oidc_token = os.environ.get("BITBUCKET_STEP_OIDC_TOKEN")
    if oidc_token:
        if not settings.role_arn:
            raise ConfigurationError(
                "BITBUCKET_STEP_OIDC_TOKEN is set but ROLE_ARN is missing — "
                "OIDC requires ROLE_ARN to assume"
            )
        if not settings.oidc_audience:
            raise ConfigurationError(
                "BITBUCKET_STEP_OIDC_TOKEN is set but OIDC_AUDIENCE is missing — "
                "set OIDC_AUDIENCE to the Bitbucket workspace ARI"
            )
        session_name = _derive_session_name(settings)
        return OidcWebIdentityStrategy(
            oidc_token=oidc_token,
            role_arn=settings.role_arn,
            audience=settings.oidc_audience,
            session_name=session_name,
            region=settings.aws_region,
        )

    # Branch 3: ROLE_ARN present but no base credentials (neither static keys nor OIDC token).
    if settings.role_arn:
        raise ConfigurationError(
            "ROLE_ARN requires AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY, "
            "or BITBUCKET_STEP_OIDC_TOKEN + OIDC_AUDIENCE"
        )

    # Branch 4: no credentials at all.
    raise ConfigurationError(
        "No valid credential configuration: set AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY, "
        "or BITBUCKET_STEP_OIDC_TOKEN + OIDC_AUDIENCE + ROLE_ARN"
    )
