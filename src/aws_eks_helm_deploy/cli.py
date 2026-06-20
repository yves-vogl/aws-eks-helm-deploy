"""CLI entry point for aws-eks-helm-deploy.

main(argv) is the console_scripts entry point registered in pyproject.toml.
It is also called by __main__.py for `python -m aws_eks_helm_deploy`.

Phase 3: ACTION=upgrade dispatches to UpgradeAction. Phase 5+ adds DiffAction + RollbackAction.

Closes Phase 1 OBS-01 PARTIAL gap (SC5): at least one structlog JSON line is now
emitted on stderr at runtime via logger.info("auth strategy selected", ...).

MIG-02: startup scan for v1-era SET/VALUES env vars emits one WARN each (D4).
"""

from __future__ import annotations

import os
import sys
from typing import Final

import structlog

from aws_eks_helm_deploy.actions.diff import DiffAction
from aws_eks_helm_deploy.actions.rollback import RollbackAction
from aws_eks_helm_deploy.actions.upgrade import UpgradeAction
from aws_eks_helm_deploy.auth import select_strategy
from aws_eks_helm_deploy.errors import ConfigurationError, PipeError
from aws_eks_helm_deploy.logging import bind_safe_context, configure_logging, get_logger
from aws_eks_helm_deploy.pipe_io import PipeIO
from aws_eks_helm_deploy.settings import Settings

V1_DEPRECATED_ENV_VARS: Final[tuple[str, ...]] = ("SET", "VALUES")
"""MIG-02: env var names present in v1.x that v2 reuses with different syntax.

v1 accepted SPACE-separated positional list strings; v2 accepts comma-separated values
(with JSON-array fallback). The mere presence of these env vars at startup triggers a
loud one-time deprecation WARN per MIG-02 / CONTEXT D4 to nudge consumers to re-read
the v2 variable reference. The detector is unconditional — not gated by any setting.
"""


def _warn_on_v1_env_vars(log: structlog.BoundLogger) -> None:
    """Emit one WARN per detected v1-era env var present in os.environ.

    MIG-02 / CONTEXT D4: detection runs unconditionally at startup. The WARN's purpose
    is to make v1 consumers re-read the v2 variable reference (the value's syntax may
    have changed from v1 space-separated to v2 comma-separated).

    Args:
        log: Bound structlog logger.

    Returns:
        None. Side effect: 0-2 `mig.v1_env_var_detected` WARN events depending on
        which v1 env vars are present.
    """
    for name in V1_DEPRECATED_ENV_VARS:
        if os.environ.get(name):
            log.warning("mig.v1_env_var_detected", name=name)


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

    # MIG-02 / D4: detect v1-era env var usage at startup; emit WARN per detected var.
    _warn_on_v1_env_vars(get_logger(__name__))

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
        if settings.action == "diff" or (settings.action == "upgrade" and settings.dry_run):
            return DiffAction(settings, strategy=strategy).run(pipe)
        if settings.action == "upgrade":
            return UpgradeAction(settings, strategy=strategy).run(pipe)
        if settings.action == "rollback":
            return RollbackAction(settings, strategy=strategy).run(pipe)
        # The Literal["upgrade", "diff", "rollback"] ensures pydantic rejects unknown values
        # before cli.py sees them — this raise is dead code but kept as a safety net.
        raise ConfigurationError(f"Unsupported action: {settings.action!r}")  # pragma: no cover
    except PipeError as exc:
        pipe.fail(exc.user_message)
        return exc.exit_code
    except Exception:  # noqa: BLE001
        pipe.fail("Unexpected error — see logs")
        return 99


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
