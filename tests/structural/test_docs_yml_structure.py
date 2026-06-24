"""Structural tests for `.github/workflows/docs.yml` (Plan 07-05 / DOC-02 SC-1 + SC-3 / D9).

Enforces SI-07-01 (no id-token), concurrency settings, generator-before-build ordering,
40-char SHA pinning, and mike deploy presence.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

WF = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "docs.yml"


def _load() -> dict:
    return yaml.safe_load(WF.read_text())


def test_docs_yml_exists() -> None:
    assert WF.exists()


def test_docs_yml_does_not_request_id_token() -> None:
    """SI-07-01 — no id-token: write anywhere in this workflow."""
    text = WF.read_text()
    assert "id-token" not in text, "docs.yml MUST NOT request id-token"


def test_docs_yml_concurrency_cancel_in_progress_false() -> None:
    data = _load()
    assert data["concurrency"]["cancel-in-progress"] is False
    assert "docs-deploy-" in data["concurrency"]["group"]


def test_docs_yml_permissions_least_privilege() -> None:
    """Workflow-level perms are read-only; contents:write is hoisted to the deploy job.

    OpenSSF Scorecard best practice (TokenPermissionsID) — least-privilege
    GITHUB_TOKEN. The mike push to gh-pages still needs contents:write at job
    level only.
    """
    data = _load()
    assert data["permissions"] == {"contents": "read"}, (
        f"Top-level permissions must be {{'contents': 'read'}}; got {data['permissions']!r}"
    )
    deploy_perms = data["jobs"]["deploy"].get("permissions", {})
    assert deploy_perms.get("contents") == "write", (
        f"Job 'deploy' must declare permissions.contents:write for the mike gh-pages push; "
        f"got {deploy_perms!r}"
    )


def test_docs_yml_uses_40_char_sha_pins() -> None:
    text = WF.read_text()
    for match in re.finditer(r"uses:\s*([\w/-]+)@([\w]+)", text):
        ref = match.group(2)
        assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref), (
            f"uses: ref must be 40-char SHA, got {match.group(0)}"
        )


def test_docs_yml_generator_runs_before_strict_build() -> None:
    text = WF.read_text()
    gen_idx = text.find("scripts/generate-variables-doc.py")
    build_idx = text.find("mkdocs build --strict")
    assert 0 < gen_idx < build_idx, (
        "generator MUST run before strict build (RESEARCH Q10 pitfall #4)"
    )


def test_docs_yml_has_mike_deploy_step() -> None:
    text = WF.read_text()
    assert "mike deploy --push --update-aliases v2 latest" in text


def test_docs_yml_strict_build_step() -> None:
    text = WF.read_text()
    assert "mkdocs build --strict" in text
