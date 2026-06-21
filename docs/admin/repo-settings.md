# Repo Settings Runbook — Phase 6 Maintainer Actions

This file documents the manual repo-admin steps that Phase 6 requires but CANNOT
be applied via PR. Run these AFTER Phase 6 merges to `main`. Each step is
idempotent — re-running a successfully applied step is harmless.

> **Required tool:** `gh` CLI (https://cli.github.com), authenticated as a repo admin.
>
> **Required env:** `gh auth status` must show `Logged in to github.com`.

---

## 1. Enable GitHub Private Vulnerability Reporting (SEC-09)

The disclosure flow documented in `SECURITY.md` routes reports through the
Security tab → "Report a vulnerability" button. That button only appears when
Private Vulnerability Reporting is enabled.

**Command:**

```bash
gh api repos/yves-vogl/aws-eks-helm-deploy/private-vulnerability-reporting -X PUT
```

Returns HTTP 204.

**Verify:**

```bash
gh api repos/yves-vogl/aws-eks-helm-deploy/private-vulnerability-reporting --jq .enabled
# Expected: true
```

---

## 2. Configure Branch Protection on `main` (CI-07)

Phase 6's CI (Plan 06-01) ships a 7-job fan-out. Branch protection MUST gate
merges to `main` on all 7 jobs passing + ≥ 1 review. An 8th context,
`cosign-verify (latest GHCR release)`, covers the Plan 06-05 cosign gate.

**Pitfall #8:** Branch protection `contexts` is case-sensitive and must match the
`name:` field of each job EXACTLY. Verify against `.github/workflows/ci.yml` before
running this command.

**Command:**

```bash
gh api repos/yves-vogl/aws-eks-helm-deploy/branches/main/protection \
  -X PUT \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "lint-typecheck (ruff + mypy)",
      "unit-coverage (100% line+branch)",
      "integration (kind + helm)",
      "trivy-image",
      "trivy-dockerfile",
      "pip-audit",
      "acceptance (docker run image)",
      "cosign-verify (latest GHCR release)"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": false,
    "require_code_owner_reviews": false
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": false,
  "required_conversation_resolution": true
}
EOF
```

**Verify:**

```bash
gh api repos/yves-vogl/aws-eks-helm-deploy/branches/main/protection \
  --jq '.required_status_checks.contexts | length'
# Expected: 8 (7 ci.yml jobs + 1 cosign-verify job)
```

**Job name to branch-protection string mapping** (source: `06-01-SUMMARY.md`):

| ci.yml job key  | `name:` string used in branch protection           |
|-----------------|-----------------------------------------------------|
| `lint-typecheck`  | `lint-typecheck (ruff + mypy)`                    |
| `unit-coverage`   | `unit-coverage (100% line+branch)`                |
| `integration`     | `integration (kind + helm)`                       |
| `trivy-image`     | `trivy-image`                                     |
| `trivy-dockerfile`| `trivy-dockerfile`                                |
| `pip-audit`       | `pip-audit`                                       |
| `acceptance`      | `acceptance (docker run image)`                   |
| cosign gate       | `cosign-verify (latest GHCR release)` (Plan 06-05)|

**Regression note:** If a future Phase modifies `ci.yml` job `name:` strings,
re-run this command with the updated `contexts` array. A silent rename otherwise
stops enforcing that check. The structural test
`tests/structural/test_ci_yml_structure.py::JOB_NAMES_REQUIRED` is the
source-of-truth for the job-key list; human-readable `name:` strings are
recorded in each plan's SUMMARY.

---

## 3. Require GPG-Signed Commits (CI-06)

Branch protection's `required_signatures` is a separate endpoint from the main
protection payload in Step 2. Run step 3 AFTER step 2 has returned successfully.

**Command:**

```bash
gh api repos/yves-vogl/aws-eks-helm-deploy/branches/main/protection/required_signatures \
  -X POST
```

Returns `{"url": "...", "enabled": true}`.

**Verify:**

```bash
gh api repos/yves-vogl/aws-eks-helm-deploy/branches/main/protection/required_signatures \
  --jq .enabled
# Expected: true
```

---

## 4. Enable "Allow auto-merge" Repo Setting (CI-05)

The `dependabot-auto-merge.yml` workflow (Plan 06-06) uses `gh pr merge --auto`,
which requires the repo-level "Allow auto-merge" toggle to be enabled.

**Command:**

```bash
gh api repos/yves-vogl/aws-eks-helm-deploy \
  -X PATCH \
  -f allow_auto_merge=true
```

**Verify:**

```bash
gh api repos/yves-vogl/aws-eks-helm-deploy --jq .allow_auto_merge
# Expected: true
```

---

## 5. Enable GitHub Pages (DOC-02)

The `.github/workflows/docs.yml` workflow (Plan 07-05) requires GitHub Pages to
be enabled with `gh-pages` as the source branch BEFORE the first `mike deploy`
run can succeed. This is a one-shot step.

**Command (idempotent — try POST first, fall back to PUT if Pages already enabled):**

```bash
# Try first-time enable:
gh api repos/yves-vogl/aws-eks-helm-deploy/pages \
  -X POST \
  -f source[branch]=gh-pages \
  -f source[path]=/

# If POST returned 409 (already enabled), use PUT instead:
gh api repos/yves-vogl/aws-eks-helm-deploy/pages \
  -X PUT \
  -f source[branch]=gh-pages \
  -f source[path]=/
```

**Verify:**

```bash
gh api repos/yves-vogl/aws-eks-helm-deploy/pages \
  --jq '{url:.html_url,source:.source}'
# Expected: { "url": "https://yves-vogl.github.io/aws-eks-helm-deploy/",
#             "source": { "branch": "gh-pages", "path": "/" } }
```

**Permissions:** repo admin OR "manage GitHub Pages settings".

**Source:** RESEARCH Q6.

---

## 6. Set default mike alias to v2 (DOC-02 SC-3)

`.github/workflows/docs.yml` deploys `v2 + latest` aliases on every `main`
commit. Setting the default alias writes `index.html` at the gh-pages root
redirecting to `/v2/`. This is a one-shot maintainer command — NOT in CI
(RESEARCH Q10 pitfall #5: combining with concurrent CI deploys can produce a
stale default).

**Run ONCE after the first `mike deploy v2 latest` workflow run succeeds:**

```bash
git fetch origin gh-pages
git worktree add /tmp/gh-pages gh-pages
cd /tmp/gh-pages

uv sync --extra docs   # installs mike 2.2.0
uv run mike set-default v2 --push

cd - && git worktree remove /tmp/gh-pages
```

**Verify:**

```bash
curl -sI https://yves-vogl.github.io/aws-eks-helm-deploy/ | grep -F 'location'
# Expected: location header redirecting to /v2/
```

**Re-run only if** the gh-pages branch is reset OR a future `mike deploy` is
misconfigured.

---

## 7. Deploy frozen v1 docs snapshot (D2 — Plan 07-01)

The mike layout in CONTEXT D2 reserves `/v1/` for a single-page frozen v1.3.0
reference. This deploy is a one-shot maintainer command (NEVER from CI —
RESEARCH Q10 pitfall #6: running from CI would re-render `/v1/` on every push,
potentially with newer mkdocs-material HTML; CI never touches it).

**Run ONCE from a local workspace pinned at the v1 docs snapshot:**

```bash
# Check out the v1.3.0 docs snapshot (or a `v1.3.0-docs-snapshot` tag if one exists):
git checkout v1.3.0  # or v1.3.0-docs-snapshot
uv sync --extra docs
uv run mike deploy --push v1

git checkout main
```

**Banner on /v1/:** CONTEXT D2 specifies the banner "v1 is frozen — security-only
patches until 2026-MM-DD (= v2.0.0 release date + 6 months) — replace at tag-cut.
Use v2: <link>." Update the v1 docs site index manually with this banner before
the `mike deploy --push v1` command.

**Verify:**

```bash
uv run mike list
# Expected output contains both `v1` and `v2`.
curl -sf https://yves-vogl.github.io/aws-eks-helm-deploy/v1/ | head -5
# Expected: v1 docs HTML renders.
```

---

## 8. Update Bitbucket Pipe Marketplace listing (D11)

After the v2.0.0 tag-cut, update the Bitbucket Pipe Marketplace listing to
reflect the new image registry, version, and capabilities (OIDC, OCI charts,
diff/rollback actions, signed images). The marketplace listing is a web-UI
only step (no Bitbucket REST API for marketplace edits as of 2026-06).

**Listing edit URL:**
https://bitbucket.org/yvesvogl/aws-eks-helm-deploy/admin/pipelines/pipe-info

**Fields to update:**
- Image tag (point at `ghcr.io/yves-vogl/aws-eks-helm-deploy:2.0.0`).
- "What's new in 2.0" description: paste from `docs/migration/v1-to-v2.md` Quick
  migration checklist.
- Tags: add `oidc`, `signed`, `multi-arch`.
- README pointer: link to the GitHub docs site (https://yves-vogl.github.io/aws-eks-helm-deploy/).

This is **not idempotent via web UI** — verify visually after submitting.

---

## 9. Post Docker Hub README deprecation banner (MIG-01)

The Docker Hub `yvogl/aws-eks-helm-deploy` repository is frozen at v1.3.0
(MIG-01). Post a deprecation banner to its README so consumers searching
Docker Hub land on the GHCR migration path.

**Banner source:** `docs/migration/v1-to-v2.md`, section "Distribution change
(Phase 6 / MIG-01)" — paste the prose verbatim.

**Docker Hub README edit URL:**
https://hub.docker.com/repository/docker/yvogl/aws-eks-helm-deploy/general

**Recommended banner template** (copy into the top of the Docker Hub README,
above the existing content):

```markdown
> **⚠️ Deprecated.** v1.3.0 is the final v1.x image and is frozen on Docker
> Hub. New consumers should pull v2.x from GitHub Container Registry at
> `ghcr.io/yves-vogl/aws-eks-helm-deploy` (rolling `:2` tag) or a pinned
> version (`:2.0.0`).
>
> Security fixes for v1.x are released for 6 months from the v2.0.0 release
> date — ending `2026-MM-DD (= v2.0.0 release date + 6 months) — replace at tag-cut.`
>
> Migration guide: https://yves-vogl.github.io/aws-eks-helm-deploy/migration/v1-to-v2/
```

Web-UI only step; no API. **Not idempotent via API.** Confirm visually after
submitting.

---

## Notes (Phase 7 — sections 5-9)

- Sections 5–7 (Pages, mike set-default, mike deploy v1) are `gh api` + `mike`
  commands and are idempotent for sections 5 and 6 (Section 7 is a one-shot
  intent — re-running is harmless but unnecessary).
- Sections 8–9 (Bitbucket Pipe Marketplace + Docker Hub banner) are web-UI
  only with no programmatic idempotency guarantee; confirm visually.
- The literal placeholder `2026-MM-DD (= v2.0.0 release date + 6 months) — replace at tag-cut.` is the SI-07-07 invariant; it appears in three places in v2.0:
  `SECURITY.md` (Plan 07-06), `docs/migration/v1-to-v2.md` (Plan 07-04), AND
  `docs/admin/repo-settings.md` Section 7 + 9 (this plan). After the v2.0.0
  tag-cut, the maintainer replaces all four occurrences in a single follow-up
  PR.
