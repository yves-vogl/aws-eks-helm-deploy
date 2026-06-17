"""Structured logging for the pipe.

OBS-01: stable field names listed in STABLE_FIELDS. Phase 2+ binds them at the top of each
action via bind_safe_context(); Phase 1 only provides the infrastructure.

OBS-02: credential blocklist enforced by bind_safe_context(). The ONLY sanctioned wrapper
for adding keys to structlog context is bind_safe_context(). Direct calls to
structlog.contextvars.bind_contextvars() bypass this guard and are excluded by convention in
Phase 1; Phase 5 (SEC-06) adds a lint rule banning direct bind_contextvars() imports.
"""

from __future__ import annotations

import logging
import sys
from typing import cast

import structlog

from aws_eks_helm_deploy.settings import Settings

# OBS-01: stable field names emitted by every action invocation in Phase 2+.
# These become the contract for log consumers (CloudWatch, Datadog, etc.).
STABLE_FIELDS: tuple[str, ...] = (
    "action",
    "cluster",
    "release",
    "namespace",
    "chart_source",
    "auth_strategy",
    "duration_ms",
)

# OBS-02: keys that must NEVER appear in structlog context — they carry credential values.
CREDENTIAL_BLOCKLIST: frozenset[str] = frozenset(
    {
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
        "session_token",
        "bitbucket_step_oidc_token",
        "bitbucket_token",
        "registry_password",
        "registry_username",
        "role_arn",  # not a credential but discloses AWS account topology
    }
)


def configure_logging(settings: Settings) -> None:
    """Configure structlog for the pipe. Call once at startup in cli.main().

    Reads settings.log_format ("human" or "json") and settings.debug (bool).
    Calling this function twice is safe — structlog.configure() replaces the
    previous configuration (idempotent at the semantic level).

    Args:
        settings: Validated pipe settings from environment variables.
    """
    log_level = logging.DEBUG if settings.debug else logging.INFO

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    processors: list[structlog.types.Processor]
    if settings.log_format == "json":
        # OBS-01: one JSON object per line on stderr; all stable keys are present
        # whenever bind_safe_context() has been called at the action entry point.
        processors = [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Human-readable default — colored ConsoleRenderer for developer ergonomics.
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a structlog BoundLogger for the given name.

    Args:
        name: Logger name (typically the module's __name__).

    Returns:
        A structlog BoundLogger bound to the given name.
    """
    return cast(structlog.BoundLogger, structlog.get_logger(name))


def bind_safe_context(**kwargs: object) -> None:
    """Bind key-value pairs to the structlog context, rejecting credential keys.

    This is the ONLY sanctioned wrapper for adding context to structlog in this
    codebase. Every key is checked against CREDENTIAL_BLOCKLIST (case-insensitive)
    before being forwarded to structlog.contextvars.bind_contextvars().

    Args:
        **kwargs: Key-value pairs to bind to the current structlog context.

    Raises:
        ValueError: If any key (lowercased) is in CREDENTIAL_BLOCKLIST.
    """
    for key in kwargs:
        if key.lower() in CREDENTIAL_BLOCKLIST:
            raise ValueError(f"Credential leak: {key!r} is blocklisted")
    structlog.contextvars.bind_contextvars(**kwargs)
