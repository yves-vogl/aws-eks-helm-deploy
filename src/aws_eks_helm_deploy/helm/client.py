"""Typed HelmClient — the sole subprocess entry point for the aws-eks-helm-deploy pipe.

REQ traceability:
    PIPE-01    — upgrade_install invokes ``helm upgrade --install`` with exact argv contract
    PIPE-02    — diff invokes ``helm diff upgrade`` via the bundled helm-diff plugin (Phase 5 D2)
    PIPE-04    — rollback invokes ``helm rollback <release> <revision>`` (Phase 5 D5)
    PIPE-05    — SAFE_UPGRADE=true adds --wait --atomic --description "pipe:safe-upgrade" to
                 upgrade argv (Phase 5 D5 / 05-RESEARCH CONTRADICTION 2)
    PIPE-06    — typed errors: HelmExecutionError (exit=5) and HelmTimeoutError (exit=6)
    HISTORY-02 — ``--history-max`` passthrough; None suppresses the flag
    META-01    — ``--set-string`` for ALL injected key=value pairs (Pitfall 4: curly braces)
    CHART-02   — repo_add / repo_update / pull_repo typed methods for RepoChart (Phase 4)
    CHART-03   — registry_login / pull_oci typed methods for OciChart (Phase 4)
    SEC-06     — every stdout/stderr capture site routes through self._redactor (CONTEXT D1)

Architecture:
    CONTEXT D1 — this is the ONLY module in the codebase that imports ``subprocess``
                 for HELM commands. chart/oci.py imports subprocess for cosign (CONTEXT D5
                 scoped exception — cosign is a separate binary, not a helm subcommand).
                 CONTEXT D1 — redactor defaults to redact_helm_output; tests inject a no-op
                 via redactor= kwarg.
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
from collections.abc import Callable
from typing import TYPE_CHECKING, Final

from aws_eks_helm_deploy.errors import ChartResolutionError, HelmExecutionError, HelmTimeoutError
from aws_eks_helm_deploy.helm.redact import redact_helm_output

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

SAFE_UPGRADE_DESCRIPTION: Final[str] = "pipe:safe-upgrade"
"""Marker substring stored in helm release history description when SAFE_UPGRADE=true.

The RollbackAction pre-flight check searches for this substring in HelmRevision.description
to detect revisions deployed with --wait --atomic. See 05-RESEARCH "CONTRADICTION 2" for the
rationale: helm 3.x does NOT record --wait status in the history description by default,
so the pipe explicitly sets it via --description on upgrade.
"""

__all__: list[str] = ["HelmClient", "HelmResult", "HelmRevision", "SAFE_UPGRADE_DESCRIPTION"]  # noqa: RUF022


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
        redactor: Callable that scrubs Secret payloads from captured
            stdout/stderr; defaults to ``redact_helm_output`` (SEC-06 /
            CONTEXT D1). Inject a no-op (``lambda s: s``) in tests that
            need raw output.
    """

    def __init__(
        self,
        kubeconfig_path: pathlib.Path,
        *,
        redactor: Callable[[str], str] = redact_helm_output,
    ) -> None:
        self._kubeconfig_path = kubeconfig_path
        self._redactor = redactor

    def _build_argv(
        self,
        release: str,
        chart_path: pathlib.Path,
        namespace: str,
        values_files: list[str],
        set_args: list[str],
        history_max: int | None,
        timeout: str,
        *,
        safe_upgrade: bool = False,
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
            safe_upgrade: When ``True``, appends ``["--wait", "--atomic",
                "--description", SAFE_UPGRADE_DESCRIPTION]`` after the
                ``--history-max`` block (PIPE-05 / CONTEXT D5). The
                ``SAFE_UPGRADE_DESCRIPTION`` marker enables the
                ``RollbackAction`` pre-flight check to detect safe-upgraded
                revisions (05-RESEARCH CONTRADICTION 2 workaround).

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
        if safe_upgrade:
            # PIPE-05 / CONTEXT D5: --wait + --atomic + --description marker for rollback safety.
            argv.extend(["--wait", "--atomic", "--description", SAFE_UPGRADE_DESCRIPTION])
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
        *,
        safe_upgrade: bool = False,
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
            safe_upgrade: When ``True``, forwards to ``_build_argv`` to append
                ``--wait --atomic --description "pipe:safe-upgrade"`` (PIPE-05 /
                CONTEXT D5). Default ``False`` preserves backward compatibility.

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
            safe_upgrade=safe_upgrade,
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
                partial_stderr = self._redactor(raw)[-1024:]
            msg = f"helm upgrade timed out after {exc.timeout}s"
            if partial_stderr:
                msg += f"; last stderr: {partial_stderr}"
            raise HelmTimeoutError(msg) from exc

        truncated_stderr = _truncate_stderr(self._redactor(result.stderr))

        if result.returncode != 0:
            raise HelmExecutionError(
                f"helm upgrade returned {result.returncode} — last stderr: {truncated_stderr}"
            )

        rev_match = REVISION_REGEX.search(result.stdout)
        revision = int(rev_match.group(1)) if rev_match else None
        return HelmResult(
            stdout=self._redactor(result.stdout),
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
            truncated_stderr = _truncate_stderr(self._redactor(result.stderr))
            raise HelmExecutionError(
                f"helm history returned {result.returncode} — last stderr: {truncated_stderr}"
            )
        entries: list[dict[str, int | str]] = json.loads(self._redactor(result.stdout))
        return [
            HelmRevision(
                revision=int(entry["revision"]),
                status=str(entry["status"]),
                chart=str(entry["chart"]),
                description=str(entry["description"]),
            )
            for entry in entries
        ]

    def diff(
        self,
        release: str,
        chart: ResolvedChart,
        namespace: str,
        values_files: list[str],
        set_args: list[str],
        timeout: str,
    ) -> str:
        """Run ``helm diff upgrade`` and return the redacted diff text (PIPE-02 / SEC-06).

        Invokes the bundled helm-diff plugin (Phase 5 D2 / Dockerfile stage
        ``helm-diff-fetch``). The diff text is routed through ``self._redactor``
        BEFORE being returned to the caller, so Secret payloads are scrubbed at
        the HelmClient boundary (defense-in-depth — SEC-06 / CONTEXT D1).

        helm-diff exit code semantics (per databus23/helm-diff README):
            - ``0`` — no differences (diff is empty)
            - ``1`` — differences exist (this is SUCCESS for the diff workflow)
            - ``≥ 2`` — error (helm-diff encountered an unexpected failure)

        Both exit codes 0 and 1 are treated as success; only ``≥ 2`` raises
        ``HelmExecutionError``.

        Args:
            release: Helm release name.
            chart: Resolved local chart descriptor. ``source_path`` is extracted
                and passed to ``_build_diff_argv``.
            namespace: Kubernetes namespace.
            values_files: List of values file paths; each produces
                ``["--values", path]`` in order (last-wins semantics).
            set_args: List of ``"key=value"`` strings; each produces
                ``["--set-string", "key=value"]`` (Pitfall 4 / RESEARCH G).
            timeout: Go-duration string passed to ``_parse_timeout``
                (e.g. ``"600s"`` or ``"10m"``).

        Returns:
            Redacted diff text (stdout from ``helm diff upgrade``).

        Raises:
            HelmExecutionError: helm-diff exited with returncode ``≥ 2``.
            HelmTimeoutError: ``subprocess.run`` raised ``subprocess.TimeoutExpired``.
        """
        argv = self._build_diff_argv(
            release,
            chart.source_path,
            namespace,
            values_files,
            set_args,
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
                partial_stderr = self._redactor(raw)[-1024:]
            msg = f"helm diff timed out after {exc.timeout}s"
            if partial_stderr:
                msg += f"; last stderr: {partial_stderr}"
            raise HelmTimeoutError(msg) from exc

        # helm-diff exit code 1 = "differences exist" = SUCCESS for the diff workflow.
        # Only returncode >= 2 indicates an actual error.
        if result.returncode >= 2:
            truncated_stderr = _truncate_stderr(self._redactor(result.stderr))
            raise HelmExecutionError(
                f"helm diff returned {result.returncode} — last stderr: {truncated_stderr}"
            )

        return self._redactor(result.stdout)

    def rollback(
        self,
        release: str,
        revision: int,
        namespace: str,
        timeout: str,
    ) -> None:
        """Run ``helm rollback <release> <revision>`` and return None on success (PIPE-04).

        Constructs argv via ``_build_rollback_argv``, invokes ``subprocess.run``
        with ``capture_output=True, text=True, check=False``, and maps exit codes
        to typed errors from the PipeError hierarchy (PIPE-06):

        - ``returncode != 0``  → ``HelmExecutionError`` (exit_code=5)
        - ``subprocess.TimeoutExpired`` → ``HelmTimeoutError`` (exit_code=6)

        On success, returns ``None`` — the caller (``RollbackAction``) logs the
        result at INFO level via structlog; stdout is not needed at the action layer.

        Stderr on the error path is redacted via ``self._redactor`` before appearing
        in the ``HelmExecutionError`` message (T-05-01 / SEC-06).

        Args:
            release: Helm release name.
            revision: Target revision number (must be a positive int).
            namespace: Kubernetes namespace.
            timeout: Go-duration string, e.g. ``"600s"`` or ``"10m"``.

        Raises:
            HelmExecutionError: helm exited with a non-zero return code (exit_code=5).
            HelmTimeoutError: ``subprocess.run`` raised ``subprocess.TimeoutExpired`` (exit_code=6).
        """
        argv = self._build_rollback_argv(release, revision, namespace)
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
                partial_stderr = self._redactor(raw)[-1024:]
            msg = f"helm rollback timed out after {exc.timeout}s"
            if partial_stderr:
                msg += f"; last stderr: {partial_stderr}"
            raise HelmTimeoutError(msg) from exc

        if result.returncode != 0:
            truncated_stderr = _truncate_stderr(self._redactor(result.stderr))
            raise HelmExecutionError(
                f"helm rollback returned {result.returncode} — last stderr: {truncated_stderr}"
            )

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

    def _build_registry_login_argv(self, registry_host: str, username: str) -> list[str]:
        """Build ``helm registry login <host> --username <u> --password-stdin`` argv.

        The password is passed via subprocess ``input=``, NOT via argv (R4 — prevents
        credential exposure in process listing / ``ps ax``).
        """
        return [
            "helm",
            "registry",
            "login",
            registry_host,
            "--username",
            username,
            "--password-stdin",  # R4 — password via stdin, NEVER argv
        ]

    def _build_pull_oci_argv(
        self,
        reference: str,
        destination: pathlib.Path,
        untar_dir: pathlib.Path,
        version: str | None,
    ) -> list[str]:
        """Build ``helm pull oci://<ref> --destination ... --untar --untar-dir ...`` argv."""
        argv: list[str] = [
            "helm",
            "pull",
            f"oci://{reference}",
            "--destination",
            str(destination),
            "--untar",
            "--untar-dir",
            str(untar_dir),
        ]
        if version is not None:
            argv.extend(["--version", version])
        return argv

    def _build_diff_argv(
        self,
        release: str,
        chart_path: pathlib.Path,
        namespace: str,
        values_files: list[str],
        set_args: list[str],
    ) -> list[str]:
        """Build the ``helm diff upgrade`` argv list (pure function — no I/O).

        The first 9 elements are always stable (PIPE-02):
            ``["helm", "diff", "upgrade", release, str(chart_path),
               "--namespace", namespace, "--kubeconfig", str(self._kubeconfig_path)]``

        Unlike ``_build_argv`` (for ``helm upgrade --install``), this method does NOT
        include ``--install``, ``--timeout``, or ``--history-max`` — helm diff is a
        read-only command and these flags are not applicable or accepted.

        SEC-06: output from the subprocess that uses this argv flows through
        ``self._redactor`` in ``diff()`` before being returned to the caller.
        PIPE-02: this argv serves the ACTION=diff / DRY_RUN=true workflow.

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

        Returns:
            Complete argv list suitable for ``subprocess.run``.
        """
        argv: list[str] = [
            "helm",
            "diff",
            "upgrade",
            release,
            str(chart_path),
            "--namespace",
            namespace,
            "--kubeconfig",
            str(self._kubeconfig_path),
        ]
        for vf in values_files:
            argv.extend(["--values", vf])
        for sa in set_args:
            argv.extend(["--set-string", sa])
        return argv

    def _build_rollback_argv(
        self,
        release: str,
        revision: int,
        namespace: str,
    ) -> list[str]:
        """Build the ``helm rollback`` argv list (pure function — no I/O).

        Returns the stable 8-element list (PIPE-04):
            ``["helm", "rollback", release, str(revision),
               "--namespace", namespace, "--kubeconfig", str(self._kubeconfig_path)]``

        No ``--wait`` or ``--timeout`` are added here — helm rollback uses its own
        defaults. Safety is enforced BEFORE this call by RollbackAction's pre-flight
        check against SAFE_UPGRADE_DESCRIPTION (CONTEXT D5 / 05-RESEARCH CONTRADICTION 2).

        Args:
            release: Helm release name.
            revision: Target revision number. Converted to ``str`` for argv.
            namespace: Kubernetes namespace.

        Returns:
            Complete argv list suitable for ``subprocess.run``.
        """
        return [
            "helm",
            "rollback",
            release,
            str(revision),
            "--namespace",
            namespace,
            "--kubeconfig",
            str(self._kubeconfig_path),
        ]

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
            truncated_stderr = _truncate_stderr(self._redactor(result.stderr))
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

    def registry_login(
        self,
        registry_host: str,
        username: str,
        password: str,
        env: dict[str, str],
    ) -> None:
        """Run ``helm registry login <host> --username <u> --password-stdin``.

        The password is passed via subprocess ``input=``, NEVER via argv (R4 — prevents
        credential exposure in process listing / ``ps ax``). The caller must unwrap
        ``SecretStr`` via ``.get_secret_value()`` before passing the plaintext here;
        that single unwrap site lives in ``chart/oci.py::OciChart._run_helm_registry_login``
        (R13 — single SecretStr unwrap site).

        Args:
            registry_host: OCI registry hostname, e.g. ``"ghcr.io"`` or
                ``"127.0.0.1:5555"``.
            username: Registry username.
            password: Plaintext password (caller has already unwrapped SecretStr).
            env: Full subprocess env dict; must contain ``HELM_REGISTRY_CONFIG`` and
                ``DOCKER_CONFIG`` for credential isolation (RESEARCH §5).

        Raises:
            ChartResolutionError: helm exited non-zero or timed out (exit_code=4).
        """
        argv = self._build_registry_login_argv(registry_host, username)
        # Bypass _run_helm_subcommand because we need input=password for --password-stdin.
        try:
            result = subprocess.run(  # noqa: S603
                argv,
                input=password,
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=60,
            )
        except subprocess.TimeoutExpired as exc:
            raise ChartResolutionError(
                f"helm registry login {registry_host} timed out after {exc.timeout}s"
            ) from exc

        if result.returncode != 0:
            truncated_stderr = _truncate_stderr(self._redactor(result.stderr))
            raise ChartResolutionError(
                f"helm registry login {registry_host} returned {result.returncode} — "
                f"last stderr: {truncated_stderr}"
            )

    def pull_oci(
        self,
        reference: str,
        destination: pathlib.Path,
        untar_dir: pathlib.Path,
        version: str | None,
        env: dict[str, str],
    ) -> None:
        """Run ``helm pull oci://<reference> --destination ... --untar --untar-dir ...``.

        Args:
            reference: Already-stripped OCI reference without the ``oci://`` prefix
                (e.g. ``"127.0.0.1:5555/charts/redis"``).
            destination: Directory where helm writes the ``.tgz`` tarball.
            untar_dir: Directory where helm extracts the chart (``--untar-dir``).
            version: Chart version string, or ``None`` to pull the latest.
            env: Full subprocess env dict; must contain ``HELM_REGISTRY_CONFIG`` and
                ``DOCKER_CONFIG`` for credential isolation (RESEARCH §5).

        Raises:
            ChartResolutionError: helm exited non-zero or timed out (exit_code=4).
        """
        argv = self._build_pull_oci_argv(reference, destination, untar_dir, version)
        self._run_helm_subcommand(
            argv, env=env, timeout=600, error_prefix=f"helm pull oci://{reference}"
        )
