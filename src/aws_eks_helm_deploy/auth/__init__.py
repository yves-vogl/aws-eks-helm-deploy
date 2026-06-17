"""Auth subpackage — composition root for AWS credential strategy selection.

Requirements traceability:
  - AUTH-01: select_strategy() is the public composition root that maps Settings
    to a concrete AuthStrategy implementation.
  - AUTH-02: AssumeRoleStrategy is composable on top of any base — select_strategy()
    wraps StaticKeysStrategy with AssumeRoleStrategy when ROLE_ARN is present.

Decision-tree pseudocode (for grep / quick reference):
    # Phase 4: insert OIDC check here (OidcWebIdentityStrategy)
    if aws_access_key_id AND aws_secret_access_key:
        base = StaticKeysStrategy(key_id, secret, session_token)
        if role_arn:
            return AssumeRoleStrategy(base, role_arn, session_name, region)
        return base
    if role_arn:
        raise ConfigurationError  # OIDC-base ships in Phase 4
    raise ConfigurationError      # no creds at all

Public exports (importable from aws_eks_helm_deploy.auth):
    select_strategy, AuthStrategy, AwsCredentials, StaticKeysStrategy, AssumeRoleStrategy
"""

from __future__ import annotations

import os
import re
import uuid
from typing import TYPE_CHECKING, Final

from aws_eks_helm_deploy.auth.assume_role import AssumeRoleStrategy
from aws_eks_helm_deploy.auth.base import AuthStrategy, AwsCredentials
from aws_eks_helm_deploy.auth.static_keys import StaticKeysStrategy
from aws_eks_helm_deploy.errors import ConfigurationError

if TYPE_CHECKING:
    from aws_eks_helm_deploy.settings import Settings

__all__: list[str] = [
    "AssumeRoleStrategy",
    "AuthStrategy",
    "AwsCredentials",
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

    Decision outcomes:
    1. StaticKeysStrategy — AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY set, no ROLE_ARN.
    2. AssumeRoleStrategy(base=StaticKeysStrategy, ...) — keys + ROLE_ARN both set.
    3. ConfigurationError (exit_code=1) — ROLE_ARN set without base credentials
       (OIDC-based assumption ships in Phase 4).
    4. ConfigurationError (exit_code=1) — neither keys nor ROLE_ARN configured.

    Args:
        settings: Validated pipe settings from environment variables.

    Returns:
        An AuthStrategy instance ready to call get_credentials() on.

    Raises:
        ConfigurationError: When the credential configuration is incomplete
            or entirely absent (exit code 1).
    """
    # Phase 4: insert OIDC check here (OidcWebIdentityStrategy)
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        base: AuthStrategy = StaticKeysStrategy(
            settings.aws_access_key_id,
            settings.aws_secret_access_key,
            settings.aws_session_token,  # may be None
        )
        if settings.role_arn:
            session_name = _derive_session_name(settings)
            return AssumeRoleStrategy(base, settings.role_arn, session_name, settings.aws_region)
        return base

    if settings.role_arn:
        raise ConfigurationError(
            "ROLE_ARN requires AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY "
            "(OIDC-based role assumption ships in Phase 4)"
        )

    raise ConfigurationError(
        "No valid credential configuration: set AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY"
    )
