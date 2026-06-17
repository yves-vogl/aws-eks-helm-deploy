"""Integration tests for UpgradeAction against a kind cluster.

Per CONTEXT D10 + RESEARCH Section C: kind does NOT accept EKS bearer tokens,
so these tests use kind's OWN admin kubeconfig via the ``kind_kubeconfig``
fixture + UpgradeAction's ``kubeconfig_override`` kwarg. The EKS-token path is
unit-tested via @mock_aws in Phase 2 + Plan 03-01.

All tests carry:
  - @pytest.mark.integration  — opts into the integration tier
  - @pytest.mark.flaky(reruns=3, reruns_delay=5)  — ROADMAP Risk 2 mitigation;
    guards against transient kind startup flakiness on cold runners (CONTEXT D10)

Requirements covered:
  - CHART-01: end-to-end deploy of minimal chart on real cluster
  - CHART-05: pipe.success message contains chart name + version (exact format)
  - PIPE-01:  helm upgrade --install chain reaches real helm binary
  - PIPE-06:  typed HelmExecutionError raised on chart-render failure
  - HISTORY-01 + HISTORY-02: HISTORY_MAX=5 + 6 upgrades → exactly 5 revisions
  - META-01:  INJECT_BITBUCKET_METADATA=true + 5 BITBUCKET_* env vars → all 5
              bitbucket.* keys in helm get values, curly-brace UUID verbatim

Integration tier is OPT-IN via ``make integration-test`` or
``pytest -m integration --no-cov``. Default ``pytest`` runs the unit tier only.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import uuid
from unittest.mock import MagicMock

import pytest
import yaml

from aws_eks_helm_deploy.actions.upgrade import UpgradeAction
from aws_eks_helm_deploy.errors import HelmExecutionError
from aws_eks_helm_deploy.pipe_io import PipeIO
from aws_eks_helm_deploy.settings import Settings

# Absolute path to the minimal chart fixture created by Task 03-5-01.
CHART_FIXTURE_PATH: pathlib.Path = (
    pathlib.Path(__file__).parent.parent / "fixtures" / "charts" / "minimal"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_settings(
    *,
    release: str,
    history_max: int | None = None,
    inject: bool = False,
    set_values: list[str] | None = None,
    chart_override: pathlib.Path | None = None,
) -> Settings:
    """Build a Settings instance with kind-compatible dummy AWS credentials.

    The ``kubeconfig_override`` kwarg on UpgradeAction bypasses EKS cluster
    fetch + token generation + write_kubeconfig, so these AWS fields are never
    used at runtime in integration tests — they satisfy pydantic validation only.
    """
    chart_path = chart_override or CHART_FIXTURE_PATH
    return Settings(
        # Required AWS fields (dummies — kubeconfig_override bypasses AWS path)
        aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
        aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        aws_region="eu-central-1",
        # cluster_name must match the kind_cluster fixture name
        cluster_name="test-pipe-integration",
        chart=str(chart_path),
        release_name=release,
        namespace="default",
        history_max=history_max,
        inject_bitbucket_metadata=inject,
        set_values=set_values or [],
    )


def _mock_pipe() -> MagicMock:
    """Return a MagicMock with spec=PipeIO for asserting .success/.fail calls.

    Uses MagicMock(spec=PipeIO) to avoid booting bitbucket-pipes-toolkit's
    real Pipe (which requires a pipe.yml + schema). The integration test scope
    is the HELM PATH, not the pipe-io plumbing (Deviation 4).
    """
    return MagicMock(spec=PipeIO)


def _run_helm(*args: str, kubeconfig: pathlib.Path) -> subprocess.CompletedProcess[str]:
    """Run a helm command against the kind cluster via the provided kubeconfig.

    Args:
        *args: Helm subcommand and flags (without ``--kubeconfig``).
        kubeconfig: Path to the kind admin kubeconfig written by kind_kubeconfig.

    Returns:
        CompletedProcess with ``returncode``, ``stdout``, ``stderr``.
    """
    return subprocess.run(
        ["helm", *args, "--kubeconfig", str(kubeconfig)],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _cleanup_release(release: str, kubeconfig: pathlib.Path) -> None:
    """Uninstall a helm release from the kind cluster; ignores errors.

    Called in teardown ``finally`` blocks to prevent orphan releases from
    leaking between test runs (T-03-05-02 mitigation).
    """
    _run_helm("uninstall", release, "-n", "default", kubeconfig=kubeconfig)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.flaky(reruns=3, reruns_delay=5)
def test_upgrade_action_deploys_minimal_chart(
    kind_cluster: str,
    kind_kubeconfig: pathlib.Path,
) -> None:
    """Happy path: UpgradeAction deploys the minimal chart and reports success.

    Requirements: CHART-01 (end-to-end on real cluster), CHART-05 (success message
    format), PIPE-01 (helm upgrade --install chain reaches real binary).

    Asserts:
      - action.run(pipe) returns 0.
      - pipe.success called once; message contains chart name + version per D7.
      - helm status reports STATUS=deployed after the action.
    """
    release = f"happy-path-{uuid.uuid4().hex[:8]}"
    settings = _build_settings(release=release)
    action = UpgradeAction(settings, kubeconfig_override=kind_kubeconfig)
    pipe = _mock_pipe()

    try:
        result = action.run(pipe)
        assert result == 0, f"Expected return code 0, got {result}"

        # CHART-05: verify pipe.success was called with the exact D7 format
        pipe.success.assert_called_once()
        success_message: str = pipe.success.call_args[0][0]
        assert "minimal" in success_message, (
            f"Expected 'minimal' in success message: {success_message!r}"
        )
        assert "0.1.0" in success_message, (
            f"Expected '0.1.0' in success message: {success_message!r}"
        )
        assert release in success_message, (
            f"Expected release name in success message: {success_message!r}"
        )
        assert success_message.startswith(f"Deployed chart minimal (0.1.0) to release {release}"), (
            f"Success message format mismatch: {success_message!r}"
        )

        # CHART-01: verify helm cluster state shows deployed
        status_proc = _run_helm(
            "status",
            release,
            "-n",
            "default",
            "-o",
            "json",
            kubeconfig=kind_kubeconfig,
        )
        assert status_proc.returncode == 0, f"helm status failed:\n{status_proc.stderr}"
        status_json = json.loads(status_proc.stdout)
        assert status_json["info"]["status"] == "deployed", (
            f"Expected 'deployed', got {status_json['info']['status']!r}"
        )
    finally:
        _cleanup_release(release, kind_kubeconfig)


@pytest.mark.integration
@pytest.mark.flaky(reruns=3, reruns_delay=5)
def test_history_max_5_retains_at_most_5_revisions(
    kind_cluster: str,
    kind_kubeconfig: pathlib.Path,
) -> None:
    """HISTORY_MAX=5 after 6 sequential upgrades → helm history shows exactly 5 revisions.

    Requirements: HISTORY-01 + HISTORY-02 (closes #17 at the wire level).

    Helm prunes deterministically after each successful upgrade once the cap is
    reached. After 6 upgrades with --history-max 5, revision 1 is pruned and
    revisions 2-6 remain (Deviation 3: assert == 5, not <= 5).

    Uses set_values=[f"test.iteration={i}"] per RESEARCH Section F to force a
    new revision on each upgrade (Helm reuses the previous revision if values
    are unchanged — a no-op upgrade does NOT bump the revision counter).
    """
    release = f"history-test-{uuid.uuid4().hex[:8]}"

    try:
        for i in range(6):
            settings = _build_settings(
                release=release,
                history_max=5,
                set_values=[f"test.iteration={i}"],
            )
            action = UpgradeAction(settings, kubeconfig_override=kind_kubeconfig)
            pipe = _mock_pipe()
            assert action.run(pipe) == 0, f"Upgrade {i} failed"

        history_proc = _run_helm(
            "history",
            release,
            "-n",
            "default",
            "-o",
            "json",
            kubeconfig=kind_kubeconfig,
        )
        assert history_proc.returncode == 0, f"helm history failed:\n{history_proc.stderr}"
        revisions: list[dict[str, object]] = json.loads(history_proc.stdout)

        # Deviation 3: exact equality — catches both over-retention and under-retention
        assert len(revisions) == 5, (
            f"Expected exactly 5 revisions after 6 upgrades with HISTORY_MAX=5, "
            f"got {len(revisions)}: {revisions}"
        )

        # The latest revision must be deployed; all prior visible ones must be superseded.
        statuses = [str(r["status"]) for r in revisions]
        assert statuses[-1] == "deployed", (
            f"Expected last revision status 'deployed', got {statuses[-1]!r}; "
            f"all statuses: {statuses}"
        )
        for s in statuses[:-1]:
            assert s == "superseded", (
                f"Expected earlier revision status 'superseded', got {s!r}; "
                f"all statuses: {statuses}"
            )
    finally:
        _cleanup_release(release, kind_kubeconfig)


@pytest.mark.integration
@pytest.mark.flaky(reruns=3, reruns_delay=5)
def test_inject_bitbucket_metadata_sets_all_5_keys(
    kind_cluster: str,
    kind_kubeconfig: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INJECT_BITBUCKET_METADATA=true with 5 BITBUCKET_* env vars → all 5 bitbucket.* keys.

    Requirements: META-01 (full wire path).

    Uses monkeypatch.setenv for BITBUCKET_* env vars — automatic cleanup on
    test teardown, no global os.environ pollution.

    The BITBUCKET_STEP_TRIGGERER_UUID includes curly braces verbatim — proves
    the corrections #4 / Pitfall 4 fix (--set-string preserves curly braces
    without helm interpreting them as template syntax).
    """
    # Set 5 BITBUCKET_* env vars via monkeypatch (auto-restored on teardown)
    monkeypatch.setenv("BITBUCKET_BUILD_NUMBER", "42")
    monkeypatch.setenv("BITBUCKET_REPO_SLUG", "my-repo")
    monkeypatch.setenv("BITBUCKET_COMMIT", "abc123def456789012345678901234567890abcd")
    monkeypatch.setenv("BITBUCKET_TAG", "v1.2.3")
    # Curly braces in UUID value — proves --set-string preserves them verbatim
    monkeypatch.setenv("BITBUCKET_STEP_TRIGGERER_UUID", "{deadbeef-cafe-1234-5678-abcdef012345}")

    release = f"inject-test-{uuid.uuid4().hex[:8]}"
    settings = _build_settings(release=release, inject=True)
    action = UpgradeAction(settings, kubeconfig_override=kind_kubeconfig)
    pipe = _mock_pipe()

    try:
        result = action.run(pipe)
        assert result == 0, f"Expected return code 0 from inject test, got {result}"

        # Assert all 5 bitbucket.* keys appear in helm get values
        values_proc = _run_helm(
            "get",
            "values",
            release,
            "-n",
            "default",
            "-o",
            "yaml",
            kubeconfig=kind_kubeconfig,
        )
        assert values_proc.returncode == 0, f"helm get values failed:\n{values_proc.stderr}"
        values = yaml.safe_load(values_proc.stdout)
        assert isinstance(values, dict) and "bitbucket" in values, (
            f"Expected 'bitbucket' mapping in helm get values, got: {values}"
        )
        bb = values["bitbucket"]

        assert str(bb.get("bitbucket_build_number")) == "42", (
            f"bitbucket_build_number mismatch: {bb.get('bitbucket_build_number')!r}"
        )
        assert bb.get("bitbucket_repo_slug") == "my-repo", (
            f"bitbucket_repo_slug mismatch: {bb.get('bitbucket_repo_slug')!r}"
        )
        assert bb.get("bitbucket_commit") == "abc123def456789012345678901234567890abcd", (
            f"bitbucket_commit mismatch: {bb.get('bitbucket_commit')!r}"
        )
        assert bb.get("bitbucket_tag") == "v1.2.3", (
            f"bitbucket_tag mismatch: {bb.get('bitbucket_tag')!r}"
        )
        # Curly-brace UUID must be preserved verbatim (--set-string proof)
        assert bb.get("bitbucket_step_triggerer_uuid") == (
            "{deadbeef-cafe-1234-5678-abcdef012345}"
        ), f"bitbucket_step_triggerer_uuid mismatch: {bb.get('bitbucket_step_triggerer_uuid')!r}"

        # Bonus: ConfigMap label bb-build surfaces the build number at render time
        kb_proc = subprocess.run(
            [
                "kubectl",
                "get",
                "configmap",
                f"{release}-config",
                "-n",
                "default",
                "-o",
                "jsonpath={.metadata.labels.bb-build}",
                "--kubeconfig",
                str(kind_kubeconfig),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if kb_proc.returncode == 0:
            assert kb_proc.stdout == "42", (
                f"Expected ConfigMap label bb-build='42', got {kb_proc.stdout!r}"
            )
    finally:
        _cleanup_release(release, kind_kubeconfig)


@pytest.mark.integration
@pytest.mark.flaky(reruns=3, reruns_delay=5)
def test_failure_path_surfaces_non_zero_exit_with_human_message(
    kind_cluster: str,
    kind_kubeconfig: pathlib.Path,
    tmp_path: pathlib.Path,
) -> None:
    """Helm chart-render failure raises HelmExecutionError with helm error in user_message.

    Requirements: PIPE-06 (typed error + non-zero exit code).

    Constructs a bad chart whose configmap.yaml uses ``required`` to force helm
    to fail at template-render time. Asserts HelmExecutionError is raised with
    exit_code=5 and the helm error message surfaces in user_message.

    Note (Deviation 5): this test calls UpgradeAction.run DIRECTLY — NOT through
    cli.py. cli.py's ``except PipeError: pipe.fail(exc.user_message)`` translation
    is covered at the unit-test level by test_cli.py::test_main_catches_pipe_error.
    The integration test scope is "does helm failure produce a typed HelmExecutionError?"
    — the exception assertion is sufficient for PIPE-06 at this tier.
    """
    # Build a bad chart whose template forces helm to fail at render time
    bad_chart = tmp_path / "bad-chart"
    bad_chart.mkdir()
    (bad_chart / "Chart.yaml").write_text("apiVersion: v2\nname: bad\nversion: 0.1.0\n")
    (bad_chart / "templates").mkdir()
    (bad_chart / "templates" / "configmap.yaml").write_text(
        "apiVersion: v1\n"
        "kind: ConfigMap\n"
        "metadata:\n"
        "  name: bad\n"
        "data:\n"
        '  x: {{ required "MISSING" .Values.does_not_exist }}\n'
    )

    release = f"fail-test-{uuid.uuid4().hex[:8]}"
    settings = _build_settings(release=release, chart_override=bad_chart)
    action = UpgradeAction(settings, kubeconfig_override=kind_kubeconfig)
    pipe = _mock_pipe()

    with pytest.raises(HelmExecutionError) as exc_info:
        action.run(pipe)

    assert exc_info.value.exit_code == 5, (
        f"Expected HelmExecutionError.exit_code=5, got {exc_info.value.exit_code}"
    )
    # helm surfaces the required() failure in stderr; check it appears in user_message
    error_str = str(exc_info.value)
    assert "MISSING" in error_str or "required" in error_str.lower(), (
        f"Expected helm error text in HelmExecutionError message: {error_str!r}"
    )
    # No release was created (helm rejected at render time) — no teardown needed
