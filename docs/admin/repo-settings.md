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

## 5. Create the v2.0 GitHub Project Board (CMN-03)

GitHub Projects v2 board creation with column configuration is web-UI only as of
2026-06. There is no `gh project create` subcommand that fully configures columns.

**Web UI navigation:**

1. Go to `https://github.com/users/yves-vogl/projects/new`.
2. Click "New project" → select the **Board** template.
3. Name: **`aws-eks-helm-deploy v2.0`**.
4. Description: "v2.0 milestone tracker."
5. Configure columns (in order): `Backlog → Ready → In Progress → In Review → Done`.
6. Link the project to the repo: from project Settings → "Manage access" → add
   `yves-vogl/aws-eks-helm-deploy` as a linked repository.
7. Add auto-add filter: configure the project to auto-add issues + PRs labeled
   `milestone:v2.0.0`.

**Verify:** The project appears at `https://github.com/users/yves-vogl/projects/<N>`
with all 5 columns and the auto-add filter active.

---

## 6. Create the Label Taxonomy (CMN-04)

The label taxonomy covers `area/*`, `type/*`, `priority/*`, plus a handful of
common labels (`breaking-change`, `good first issue`, `help wanted`,
`dependencies`, `python`, `docker`, `ci`).

**Command (one-shot — idempotent because `|| true` swallows the
"already exists" error from `gh`):**

```bash
REPO=yves-vogl/aws-eks-helm-deploy

# area/* labels (blue family)
for label in \
    "area/auth" "area/chart" "area/ci" "area/docs" \
    "area/helm" "area/oidc" "area/security" "area/triage"; do
  gh label create "$label" --color "0075ca" --repo "$REPO" 2>/dev/null || true
done

# type/* labels (orange-red family)
for label in "type/bug" "type/feature" "type/chore" "type/docs" "type/security"; do
  gh label create "$label" --color "d93f0b" --repo "$REPO" 2>/dev/null || true
done

# priority/* labels (yellow family)
for label in "priority/p0" "priority/p1" "priority/p2" "priority/p3"; do
  gh label create "$label" --color "e4e669" --repo "$REPO" 2>/dev/null || true
done

# Stand-alone labels
gh label create "breaking-change"  --color "b60205" --repo "$REPO" 2>/dev/null || true
gh label create "good first issue" --color "7057ff" --repo "$REPO" 2>/dev/null || true
gh label create "help wanted"      --color "008672" --repo "$REPO" 2>/dev/null || true
gh label create "dependencies"     --color "0366d6" --repo "$REPO" 2>/dev/null || true
gh label create "python"           --color "2b67c6" --repo "$REPO" 2>/dev/null || true
gh label create "docker"           --color "0db7ed" --repo "$REPO" 2>/dev/null || true
gh label create "ci"               --color "f9d0c4" --repo "$REPO" 2>/dev/null || true
```

**Verify:**

```bash
gh label list --repo $REPO --json name --jq 'length'
# Expected: at least 20 (8 area + 5 type + 4 priority + 7 standalone)
```

---

## 7. Enable GitHub Pages (DOC-02)

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

## 8. Set default mike alias to v2 (DOC-02 SC-3)

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

## 9. Deploy frozen v1 docs snapshot (D2 — Plan 07-01)

The mike layout in CONTEXT D2 reserves `/v1/` for a single-page frozen v1.x
reference. The v1.x line was distributed only via Docker Hub (no `v1.3.0` git
tag exists in this repo), so the snapshot is **authored fresh** with a single
landing page that explains v1 is frozen and points readers at v2.

This deploy is a one-shot maintainer command (NEVER from CI —
RESEARCH Q10 pitfall #6: running from CI would re-render `/v1/` on every push,
potentially with newer mkdocs-material HTML; CI never touches it).

**One-shot procedure (mike needs a git repo, so we run it from the main worktree
with a side-by-side `mkdocs.yml` pointing at a tiny `docs/` tree):**

```bash
# 1. Stage v1 snapshot source under a gitignored directory.
mkdir -p .v1-snapshot/docs

# 2. Author a minimal docs/index.md with the "v1 frozen" banner.
cat > .v1-snapshot/docs/index.md <<'EOF'
# aws-eks-helm-deploy v1 — frozen

!!! warning "v1.x is not maintained"
    The v1.x line of this pipe was distributed via Docker Hub at
    `yvogl/aws-eks-helm-deploy` and is **frozen at v1.3.0**. No active
    maintenance is provided — no security patches, no bug fixes.

    Use **v2** for all new and existing deployments:
    <https://yves-vogl.github.io/aws-eks-helm-deploy/v2/>
EOF
# (Expand with a v1 environment-variable table and the "Migration" cross-link;
# see the README excerpt for canonical content.)

# 3. Author a minimal mkdocs.yml.
cat > .v1-snapshot/mkdocs.yml <<'EOF'
site_name: aws-eks-helm-deploy (v1 — frozen)
site_url: https://yves-vogl.github.io/aws-eks-helm-deploy/v1/
repo_url: https://github.com/yves-vogl/aws-eks-helm-deploy
docs_dir: docs
theme: { name: material, features: [content.code.copy] }
nav:
  - Frozen v1: index.md
markdown_extensions:
  - admonition
EOF

# 4. Deploy via mike (pushes to gh-pages, adds a `v1` entry to versions.json).
uv sync --extra docs
uv run --extra docs mike deploy --push --config-file .v1-snapshot/mkdocs.yml v1

# 5. Drop the snapshot tree (it is gitignored — see `.gitignore`).
rm -rf .v1-snapshot
```

**Verify:**

```bash
uv run mike list
# Expected output contains both `v1` and `v2`.
curl -sI https://yves-vogl.github.io/aws-eks-helm-deploy/v1/
# Expected: HTTP/2 200 from server: GitHub.com
```

---

## 10. Update Bitbucket Pipe Marketplace listing (D11)

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

## 11. Post Docker Hub README deprecation banner (MIG-01)

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
> **⚠️ Not maintained.** v1.3.0 is the final v1.x image and is **frozen** on
> Docker Hub. No security patches or bug fixes will be released for v1.x.
>
> New consumers — and existing v1 users — should pull v2.x from GitHub
> Container Registry at `ghcr.io/yves-vogl/aws-eks-helm-deploy` (rolling `:2`
> tag) or a pinned version (`:2.0.0`).
>
> Migration guide: https://yves-vogl.github.io/aws-eks-helm-deploy/v2/migration/v1-to-v2/
```

Web-UI only step; no API. **Not idempotent via API.** Confirm visually after
submitting.

## 12. Sanity-Check Post-Actions

After completing steps 1–7, run this one-liner to confirm everything is wired:

```bash
REPO=yves-vogl/aws-eks-helm-deploy

echo "=== Repo settings ==="
gh api repos/$REPO --jq '{visibility, default_branch, allow_auto_merge}'

echo "=== Private Vulnerability Reporting ==="
gh api repos/$REPO/private-vulnerability-reporting --jq '{enabled}'

echo "=== Branch protection ==="
gh api repos/$REPO/branches/main/protection --jq '{
  enforce_admins:     .enforce_admins.enabled,
  required_reviews:   .required_pull_request_reviews.required_approving_review_count,
  status_check_count: (.required_status_checks.contexts | length),
  contexts:           .required_status_checks.contexts
}'

echo "=== Required signatures ==="
gh api repos/$REPO/branches/main/protection/required_signatures --jq '.enabled'

echo "=== Label count ==="
gh label list --repo $REPO --json name --jq 'length'
```

**Expected results:**
- `allow_auto_merge: true`
- Private Vulnerability Reporting `enabled: true`
- `enforce_admins: true`, `required_reviews: 1`, `status_check_count: 8`
- Required signatures `true`
- Label count `>= 20`

---

## Notes

- **Section grouping:** §§1-4 are Phase 6 commit-time settings (PVR + branch
  protection + GPG + auto-merge). §§5-6 are Phase 6 web-UI / one-shot CLI
  steps (Project Board + Labels). §§7-11 are Phase 7 v2.0.0 release-ceremony
  steps (Pages enablement + mike one-shots + Marketplace + Docker Hub banner).
  §12 is the post-actions sanity-check covering all 11 prior sections.
- Sections 7–9 (Pages, mike set-default, mike deploy v1) are `gh api` + `mike`
  commands and are idempotent for sections 7 and 8 (Section 9 is a one-shot
  intent — re-running is harmless but unnecessary).
- Sections 10–11 (Bitbucket Pipe Marketplace + Docker Hub banner) are web-UI
  only with no programmatic idempotency guarantee; confirm visually.
- **v1.x is not maintained.** The v1.3.0 image on Docker Hub is the final v1
  release; no security patches or bug fixes are committed to v1.x. The original
  Phase 7 design assumed a 6-month security-fix window (D10 / SI-07-07 placeholder),
  but the policy was revised post-v2.0.0 to a clean break — users should migrate
  to v2.x. SECURITY.md, the migration guide, and §§9 + 11 of this runbook all
  carry the "not maintained" wording verbatim.
