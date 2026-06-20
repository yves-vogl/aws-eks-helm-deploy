"""Trivy SARIF parser + dedup-aware GitHub Issue creator (Phase 6 / SEC-07).

Reads a Trivy-generated SARIF file, deduplicates findings against existing open
issues with the `area/security` label by (image_digest, cve_id) hash, and opens
new issues for CRITICAL (priority/p0) and HIGH (priority/p1) findings.

This script is CI infrastructure — NOT product code. It is excluded from the
100% coverage gate via [tool.coverage.run] omit in pyproject.toml (RESEARCH §A5).

REQ traceability:
  - SEC-07: scheduled vulnerability rescan → auto-issue with dedup
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import subprocess
import sys
from typing import Any

LOG = logging.getLogger("rescan-issue-creator")

LABEL_SECURITY = "area/security"
LABEL_PRIORITY_P0 = "priority/p0"
LABEL_PRIORITY_P1 = "priority/p1"

SEVERITY_LABEL_MAP: dict[str, str] = {
    "CRITICAL": LABEL_PRIORITY_P0,
    "HIGH": LABEL_PRIORITY_P1,
}


def _run_gh(args: list[str]) -> str:
    """Run `gh` with args; return stdout. Raise CalledProcessError on non-zero."""
    result = subprocess.run(["gh", *args], check=True, capture_output=True, text=True)
    return result.stdout


def _list_existing_issue_titles(repo: str) -> set[str]:
    """List titles of currently open issues with area/security label."""
    raw = _run_gh(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--label",
            LABEL_SECURITY,
            "--state",
            "open",
            "--json",
            "title",
            "--limit",
            "1000",
        ]
    )
    issues: list[dict[str, str]] = json.loads(raw)
    return {issue["title"] for issue in issues}


def _parse_sarif(path: pathlib.Path) -> list[dict[str, str]]:
    """Parse Trivy SARIF; return list of {cve_id, severity, package, summary}.

    Only returns findings with severity CRITICAL or HIGH (Trivy emits these as
    `error` and `warning` in SARIF; the original severity is in `properties`).
    """
    sarif = json.loads(path.read_text())
    findings: list[dict[str, str]] = []
    for run in sarif.get("runs", []):
        rules = {
            rule["id"]: rule
            for rule in run.get("tool", {}).get("driver", {}).get("rules", [])
        }
        for result in run.get("results", []):
            rule_id = result.get("ruleId", "")
            rule = rules.get(rule_id, {})
            # First check for explicit severity tag (e.g., ["CRITICAL"])
            tags = rule.get("properties", {}).get("tags", [])
            level_tag = next((t for t in tags if t.upper() in SEVERITY_LABEL_MAP), "")
            if not level_tag:
                # Fall back to CVSS score → severity bucket
                severity_score = rule.get("properties", {}).get("security-severity", "")
                try:
                    cvss = float(severity_score)
                except (ValueError, TypeError):
                    cvss = 0.0
                level_tag = "CRITICAL" if cvss >= 9.0 else "HIGH" if cvss >= 7.0 else ""
            if not level_tag or level_tag.upper() not in SEVERITY_LABEL_MAP:
                continue
            findings.append(
                {
                    "cve_id": rule_id,
                    "severity": level_tag.upper(),
                    "summary": result.get("message", {}).get("text", "")[:200],
                    "package": rule.get("name", ""),
                }
            )
    return findings


def _make_issue_title(tag: str, digest: str, cve_id: str) -> str:
    """Deterministic title — used as the dedup key (title-equality).

    The digest is included so re-tagging `:latest` to a new digest creates new
    issues (the previous issues remain valid against the old digest).
    """
    digest_short = digest.split(":")[-1][:12] if ":" in digest else digest[:12]
    return f"[security] {cve_id} in :{tag} (digest {digest_short})"


def _resolve_digest(image_ref: str) -> str:
    """Resolve the manifest digest for an image:tag via `docker buildx imagetools inspect`."""
    raw = subprocess.run(
        [
            "docker",
            "buildx",
            "imagetools",
            "inspect",
            image_ref,
            "--format",
            "{{json .Manifest}}",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    manifest: dict[str, Any] = json.loads(raw)
    return str(manifest.get("digest", "unknown"))


def main(argv: list[str] | None = None) -> int:
    """Entry point: parse arguments, resolve digest, parse SARIF, create deduplicated issues."""
    parser = argparse.ArgumentParser(description="Create dedup GitHub Issues from Trivy SARIF.")
    parser.add_argument("--sarif", required=True, type=pathlib.Path)
    parser.add_argument("--tag", required=True, help="Image tag scanned (e.g., latest, 2)")
    parser.add_argument("--repo", required=True, help="<owner>/<repo>")
    parser.add_argument("--image", default="ghcr.io/yves-vogl/aws-eks-helm-deploy")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not args.sarif.is_file():
        LOG.error("SARIF file not found: %s", args.sarif)
        return 2

    image_ref = f"{args.image}:{args.tag}"
    try:
        digest = _resolve_digest(image_ref)
    except subprocess.CalledProcessError as exc:
        LOG.error("Could not resolve digest for %s: %s", image_ref, exc)
        return 2

    findings = _parse_sarif(args.sarif)
    LOG.info("Parsed %d CRITICAL/HIGH findings from %s", len(findings), args.sarif)
    if not findings:
        return 0

    existing_titles = _list_existing_issue_titles(args.repo)
    LOG.info("Found %d existing open security issues", len(existing_titles))

    created = 0
    skipped = 0
    for finding in findings:
        title = _make_issue_title(args.tag, digest, finding["cve_id"])
        if title in existing_titles:
            skipped += 1
            continue
        priority_label = SEVERITY_LABEL_MAP[finding["severity"]]
        body = (
            f"**Image:** `{image_ref}`\n"
            f"**Digest:** `{digest}`\n"
            f"**CVE:** `{finding['cve_id']}`\n"
            f"**Severity:** `{finding['severity']}`\n"
            f"**Package:** `{finding['package']}`\n\n"
            f"**Trivy summary:**\n\n```\n{finding['summary']}\n```\n\n"
            "Detected by the daily security-rescan workflow (Phase 6 / SEC-07).\n"
        )
        if args.dry_run:
            LOG.info("DRY-RUN: would create issue: %s", title)
        else:
            _run_gh(
                [
                    "issue",
                    "create",
                    "--repo",
                    args.repo,
                    "--title",
                    title,
                    "--body",
                    body,
                    "--label",
                    LABEL_SECURITY,
                    "--label",
                    priority_label,
                ]
            )
        created += 1

    LOG.info("Issues created: %d, skipped (dedup): %d", created, skipped)
    return 0


if __name__ == "__main__":
    sys.exit(main())
