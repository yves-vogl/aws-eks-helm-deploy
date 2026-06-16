"""CLI entry point for aws-eks-helm-deploy.

main(argv) is the console_scripts entry point registered in pyproject.toml.
It is also called by __main__.py for `python -m aws_eks_helm_deploy`.

Phase 1 placeholder: instantiates Settings and PipeIO, emits a success message,
and returns exit code 0. Real ACTION dispatch (upgrade/diff/rollback) lands in
Phase 3+. configure_logging() is deferred to Plan D so OBS-01/02 lands in a
focused commit.
"""

from __future__ import annotations

from aws_eks_helm_deploy.errors import PipeError
from aws_eks_helm_deploy.pipe_io import PipeIO
from aws_eks_helm_deploy.settings import Settings


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns an integer exit code.

    Args:
        argv: Optional argument list (reserved for future flag parsing).

    Returns:
        0 on success, exc.exit_code on PipeError, 99 on unexpected Exception.
    """
    settings = Settings()
    pipe = PipeIO()
    try:
        # Phase 1 skeleton: no real action dispatched yet.
        # ACTION dispatch (upgrade / diff / rollback) lands in Phase 3+.
        _ = settings  # settings is consumed in Phase 3+
        pipe.success("Phase 1 skeleton — no action executed")
        return 0
    except PipeError as exc:
        pipe.fail(exc.user_message)
        return exc.exit_code
    except Exception:  # noqa: BLE001
        pipe.fail("Unexpected error — see logs")
        return 99


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.exit(main())
