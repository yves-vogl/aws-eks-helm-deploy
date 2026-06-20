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

## 7. Docker Hub README Update (MIG-01 / CONTEXT D10)

This step depends on Plan 06-11's deliverable (`docs/guides/v1-to-v2.md`). When
Plan 06-11 ships, run the following:

**Manual web UI step:**

1. Sign in to https://hub.docker.com as the Docker Hub owner of
   `yvogl/aws-eks-helm-deploy`.
2. Navigate to
   https://hub.docker.com/repository/docker/yvogl/aws-eks-helm-deploy.
3. Click **"Manage Repository"** → **"Description"**.
4. Replace the description with the verbatim text from
   `docs/guides/v1-to-v2.md` "Distribution change" section (sealed in
   CONTEXT D10).
5. Click **"Update"**.

**Verify:** Open the Docker Hub page in an incognito browser; the deprecation
notice + GHCR link is the first visible content.

---

## 8. Sanity-Check Post-Actions

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

- These actions are NOT in scope for the Phase 6 automated verifier — the
  verifier checks that THIS DOCUMENT exists and is complete, but cannot verify
  the maintainer ran the commands.
- If a future Phase renames a `ci.yml` job's `name:` field, re-run Step 2 with
  the updated `contexts` array. The structural test
  `tests/structural/test_ci_yml_structure.py::JOB_NAMES_REQUIRED` is the
  source-of-truth for the job-key list; human-readable `name:` strings are
  recorded in each plan's SUMMARY.
- The cosign-verify context string in Step 2 comes from Plan 06-05.
- Steps 1–4 are `gh` CLI commands and are idempotent — safe to re-run.
- Step 5 (Project board) and Step 7 (Docker Hub) are web-UI steps with no
  programmatic idempotency guarantee; check the UI before re-running.
