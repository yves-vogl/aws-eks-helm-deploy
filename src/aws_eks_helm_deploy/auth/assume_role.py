"""Composable STS AssumeRole on top of any AuthStrategy.

Requirements traceability:
  - AUTH-02: AssumeRoleStrategy wraps any base AuthStrategy and calls STS AssumeRole
    on top of its credentials, returning short-lived AwsCredentials with an expiration.

Rationale:
    This strategy is intentionally stateless — it calls the base strategy and STS on
    every get_credentials() invocation with no caching or token refresh. The pipe runs
    once and exits; a single STS call at startup is sufficient for the 1-hour window
    of an ordinary helm upgrade run.

    Composability: the base can be any object satisfying the AuthStrategy Protocol.
    Phase 2 uses StaticKeysStrategy as the base. Phase 4 will use OidcWebIdentityStrategy
    as the base — no change to this class is needed.

Security notes (STRIDE T-02-03-01 through T-02-03-04):
    - Error messages include only AWS-side Code + Message (never credential values).
    - endpoint_url is hardcoded to the regional STS endpoint — no global-endpoint fallback.
    - RoleSessionName is taken verbatim from the constructor
      (Plan 02-04 enforces length/char limits).
    - RoleArn unauthorised? → ClientError → AuthenticationError (AWS trust-policy controls access).
"""

from __future__ import annotations

import boto3
import boto3.session
import botocore.config
import botocore.exceptions
from mypy_boto3_sts.type_defs import CredentialsTypeDef

from aws_eks_helm_deploy.auth.base import AuthStrategy, AwsCredentials
from aws_eks_helm_deploy.errors import AuthenticationError, ConfigurationError

__all__: list[str] = ["AssumeRoleStrategy"]


class AssumeRoleStrategy:
    """Calls STS AssumeRole on top of any base AuthStrategy.

    Constructs a regional boto3.Session from the base strategy's credentials and
    calls ``sts.assume_role`` to obtain short-lived credentials. The returned
    AwsCredentials includes an expiration datetime from the STS response.

    Args:
        base: Any object satisfying the AuthStrategy Protocol. Called on every
            get_credentials() invocation — no base-strategy caching.
        role_arn: Full ARN of the IAM role to assume
            (e.g. ``arn:aws:iam::123456789012:role/MyRole``).
        session_name: RoleSessionName passed to STS verbatim.
            Callers (Plan 02-04) are responsible for enforcing the AWS 64-char
            limit and the ``[\\w+=,.@-]+`` character constraint.
        region: AWS region for the regional STS endpoint
            (e.g. ``eu-central-1``). Determines ``endpoint_url``.
    """

    def __init__(
        self,
        base: AuthStrategy,
        role_arn: str,
        session_name: str,
        region: str,
    ) -> None:
        self._base = base
        self._role_arn = role_arn
        self._session_name = session_name
        self._region = region

    def get_credentials(self) -> AwsCredentials:
        """Obtain short-lived credentials via STS AssumeRole.

        Calls the base strategy, constructs a regional boto3.Session, and calls
        ``sts.assume_role``. Returns an AwsCredentials with session_token and
        expiration populated from the STS response.

        Raises:
            AuthenticationError: STS returned a ClientError (e.g. AccessDenied,
                InvalidClientTokenId). Exit code 2.
            ConfigurationError: No AWS credentials available to sign the STS call.
                Exit code 1.
        """
        base_credentials = self._base.get_credentials()
        boto3_kwargs = base_credentials.to_boto3_kwargs()

        session = boto3.session.Session(
            region_name=self._region,
            aws_access_key_id=boto3_kwargs["aws_access_key_id"],
            aws_secret_access_key=boto3_kwargs["aws_secret_access_key"],
            aws_session_token=boto3_kwargs.get("aws_session_token"),
        )

        sts = session.client(
            "sts",
            endpoint_url=f"https://sts.{self._region}.amazonaws.com",
            config=botocore.config.Config(
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )

        try:
            # ExternalId: Phase 2 deferred — see AUTH-NEXT (Phase 4 + IAM template work)
            # Duration: omit DurationSeconds — accept AWS default 3600s per RESEARCH Section E
            response = sts.assume_role(
                RoleArn=self._role_arn,
                RoleSessionName=self._session_name,
            )
        except botocore.exceptions.ClientError as exc:
            code = exc.response["Error"]["Code"]
            message = exc.response["Error"]["Message"]
            raise AuthenticationError(f"STS AssumeRole failed [{code}]: {message}") from exc
        except botocore.exceptions.NoCredentialsError as exc:
            raise ConfigurationError("No AWS credentials found for STS AssumeRole") from exc

        creds: CredentialsTypeDef = response["Credentials"]
        return AwsCredentials(
            access_key_id=creds["AccessKeyId"],
            secret_access_key=creds["SecretAccessKey"],
            session_token=creds["SessionToken"],
            expiration=creds["Expiration"],
        )
