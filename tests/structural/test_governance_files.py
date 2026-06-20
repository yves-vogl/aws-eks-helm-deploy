"""Structural tests for Phase 6 Plan 06-10 governance files.

Asserts that:
- docs/admin/repo-settings.md exists and is comprehensive (PVR, auto-merge,
  branch protection, signed commits, project board, label taxonomy).
- .github/ISSUE_TEMPLATE/bug_report.yml and feature_request.yml parse as valid
  YAML, have a ``body:`` section with required fields, and declare ``labels:``.
- .github/ISSUE_TEMPLATE/config.yml has blank_issues_enabled=false and
  contact_links with a security entry.
- .github/PULL_REQUEST_TEMPLATE.md has the required section headers.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
REPO_SETTINGS = REPO_ROOT / "docs" / "admin" / "repo-settings.md"
BUG_TEMPLATE = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml"
FEATURE_TEMPLATE = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml"
CONFIG_YML = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml"
PR_TEMPLATE = REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"


# ---------------------------------------------------------------------------
# docs/admin/repo-settings.md
# ---------------------------------------------------------------------------


def test_repo_settings_exists() -> None:
    """docs/admin/repo-settings.md must exist."""
    assert REPO_SETTINGS.exists(), f"Missing: {REPO_SETTINGS}"


def test_repo_settings_min_length() -> None:
    """docs/admin/repo-settings.md must be at least 80 lines (comprehensive runbook)."""
    lines = REPO_SETTINGS.read_text().splitlines()
    assert len(lines) >= 80, f"docs/admin/repo-settings.md too short: {len(lines)} lines (min 80)"


def test_repo_settings_mentions_pvr() -> None:
    """docs/admin/repo-settings.md must mention Private Vulnerability Reporting."""
    content = REPO_SETTINGS.read_text()
    assert "private-vulnerability-reporting" in content, (
        "docs/admin/repo-settings.md must contain 'private-vulnerability-reporting'"
    )


def test_repo_settings_mentions_auto_merge() -> None:
    """docs/admin/repo-settings.md must document the allow_auto_merge repo setting."""
    content = REPO_SETTINGS.read_text()
    assert "allow_auto_merge" in content, (
        "docs/admin/repo-settings.md must contain 'allow_auto_merge'"
    )


def test_repo_settings_mentions_required_signatures() -> None:
    """docs/admin/repo-settings.md must document GPG-signed commits via required_signatures."""
    content = REPO_SETTINGS.read_text()
    assert "required_signatures" in content, (
        "docs/admin/repo-settings.md must contain 'required_signatures'"
    )


def test_repo_settings_mentions_label_create() -> None:
    """docs/admin/repo-settings.md must contain the gh label create taxonomy loop."""
    content = REPO_SETTINGS.read_text()
    assert "gh label create" in content, (
        "docs/admin/repo-settings.md must contain 'gh label create' taxonomy commands"
    )


def test_repo_settings_mentions_project_board() -> None:
    """docs/admin/repo-settings.md must document the Project board creation (CMN-03)."""
    content = REPO_SETTINGS.read_text()
    assert "Backlog" in content, (
        "docs/admin/repo-settings.md must document Project board columns (Backlog ...)"
    )


# ---------------------------------------------------------------------------
# .github/ISSUE_TEMPLATE/bug_report.yml
# ---------------------------------------------------------------------------


def test_bug_report_template_exists() -> None:
    """bug_report.yml must exist."""
    assert BUG_TEMPLATE.exists(), f"Missing: {BUG_TEMPLATE}"


def test_bug_report_template_valid_yaml() -> None:
    """bug_report.yml must parse as valid YAML."""
    data = yaml.safe_load(BUG_TEMPLATE.read_text())
    assert isinstance(data, dict), "bug_report.yml must be a YAML mapping"


def test_bug_report_has_labels() -> None:
    """bug_report.yml must declare a labels: field."""
    data = yaml.safe_load(BUG_TEMPLATE.read_text())
    assert "labels" in data, "bug_report.yml must have a 'labels:' field"
    assert len(data["labels"]) >= 1, "bug_report.yml labels must not be empty"


def test_bug_report_has_body() -> None:
    """bug_report.yml must have a body: with form fields."""
    data = yaml.safe_load(BUG_TEMPLATE.read_text())
    assert "body" in data, "bug_report.yml must have a 'body:' section"
    assert isinstance(data["body"], list), "bug_report.yml body must be a list"
    assert len(data["body"]) >= 3, "bug_report.yml body must have at least 3 fields"


def test_bug_report_requires_pipe_version() -> None:
    """bug_report.yml must require the pipe-version field (CMN-01)."""
    content = BUG_TEMPLATE.read_text()
    assert "pipe-version" in content, "bug_report.yml must include a 'pipe-version' input field"


def test_bug_report_requires_runtime_context() -> None:
    """bug_report.yml must require a runtime context field (CMN-01)."""
    content = BUG_TEMPLATE.read_text()
    assert "runtime" in content.lower(), "bug_report.yml must include a runtime context field"


def test_bug_report_requires_reproduction() -> None:
    """bug_report.yml must require reproduction steps (CMN-01)."""
    content = BUG_TEMPLATE.read_text()
    assert "reproduction" in content.lower() or "repro" in content.lower(), (
        "bug_report.yml must include reproduction steps"
    )


# ---------------------------------------------------------------------------
# .github/ISSUE_TEMPLATE/feature_request.yml
# ---------------------------------------------------------------------------


def test_feature_request_template_exists() -> None:
    """feature_request.yml must exist."""
    assert FEATURE_TEMPLATE.exists(), f"Missing: {FEATURE_TEMPLATE}"


def test_feature_request_template_valid_yaml() -> None:
    """feature_request.yml must parse as valid YAML."""
    data = yaml.safe_load(FEATURE_TEMPLATE.read_text())
    assert isinstance(data, dict), "feature_request.yml must be a YAML mapping"


def test_feature_request_has_labels() -> None:
    """feature_request.yml must declare a labels: field."""
    data = yaml.safe_load(FEATURE_TEMPLATE.read_text())
    assert "labels" in data, "feature_request.yml must have a 'labels:' field"
    assert len(data["labels"]) >= 1, "feature_request.yml labels must not be empty"


def test_feature_request_has_body() -> None:
    """feature_request.yml must have a body: with form fields."""
    data = yaml.safe_load(FEATURE_TEMPLATE.read_text())
    assert "body" in data, "feature_request.yml must have a 'body:' section"
    assert isinstance(data["body"], list), "feature_request.yml body must be a list"
    assert len(data["body"]) >= 3, "feature_request.yml body must have at least 3 fields"


def test_feature_request_requires_use_case() -> None:
    """feature_request.yml must require use-case field (CMN-01)."""
    content = FEATURE_TEMPLATE.read_text()
    assert "use-case" in content or "use_case" in content, (
        "feature_request.yml must include a use-case field"
    )


def test_feature_request_requires_motivation() -> None:
    """feature_request.yml must require a motivation field (CMN-01)."""
    content = FEATURE_TEMPLATE.read_text()
    assert "motivation" in content.lower(), "feature_request.yml must include a motivation field"


# ---------------------------------------------------------------------------
# .github/ISSUE_TEMPLATE/config.yml
# ---------------------------------------------------------------------------


def test_issue_config_exists() -> None:
    """config.yml must exist."""
    assert CONFIG_YML.exists(), f"Missing: {CONFIG_YML}"


def test_issue_config_valid_yaml() -> None:
    """config.yml must parse as valid YAML."""
    data = yaml.safe_load(CONFIG_YML.read_text())
    assert isinstance(data, dict), "config.yml must be a YAML mapping"


def test_issue_config_blank_issues_disabled() -> None:
    """config.yml must disable blank issues."""
    data = yaml.safe_load(CONFIG_YML.read_text())
    assert data.get("blank_issues_enabled") is False, (
        "config.yml must have blank_issues_enabled: false"
    )


def test_issue_config_has_contact_links() -> None:
    """config.yml must have contact_links (for security + marketplace redirects)."""
    data = yaml.safe_load(CONFIG_YML.read_text())
    assert "contact_links" in data, "config.yml must have 'contact_links:'"
    assert isinstance(data["contact_links"], list), "contact_links must be a list"
    assert len(data["contact_links"]) >= 1, "contact_links must have at least one entry"


def test_issue_config_security_redirect() -> None:
    """config.yml must redirect security reports to the security page."""
    content = CONFIG_YML.read_text()
    assert "security" in content.lower(), "config.yml must contain a security contact_links entry"


# ---------------------------------------------------------------------------
# .github/PULL_REQUEST_TEMPLATE.md
# ---------------------------------------------------------------------------


def test_pr_template_exists() -> None:
    """.github/PULL_REQUEST_TEMPLATE.md must exist."""
    assert PR_TEMPLATE.exists(), f"Missing: {PR_TEMPLATE}"


def test_pr_template_has_merge_checklist() -> None:
    """PR template must have a 'Merge checklist' section (CMN-02)."""
    content = PR_TEMPLATE.read_text()
    assert "Merge checklist" in content, (
        ".github/PULL_REQUEST_TEMPLATE.md must have a 'Merge checklist' section"
    )


def test_pr_template_mentions_release_please() -> None:
    """PR template must mention release-please (Conventional Commit workflow)."""
    content = PR_TEMPLATE.read_text()
    assert "release-please" in content.lower() or "release please" in content.lower(), (
        ".github/PULL_REQUEST_TEMPLATE.md must mention release-please"
    )


def test_pr_template_mentions_conventional_commit() -> None:
    """PR template must mention Conventional Commit format."""
    content = PR_TEMPLATE.read_text()
    assert "Conventional Commit" in content, (
        ".github/PULL_REQUEST_TEMPLATE.md must mention Conventional Commit format"
    )


def test_pr_template_mentions_adr() -> None:
    """PR template must mention ADR (architectural decision records)."""
    content = PR_TEMPLATE.read_text()
    assert "ADR" in content, ".github/PULL_REQUEST_TEMPLATE.md must mention ADR"


def test_pr_template_mentions_digest_pin() -> None:
    """PR template must remind contributors to pin actions to SHA digests (Pitfall #5)."""
    content = PR_TEMPLATE.read_text()
    assert "Pitfall #5" in content or "40-char" in content or "SHA digest" in content, (
        ".github/PULL_REQUEST_TEMPLATE.md must mention SHA digest pinning for workflow actions"
    )
