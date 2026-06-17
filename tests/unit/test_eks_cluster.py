"""Unit tests for ClusterAccess + get_cluster_access (PIPE-01 prerequisite).

Uses moto 5.2.2 @mock_aws to spin up an EKS cluster fixture in-memory;
no real AWS account required.
"""

from __future__ import annotations

import dataclasses

import boto3
import pytest
from moto import mock_aws

from aws_eks_helm_deploy.eks.cluster import ClusterAccess, get_cluster_access
from aws_eks_helm_deploy.errors import ClusterAccessError

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

_DUMMY_CREDS = {
    "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "region_name": "eu-central-1",
}


def _create_eks_cluster(session: boto3.session.Session, name: str, region: str) -> dict:  # type: ignore[type-arg]
    """Create a moto-backed EKS cluster and return the response dict."""
    client = session.client("eks", region_name=region)
    return client.create_cluster(
        name=name,
        roleArn="arn:aws:iam::123456789012:role/eks-mock",
        resourcesVpcConfig={"subnetIds": ["subnet-12345678"]},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_module_imports_without_session() -> None:
    """ClusterAccess and get_cluster_access are importable with no AWS calls."""
    import aws_eks_helm_deploy.eks.cluster as _m

    assert hasattr(_m, "ClusterAccess")
    assert hasattr(_m, "get_cluster_access")


@pytest.mark.unit
def test_cluster_access_is_frozen_dataclass() -> None:
    """ClusterAccess is a frozen dataclass; mutation raises FrozenInstanceError."""
    assert dataclasses.is_dataclass(ClusterAccess)
    obj = ClusterAccess(
        name="test",
        endpoint="https://example.com",
        ca_data="abc123",
        region="eu-central-1",
    )
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        obj.name = "mutated"  # type: ignore[misc]


@pytest.mark.unit
def test_cluster_access_field_order_and_types() -> None:
    """ClusterAccess has exactly 4 fields: name, endpoint, ca_data, region — all str."""
    fields = dataclasses.fields(ClusterAccess)
    assert len(fields) == 4
    names = [f.name for f in fields]
    assert names == ["name", "endpoint", "ca_data", "region"]
    for f in fields:
        assert f.type is str or f.type == "str", f"Field {f.name} expected str, got {f.type}"


@mock_aws
@pytest.mark.unit
def test_get_cluster_access_happy_path() -> None:
    """get_cluster_access returns a populated ClusterAccess under @mock_aws."""
    session = boto3.Session(**_DUMMY_CREDS)
    _create_eks_cluster(session, "my-cluster", "eu-central-1")

    result = get_cluster_access(session, "my-cluster", "eu-central-1")

    assert isinstance(result, ClusterAccess)
    assert result.name == "my-cluster"
    assert result.endpoint.startswith("https://")
    assert result.ca_data != ""
    assert result.region == "eu-central-1"


@mock_aws
@pytest.mark.unit
def test_get_cluster_access_ca_data_passed_through_verbatim() -> None:
    """ca_data is passed through verbatim — no base64 decode (Pitfall 1 mitigation)."""
    session = boto3.Session(**_DUMMY_CREDS)
    _create_eks_cluster(session, "my-cluster", "eu-central-1")

    # Capture raw ca data from describe_cluster directly
    resp = session.client("eks", region_name="eu-central-1").describe_cluster(name="my-cluster")
    expected_ca_data: str = resp["cluster"]["certificateAuthority"]["data"]

    result = get_cluster_access(session, "my-cluster", "eu-central-1")

    assert result.ca_data == expected_ca_data


@mock_aws
@pytest.mark.unit
def test_get_cluster_access_missing_cluster_raises_cluster_access_error() -> None:
    """Missing cluster raises ClusterAccessError with exit_code=3 and AWS error code."""
    session = boto3.Session(**_DUMMY_CREDS)
    # Do NOT create the cluster — moto returns ResourceNotFoundException naturally

    with pytest.raises(ClusterAccessError) as exc_info:
        get_cluster_access(session, "does-not-exist", "eu-central-1")

    assert exc_info.value.exit_code == 3
    assert "ResourceNotFoundException" in str(exc_info.value) or "does-not-exist" in str(
        exc_info.value
    )


@mock_aws
@pytest.mark.unit
def test_get_cluster_access_uses_session_region() -> None:
    """Explicit region parameter is honoured — cluster created in us-east-1 is reachable."""
    creds = {**_DUMMY_CREDS, "region_name": "us-east-1"}
    session = boto3.Session(**creds)
    _create_eks_cluster(session, "us-cluster", "us-east-1")

    result = get_cluster_access(session, "us-cluster", "us-east-1")

    assert result.region == "us-east-1"
    assert result.name == "us-cluster"
