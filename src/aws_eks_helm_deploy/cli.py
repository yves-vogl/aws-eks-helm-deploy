"""CLI entry point for aws-eks-helm-deploy.

main(argv) is the console_scripts entry point registered in pyproject.toml.
It is also called by __main__.py for `python -m aws_eks_helm_deploy`.

Phase 2: instantiates Settings, configures structured logging (OBS-01/02),
selects the auth strategy via select_strategy(settings), and logs the selection.
Real ACTION dispatch (upgrade/diff/rollback) lands in Phase 3+.

Closes Phase 1 OBS-01 PARTIAL gap (SC5): at least one structlog JSON line is now
emitted on stderr at runtime via logger.info("auth strategy selected", ...).
"""

from __future__ import annotations

import sys

from aws_eks_helm_deploy.auth import select_strategy
from aws_eks_helm_deploy.errors import PipeError
from aws_eks_helm_deploy.logging import bind_safe_context, configure_logging, get_logger
from aws_eks_helm_deploy.pipe_io import PipeIO
from aws_eks_helm_deploy.settings import Settings


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns an integer exit code.

    Args:
        argv: Optional argument list (reserved for future flag parsing).

    Returns:
        0 on success, 1 on Settings construction failure, exc.exit_code on PipeError,
        99 on unexpected Exception.
    """
    try:
        settings = Settings()
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"Configuration error: {exc}\n")
        return 1
    configure_logging(settings)

    # Select auth strategy between configure_logging and PipeIO construction.
    # ConfigurationError surfaces immediately as a pipe failure (exit code 1).
    try:
        strategy = select_strategy(settings)
    except PipeError as exc:
        pipe = PipeIO()
        pipe.fail(exc.user_message)
        return exc.exit_code

    bind_safe_context(auth_strategy=type(strategy).__name__)
    logger = get_logger(__name__)
    logger.info("auth strategy selected", auth_strategy=type(strategy).__name__)

    pipe = PipeIO()
    try:
        # Phase 2 skeleton: strategy selected but not invoked.
        # ACTION dispatch (upgrade / diff / rollback) lands in Phase 3+.
        # Phase 3 will call strategy.get_credentials() inside UpgradeAction.run().
        pipe.success("Phase 2 skeleton — auth strategy selected; action dispatch lands in Phase 3+")
        return 0
    except PipeError as exc:
        pipe.fail(exc.user_message)
        return exc.exit_code
    except Exception:  # noqa: BLE001
        pipe.fail("Unexpected error — see logs")
        return 99


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
