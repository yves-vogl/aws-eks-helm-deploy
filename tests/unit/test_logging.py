"""Unit tests for aws_eks_helm_deploy.logging.

Covers:
  - configure_logging with human (default) renderer
  - configure_logging with json renderer (LOG_FORMAT=json)
  - DEBUG=true lowers log threshold to DEBUG
  - DEBUG=false (default) blocks debug-level lines
  - configure_logging idempotency (double-call)
  - bind_safe_context blocks each credential key in CREDENTIAL_BLOCKLIST
  - bind_safe_context is case-insensitive on key comparison
  - bind_safe_context forwards safe keys to structlog.contextvars.bind_contextvars
  - get_logger returns an object with info and debug attributes
  - STABLE_FIELDS exact regression guard

100% line + branch coverage on src/aws_eks_helm_deploy/logging.py is required
so that Plan B's --cov-fail-under=100 gate stays green once logging.py exists.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
import structlog
from pytest_mock import MockerFixture

from aws_eks_helm_deploy.logging import (
    CREDENTIAL_BLOCKLIST,
    STABLE_FIELDS,
    bind_safe_context,
    configure_logging,
    get_logger,
)
from aws_eks_helm_deploy.settings import Settings

# ---------------------------------------------------------------------------
# Autouse fixture: reset structlog state between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_structlog() -> Iterator[None]:
    """Reset structlog configuration and context vars after each test."""
    yield
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()


# ---------------------------------------------------------------------------
# configure_logging — human renderer
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_configure_logging_human_default(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Human renderer is active when LOG_FORMAT is unset (default)."""
    # Ensure LOG_FORMAT is not set
    monkeypatch.delenv("LOG_FORMAT", raising=False)
    settings = Settings()
    configure_logging(settings)

    get_logger("test").info("hello")  # type: ignore[union-attr]

    captured = capsys.readouterr()
    assert "hello" in captured.err
    # Human renderer output is NOT valid JSON (it uses colored key=value format)
    has_json_line = False
    for line in captured.err.splitlines():
        if not line.strip():
            continue
        try:
            json.loads(line)
            has_json_line = True
        except json.JSONDecodeError:
            pass
    assert not has_json_line, "Human renderer must NOT emit JSON"


# ---------------------------------------------------------------------------
# configure_logging — JSON renderer
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_configure_logging_json_emits_parseable_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JSON renderer emits one parseable JSON object per line."""
    monkeypatch.setenv("LOG_FORMAT", "json")
    settings = Settings()
    configure_logging(settings)

    get_logger("test").info("hello", action="upgrade")  # type: ignore[union-attr]

    captured = capsys.readouterr()
    matched: dict[str, object] | None = None
    for line in captured.err.splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
            if parsed.get("event") == "hello":
                matched = parsed
        except json.JSONDecodeError:
            continue

    assert matched is not None, "No JSON line with event='hello' found in stderr"
    assert matched.get("action") == "upgrade"
    assert "timestamp" in matched, "JSON output must include a timestamp key"
    # Verify ISO-8601-ish format (starts with digit year)
    ts = str(matched["timestamp"])
    assert ts[0].isdigit(), f"timestamp {ts!r} does not look like ISO-8601"


# ---------------------------------------------------------------------------
# DEBUG level control
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_debug_true_lowers_threshold(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEBUG=true makes debug-level messages appear on stderr."""
    monkeypatch.setenv("DEBUG", "true")
    settings = Settings()
    configure_logging(settings)

    get_logger("test").debug("dbg")  # type: ignore[union-attr]

    captured = capsys.readouterr()
    assert "dbg" in captured.err


@pytest.mark.unit
def test_debug_false_blocks_debug_lines(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """DEBUG=false (default) means debug-level messages do NOT appear."""
    settings = Settings()
    assert settings.debug is False
    configure_logging(settings)

    get_logger("test").debug("dbg")  # type: ignore[union-attr]

    captured = capsys.readouterr()
    assert "dbg" not in captured.err


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_configure_logging_is_idempotent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Calling configure_logging twice does not duplicate log output."""
    settings = Settings()
    configure_logging(settings)
    configure_logging(settings)

    get_logger("test").info("once")  # type: ignore[union-attr]

    captured = capsys.readouterr()
    # "once" must appear at least once
    assert "once" in captured.err
    # Must not appear more than once (no handler duplication)
    assert captured.err.count("once") == 1


# ---------------------------------------------------------------------------
# bind_safe_context — credential guard
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_bind_safe_context_blocks_aws_access_key_id() -> None:
    """bind_safe_context raises ValueError for aws_access_key_id."""
    with pytest.raises(ValueError, match="aws_access_key_id"):
        bind_safe_context(aws_access_key_id="AKIA...")


@pytest.mark.unit
@pytest.mark.parametrize("cred_key", sorted(CREDENTIAL_BLOCKLIST))
def test_bind_safe_context_blocks_all_credentials(cred_key: str) -> None:
    """bind_safe_context raises ValueError for every member of CREDENTIAL_BLOCKLIST."""
    with pytest.raises(ValueError, match=cred_key):
        bind_safe_context(**{cred_key: "secret-value"})


@pytest.mark.unit
def test_bind_safe_context_case_insensitive() -> None:
    """bind_safe_context guard is case-insensitive (AWS_SECRET_ACCESS_KEY blocked)."""
    with pytest.raises(ValueError):
        bind_safe_context(AWS_SECRET_ACCESS_KEY="secret")  # noqa: S106


@pytest.mark.unit
def test_bind_safe_context_passes_safe_keys(mocker: MockerFixture) -> None:
    """bind_safe_context forwards non-blocklisted keys to bind_contextvars."""
    mock_bind = mocker.patch("aws_eks_helm_deploy.logging.structlog.contextvars.bind_contextvars")
    bind_safe_context(action="upgrade", cluster="prod")
    mock_bind.assert_called_once_with(action="upgrade", cluster="prod")


# ---------------------------------------------------------------------------
# get_logger
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_logger_returns_bound_logger() -> None:
    """get_logger returns an object with info and debug attributes."""
    logger = get_logger("foo")
    assert hasattr(logger, "info")
    assert hasattr(logger, "debug")


# ---------------------------------------------------------------------------
# STABLE_FIELDS regression guard
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_stable_fields_contains_obs01_contract() -> None:
    """STABLE_FIELDS must match the exact OBS-01 contract tuple (order matters)."""
    assert STABLE_FIELDS == (
        "action",
        "cluster",
        "release",
        "namespace",
        "chart_source",
        "auth_strategy",
        "duration_ms",
    )
