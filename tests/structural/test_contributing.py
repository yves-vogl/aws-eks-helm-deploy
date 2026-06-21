"""Structural tests for Phase 7 / Plan 07-06 / DOC-05.

Asserts CONTRIBUTING.md documents the uv sync / pre-commit / pytest / kind
development loop and the Conventional Commits rule.
"""

from __future__ import annotations

import pathlib

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Paths and invariants
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRIBUTING_MD = REPO_ROOT / "CONTRIBUTING.md"

REQUIRED_TOKENS: frozenset[str] = frozenset(
    {
        "uv sync",
        "pre-commit",
        "pytest",
        "kind",
        "Conventional Commits",
    }
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_contributing_md_exists() -> None:
    """CONTRIBUTING.md must exist at the repo root."""
    assert CONTRIBUTING_MD.is_file(), f"CONTRIBUTING.md missing at {CONTRIBUTING_MD}"


def test_contributing_documents_uv_sync() -> None:
    """DOC-05: CONTRIBUTING.md documents the ``uv sync`` step."""
    assert "uv sync" in CONTRIBUTING_MD.read_text(encoding="utf-8"), (
        "CONTRIBUTING.md must document `uv sync` as part of the dev loop (DOC-05)."
    )


def test_contributing_documents_pre_commit() -> None:
    """DOC-05: CONTRIBUTING.md documents ``pre-commit``."""
    assert "pre-commit" in CONTRIBUTING_MD.read_text(encoding="utf-8"), (
        "CONTRIBUTING.md must document `pre-commit` as part of the dev loop (DOC-05)."
    )


def test_contributing_documents_pytest() -> None:
    """DOC-05: CONTRIBUTING.md references ``pytest`` (the test runner)."""
    assert "pytest" in CONTRIBUTING_MD.read_text(encoding="utf-8"), (
        "CONTRIBUTING.md must reference `pytest` as the test runner (DOC-05)."
    )


def test_contributing_documents_kind() -> None:
    """DOC-05: CONTRIBUTING.md mentions ``kind`` for the integration smoke loop."""
    text = CONTRIBUTING_MD.read_text(encoding="utf-8")
    assert "kind" in text.lower(), (
        "CONTRIBUTING.md must mention `kind` for the integration loop "
        "(case-insensitive — tolerates Kind / KinD / kind) (DOC-05)."
    )


def test_contributing_documents_conventional_commits() -> None:
    """DOC-05: CONTRIBUTING.md references the Conventional Commits rule."""
    assert "Conventional Commits" in CONTRIBUTING_MD.read_text(encoding="utf-8"), (
        "CONTRIBUTING.md must reference Conventional Commits (DOC-05)."
    )


def test_contributing_all_required_tokens_covered() -> None:
    """DOC-05 aggregate gate: every required token must be present."""
    text = CONTRIBUTING_MD.read_text(encoding="utf-8")
    # ``kind`` may appear capitalised; downcast for the membership check.
    text_lower = text.lower()
    missing = sorted(token for token in REQUIRED_TOKENS if token.lower() not in text_lower)
    assert not missing, (
        "CONTRIBUTING.md is missing required DOC-05 dev-loop tokens: "
        f"{missing}. Each token must appear at least once."
    )
