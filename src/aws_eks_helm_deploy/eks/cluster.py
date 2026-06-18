"""ClusterAccess value object + boto3 describe_cluster wrapper for aws-eks-helm-deploy.

Requirements traceability:
  - PIPE-01 prerequisite: provides the endpoint + CA data that kube/kubeconfig.py
    writes into the helm-readable kubeconfig.

Security note (T-03-01): ca_data is base64-encoded public certificate material;
passed through verbatim per Pitfall 1 — do NOT base64-decode it before writing
to the kubeconfig. The certificate-authority-data field in the kubeconfig expects
the already-base64-encoded form returned by the EKS API.

Session contract: this module accepts a pre-constructed boto3.Session. Session
credential validity is the CALLER's responsibility (Plan 03-04's composition root
validates upstream via select_strategy). NoCredentialsError and similar session
errors propagate unmodified and are caught by cli.main()'s top-level except.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import boto3.session
import botocore.exceptions

from aws_eks_helm_deploy.errors import ClusterAccessError

if TYPE_CHECKING:
    pass

__all__: list[str] = ["ClusterAccess", "get_cluster_access"]


@dataclasses.dataclass(frozen=True)
class ClusterAccess:
    """Immutable EKS cluster access descriptor.

    Produced by get_cluster_access(); consumed by kube/kubeconfig.write_kubeconfig().

    Fields:
        name: EKS cluster name (= CLUSTER_NAME env var). Doubles as the kubeconfig
            context name per CONTEXT D7.
        endpoint: HTTPS URL for the EKS API server (from describe_cluster response).
        ca_data: Base64-encoded CA certificate from certificateAuthority.data.
            Passed through VERBATIM — never decoded (Pitfall 1 mitigation).
        region: AWS region where the cluster lives.
    """

    name: str
    endpoint: str
    ca_data: str
    region: str


def get_cluster_access(
    session: boto3.session.Session,
    cluster_name: str,
    region: str,
) -> ClusterAccess:
    """Fetch EKS cluster endpoint and CA certificate from the AWS API.

    Args:
        session: Pre-configured boto3.Session with caller-provided credentials.
            Session credential validity is the caller's responsibility.
        cluster_name: EKS cluster name to describe.
        region: AWS region where the cluster lives.

    Returns:
        ClusterAccess frozen dataclass with endpoint, ca_data, and region.

    Raises:
        ClusterAccessError: If botocore raises ClientError (e.g. cluster not found,
            access denied). Extracts the AWS error code and message for the error
            message. Exit code 3.
    """
    eks = session.client("eks", region_name=region)
    try:
        resp = eks.describe_cluster(name=cluster_name)
    except botocore.exceptions.ClientError as exc:
        code: str = exc.response["Error"]["Code"]
        message: str = exc.response["Error"]["Message"]
        raise ClusterAccessError(f"EKS describe_cluster failed [{code}]: {message}") from exc
    cluster = resp["cluster"]
    return ClusterAccess(
        name=cluster_name,
        endpoint=cluster["endpoint"],
        ca_data=cluster["certificateAuthority"]["data"],
        region=region,
    )
