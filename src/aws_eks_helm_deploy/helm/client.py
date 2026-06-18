"""Typed HelmClient — the sole subprocess entry point for the aws-eks-helm-deploy pipe.

REQ traceability:
    PIPE-01    — upgrade_install invokes ``helm upgrade --install`` with exact argv contract
    PIPE-06    — typed errors: HelmExecutionError (exit=5) and HelmTimeoutError (exit=6)
    HISTORY-02 — ``--history-max`` passthrough; None suppresses the flag
    META-01    — ``--set-string`` for ALL injected key=value pairs (Pitfall 4: curly braces)
    CHART-02   — repo_add / repo_update / pull_repo typed methods for RepoChart (Phase 4)

Architecture:
    CONTEXT D1 — this is the ONLY module in the codebase that imports ``subprocess``.
    CONTEXT D2 — sync ``subprocess.run`` only; stderr truncated to last 32 KB.
    CONTEXT D9 — ``_build_argv`` is a pure function, snapshot-tested via syrupy.

Pitfall coverage:
    Pitfall 3 — ``history_max=0`` means UNLIMITED; valid value, emits ``--history-max 0``.
    Pitfall 4 — BITBUCKET_STEP_TRIGGERER_UUID contains curly braces; ``--set-string``
                 forces string interpretation for ALL set_args entries (RESEARCH G).
"""

from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import re
import subprocess
from typing import TYPE_CHECKING, Final

from aws_eks_helm_deploy.errors import ChartResolutionError, HelmExecutionError, HelmTimeoutError

if TYPE_CHECKING:
    from aws_eks_helm_deploy.chart.base import ResolvedChart

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

STDERR_MAX_BYTES: Final[int] = 32 * 1024
"""Maximum stderr bytes surfaced in HelmExecutionError / HelmTimeoutError messages."""

REVISION_REGEX: Final[re.Pattern[str]] = re.compile(r"^REVISION:\s*(\d+)", re.MULTILINE)
"""Parses ``REVISION: N`` from ``helm upgrade --install`` stdout (RESEARCH Section A)."""

TRUNCATION_MARKER: Final[str] = "...[truncated]...\n"
"""Prepended to truncated stderr so consumers know the output is partial."""

__all__: list[str] = ["HelmClient", "HelmResult", "HelmRevision"]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _parse_timeout(s: str) -> int:
    """Parse a Go-duration string into total seconds.

    Supported formats: ``"600s"``, ``"10m"``, ``"1h"``, ``"5m30s"``, ``"1h30m"``.

    Args:
        s: Go-duration string such as ``"600s"`` or ``"5m30s"``.

    Returns:
        Total seconds as an integer.

    Raises:
        ValueError: If the string does not match a valid Go-duration pattern or
            resolves to zero duration (empty string).
    """
    m = re.fullmatch(r"((?P<h>\d+)h)?((?P<m>\d+)m)?((?P<s>\d+)s)?", s)
    if m is None or not any(m.group(k) for k in ("h", "m", "s")):
        raise ValueError(f"invalid timeout: {s!r}")
    h = int(m.group("h") or 0)
    mins = int(m.group("m") or 0)
    secs = int(m.group("s") or 0)
    total = h * 3600 + mins * 60 + secs
    if total == 0:
        raise ValueError(f"invalid timeout: {s!r}")
    return total


def _truncate_stderr(s: str) -> str:
    """Truncate stderr to the last 32 KB if it exceeds STDERR_MAX_BYTES.

    The byte-length is checked conservatively (UTF-8 encoded), but the slicing
    uses character positions (helm stderr is ASCII-dominant; char ≈ byte).
    The TRUNCATION_MARKER is prepended so consumers see that content was dropped.

    Args:
        s: Raw stderr string from subprocess.run.

    Returns:
        Original string if ≤ 32 KB; otherwise TRUNCATION_MARKER + last 32 KB.
    """
    if len(s.encode("utf-8")) > STDERR_MAX_BYTES:
        return TRUNCATION_MARKER + s[-STDERR_MAX_BYTES:]
    return s


# ---------------------------------------------------------------------------
# Public value objects
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class HelmResult:
    """Immutable result of a successful ``helm upgrade --install`` invocation.

    Attributes:
        stdout: Full stdout captured from the helm subprocess.
        stderr: Post-truncation stderr (≤ 32 KB + TRUNCATION_MARKER if truncated).
        returncode: Always 0 on success (non-zero raises HelmExecutionError).
        revision: Helm release revision parsed from stdout via REVISION_REGEX,
            or None if the ``REVISION:`` line is absent.
    """

    stdout: str
    stderr: str
    returncode: int
    revision: int | None


@dataclasses.dataclass(frozen=True)
class HelmRevision:
    """Immutable helm release revision record from ``helm history -o json``.

    Attributes:
        revision: Revision number (monotonically increasing integer).
        status:  Release status string, e.g. ``"deployed"``, ``"superseded"``.
        chart:   Chart name + version string, e.g. ``"minimal-0.1.0"``.
        description: Human-readable description, e.g. ``"Install complete"``.
    """

    revision: int
    status: str
    chart: str
    description: str


# ---------------------------------------------------------------------------
# HelmClient
# ---------------------------------------------------------------------------


class HelmClient:
    """Typed wrapper around the ``helm`` CLI binary.

    This class is the ONLY module in the codebase that calls ``subprocess.run``
    (CONTEXT D1 layering rule). All other modules must call helm indirectly via
    this class.

    Args:
        kubeconfig_path: Absolute path to a kubeconfig file. The file must
            exist and be accessible when ``upgrade_install`` or ``history``
            is called. No validation is performed in the constructor.
    """

    def __init__(self, kubeconfig_path: pathlib.Path) -> None:
        self._kubeconfig_path = kubeconfig_path

    def _build_argv(
        self,
        release: str,
        chart_path: pathlib.Path,
        namespace: str,
        values_files: list[str],
        set_args: list[str],
        history_max: int | None,
        timeout: str,
    ) -> list[str]:
        """Build the ``helm upgrade --install`` argv list (pure function — no I/O).

        The first 11 elements are always stable (PIPE-01 + HISTORY-02):
            ``["helm", "upgrade", release, str(chart_path), "--install",
               "--namespace", namespace, "--kubeconfig", str(self._kubeconfig_path),
               "--timeout", timeout]``

        Args:
            release: Helm release name.
            chart_path: Absolute path to the local chart directory.
            namespace: Kubernetes namespace.
            values_files: List of values file paths; each produces
                ``["--values", path]`` in order (last-wins semantics).
            set_args: List of ``"key=value"`` strings; each produces
                ``["--set-string", "key=value"]``. Uses ``--set-string``
                (not ``--set``) for ALL entries to handle curly-brace values
                such as BITBUCKET_STEP_TRIGGERER_UUID (RESEARCH G / Pitfall 4).
            history_max: When ``None``, ``--history-max`` is omitted (helm
                uses its own default of 10). When 0 or any non-negative int,
                ``--history-max <N>`` is appended (0 means unlimited per
                CONTEXT D4 / Pitfall 3).
            timeout: Go-duration string passed verbatim to helm
                (e.g. ``"600s"`` or ``"10m"``).

        Returns:
            Complete argv list suitable for ``subprocess.run``.
        """
        argv: list[str] = [
            "helm",
            "upgrade",
            release,
            str(chart_path),
            "--install",
            "--namespace",
            namespace,
            "--kubeconfig",
            str(self._kubeconfig_path),
            "--timeout",
            timeout,
        ]
        for vf in values_files:
            argv.extend(["--values", vf])
        for sa in set_args:
            argv.extend(["--set-string", sa])
        if history_max is not None:
            argv.extend(["--history-max", str(history_max)])
        return argv

    def upgrade_install(
        self,
        release: str,
        chart: ResolvedChart,
        namespace: str,
        values_files: list[str],
        set_args: list[str],
        history_max: int | None,
        timeout: str,
    ) -> HelmResult:
        """Run ``helm upgrade --install`` and return a typed result.

        Constructs the argv via ``_build_argv``, invokes ``subprocess.run``
        with ``check=False, capture_output=True, text=True``, and maps exit
        codes to typed errors from the PipeError hierarchy (PIPE-06):

        - ``returncode != 0``  → ``HelmExecutionError`` (exit_code=5)
        - ``subprocess.TimeoutExpired`` → ``HelmTimeoutError`` (exit_code=6)

        Stderr is truncated to the last 32 KB on BOTH success and failure
        paths (T-03-02-03 — defense against memory blow-up on chatty helm
        error chains).

        Args:
            release: Helm release name.
            chart: Resolved local chart descriptor. The ``source_path``
                attribute is extracted and passed to ``_build_argv``.
                (``ResolvedChart`` lands in Plan 03-03; tests substitute a
                duck-typed ``SimpleNamespace``.)
            namespace: Kubernetes namespace.
            values_files: List of values file paths.
            set_args: List of ``"key=value"`` strings for ``--set-string``.
            history_max: ``None`` to omit ``--history-max``; 0 or N≥1 to pass it.
            timeout: Go-duration string, e.g. ``"600s"`` or ``"10m"``.

        Returns:
            ``HelmResult`` with stdout, truncated stderr, returncode=0, and
            the parsed revision number (or None if absent from stdout).

        Raises:
            HelmExecutionError: helm exited with a non-zero return code.
            HelmTimeoutError: ``subprocess.run`` raised ``subprocess.TimeoutExpired``.
        """
        argv = self._build_argv(
            release,
            chart.source_path,
            namespace,
            values_files,
            set_args,
            history_max,
            timeout,
        )
        timeout_seconds = _parse_timeout(timeout)
        try:
            result = subprocess.run(  # noqa: S603
                argv,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                env=os.environ.copy(),
            )
        except subprocess.TimeoutExpired as exc:
            partial_stderr = ""
            if exc.stderr is not None:
                raw: str = (
                    exc.stderr
                    if isinstance(exc.stderr, str)
                    else exc.stderr.decode("utf-8", errors="replace")
                )
                partial_stderr = raw[-1024:]
            msg = f"helm upgrade timed out after {exc.timeout}s"
            if partial_stderr:
                msg += f"; last stderr: {partial_stderr}"
            raise HelmTimeoutError(msg) from exc

        truncated_stderr = _truncate_stderr(result.stderr)

        if result.returncode != 0:
            raise HelmExecutionError(
                f"helm upgrade returned {result.returncode} — last stderr: {truncated_stderr}"
            )

        rev_match = REVISION_REGEX.search(result.stdout)
        revision = int(rev_match.group(1)) if rev_match else None
        return HelmResult(
            stdout=result.stdout,
            stderr=truncated_stderr,
            returncode=0,
            revision=revision,
        )

    def history(self, release: str, namespace: str) -> list[HelmRevision]:
        """Fetch the release history from helm and return typed revision records.

        Runs ``helm history <release> -n <namespace> -o json --kubeconfig <path>``
        and parses the JSON output.

        JSON shape per ``helm history -o json`` (RESEARCH Section A):
        ``[{"revision": 1, "updated": "...", "status": "...",
            "chart": "...", "app_version": "...", "description": "..."}]``

        Args:
            release: Helm release name.
            namespace: Kubernetes namespace.

        Returns:
            List of ``HelmRevision`` records ordered by revision (ascending,
            as returned by helm). Returns an empty list if the release has no
            history (``stdout == "[]"``).

        Raises:
            HelmExecutionError: helm exited with a non-zero return code
                (e.g. release not found).
        """
        argv = [
            "helm",
            "history",
            release,
            "-n",
            namespace,
            "-o",
            "json",
            "--kubeconfig",
            str(self._kubeconfig_path),
        ]
        result = subprocess.run(  # noqa: S603
            argv,
            capture_output=True,
            text=True,
            check=False,
            env=os.environ.copy(),
        )
        if result.returncode != 0:
            truncated_stderr = _truncate_stderr(result.stderr)
            raise HelmExecutionError(
                f"helm history returned {result.returncode} — last stderr: {truncated_stderr}"
            )
        entries: list[dict[str, int | str]] = json.loads(result.stdout)
        return [
            HelmRevision(
                revision=int(entry["revision"]),
                status=str(entry["status"]),
                chart=str(entry["chart"]),
                description=str(entry["description"]),
            )
            for entry in entries
        ]

    # -----------------------------------------------------------------------
    # Private argv builders — chart-resolution subcommands (Plan 04-06)
    # -----------------------------------------------------------------------

    def _build_repo_add_argv(self, name: str, repo_url: str) -> list[str]:
        """Build ``helm repo add <name> <url>`` argv (pure function — no I/O)."""
        return ["helm", "repo", "add", name, repo_url]

    def _build_repo_update_argv(self, name: str) -> list[str]:
        """Build ``helm repo update <name>`` argv (pure function — no I/O)."""
        return ["helm", "repo", "update", name]

    def _build_pull_repo_argv(
        self,
        repo_chart: str,
        destination: pathlib.Path,
        untar_dir: pathlib.Path,
        version: str | None,
    ) -> list[str]:
        """Build ``helm pull <repo>/<chart> --destination ... --untar --untar-dir ...`` argv."""
        argv: list[str] = [
            "helm",
            "pull",
            repo_chart,
            "--destination",
            str(destination),
            "--untar",
            "--untar-dir",
            str(untar_dir),
        ]
        if version is not None:
            argv.extend(["--version", version])
        return argv

    # -----------------------------------------------------------------------
    # Private helper — shared subprocess runner for chart-resolution commands
    # -----------------------------------------------------------------------

    def _run_helm_subcommand(
        self,
        argv: list[str],
        *,
        env: dict[str, str],
        timeout: int,
        error_prefix: str,
    ) -> None:
        """Run a helm sub-command; raise ChartResolutionError on non-zero returncode.

        Unlike upgrade_install, chart-resolution sub-commands (repo add, repo update, pull)
        raise ChartResolutionError (exit_code=4), NOT HelmExecutionError (exit_code=5),
        because the failure surfaces in the CHART RESOLUTION step — before the helm
        upgrade --install action starts. Consumers reading the exit code can distinguish
        "couldn't find / pull the chart" (4) from "helm upgrade --install itself failed" (5).
        """
        try:
            result = subprocess.run(  # noqa: S603
                argv,
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            partial_stderr = ""
            if exc.stderr is not None:
                raw: str = (
                    exc.stderr
                    if isinstance(exc.stderr, str)
                    else exc.stderr.decode("utf-8", errors="replace")
                )
                partial_stderr = raw[-1024:]
            msg = f"{error_prefix} timed out after {exc.timeout}s"
            if partial_stderr:
                msg += f"; last stderr: {partial_stderr}"
            raise ChartResolutionError(msg) from exc

        if result.returncode != 0:
            truncated_stderr = _truncate_stderr(result.stderr)
            raise ChartResolutionError(
                f"{error_prefix} returned {result.returncode} — last stderr: {truncated_stderr}"
            )

    # -----------------------------------------------------------------------
    # Public chart-resolution methods (Plan 04-06)
    # -----------------------------------------------------------------------

    def repo_add(self, name: str, repo_url: str, env: dict[str, str]) -> None:
        """Run ``helm repo add <name> <repo_url>`` in an isolated env.

        Args:
            name: Repository alias to register (e.g. ``"bitnami"``).
            repo_url: HTTPS URL of the helm repository index.
            env: Full subprocess env dict; must contain HELM_REPOSITORY_CONFIG
                and HELM_REPOSITORY_CACHE for cache isolation (R7).

        Raises:
            ChartResolutionError: helm exited non-zero or timed out (exit_code=4).
        """
        argv = self._build_repo_add_argv(name, repo_url)
        self._run_helm_subcommand(argv, env=env, timeout=60, error_prefix=f"helm repo add {name}")

    def repo_update(self, name: str, env: dict[str, str]) -> None:
        """Run ``helm repo update <name>`` to refresh the cached chart index.

        Args:
            name: Repository alias previously registered via repo_add.
            env: Full subprocess env dict with HELM_REPOSITORY_CONFIG isolation.

        Raises:
            ChartResolutionError: helm exited non-zero or timed out (exit_code=4).
        """
        argv = self._build_repo_update_argv(name)
        self._run_helm_subcommand(
            argv, env=env, timeout=120, error_prefix=f"helm repo update {name}"
        )

    def pull_repo(
        self,
        repo_chart: str,
        destination: pathlib.Path,
        untar_dir: pathlib.Path,
        version: str | None,
        env: dict[str, str],
    ) -> None:
        """Run ``helm pull <repo>/<chart> --destination ... --untar --untar-dir ...``.

        Args:
            repo_chart: ``"<repo-name>/<chart-name>"`` reference string.
            destination: Directory where helm writes the ``.tgz`` tarball.
            untar_dir: Directory where helm extracts the chart (``--untar-dir``).
            version: Chart version string, or ``None`` to pull the latest.
            env: Full subprocess env dict with HELM_REPOSITORY_CONFIG isolation.

        Raises:
            ChartResolutionError: helm exited non-zero or timed out (exit_code=4).
        """
        argv = self._build_pull_repo_argv(repo_chart, destination, untar_dir, version)
        self._run_helm_subcommand(
            argv, env=env, timeout=600, error_prefix=f"helm pull {repo_chart}"
        )
