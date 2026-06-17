"""EKS bearer-token generator for aws-eks-helm-deploy.

Requirements traceability:
  - AUTH-07: pure-boto3 EKS token generation (no awscli import)

Pure-boto3 — does NOT import awscli; verified by grep gate in 02-VALIDATION.md.
Implements the same algorithm as awscli.customizations.eks.get_token without
importing awscli. Uses botocore's event system to inject x-k8s-aws-id into
the presigned STS GetCallerIdentity URL so it appears in X-Amz-SignedHeaders.

References:
  - awscli source: github.com/aws/aws-cli/blob/develop/awscli/customizations/eks/get_token.py
  - aws-iam-authenticator: github.com/kubernetes-sigs/aws-iam-authenticator/
    blob/master/pkg/token/token.go
"""

from __future__ import annotations

import base64
from typing import Any, Final  # Any needed for botocore event handler params

import boto3.session
import botocore.config
import botocore.exceptions

from aws_eks_helm_deploy.errors import EksTokenError

# ---------------------------------------------------------------------------
# Module-level constants (all Final per AUTH-07 spec; match upstream values)
# ---------------------------------------------------------------------------

TOKEN_PREFIX: Final[str] = "k8s-aws-v1."  # noqa: S105 — not a password; EKS token format prefix
"""Literal prefix prepended to every EKS bearer token."""

K8S_AWS_ID_HEADER: Final[str] = "x-k8s-aws-id"
"""HTTP header carrying the EKS cluster name; must be signed into the URL."""

URL_TIMEOUT: Final[int] = 60
"""X-Amz-Expires value in seconds; hardcoded per upstream spec (not configurable)."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_eks_token(
    session: boto3.session.Session,
    cluster_name: str,
    region: str,
) -> str:
    """Generate a k8s-aws-v1.<base64url> bearer token for EKS via pure boto3.

    Replicates the algorithm from awscli.customizations.eks.get_token without
    importing awscli. The x-k8s-aws-id header is injected into the presigned
    URL via botocore events so it appears in X-Amz-SignedHeaders=host;x-k8s-aws-id.

    Args:
        session: A boto3.Session pre-configured with the desired AWS credentials.
            The caller is responsible for credential selection (see auth/base.py).
        cluster_name: EKS cluster name (becomes the x-k8s-aws-id header value).
            Signed into the URL via SigV4 HMAC — changing the name changes the token.
        region: AWS region where the cluster lives.
            Determines the regional STS endpoint (`sts.{region}.amazonaws.com`).

    Returns:
        Bearer token string starting with 'k8s-aws-v1.' and containing no
        '=' padding characters (base64url-no-padding per upstream spec).

    Raises:
        EksTokenError: If botocore raises ClientError (e.g. invalid credentials,
            STS service errors) or NoCredentialsError (session misconfiguration).
    """
    # Always use the regional STS endpoint — the global endpoint is rejected
    # by most EKS clusters (T-02-01-03 mitigation).
    sts = session.client(
        "sts",
        endpoint_url=f"https://sts.{region}.amazonaws.com",
        config=botocore.config.Config(
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )

    # Closure-based header store: carries the x-k8s-aws-id value across
    # the two event handlers. A local dict (not module-level state) avoids
    # any inter-call collision if multiple sessions are used concurrently.
    _header_store: dict[str, str] = {}

    def _retrieve_header(
        params: dict[str, Any],
        **kwargs: Any,  # noqa: ANN401 — botocore event kwargs are untyped
    ) -> None:
        """Extract x-k8s-aws-id from Params before botocore validates them.

        Passing x-k8s-aws-id directly in Params would raise ParamValidationError
        (STS GetCallerIdentity has no such parameter). We always pass the header
        in Params (see generate_presigned_url call below), so this handler always
        finds and extracts it. The pop() prevents botocore's param-validation from
        seeing the unsupported key.
        """
        _header_store["value"] = str(params.pop(K8S_AWS_ID_HEADER))

    def _inject_header(
        request: Any,  # noqa: ANN401 — AWSPreparedRequest; no usable botocore type stub
        **kwargs: Any,  # noqa: ANN401 — botocore event kwargs are untyped
    ) -> None:
        """Inject x-k8s-aws-id into the request before SigV4 signing.

        This fires after _retrieve_header (different event) and before signing,
        so the header value is included in X-Amz-SignedHeaders (T-02-01-04
        mitigation). The `request` argument is botocore's AWSPreparedRequest
        whose .headers is a plain dict; botocore's type stubs provide no
        more-specific type for before-sign event arguments.
        """
        # botocore types `request` as Any; .headers attribute access is safe at runtime.
        # The ANN401 noqa above is accepted: botocore provides no typed stub for this arg.
        request.headers[K8S_AWS_ID_HEADER] = _header_store["value"]

    sts.meta.events.register(
        "provide-client-params.sts.GetCallerIdentity",
        _retrieve_header,
    )
    sts.meta.events.register(
        "before-sign.sts.GetCallerIdentity",
        _inject_header,
    )

    try:
        url: str = sts.generate_presigned_url(
            "get_caller_identity",
            Params={K8S_AWS_ID_HEADER: cluster_name},
            ExpiresIn=URL_TIMEOUT,
            HttpMethod="GET",
        )
    except botocore.exceptions.ClientError as exc:
        code = exc.response["Error"]["Code"]
        message = exc.response["Error"]["Message"]
        raise EksTokenError(f"EKS token generation failed [{code}]: {message}") from exc
    except botocore.exceptions.NoCredentialsError as exc:
        raise EksTokenError("No AWS credentials available for EKS token generation") from exc

    encoded = base64.urlsafe_b64encode(url.encode("utf-8")).decode("utf-8").rstrip("=")
    return TOKEN_PREFIX + encoded
