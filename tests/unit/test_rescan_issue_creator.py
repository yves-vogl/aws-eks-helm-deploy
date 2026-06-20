"""Unit tests for scripts/rescan-issue-creator.py — Trivy SARIF parser + dedup logic.

Phase 6 / SEC-07. The script itself is excluded from 100% coverage (scripts/ omit in
pyproject.toml) but these unit tests cover the dedup logic, SARIF parser, and happy/error paths.

The module is loaded via importlib because the filename contains a hyphen.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys
import types

import pytest
from pytest_mock import MockerFixture

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Module load — importlib required because filename contains a hyphen
# ---------------------------------------------------------------------------

_SCRIPT_PATH = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "rescan-issue-creator.py"


def _load_ric() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("rescan_issue_creator", _SCRIPT_PATH)
    assert spec is not None, f"Could not build spec for {_SCRIPT_PATH}"
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rescan_issue_creator"] = mod
    spec.loader.exec_module(mod)
    return mod


ric = _load_ric()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sarif(
    rule_id: str,
    severity_score: str = "",
    tags: list[str] | None = None,
    message: str = "A vulnerability",
    package_name: str = "libfoo",
) -> dict[str, object]:
    """Build a minimal SARIF dict with one finding."""
    properties: dict[str, object] = {}
    if severity_score:
        properties["security-severity"] = severity_score
    if tags is not None:
        properties["tags"] = tags

    rule: dict[str, object] = {
        "id": rule_id,
        "name": package_name,
        "properties": properties,
    }

    return {
        "runs": [
            {
                "tool": {"driver": {"rules": [rule]}},
                "results": [
                    {
                        "ruleId": rule_id,
                        "message": {"text": message},
                    }
                ],
            }
        ]
    }


def _write_sarif(tmp_path: pathlib.Path, data: dict[str, object]) -> pathlib.Path:
    """Write SARIF dict to a temp file and return the path."""
    p = tmp_path / "trivy.sarif"
    p.write_text(json.dumps(data))
    return p


# ---------------------------------------------------------------------------
# _parse_sarif
# ---------------------------------------------------------------------------


def test_parse_sarif_empty_returns_no_findings(tmp_path: pathlib.Path) -> None:
    """Empty runs list → empty findings list."""
    p = _write_sarif(tmp_path, {"runs": []})
    assert ric._parse_sarif(p) == []


def test_parse_sarif_critical_finding_with_cvss_score(tmp_path: pathlib.Path) -> None:
    """CVSS >= 9.0 maps to severity CRITICAL."""
    data = _make_sarif("CVE-2024-1234", severity_score="9.8")
    p = _write_sarif(tmp_path, data)
    findings = ric._parse_sarif(p)
    assert len(findings) == 1
    assert findings[0]["cve_id"] == "CVE-2024-1234"
    assert findings[0]["severity"] == "CRITICAL"


def test_parse_sarif_high_finding_with_cvss_score(tmp_path: pathlib.Path) -> None:
    """CVSS in range [7.0, 9.0) maps to severity HIGH."""
    data = _make_sarif("CVE-2024-5678", severity_score="7.5")
    p = _write_sarif(tmp_path, data)
    findings = ric._parse_sarif(p)
    assert len(findings) == 1
    assert findings[0]["severity"] == "HIGH"


def test_parse_sarif_low_finding_filtered_out(tmp_path: pathlib.Path) -> None:
    """CVSS < 7.0 is excluded from results (not CRITICAL or HIGH)."""
    data = _make_sarif("CVE-2024-LOW", severity_score="5.0")
    p = _write_sarif(tmp_path, data)
    assert ric._parse_sarif(p) == []


def test_parse_sarif_no_severity_filtered_out(tmp_path: pathlib.Path) -> None:
    """Missing or non-numeric security-severity → filtered out."""
    data = _make_sarif("CVE-2024-NOSEV", severity_score="N/A")
    p = _write_sarif(tmp_path, data)
    assert ric._parse_sarif(p) == []


def test_parse_sarif_critical_tag_takes_precedence(tmp_path: pathlib.Path) -> None:
    """When tags: ['CRITICAL'] is present, it is used directly (not CVSS score)."""
    data = _make_sarif("CVE-2024-TAG", tags=["CRITICAL"], severity_score="4.0")
    p = _write_sarif(tmp_path, data)
    findings = ric._parse_sarif(p)
    assert len(findings) == 1
    assert findings[0]["severity"] == "CRITICAL"


def test_parse_sarif_high_tag_takes_precedence(tmp_path: pathlib.Path) -> None:
    """When tags: ['HIGH'] is present, it maps to HIGH (not CVSS-derived)."""
    data = _make_sarif("CVE-2024-HTAG", tags=["HIGH"], severity_score="2.0")
    p = _write_sarif(tmp_path, data)
    findings = ric._parse_sarif(p)
    assert len(findings) == 1
    assert findings[0]["severity"] == "HIGH"


# ---------------------------------------------------------------------------
# _make_issue_title
# ---------------------------------------------------------------------------


def test_make_issue_title_includes_short_digest() -> None:
    """The issue title contains the first 12 chars of the digest hex part."""
    digest = "sha256:abcdef123456789012345678901234567890"
    title = ric._make_issue_title("latest", digest, "CVE-2024-0001")
    # hex part starts after "sha256:"
    assert "abcdef123456" in title


def test_make_issue_title_distinguishes_tags() -> None:
    """Same CVE on :latest vs :2 produces different issue titles."""
    digest = "sha256:aabbccddeeff001122334455"
    title_latest = ric._make_issue_title("latest", digest, "CVE-2024-9999")
    title_2 = ric._make_issue_title("2", digest, "CVE-2024-9999")
    assert title_latest != title_2
    assert ":latest" in title_latest
    assert ":2" in title_2


def test_make_issue_title_format() -> None:
    """Issue title must follow the [security] prefix convention."""
    title = ric._make_issue_title("latest", "sha256:abc123xyz000ab", "CVE-2024-1111")
    assert title.startswith("[security]")
    assert "CVE-2024-1111" in title


# ---------------------------------------------------------------------------
# SEVERITY_LABEL_MAP
# ---------------------------------------------------------------------------


def test_severity_label_map_critical_maps_to_p0() -> None:
    """CRITICAL severity must map to the priority/p0 label."""
    assert ric.SEVERITY_LABEL_MAP["CRITICAL"] == "priority/p0"


def test_severity_label_map_high_maps_to_p1() -> None:
    """HIGH severity must map to the priority/p1 label."""
    assert ric.SEVERITY_LABEL_MAP["HIGH"] == "priority/p1"


# ---------------------------------------------------------------------------
# main() integration-style tests (heavily mocked)
# ---------------------------------------------------------------------------


def test_main_sarif_missing_returns_2(tmp_path: pathlib.Path) -> None:
    """When --sarif points to a non-existent file, main() returns exit code 2."""
    missing = tmp_path / "nonexistent.sarif"
    result = ric.main(["--sarif", str(missing), "--tag", "latest", "--repo", "owner/repo"])
    assert result == 2


def test_main_with_no_findings_returns_zero(tmp_path: pathlib.Path, mocker: MockerFixture) -> None:
    """When SARIF has no CRITICAL/HIGH findings, main() returns 0 without calling gh."""
    empty_sarif = _write_sarif(tmp_path, {"runs": []})
    mocker.patch.object(ric, "_resolve_digest", return_value="sha256:000000000000")
    mock_list = mocker.patch.object(ric, "_list_existing_issue_titles", return_value=set())
    mock_gh = mocker.patch.object(ric, "_run_gh")

    result = ric.main(["--sarif", str(empty_sarif), "--tag", "latest", "--repo", "owner/repo"])

    assert result == 0
    mock_list.assert_not_called()
    mock_gh.assert_not_called()


def test_main_dedup_skips_existing_issue(tmp_path: pathlib.Path, mocker: MockerFixture) -> None:
    """When the title already exists in open issues, _run_gh for issue create is NOT called."""
    sarif_path = _write_sarif(tmp_path, _make_sarif("CVE-2024-DEDUP", severity_score="9.1"))
    digest = "sha256:aabbccddeeff0011"
    mocker.patch.object(ric, "_resolve_digest", return_value=digest)

    # Pre-compute the expected title so we can inject it as existing
    expected_title = ric._make_issue_title("latest", digest, "CVE-2024-DEDUP")
    mocker.patch.object(ric, "_list_existing_issue_titles", return_value={expected_title})
    mock_gh = mocker.patch.object(ric, "_run_gh")

    result = ric.main(["--sarif", str(sarif_path), "--tag", "latest", "--repo", "owner/repo"])

    assert result == 0
    # _run_gh for "issue create" must NOT have been called
    for call in mock_gh.call_args_list:
        args_list: list[str] = call.args[0]
        assert not (args_list[0] == "issue" and args_list[1] == "create"), (
            "Expected _run_gh('issue', 'create', ...) to be skipped for duplicate issue"
        )


def test_main_creates_new_issue_when_not_duplicate(
    tmp_path: pathlib.Path, mocker: MockerFixture
) -> None:
    """When the title is not in existing issues, _run_gh IS called with 'issue create'."""
    sarif_path = _write_sarif(
        tmp_path, _make_sarif("CVE-2024-NEW", severity_score="9.5", message="A critical vuln")
    )
    mocker.patch.object(ric, "_resolve_digest", return_value="sha256:001122334455")
    mocker.patch.object(ric, "_list_existing_issue_titles", return_value=set())
    mock_gh = mocker.patch.object(ric, "_run_gh", return_value="")

    result = ric.main(["--sarif", str(sarif_path), "--tag", "latest", "--repo", "owner/repo"])

    assert result == 0
    # Verify that at least one call was "issue create"
    issue_create_calls = [
        call
        for call in mock_gh.call_args_list
        if len(call.args[0]) >= 2 and call.args[0][0] == "issue" and call.args[0][1] == "create"
    ]
    assert len(issue_create_calls) == 1, (
        f"Expected exactly 1 'gh issue create' call; got {len(issue_create_calls)}"
    )
    # Confirm --label area/security is present
    flat_args: list[str] = issue_create_calls[0].args[0]
    assert "area/security" in flat_args
    assert "priority/p0" in flat_args  # CRITICAL → p0


def test_main_dry_run_does_not_create_issue(tmp_path: pathlib.Path, mocker: MockerFixture) -> None:
    """--dry-run prevents actual 'gh issue create' invocation."""
    sarif_path = _write_sarif(tmp_path, _make_sarif("CVE-2024-DRY", severity_score="9.0"))
    mocker.patch.object(ric, "_resolve_digest", return_value="sha256:dryrundigest00")
    mocker.patch.object(ric, "_list_existing_issue_titles", return_value=set())
    mock_gh = mocker.patch.object(ric, "_run_gh")

    result = ric.main(
        ["--sarif", str(sarif_path), "--tag", "latest", "--repo", "owner/repo", "--dry-run"]
    )

    assert result == 0
    for call in mock_gh.call_args_list:
        args_list = call.args[0]
        assert not (args_list[0] == "issue" and args_list[1] == "create"), (
            "DRY-RUN must not call 'gh issue create'"
        )


def test_main_digest_resolution_failure_returns_2(
    tmp_path: pathlib.Path, mocker: MockerFixture
) -> None:
    """When _resolve_digest raises CalledProcessError, main() returns exit code 2."""
    sarif_path = _write_sarif(tmp_path, _make_sarif("CVE-2024-FAIL", severity_score="9.8"))
    mocker.patch.object(
        ric,
        "_resolve_digest",
        side_effect=subprocess.CalledProcessError(1, "docker"),
    )

    result = ric.main(["--sarif", str(sarif_path), "--tag", "latest", "--repo", "owner/repo"])

    assert result == 2
