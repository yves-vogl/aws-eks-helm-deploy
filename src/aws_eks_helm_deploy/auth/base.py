"""AuthStrategy Protocol and AwsCredentials value object for aws-eks-helm-deploy.

Requirements traceability:
  - AUTH-01: defines the AuthStrategy Protocol (structural typing contract) and the
    AwsCredentials frozen dataclass consumed by all strategy implementations.

Security note (STRIDE T-02-02-01 / T-02-02-02 / T-02-02-03):
  - AwsCredentials.__repr__ masks secret_access_key and shows only the last 4 chars
    of access_key_id — safe to pass to get_logger() or structlog context values.
  - AwsCredentials.to_boto3_kwargs() produces keys that ARE in CREDENTIAL_BLOCKLIST;
    callers MUST NOT spread raw creds into bind_safe_context() — that raises ValueError.
  - frozen=True means mutation raises FrozenInstanceError — credentials cannot be
    silently rotated after construction.

Class definition order: AwsCredentials FIRST, AuthStrategy SECOND (Protocol references
the dataclass in its method signature). `from __future__ import annotations` defers all
annotation evaluation so forward references work without quoting.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Protocol, runtime_checkable

__all__: list[str] = ["AuthStrategy", "AwsCredentials"]


@dataclasses.dataclass(frozen=True)
class AwsCredentials:
    """Immutable AWS credential set produced by an AuthStrategy.

    The __repr__ masks sensitive fields — safe to pass to get_logger().
    Never log or bind the actual secret values directly.

    Fields:
        access_key_id: IAM access key ID (starts with AKIA for long-term,
            ASIA for temporary/assumed-role credentials).
        secret_access_key: The secret part of the key pair. Never logged.
        session_token: Required for temporary credentials (assumed-role, session-token).
            None for long-term IAM user key pairs.
        expiration: UTC datetime when temporary credentials expire.
            None for long-term keys. NOT passed to boto3 (metadata only).
    """

    access_key_id: str
    secret_access_key: str
    session_token: str | None = None
    expiration: datetime | None = None

    def __repr__(self) -> str:
        """Return a masked representation safe for logging.

        Shows only the last 4 characters of access_key_id (prefixed with '...'),
        or '****' if the key is shorter than 4 characters.
        secret_access_key is always shown as '<redacted>'.
        session_token presence is indicated as '<redacted>' (never the value).
        expiration is omitted entirely (informational only, per DEVIATION 1).
        """
        tail = self.access_key_id[-4:] if len(self.access_key_id) >= 4 else "****"
        base = f"AwsCredentials(access_key_id=...{tail}, secret_access_key=<redacted>"
        if self.session_token is not None:
            return base + ", session_token=<redacted>)"
        return base + ")"

    def to_boto3_kwargs(self) -> dict[str, str]:
        """Return a dict suitable for spreading into boto3.Session() or client().

        Keys produced: aws_access_key_id, aws_secret_access_key, and optionally
        aws_session_token (only when session_token is not None). The expiration
        field is intentionally excluded — it is not a boto3 Session kwarg.

        Security note: These keys are in CREDENTIAL_BLOCKLIST. Spreading the
        returned dict into bind_safe_context() will raise ValueError — this is
        the intended behavior (see T-02-02-02).
        """
        kwargs: dict[str, str] = {
            "aws_access_key_id": self.access_key_id,
            "aws_secret_access_key": self.secret_access_key,
        }
        if self.session_token is not None:
            kwargs["aws_session_token"] = self.session_token
        return kwargs


@runtime_checkable
class AuthStrategy(Protocol):
    """Protocol satisfied by any AWS credential provider.

    Implementations: StaticKeysStrategy (Plan 02-03), AssumeRoleStrategy (Plan 02-03),
    OidcWebIdentityStrategy (Phase 4). No inheritance required — structural typing only.

    @runtime_checkable enables isinstance(obj, AuthStrategy) checks in select_strategy()
    and in tests. Runtime check verifies the method NAME only, not the signature.
    """

    def get_credentials(self) -> AwsCredentials:
        """Return a set of AWS credentials.

        Must not cache or refresh internally. The pipe calls this once at startup
        and discards the credentials after the helm action completes.
        """
        ...
