"""Unit tests for write_kubeconfig (CHART-01 prerequisite).

Verifies tempfile lifecycle, 0600 permissions, YAML structure, and cleanup
behavior — including the FileNotFoundError suppression branch (CONTEXT D3
belt-and-braces).
"""

from __future__ import annotations

import os
import pathlib
import tempfile

import pytest
import yaml

from aws_eks_helm_deploy.eks.cluster import ClusterAccess
from aws_eks_helm_deploy.kube.kubeconfig import write_kubeconfig

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_cluster_access(name: str = "test-cluster") -> ClusterAccess:
    return ClusterAccess(
        name=name,
        endpoint="https://api.example.com",
        ca_data="LS0tLS1CRUdJTi...",
        region="eu-central-1",
    )


_TOKEN = "k8s-aws-v1.AAAAA"  # noqa: S105 — not a password; EKS token format test fixture

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_module_imports_clean() -> None:
    """write_kubeconfig is importable with no side effects."""
    import aws_eks_helm_deploy.kube.kubeconfig as _mod

    assert callable(_mod.write_kubeconfig)


@pytest.mark.unit
def test_yields_path_in_tempdir() -> None:
    """The yielded path lives in tempfile.gettempdir()."""
    cluster = _make_cluster_access()
    with write_kubeconfig(cluster, _TOKEN) as p:
        assert p.parent == pathlib.Path(tempfile.gettempdir())


@pytest.mark.unit
def test_yields_path_with_eks_kubeconfig_prefix_and_yaml_suffix() -> None:
    """The yielded filename has prefix 'eks-kubeconfig-' and suffix '.yaml'."""
    cluster = _make_cluster_access()
    with write_kubeconfig(cluster, _TOKEN) as p:
        assert p.name.startswith("eks-kubeconfig-")
        assert p.name.endswith(".yaml")


@pytest.mark.unit
def test_file_exists_during_context() -> None:
    """The kubeconfig file exists and is a regular file during the with block."""
    cluster = _make_cluster_access()
    with write_kubeconfig(cluster, _TOKEN) as p:
        assert p.exists()
        assert p.is_file()


@pytest.mark.unit
def test_file_mode_is_0600() -> None:
    """The yielded file has mode 0600 (owner read/write only)."""
    cluster = _make_cluster_access()
    with write_kubeconfig(cluster, _TOKEN) as p:
        assert (p.stat().st_mode & 0o777) == 0o600


@pytest.mark.unit
def test_chmod_happens_before_write_content(mocker) -> None:  # type: ignore[no-untyped-def]
    """chmod 0600 is called BEFORE write_text (Pitfall 2 / race-window mitigation).

    Implementation: patch os.chmod in the kubeconfig module and pathlib.Path.write_text
    via mocker. Capture call ORDER in a shared list and assert chmod precedes write_text.

    Note on side_effect signature for patch.object: when patching an instance method on a
    class, the mock's side_effect receives only the *args* passed to the method (excluding
    self) because patch.object replaces the unbound function descriptor. We therefore use
    a simple lambda that appends to the list and delegates to the real method via closure.
    """
    call_order: list[str] = []
    original_chmod = os.chmod

    def recording_chmod(path: str | pathlib.Path, mode: int, **kwargs: object) -> None:
        call_order.append("chmod")
        original_chmod(path, mode, **kwargs)

    def recording_write_text(data: str, *args: object, **kwargs: object) -> None:
        # side_effect for patch.object receives method args without self
        call_order.append("write_text")
        # delegate to original via unbound call; the mock wraps the Path instance
        # so we cannot easily call original_write_text here without the instance.
        # We only need to record the order — returning None is fine; the file may
        # be empty after the test but the tempfile is deleted on context exit anyway.

    mocker.patch("aws_eks_helm_deploy.kube.kubeconfig.os.chmod", side_effect=recording_chmod)
    mocker.patch.object(pathlib.Path, "write_text", side_effect=recording_write_text)

    cluster = _make_cluster_access()
    with write_kubeconfig(cluster, _TOKEN):
        pass

    # chmod must appear before write_text in the call order
    assert "chmod" in call_order
    assert "write_text" in call_order
    chmod_idx = next(i for i, v in enumerate(call_order) if v == "chmod")
    write_idx = next(i for i, v in enumerate(call_order) if v == "write_text")
    assert chmod_idx < write_idx, f"Expected chmod before write_text, got order: {call_order}"


@pytest.mark.unit
def test_yaml_structure_matches_kubeconfig_v1_format() -> None:
    """The kubeconfig YAML has all six required top-level keys."""
    cluster = _make_cluster_access()
    with write_kubeconfig(cluster, _TOKEN) as p:
        data = yaml.safe_load(p.read_text())

    assert data["apiVersion"] == "v1"
    assert data["kind"] == "Config"
    assert isinstance(data["preferences"], dict)
    assert isinstance(data["clusters"], list)
    assert isinstance(data["users"], list)
    assert isinstance(data["contexts"], list)
    assert isinstance(data["current-context"], str)
    assert data["current-context"] == cluster.name


@pytest.mark.unit
def test_ca_data_passed_through_verbatim() -> None:
    """certificate-authority-data equals cluster.ca_data byte-for-byte (Pitfall 1 mitigation)."""
    fake_ca = "LS0tLS1CRUdJTi..."
    cluster = _make_cluster_access()
    with write_kubeconfig(cluster, _TOKEN) as p:
        data = yaml.safe_load(p.read_text())

    assert data["clusters"][0]["cluster"]["certificate-authority-data"] == fake_ca


@pytest.mark.unit
def test_token_inlined_under_user_token() -> None:
    """Token is inlined verbatim under users[0].user.token; no exec block present."""
    token = "k8s-aws-v1.AAAAA"  # noqa: S105 — not a password; EKS token format test fixture
    cluster = _make_cluster_access()
    with write_kubeconfig(cluster, token) as p:
        data = yaml.safe_load(p.read_text())

    assert data["users"][0]["user"]["token"] == token
    assert "exec" not in data["users"][0]["user"]


@pytest.mark.unit
def test_cluster_name_used_for_context_user_and_current_context() -> None:
    """cluster.name appears in clusters[0], users[0], contexts[0], and current-context."""
    cluster = _make_cluster_access(name="prod-eks")
    with write_kubeconfig(cluster, _TOKEN) as p:
        data = yaml.safe_load(p.read_text())

    assert data["clusters"][0]["name"] == "prod-eks"
    assert data["users"][0]["name"] == "prod-eks"
    assert data["contexts"][0]["name"] == "prod-eks"
    assert data["contexts"][0]["context"]["cluster"] == "prod-eks"
    assert data["contexts"][0]["context"]["user"] == "prod-eks"
    assert data["current-context"] == "prod-eks"


@pytest.mark.unit
def test_file_deleted_on_context_exit_normal() -> None:
    """The tempfile is deleted after the with block exits normally."""
    cluster = _make_cluster_access()
    with write_kubeconfig(cluster, _TOKEN) as p:
        captured = p

    assert not captured.exists()


@pytest.mark.unit
def test_file_deleted_on_context_exit_exception() -> None:
    """The tempfile is deleted even when the with block raises an exception."""
    cluster = _make_cluster_access()
    captured: pathlib.Path | None = None

    with pytest.raises(RuntimeError), write_kubeconfig(cluster, _TOKEN) as p:
        captured = p
        raise RuntimeError("boom")

    assert captured is not None
    assert not captured.exists()


@pytest.mark.unit
def test_unlink_suppresses_file_not_found() -> None:
    """FileNotFoundError in finally is suppressed when file already deleted inside block."""
    cluster = _make_cluster_access()

    # This should NOT raise — the FileNotFoundError in finally is caught
    with write_kubeconfig(cluster, _TOKEN) as p:
        p.unlink()  # Manually delete inside the block

    # Reaching here means no exception propagated — test passes
    assert not p.exists()
