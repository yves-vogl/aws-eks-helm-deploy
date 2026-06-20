"""Structural tests for .github/dependabot.yml (Phase 6 / CI-05 / SEC-08 / D6 / RESEARCH C3).

Asserts: 3 ecosystems, pip uses chore prefix (C3), docker uses fix prefix (SEC-08),
explicit groups blocks, weekly schedule for all ecosystems.
"""

from __future__ import annotations

import pathlib
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

DEPENDABOT_YML_PATH = pathlib.Path(__file__).resolve().parents[2] / ".github" / "dependabot.yml"
EXPECTED_ECOSYSTEMS: frozenset[str] = frozenset({"pip", "docker", "github-actions"})

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> dict[str, Any]:
    """Parse .github/dependabot.yml once for the module."""
    return yaml.safe_load(DEPENDABOT_YML_PATH.read_text())  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_ecosystem(config: dict[str, Any], ecosystem: str) -> dict[str, Any]:
    """Return the update entry matching the given package-ecosystem name."""
    for entry in config["updates"]:
        if entry.get("package-ecosystem") == ecosystem:
            return entry  # type: ignore[no-any-return]
    raise KeyError(f"Ecosystem {ecosystem!r} not found in dependabot.yml updates")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_dependabot_yml_exists() -> None:
    """.github/dependabot.yml must exist at the repo root."""
    assert DEPENDABOT_YML_PATH.is_file(), f"Expected {DEPENDABOT_YML_PATH} to exist"


def test_dependabot_has_three_ecosystems(config: dict[str, Any]) -> None:
    """dependabot.yml must configure exactly 3 ecosystems: pip, docker, github-actions (D6)."""
    actual: frozenset[str] = frozenset(entry["package-ecosystem"] for entry in config["updates"])
    assert actual == EXPECTED_ECOSYSTEMS, f"Expected ecosystems {EXPECTED_ECOSYSTEMS}, got {actual}"


def test_pip_ecosystem_uses_chore_prefix(config: dict[str, Any]) -> None:
    """pip ecosystem must use 'chore' commit-message prefix (C3 correction).

    Using 'fix' would cause release-please to cut a patch release on every
    Python dep bump — the C3 correction prevents this.
    """
    prefix = _get_ecosystem(config, "pip")["commit-message"]["prefix"]
    assert prefix == "chore", (
        f"pip commit-message.prefix must be 'chore' (C3 correction), got {prefix!r}"
    )


def test_docker_ecosystem_uses_fix_prefix(config: dict[str, Any]) -> None:
    """docker ecosystem must use 'fix' commit-message prefix (SEC-08 contract).

    fix(deps): base-image bump → release-please reads as patch → opens Release PR
    → maintainer merges → release.yml republishes a freshly-scanned image to GHCR.
    """
    prefix = _get_ecosystem(config, "docker")["commit-message"]["prefix"]
    assert prefix == "fix", (
        f"docker commit-message.prefix must be 'fix' (SEC-08 contract), got {prefix!r}"
    )


def test_github_actions_ecosystem_uses_chore_prefix(config: dict[str, Any]) -> None:
    """github-actions ecosystem must use 'chore' commit-message prefix.

    Action SHA bumps are CI-only; they must not trigger release-please patch releases.
    """
    prefix = _get_ecosystem(config, "github-actions")["commit-message"]["prefix"]
    assert prefix == "chore", (
        f"github-actions commit-message.prefix must be 'chore', got {prefix!r}"
    )


def test_all_ecosystems_have_groups(config: dict[str, Any]) -> None:
    """Every ecosystem entry must define a non-empty 'groups' dict (D6 PR-noise reduction)."""
    for entry in config["updates"]:
        ecosystem = entry["package-ecosystem"]
        groups = entry.get("groups")
        assert groups and isinstance(groups, dict) and len(groups) > 0, (
            f"Ecosystem {ecosystem!r} is missing a non-empty 'groups' block (D6 contract)"
        )


def test_docker_groups_match_base_patterns(config: dict[str, Any]) -> None:
    """docker 'docker-base' group must include 'python' and a 'debian*' pattern."""
    docker_entry = _get_ecosystem(config, "docker")
    patterns: list[str] = docker_entry["groups"]["docker-base"]["patterns"]
    assert "python" in patterns, f"docker-base group must include 'python' pattern, got {patterns}"
    debian_patterns = [p for p in patterns if p.startswith("debian")]
    assert debian_patterns, f"docker-base group must include a 'debian*' pattern, got {patterns}"


def test_github_actions_group_matches_all(config: dict[str, Any]) -> None:
    """github-actions 'actions' group must use the catch-all pattern ['*']."""
    entry = _get_ecosystem(config, "github-actions")
    patterns: list[str] = entry["groups"]["actions"]["patterns"]
    assert patterns == ["*"], (
        f"github-actions 'actions' group patterns must be ['*'], got {patterns}"
    )


def test_all_ecosystems_use_weekly_schedule(config: dict[str, Any]) -> None:
    """Every ecosystem must use weekly schedule interval (Monday 06:00 Europe/Berlin)."""
    for entry in config["updates"]:
        ecosystem = entry["package-ecosystem"]
        interval = entry["schedule"]["interval"]
        assert interval == "weekly", (
            f"Ecosystem {ecosystem!r} schedule.interval must be 'weekly', got {interval!r}"
        )
