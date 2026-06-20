"""OidcWebIdentityStrategy — exchanges a Bitbucket OIDC JWT for short-lived AWS credentials.

Requirements traceability:
  - AUTH-03: implements the OIDC web-identity credential provider using
    STS AssumeRoleWithWebIdentity with botocore.UNSIGNED (unauthenticated call).

Security note (STRIDE T-04-03-01 / T-04-03-03 / T-04-03-04):
  - The pipe does NOT re-validate the OIDC JWT — STS validates the ``aud`` claim
    against the OIDC provider's JWKS. The ``audience`` constructor argument is recorded
    for traceability/debug logging only. The IAM trust-policy template
    (Plan 04-04 / docs/guides/oidc-setup.md) is the consumer-side gate that constrains
    which ``aud`` values can assume the role.
  - ``botocore.UNSIGNED`` is required (R3 mitigation): ``AssumeRoleWithWebIdentity`` is
    an unauthenticated STS call — the authentication IS the OIDC JWT. Without UNSIGNED,
    the default boto3 Session would raise ``NoCredentialsError`` before the request goes
    out over the wire.
  - The ``_oidc_token`` private attribute is accessed ONLY inside ``get_credentials()``
    and passed as ``WebIdentityToken=`` to the STS call. No ``__repr__`` override is
    defined — the default object repr shows the memory address, not field values
    (T-04-03-01 mitigation).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import boto3
import boto3.session
import botocore.config
import botocore.exceptions
from botocore import UNSIGNED

from aws_eks_helm_deploy.auth.base import AwsCredentials
from aws_eks_helm_deploy.errors import AuthenticationError

if TYPE_CHECKING:
    # `mypy_boto3_sts` is a dev-only type-stub package; it is NOT installed in
    # the runtime image. Guard the import so the runtime module load does not
    # fail with ModuleNotFoundError on the published Docker image.
    from mypy_boto3_sts.type_defs import CredentialsTypeDef

__all__: list[str] = ["OidcWebIdentityStrategy"]


class OidcWebIdentityStrategy:
    """Exchanges a Bitbucket OIDC JWT for short-lived AWS credentials.

    Calls STS ``AssumeRoleWithWebIdentity`` with ``botocore.UNSIGNED`` — the call is
    authenticated by the OIDC JWT itself, not by pre-existing AWS credentials.

    AUTH-03 mechanic:
      1. Build an unauthenticated ``boto3.session.Session`` for the target region.
      2. Build a regional STS client with ``signature_version=UNSIGNED``.
      3. Call ``assume_role_with_web_identity(RoleArn, RoleSessionName, WebIdentityToken)``.
         No audience kwarg — the audience is encoded in the JWT's ``aud`` claim and
         validated by STS against the IAM trust-policy condition key (CONTEXT D2).
      4. Map the STS ``Credentials`` block to a frozen ``AwsCredentials`` and return it.

    Args:
        oidc_token: The OIDC JWT from ``BITBUCKET_STEP_OIDC_TOKEN`` (set by ``select_strategy``).
        role_arn: Full ARN of the IAM role to assume.
        audience: Bitbucket workspace ARI from ``OIDC_AUDIENCE``. INFORMATIONAL ONLY —
            NOT passed to STS. The audience is encoded in the JWT; STS reads the ``aud``
            claim itself and matches it against the IAM trust-policy condition.
        session_name: RoleSessionName passed to STS verbatim (derived by ``_derive_session_name``).
        region: AWS region for the regional STS endpoint (e.g. ``eu-central-1``).
    """

    def __init__(
        self,
        oidc_token: str,
        role_arn: str,
        audience: str,
        session_name: str,
        region: str,
    ) -> None:
        self._oidc_token = oidc_token
        self._role_arn = role_arn
        self._audience = audience  # NOT passed to STS — stored for traceability only
        self._session_name = session_name
        self._region = region

    def get_credentials(self) -> AwsCredentials:
        """Obtain short-lived credentials via STS AssumeRoleWithWebIdentity.

        Builds an unauthenticated STS client (``signature_version=UNSIGNED``) and calls
        ``assume_role_with_web_identity``. No pre-existing AWS credentials are required.

        Returns:
            A frozen ``AwsCredentials`` with ``access_key_id`` starting with ``ASIA``
            (temporary-credential prefix), a non-None ``session_token``, and an
            ``expiration`` datetime from the STS response.

        Raises:
            AuthenticationError: STS returned a ``ClientError`` (e.g. ``InvalidIdentityToken``,
                ``AccessDenied``). Exit code 2. The AWS error code and message are embedded
                in the exception message for operator diagnostics.
        """
        session = boto3.session.Session(region_name=self._region)
        sts = session.client(
            "sts",
            endpoint_url=f"https://sts.{self._region}.amazonaws.com",
            config=botocore.config.Config(
                retries={"max_attempts": 3, "mode": "standard"},
                signature_version=UNSIGNED,
            ),
        )

        try:
            response = sts.assume_role_with_web_identity(
                RoleArn=self._role_arn,
                RoleSessionName=self._session_name,
                WebIdentityToken=self._oidc_token,
                # NOTE: The audience is NOT passed here — the aud claim is inside the JWT.
                # STS reads it and validates against the IAM trust-policy condition key.
                # The AssumeRoleWithWebIdentity API does not accept an audience parameter.
            )
        except botocore.exceptions.ClientError as exc:
            code = exc.response["Error"]["Code"]
            message = exc.response["Error"]["Message"]
            raise AuthenticationError(
                f"STS AssumeRoleWithWebIdentity failed [{code}]: {message}"
            ) from exc

        creds: CredentialsTypeDef = response["Credentials"]
        return AwsCredentials(
            access_key_id=creds["AccessKeyId"],
            secret_access_key=creds["SecretAccessKey"],
            session_token=creds["SessionToken"],
            expiration=creds["Expiration"],
        )
