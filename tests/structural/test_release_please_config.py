"""Structural tests for `.release-please-config.json` schema (Phase 6 / CI-02 / CONTEXT D1)."""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / ".release-please-config.json"
MANIFEST_PATH = REPO_ROOT / ".release-please-manifest.json"
REQUIRED_KEYS: frozenset[str] = frozenset(
    {"$schema", "release-type", "package-name", "extra-files"}
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> dict[str, Any]:
    """Load .release-please-config.json once for the module."""
    return json.loads(CONFIG_PATH.read_text())  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_config_exists() -> None:
    """`.release-please-config.json` must exist at the repo root."""
    assert CONFIG_PATH.is_file(), f"Expected {CONFIG_PATH} to exist"


def test_manifest_exists() -> None:
    """`.release-please-manifest.json` must exist at the repo root."""
    assert MANIFEST_PATH.is_file(), f"Expected {MANIFEST_PATH} to exist"


def test_release_please_config_is_valid_json() -> None:
    """`.release-please-config.json` must be parseable as JSON."""
    json.loads(CONFIG_PATH.read_text())


def test_config_has_required_keys(config: dict[str, Any]) -> None:
    """Config must contain all required top-level keys (D1 contract)."""
    missing = REQUIRED_KEYS - set(config.keys())
    assert not missing, f"Missing required keys in .release-please-config.json: {missing}"


def test_release_type_is_python(config: dict[str, Any]) -> None:
    """release-type must be 'python' so release-please updates pyproject.toml (D1)."""
    assert config["release-type"] == "python"


def test_package_name_is_aws_eks_helm_deploy(config: dict[str, Any]) -> None:
    """package-name must match the distribution name (D1)."""
    assert config["package-name"] == "aws-eks-helm-deploy"


def test_extra_files_lists_pipe_yml(config: dict[str, Any]) -> None:
    """extra-files must include pipe.yml with type=yaml and jsonpath=$.image (D1 + RESEARCH)."""
    extra_files: list[dict[str, str]] = config["extra-files"]
    matching = [
        entry
        for entry in extra_files
        if entry.get("path") == "pipe.yml"
        and entry.get("type") == "yaml"
        and entry.get("jsonpath") == "$.image"
    ]
    assert matching, (
        "extra-files must contain an entry with path='pipe.yml', type='yaml', jsonpath='$.image'."
        f" Found: {extra_files}"
    )


def test_manifest_seeds_2_0_0_rc_0() -> None:
    """Manifest must seed the version baseline at 2.0.0-rc.0 (CONTEXT D1)."""
    manifest: dict[str, str] = json.loads(MANIFEST_PATH.read_text())
    assert manifest["."] == "2.0.0-rc.0", (
        f"Expected manifest['.'] == '2.0.0-rc.0', got {manifest['.']!r}"
    )
