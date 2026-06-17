"""Static-keys strategy — wraps env-supplied keys into an AwsCredentials. No AWS calls.

Requirements traceability:
  - AUTH-01: StaticKeysStrategy is a concrete implementation of the AuthStrategy Protocol.
    It accepts explicitly-provided AWS key material and returns a plain AwsCredentials
    value object without making any AWS API calls.

Design note:
    This class is intentionally trivial. All presence/format validation of the
    underlying key values happens upstream in Settings (pydantic). This class
    trusts that its constructor arguments are valid non-empty strings.

    expiration is NEVER set — long-term IAM key pairs have no expiration.
    STS-sourced temporary credentials (which do have an expiration) come from
    AssumeRoleStrategy, not from this class.
"""

from __future__ import annotations

from aws_eks_helm_deploy.auth.base import AwsCredentials

__all__: list[str] = ["StaticKeysStrategy"]


class StaticKeysStrategy:
    """Wraps static AWS access key material into an AwsCredentials value object.

    No AWS API calls are made. The class satisfies the AuthStrategy Protocol
    structurally (has a get_credentials() method returning AwsCredentials).

    Args:
        access_key_id: AWS access key ID (e.g. ``AKIAIOSFODNN7EXAMPLE``).
        secret_access_key: Corresponding secret access key.
        session_token: Optional session token for temporary credentials
            (e.g. when the base environment already uses assumed-role creds).
            Defaults to ``None`` for long-term IAM key pairs.
    """

    def __init__(
        self,
        access_key_id: str,
        secret_access_key: str,
        session_token: str | None = None,
    ) -> None:
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._session_token = session_token

    def get_credentials(self) -> AwsCredentials:
        """Return an AwsCredentials constructed from the key material supplied at init.

        Returns the same credential values on every call (the strategy is stateless).
        expiration is always None — long-term keys have no expiration.
        """
        return AwsCredentials(
            access_key_id=self._access_key_id,
            secret_access_key=self._secret_access_key,
            session_token=self._session_token,
        )
