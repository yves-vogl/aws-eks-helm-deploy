"""Secure kubeconfig tempfile writer for aws-eks-helm-deploy.

Requirements traceability:
  - CHART-01 prerequisite: provides the kubeconfig path that HelmClient consumes.
  - PIPE-01 prerequisite: the kubeconfig bridges the EKS cluster descriptor to
    the helm subprocess via a 0600-permissioned tempfile.

Security notes:
  - Pitfall 1 (ca_data verbatim): cluster.ca_data is already base64-encoded;
    write it directly to certificate-authority-data WITHOUT decoding. Decoding
    and re-encoding introduces base64 padding divergence (moto vs real AWS).
  - Pitfall 2 (chmod-before-write, T-03-01): os.chmod(path, 0o600) fires
    IMMEDIATELY after NamedTemporaryFile creates the empty file, BEFORE
    path.write_text(). The race window is "empty file at default umask mode" —
    zero credential material at that point. write_text fires only after chmod.
  - T-03-02 (token in FILE not argv): the token is written to the kubeconfig
    file; helm receives --kubeconfig /tmp/eks-kubeconfig-XXX.yaml in argv.
    ps ax shows the path, not the token.

Error layering (Deviation 2 from PLAN.md):
  This module does NOT raise KubeconfigError. OSError / PermissionError from
  NamedTemporaryFile, os.chmod, or write_text propagate as-is. The action layer
  (Plan 03-04's actions/upgrade.py) wraps the with write_kubeconfig(...) call in
  try: ... except OSError as exc: raise KubeconfigError(...) from exc.
  This keeps the writer testable in isolation and puts error context (which
  cluster? which release?) at the call site where it is available.
"""

from __future__ import annotations

import contextlib
import os
import pathlib
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from aws_eks_helm_deploy.eks.cluster import ClusterAccess

__all__: list[str] = ["write_kubeconfig"]


def _build_kubeconfig_yaml(cluster: ClusterAccess, token: str) -> str:
    """Build a minimal kubeconfig YAML string for the given EKS cluster + bearer token.

    The structure mirrors what 'aws eks update-kubeconfig' produces but uses an
    inlined token (user.token) instead of an exec: credential provider block.
    ca_data is passed through verbatim from cluster.ca_data (Pitfall 1 mitigation).

    Args:
        cluster: ClusterAccess descriptor with name, endpoint, ca_data, region.
        token: Bearer token string (k8s-aws-v1.<base64url>) produced by
            generate_eks_token(). Inlined verbatim under users[0].user.token.

    Returns:
        YAML string suitable for writing to a kubeconfig file.
    """
    kubeconfig: dict[str, object] = {
        "apiVersion": "v1",
        "kind": "Config",
        "preferences": {},
        "clusters": [
            {
                "name": cluster.name,
                "cluster": {
                    "server": cluster.endpoint,
                    "certificate-authority-data": cluster.ca_data,
                },
            }
        ],
        "users": [
            {
                "name": cluster.name,
                "user": {
                    "token": token,
                },
            }
        ],
        "contexts": [
            {
                "name": cluster.name,
                "context": {
                    "cluster": cluster.name,
                    "user": cluster.name,
                },
            }
        ],
        "current-context": cluster.name,
    }
    return yaml.safe_dump(kubeconfig, default_flow_style=False, sort_keys=False)


@contextmanager
def write_kubeconfig(cluster: ClusterAccess, token: str) -> Iterator[pathlib.Path]:
    """Yield a Path to a securely-permissioned tempfile kubeconfig.

    Creates an empty tempfile, sets mode 0600 (before writing any content to
    close the race window per T-03-01), writes the kubeconfig YAML, yields the
    path, then deletes the file on exit — even if the with block raises.

    Args:
        cluster: ClusterAccess descriptor (name, endpoint, ca_data, region).
            Produced by eks.cluster.get_cluster_access().
        token: EKS bearer token string. Inlined under users[0].user.token.
            Produced by aws.eks_token.generate_eks_token().

    Yields:
        pathlib.Path to the tempfile in tempfile.gettempdir() with prefix
        'eks-kubeconfig-' and suffix '.yaml'.

    Note:
        OSError / PermissionError from filesystem operations propagate as-is.
        The action layer (actions/upgrade.py) wraps this in a KubeconfigError
        handler (see Deviation 2 in PLAN.md).
    """
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        delete=False,
        prefix="eks-kubeconfig-",
    ) as tmp:
        path = pathlib.Path(tmp.name)
    # File exists but is EMPTY; set 0600 BEFORE writing content (Pitfall 2 / T-03-01)
    os.chmod(path, 0o600)
    try:
        path.write_text(_build_kubeconfig_yaml(cluster, token))
        yield path
    finally:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()
