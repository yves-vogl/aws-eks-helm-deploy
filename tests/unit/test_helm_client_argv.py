"""syrupy snapshot tests for HelmClient._build_argv.

The argv is a pure function — snapshot tests detect regressions on flag order,
``--set-string`` vs ``--set``, and ``--history-max`` emission.

CONTEXT D9 + RESEARCH Section D; mitigates ROADMAP Risk 1 (v1.x timeout edge
cases creeping back). Snapshots are committed to git (NOT in .gitignore).
"""

from __future__ import annotations

import pathlib

import pytest

from aws_eks_helm_deploy.helm.client import HelmClient


def _client() -> HelmClient:
    """Return a HelmClient with a deterministic kubeconfig path for snapshots."""
    return HelmClient(kubeconfig_path=pathlib.Path("/tmp/test-kubeconfig.yaml"))


@pytest.mark.unit
def test_upgrade_argv_minimal(snapshot: object) -> None:
    """Minimal call: no values files, no set_args, history_max=None, short timeout."""
    argv = _client()._build_argv(
        release="rel",
        chart_path=pathlib.Path("/charts/c"),
        namespace="default",
        values_files=[],
        set_args=[],
        history_max=None,
        timeout="600s",
    )
    assert argv == snapshot


@pytest.mark.unit
def test_upgrade_argv_with_values(snapshot: object) -> None:
    """Two values files produce two ``--values`` pairs in order (last-wins)."""
    argv = _client()._build_argv(
        release="rel",
        chart_path=pathlib.Path("/charts/c"),
        namespace="default",
        values_files=["base.yaml", "prod.yaml"],
        set_args=[],
        history_max=None,
        timeout="600s",
    )
    assert argv == snapshot


@pytest.mark.unit
def test_upgrade_argv_with_set_args(snapshot: object) -> None:
    """set_args produce ``--set-string`` (not ``--set``) for each entry."""
    argv = _client()._build_argv(
        release="rel",
        chart_path=pathlib.Path("/charts/c"),
        namespace="default",
        values_files=[],
        set_args=["image.tag=latest", "replicas=3"],
        history_max=None,
        timeout="600s",
    )
    assert argv == snapshot


@pytest.mark.unit
def test_upgrade_argv_with_history_max(snapshot: object) -> None:
    """history_max=5 produces ``--history-max 5`` in argv."""
    argv = _client()._build_argv(
        release="rel",
        chart_path=pathlib.Path("/charts/c"),
        namespace="default",
        values_files=[],
        set_args=[],
        history_max=5,
        timeout="600s",
    )
    assert argv == snapshot


@pytest.mark.unit
def test_upgrade_argv_with_history_max_zero(snapshot: object) -> None:
    """history_max=0 produces ``--history-max 0`` (0 means unlimited per CONTEXT D4)."""
    argv = _client()._build_argv(
        release="rel",
        chart_path=pathlib.Path("/charts/c"),
        namespace="default",
        values_files=[],
        set_args=[],
        history_max=0,
        timeout="600s",
    )
    assert argv == snapshot


@pytest.mark.unit
def test_upgrade_argv_history_max_none_omits_flag(snapshot: object) -> None:
    """history_max=None must NOT produce ``--history-max`` in argv."""
    argv = _client()._build_argv(
        release="rel",
        chart_path=pathlib.Path("/charts/c"),
        namespace="default",
        values_files=[],
        set_args=[],
        history_max=None,
        timeout="600s",
    )
    assert argv == snapshot
    assert "--history-max" not in argv


@pytest.mark.unit
def test_upgrade_argv_with_bitbucket_metadata(snapshot: object) -> None:
    """Bitbucket UUID with curly braces survives via ``--set-string`` (RESEARCH G / Pitfall 4).

    This snapshot is the canonical regression guard for T-03-02-04: any PR that
    accidentally changes ``--set-string`` back to ``--set`` will fail here.
    """
    argv = _client()._build_argv(
        release="rel",
        chart_path=pathlib.Path("/charts/c"),
        namespace="default",
        values_files=[],
        set_args=[
            "bitbucket.bitbucket_build_number=42",
            "bitbucket.bitbucket_step_triggerer_uuid={xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}",
        ],
        history_max=None,
        timeout="600s",
    )
    assert argv == snapshot
    assert "--set-string" in argv
    assert "--set" not in argv


@pytest.mark.unit
def test_upgrade_argv_full(snapshot: object) -> None:
    """All flags combined: 2 values files + 5 bitbucket set_args + history_max=10 + timeout."""
    argv = _client()._build_argv(
        release="my-release",
        chart_path=pathlib.Path("/charts/minimal"),
        namespace="prod",
        values_files=["base.yaml", "prod.yaml"],
        set_args=[
            "bitbucket.bitbucket_build_number=99",
            "bitbucket.bitbucket_repo_slug=my-repo",
            "bitbucket.bitbucket_commit=abc123def456abc123def456abc123def456abc1",
            "bitbucket.bitbucket_tag=v1.2.3",
            "bitbucket.bitbucket_step_triggerer_uuid={xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}",
        ],
        history_max=10,
        timeout="10m",
    )
    assert argv == snapshot


# ---------------------------------------------------------------------------
# New argv builders for repo_add, repo_update, pull_repo (Plan 04-06)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_repo_add_argv(snapshot: object) -> None:
    """helm repo add <name> <url> — argv snapshot."""
    argv = _client()._build_repo_add_argv("bitnami", "https://charts.bitnami.com/bitnami")
    assert argv == snapshot


@pytest.mark.unit
def test_repo_update_argv(snapshot: object) -> None:
    """helm repo update <name> — argv snapshot."""
    argv = _client()._build_repo_update_argv("bitnami")
    assert argv == snapshot


@pytest.mark.unit
def test_pull_repo_argv_with_version(snapshot: object) -> None:
    """helm pull <repo>/<chart> with --version flag — argv snapshot."""
    argv = _client()._build_pull_repo_argv(
        "bitnami/redis",
        pathlib.Path("/tmp/dest"),
        pathlib.Path("/tmp/unpacked"),
        "18.5.0",
    )
    assert argv == snapshot


@pytest.mark.unit
def test_pull_repo_argv_without_version(snapshot: object) -> None:
    """helm pull <repo>/<chart> without --version flag — argv snapshot."""
    argv = _client()._build_pull_repo_argv(
        "bitnami/redis",
        pathlib.Path("/tmp/dest"),
        pathlib.Path("/tmp/unpacked"),
        None,
    )
    assert argv == snapshot


# ---------------------------------------------------------------------------
# New argv builders for registry_login + pull_oci (Plan 04-07)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_registry_login_argv(snapshot: object) -> None:
    """helm registry login uses --password-stdin (NOT --password <value>) — argv snapshot.

    This snapshot is the canonical regression guard for T-04-07-01: any PR that
    accidentally switches to '--password <value>' will fail here and in the negative
    grep check (R4 structural enforcement).
    """
    argv = _client()._build_registry_login_argv("127.0.0.1:5555", "alice")
    assert argv == snapshot
    assert "--password-stdin" in argv
    assert "--password" not in [a for a in argv if not a.startswith("--password-stdin")]


@pytest.mark.unit
def test_pull_oci_argv_with_version(snapshot: object) -> None:
    """helm pull oci://<ref> with --version flag — argv snapshot."""
    argv = _client()._build_pull_oci_argv(
        "127.0.0.1:5555/charts/redis",
        pathlib.Path("/tmp/dest"),
        pathlib.Path("/tmp/unpacked"),
        "18.5.0",
    )
    assert argv == snapshot
    assert "--untar" in argv


@pytest.mark.unit
def test_pull_oci_argv_without_version(snapshot: object) -> None:
    """helm pull oci://<ref> without --version flag — argv snapshot."""
    argv = _client()._build_pull_oci_argv(
        "127.0.0.1:5555/charts/redis",
        pathlib.Path("/tmp/dest"),
        pathlib.Path("/tmp/unpacked"),
        None,
    )
    assert argv == snapshot
    assert "--version" not in argv
