"""Error hierarchy for aws-eks-helm-deploy.

All pipe-originated exceptions inherit from PipeError. cli.main() catches
PipeError and maps it to a typed exit code. Bare Exception is caught as exit 99.

Exit code reference:
    1  — PipeError (base) / ConfigurationError
    2  — AuthenticationError
    3  — ClusterAccessError / EksTokenError (shared — both are EKS-reach failures)
    4  — ChartResolutionError
    5  — HelmError
    6  — HelmTimeoutError
    7  — KubeconfigError
"""

from __future__ import annotations


class PipeError(Exception):
    """Root for all pipe-originated errors. cli.main() catches this."""

    exit_code: int = 1

    def __init__(self, message: str, exit_code: int | None = None) -> None:
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code

    @property
    def user_message(self) -> str:
        """Human-readable message safe to surface in pipe output."""
        return str(self)


class ConfigurationError(PipeError):
    """Bad or missing env var. Exit code 1."""

    exit_code = 1


class AuthenticationError(PipeError):
    """STS / OIDC authentication failed. Exit code 2."""

    exit_code = 2


class ClusterAccessError(PipeError):
    """EKS describe-cluster failed. Exit code 3."""

    exit_code = 3


class ChartResolutionError(PipeError):
    """Chart not found or version missing. Exit code 4."""

    exit_code = 4


class HelmError(PipeError):
    """helm exited non-zero. Exit code 5."""

    exit_code = 5


class HelmTimeoutError(PipeError):
    """helm --wait timed out. Exit code 6."""

    exit_code = 6


class EksTokenError(PipeError):
    """EKS bearer-token generation via boto3 failed.

    Exit code 3 (shared with ClusterAccessError). Both errors represent
    EKS-reach failures — a failed token mint and a failed describe-cluster
    call are surfaced to consumers identically. Observability is provided
    by the typed exception class name via structlog (not the exit code).
    """

    exit_code = 3


class KubeconfigError(PipeError):
    """Failed to write the EKS kubeconfig tempfile (disk full, permissions, etc.). Exit code 7."""

    exit_code = 7
