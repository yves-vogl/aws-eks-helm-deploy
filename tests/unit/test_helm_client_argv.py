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
def test_upgrade_argv_with_set_json_args(snapshot: object) -> None:
    """set_json_args produce ``--set-json`` for each entry (META-01 fix)."""
    argv = _client()._build_argv(
        release="rel",
        chart_path=pathlib.Path("/charts/c"),
        namespace="default",
        values_files=[],
        set_args=[],
        history_max=None,
        timeout="600s",
        set_json_args=['bitbucket.bitbucket_step_triggerer_uuid="{deadbeef-cafe-1234}"'],
    )
    assert argv == snapshot


@pytest.mark.unit
def test_diff_argv_with_set_json_args(snapshot: object) -> None:
    """_build_diff_argv: set_json_args produce ``--set-json`` for each entry."""
    argv = _client()._build_diff_argv(
        release="rel",
        chart_path=pathlib.Path("/charts/c"),
        namespace="default",
        values_files=[],
        set_args=[],
        set_json_args=['bitbucket.bitbucket_step_triggerer_uuid="{deadbeef-cafe-1234}"'],
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


# ---------------------------------------------------------------------------
# New argv builder for _build_diff_argv (Plan 05-03 — PIPE-02)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_diff_argv_minimal_returns_stable_prefix() -> None:
    """Minimal call: no values files, no set_args — 9-element stable prefix."""
    argv = _client()._build_diff_argv(
        release="my-release",
        chart_path=pathlib.Path("/path/to/chart"),
        namespace="ns",
        values_files=[],
        set_args=[],
    )
    assert argv == [
        "helm",
        "diff",
        "upgrade",
        "my-release",
        "/path/to/chart",
        "--namespace",
        "ns",
        "--kubeconfig",
        "/tmp/test-kubeconfig.yaml",
    ]
    assert len(argv) == 9


@pytest.mark.unit
def test_build_diff_argv_appends_values_files_in_order() -> None:
    """Two values files produce two --values pairs appended in input order."""
    argv = _client()._build_diff_argv(
        release="my-release",
        chart_path=pathlib.Path("/path/to/chart"),
        namespace="ns",
        values_files=["base.yaml", "prod.yaml"],
        set_args=[],
    )
    assert "--values" in argv
    idx_base = argv.index("base.yaml")
    idx_prod = argv.index("prod.yaml")
    # Each value file must be preceded by --values
    assert argv[idx_base - 1] == "--values"
    assert argv[idx_prod - 1] == "--values"
    # Input order preserved: base before prod
    assert idx_base < idx_prod


@pytest.mark.unit
def test_build_diff_argv_appends_set_args_with_set_string_flag() -> None:
    """set_args produce --set-string (NOT --set) — Pitfall 4 / curly-brace handling."""
    argv = _client()._build_diff_argv(
        release="my-release",
        chart_path=pathlib.Path("/path/to/chart"),
        namespace="ns",
        values_files=[],
        set_args=["key1=val1", "key2=val2"],
    )
    assert "--set-string" in argv
    assert argv.count("--set-string") == 2
    # Must NOT use --set (plain) for any entry
    assert "--set" not in argv


@pytest.mark.unit
def test_build_diff_argv_does_not_include_install_flag() -> None:
    """--install must NOT appear in diff argv (helm diff upgrade != helm upgrade --install)."""
    argv = _client()._build_diff_argv(
        release="my-release",
        chart_path=pathlib.Path("/path/to/chart"),
        namespace="ns",
        values_files=[],
        set_args=[],
    )
    assert "--install" not in argv


@pytest.mark.unit
def test_build_diff_argv_does_not_include_timeout_or_history_max() -> None:
    """--timeout and --history-max must NOT appear in diff argv (diff is read-only)."""
    argv = _client()._build_diff_argv(
        release="my-release",
        chart_path=pathlib.Path("/path/to/chart"),
        namespace="ns",
        values_files=[],
        set_args=[],
    )
    assert "--timeout" not in argv
    assert "--history-max" not in argv


# ---------------------------------------------------------------------------
# SAFE_UPGRADE _build_argv extension (Plan 05-05 — PIPE-05)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_argv_safe_upgrade_false_does_not_add_wait_or_rollback_flag() -> None:
    """safe_upgrade=False (default) omits --wait, --rollback-on-failure, --atomic, --description.

    Issue #70 migration: helm 4.2.2 renamed --atomic to --rollback-on-failure. We assert that
    neither the new nor the old flag form leaks into the default argv (the old --atomic is
    still accepted by helm v4 as a deprecated alias, but the pipe must not emit either form
    unless safe_upgrade=True).
    """
    argv = _client()._build_argv(
        release="rel",
        chart_path=pathlib.Path("/charts/c"),
        namespace="default",
        values_files=[],
        set_args=[],
        history_max=None,
        timeout="600s",
        safe_upgrade=False,
    )
    assert "--wait" not in argv
    assert "--rollback-on-failure" not in argv
    assert "--atomic" not in argv  # helm 3 legacy form — must not appear either
    assert "--description" not in argv


@pytest.mark.unit
def test_build_argv_safe_upgrade_true_appends_wait_rollback_description() -> None:
    """safe_upgrade=True appends helm-v4 canonical flags at argv tail.

    Issue #70: argv tail is now ``--wait --rollback-on-failure --description
    pipe:safe-upgrade`` (helm 4.2.2 pkg/cmd/upgrade.go L290 — --atomic is a deprecated alias).
    The marker string ``"pipe:safe-upgrade"`` is INTENTIONALLY unchanged so RollbackAction
    pre-flight can still match historical releases deployed by older pipe builds.
    """
    argv = _client()._build_argv(
        release="rel",
        chart_path=pathlib.Path("/charts/c"),
        namespace="default",
        values_files=[],
        set_args=[],
        history_max=None,
        timeout="600s",
        safe_upgrade=True,
    )
    assert argv[-4:] == [
        "--wait",
        "--rollback-on-failure",
        "--description",
        "pipe:safe-upgrade",
    ]
    # Defensive: the deprecated helm-3 alias must NOT appear (avoids stderr deprecation
    # warnings on every safe upgrade).
    assert "--atomic" not in argv


@pytest.mark.unit
def test_build_rollback_argv_minimal_shape() -> None:
    """_build_rollback_argv returns exact 8-element stable shape (PIPE-04)."""
    argv = _client()._build_rollback_argv(
        release="my-release",
        revision=3,
        namespace="ns",
    )
    assert argv == [
        "helm",
        "rollback",
        "my-release",
        "3",
        "--namespace",
        "ns",
        "--kubeconfig",
        "/tmp/test-kubeconfig.yaml",
    ]


@pytest.mark.unit
def test_build_rollback_argv_uses_str_of_revision_int() -> None:
    """revision int is converted to str in argv (helm CLI requires string argv element)."""
    argv = _client()._build_rollback_argv(
        release="rel",
        revision=42,
        namespace="default",
    )
    assert argv[3] == "42"
    assert isinstance(argv[3], str)


@pytest.mark.unit
def test_build_argv_safe_upgrade_does_not_duplicate_when_already_in_set_args() -> None:
    """safe_upgrade=True adds --wait exactly once even when set_args has other content."""
    argv = _client()._build_argv(
        release="rel",
        chart_path=pathlib.Path("/charts/c"),
        namespace="default",
        values_files=[],
        set_args=["something=else"],
        history_max=None,
        timeout="600s",
        safe_upgrade=True,
    )
    assert argv.count("--wait") == 1
