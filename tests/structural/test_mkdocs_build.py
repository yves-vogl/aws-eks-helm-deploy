"""Structural tests for Phase 7 Plan 07-01 mkdocs scaffolding.

Asserts ``mkdocs.yml`` declares the mkdocs-material theme + canonical nav, and
that ``uv run mkdocs build --strict`` exits 0 against the current docs tree
(per D1 + RESEARCH Q9).
"""

from __future__ import annotations

import importlib.util
import pathlib
import shutil
import subprocess
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Paths and invariants
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MKDOCS_YML = REPO_ROOT / "mkdocs.yml"

# Note: the "Admin" slot (docs/admin/repo-settings.md) was removed from the
# published nav post-v2.0.0 — the runbook is for maintainers only and the
# file is excluded via exclude_docs in mkdocs.yml. It stays in the repo for
# version control but does not belong on the public docs site.
REQUIRED_NAV_TITLES: frozenset[str] = frozenset(
    {
        "Home",
        "Quickstart",
        "Migration v1 → v2",
        "Guides",
        "Reference",
        "ADRs",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_mkdocs_yml() -> dict[str, Any]:
    """Load ``mkdocs.yml`` tolerating the ``!!python/name:`` superfences tag.

    mkdocs.yml declares a custom YAML tag for the pymdownx mermaid superfences
    custom_fence (``!!python/name:pymdownx.superfences.fence_code_format``).
    ``yaml.safe_load`` rejects that tag; use the custom loader from mkdocs's own
    config module if available, otherwise add the tag as a no-op constructor.
    """

    class _IgnorePythonNameLoader(yaml.SafeLoader):
        pass

    def _ignore_python_name(loader: yaml.SafeLoader, suffix: str, node: yaml.Node) -> str:
        del loader, suffix, node
        return "<python-name>"

    _IgnorePythonNameLoader.add_multi_constructor(  # type: ignore[no-untyped-call]
        "tag:yaml.org,2002:python/name:", _ignore_python_name
    )
    loaded: dict[str, Any] = yaml.load(
        MKDOCS_YML.read_text(encoding="utf-8"),
        Loader=_IgnorePythonNameLoader,  # noqa: S506
    )
    return loaded


def _collect_nav_top_titles(nav: list[Any]) -> list[str]:
    titles: list[str] = []
    for entry in nav:
        if isinstance(entry, dict):
            titles.extend(entry.keys())
        elif isinstance(entry, str):
            titles.append(entry)
    return titles


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_mkdocs_yml_exists() -> None:
    """mkdocs.yml must exist at the repo root."""
    assert MKDOCS_YML.is_file(), f"mkdocs.yml missing at {MKDOCS_YML}"


def test_mkdocs_yml_declares_mkdocs_material_theme() -> None:
    """mkdocs.yml must declare ``theme: name: material`` (D1)."""
    cfg = _load_mkdocs_yml()
    assert cfg.get("theme", {}).get("name") == "material", (
        "mkdocs.yml must declare `theme: name: material` per D1 / DOC-02. "
        f"Got: {cfg.get('theme')!r}"
    )


def test_mkdocs_yml_has_nav_skeleton() -> None:
    """All Phase 7 nav slots must be present (D1 + D7)."""
    cfg = _load_mkdocs_yml()
    titles = set(_collect_nav_top_titles(cfg["nav"]))
    missing = REQUIRED_NAV_TITLES - titles
    assert not missing, (
        f"mkdocs.yml nav missing required Phase 7 entries: {sorted(missing)}. Got: {sorted(titles)}"
    )


def test_mkdocs_yml_strict_mode_invariant_documented() -> None:
    """``strict: true`` must be declared at the top level of mkdocs.yml.

    Belt-and-braces with the ``--strict`` CLI flag enforced by Plan 07-05's
    docs.yml workflow. RESEARCH Q9 / SI-07-03.
    """
    text = MKDOCS_YML.read_text(encoding="utf-8")
    assert "strict: true" in text, (
        "mkdocs.yml must declare `strict: true` at the top level (RESEARCH Q9)."
    )


def test_mkdocs_build_strict_exits_zero(tmp_path: pathlib.Path) -> None:
    """``mkdocs build --strict`` must exit 0 against the Wave-1 nav skeleton."""
    if importlib.util.find_spec("mkdocs") is None or shutil.which("mkdocs") is None:
        pytest.skip("mkdocs not installed; install with `uv sync --extra docs`")

    site_dir = tmp_path / "site"
    result = subprocess.run(
        ["mkdocs", "build", "--strict", "--site-dir", str(site_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if result.returncode != 0:
        stderr_head = "\n".join(result.stderr.splitlines()[:40])
        stdout_head = "\n".join(result.stdout.splitlines()[:40])
        pytest.fail(
            "mkdocs build --strict failed (returncode="
            f"{result.returncode}).\nSTDERR (first 40 lines):\n{stderr_head}\n"
            f"STDOUT (first 40 lines):\n{stdout_head}"
        )
    assert (site_dir / "index.html").is_file(), "rendered site missing index.html"
