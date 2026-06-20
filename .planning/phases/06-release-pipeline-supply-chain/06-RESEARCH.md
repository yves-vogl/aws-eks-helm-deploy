# Phase 6: Release Pipeline & Supply Chain — Research

**Researched:** 2026-06-20
**Domain:** GitHub Actions CI/CD, supply-chain security (Cosign/SLSA/SBOM), release-please, multi-arch Docker, OpenSSF Scorecard
**Confidence:** HIGH (all action digests verified via `gh api`; ARM runner availability confirmed via official GitHub changelog)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D1** — release-please flow: maintainer-merge, no auto-merge on release-PR. `.release-please-config.json` with `release-type: python`, `package-name: aws-eks-helm-deploy`. `.release-please-manifest.json` seeded at `"."` → `"2.0.0-rc.0"`.

**D2** — `.trivyignore` rationale + expiry format: `<CVE-ID>  # expires=YYYY-MM-DD rationale="…" reviewer=<github-handle>`. Script `scripts/trivyignore-check.sh` enforces 180-day cap. Unit test `tests/unit/test_trivyignore_check.py`.

**D3** — `.scorecard-exception.md` YAML frontmatter table; CI workflow parses and fails if `review_date` is past.

**D4** — amd64 native runner = `ubuntu-24.04` (pinned); arm64 = `ubuntu-24.04-arm` (pinned). NOT `ubuntu-latest`.

**D5** — release-please default `changelog-types` (no customization).

**D6** — Dependabot grouping: 3 ecosystems (pip, docker, github-actions) with explicit groups. Auto-merge workflow `.github/workflows/dependabot-auto-merge.yml`.

**D7** — Cosign verify gate in `.github/workflows/cosign-verify.yml` on `pull_request` against `main`.

**D8** — SBOM filenames: `sbom.spdx.json` and `sbom.cyclonedx.json`; both via `anchore/sbom-action@v0`; both attested via `cosign attest --predicate <path> --type spdxjson` / `cyclonedx`.

**D9** — CI job topology: parallel fan-out (7 jobs: lint-typecheck, unit-coverage, integration, trivy-image, trivy-dockerfile, pip-audit, acceptance).

**D10** — MIG-01 Docker Hub README update: manual + documented in `docs/guides/v1-to-v2.md`.

### Claude's Discretion

None identified beyond the 10 locked decisions.

### Deferred Ideas (OUT OF SCOPE)

- Reusable GitHub Action wrapper (CI-NEXT-01) — v2.1+
- Docker Hub README automation — v2.1+
- In-cluster verify policy (Sigstore policy controller / Connaisseur)
- `cosign verify-blob` integration tests against published images
- Custom Scorecard checks
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| IMAGE-04 | Multi-arch `linux/amd64` + `linux/arm64` via native runners (no QEMU) | Native runner labels confirmed; multi-arch buildx matrix pattern documented |
| IMAGE-06 | Cold-start benchmark < 10s, documented in README | Benchmark script methodology provided |
| SEC-01 | Cosign keyless sign via OIDC → Fulcio → Rekor; `--bundle` for offline verify | Permissions block + cosign workflow pattern documented |
| SEC-02 | SBOM in SPDX + CycloneDX as Cosign attestations | `anchore/sbom-action` `output-file` + `format` confirmed; `cosign attest` pattern |
| SEC-03 | SLSA build provenance via `actions/attest-build-provenance` | Permissions (`attestations: write`) confirmed |
| SEC-04 | Trivy scans image, Dockerfile, chart fixtures, secret-leak on every PR | Job topology + `.trivyignore` enforcement documented |
| SEC-05 | pip-audit on every PR | Existing script reuse pattern documented |
| SEC-07 | Daily Trivy rescan → SARIF → auto-issue on CRITICAL/HIGH | Workflow skeleton provided |
| SEC-08 | Dependabot docker ecosystem with `fix(deps):` prefix → release-please patch | Already in `dependabot.yml`; needs grouping updates |
| SEC-09 | GitHub Private Vulnerability Reporting enabled; SECURITY.md update | API command confirmed |
| SEC-10 | OpenSSF Scorecard ≥ 8/10; `.scorecard-exception.md` with stale-check | Existing `scorecard.yml` confirmed; extension documented |
| CI-01 | ci.yml expanded to 7-job fan-out | Full job topology + names documented |
| CI-02 | release-please drives release.yml | Config schema documented |
| CI-03 | release.yml builds multi-arch, signs, attests, pushes to GHCR | Full workflow architecture documented |
| CI-04 | Thin `bitbucket-pipelines.yml` for Marketplace listing only | Minimal pipeline pattern documented |
| CI-05 | Dependabot auto-merge once CI passes | `dependabot-auto-merge.yml` pattern documented |
| CI-06 | GPG-signed commits on main | Branch protection API command provided |
| CI-07 | Branch protection: signed commits, 1+ review, required checks, no direct pushes | `gh api` payload documented |
| CMN-01 | Issue templates: `bug_report.yml` + `feature_request.yml` | Standard GitHub structure documented |
| CMN-02 | PR template with merge checklist | Standard GitHub structure documented |
| CMN-03 | GitHub Project board v2.0 milestone | Manual step documented |
| CMN-04 | Label taxonomy applied | `gh label create` loop documented |
| MIG-01 | Docker Hub frozen at v1.3.0; GHCR `:2` rolling tag; Docker Hub README update | D10 + GHCR `:2` tagging strategy documented |
</phase_requirements>

---

## Summary

Phase 6 is almost entirely `.github/workflows/*.yml`, config files (`.release-please-config.json`, `.github/dependabot.yml`), scripts (`scripts/trivyignore-check.sh`, `scripts/benchmark-cold-start.sh`), and governance files (`SECURITY.md` update, `CONTRIBUTING.md` update, `.github/ISSUE_TEMPLATE/`, `.github/PULL_REQUEST_TEMPLATE.md`, `.scorecard-exception.md`). There are no Python source changes. The `Dockerfile` gains OCI annotations and a multi-arch download strategy (replacing the current `linux/amd64`-only `helm-fetch`, `cosign-fetch`, and `helm-diff-fetch` stages).

The existing codebase is well-prepared: `dependabot.yml` already covers the 3 ecosystems (but needs grouping updates per D6); `scorecard.yml` already exists (pinned to digest `4eaacf0543bb3f2c246792bd56e8cdeffafb205a`); `SECURITY.md` and `CONTRIBUTING.md` exist (but need Phase 6 content updates); `ci.yml` is a single-job pre-commit runner (needs full fan-out per D9). The current `bitbucket-pipelines.yml` is the v1.x build+push pipeline — Phase 6 replaces it with a minimal Marketplace-only stub.

**Primary recommendation:** Build the 11 plans in wave order (D9 CI fan-out first, release-please bootstrap second, then multi-arch build, sign+SBOM+SLSA, verify gate, Dependabot/rescan/security/scorecard/governance/bitbucket in Wave 5). All GitHub Actions must be pinned to the SHA digests verified below.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Image build (multi-arch) | GitHub Actions CI (release.yml) | Dockerfile (build spec) | Docker BuildKit multi-arch matrix runs natively in GH Actions |
| Image signing | GitHub Actions CI (release.yml) | Sigstore/Rekor (public log) | OIDC token is only available inside GH Actions job |
| SBOM generation | GitHub Actions CI (anchore/sbom-action) | — | Syft runs as a workflow step against the built image |
| SLSA provenance | GitHub Actions CI (attest-build-provenance) | GitHub Attestation store | GitHub-native; writes to repo's attestation store |
| Vulnerability scanning (PR gate) | GitHub Actions CI (trivy-action + trivy-dockerfile) | Code Scanning (SARIF) | Run on every PR; results go to Security tab |
| Vulnerability scanning (continuous) | GitHub Actions Cron (security-rescan.yml) | GitHub Issues (auto-created) | Daily scan of published image |
| Release versioning | release-please (cloud) | pyproject.toml / pipe.yml / CHANGELOG.md | release-please reads commits and opens/updates the release PR |
| Dependency updates | Dependabot (GitHub service) | ci.yml (gate) | Dependabot opens PRs; CI gates merge |
| Supply-chain score | OpenSSF Scorecard (ossf/scorecard-action) | Code Scanning SARIF | Weekly + on-push to main |
| Cosign verify gate | cosign-verify.yml (PR workflow) | — | Separate workflow; blocks merge if image lacks valid signature |
| Branch protection / GPG enforcement | GitHub Settings (manual) | gh api | Cannot be done via PR; requires admin action |
| Marketplace listing (Bitbucket) | bitbucket-pipelines.yml (stub) | — | Marketplace reads pipe.yml; pipeline just needs to not fail |

---

## Action Digest Resolution

All SHAs verified via `gh api repos/<owner>/<repo>/git/refs/tags/<tag>` on 2026-06-20. [VERIFIED: gh api]

| Action | Latest Tag | Commit SHA | Notes |
|--------|-----------|------------|-------|
| `googleapis/release-please-action` | v5.0.0 | `45996ed1f6d02564a971a2fa1b5860e934307cf7` | **v5** is latest — CONTEXT.md references v4; see Contradictions section |
| `sigstore/cosign-installer` | v4.1.2 | `6f9f17788090df1f26f669e9d70d6ae9567deba6` | Installs cosign in CI |
| `anchore/sbom-action` | v0.24.0 | `e22c389904149dbc22b58101806040fa8d37a610` | Syft SBOM generation |
| `actions/attest-build-provenance` | v4.1.0 | `a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32` | **v4** is latest — CONTEXT.md references v1; see Contradictions section |
| `aquasecurity/trivy-action` | v0.36.0 | `ed142fd0673e97e23eac54620cfb913e5ce36c25` | Annotated tag; dereferenced to commit SHA |
| `ossf/scorecard-action` | v2.4.3 | `4eaacf0543bb3f2c246792bd56e8cdeffafb205a` | Already pinned correctly in `scorecard.yml` |
| `docker/login-action` | v4.2.0 | `650006c6eb7dba73a995cc03b0b2d7f5ca915bee` | GHCR login |
| `docker/setup-buildx-action` | v4.1.0 | `d7f5e7f509e45cec5c76c4d5afdd7de93d0b3df5` | Multi-arch buildx setup |
| `docker/metadata-action` | v6.1.0 | `80c7e94dd9b9319bd5eb7a0e0fe9291e23a2a2e9` | OCI annotations + tag generation |
| `docker/build-push-action` | v7.2.0 | `f9f3042f7e2789586610d6e8b85c8f03e5195baf` | Build + push to GHCR |
| `actions/checkout` | v7.0.0 (latest) / v4.2.2 (currently pinned) | v4.2.2 = `11bd71901bbe5b1630ceea73d27597364c9af683` / v7.0.0 = `9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0` | Planner to decide: update to v7 in Phase 6 or leave at v4.2.2; v4.2.2 is still valid |
| `actions/upload-artifact` | v7.0.1 | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` | Already pinned correctly in `scorecard.yml` |
| `actions/setup-python` | v6.2.0 | `a309ff8b426b58ec0e2a45f0f869d46889d02405` | Only needed if Phase 6 jobs need Python outside uv |
| `astral-sh/setup-uv` | v8.2.0 (latest) / v3.2.4 (currently pinned) | v3.2.4 = `caf0cab7a618c569241d31dcd442f54681755d39` / v8.2.0 = `fac544c07dec837d0ccb6301d7b5580bf5edae39` | Planner to decide: update in Phase 6 or leave at v3.2.4 (both valid) |
| `github/codeql-action` | v3 (pinned tag) | `dd903d2e4f5405488e5ef1422510ee31c8b32357` | Already pinned correctly in `codeql.yml` and `scorecard.yml` |

**Important notes on version jumps:**
- `googleapis/release-please-action` jumped from v4 to v5 since CONTEXT.md was written. v5 schema is likely backward-compatible but planner should verify `release-please-config.json` syntax. [ASSUMED: backward-compatible]
- `actions/attest-build-provenance` jumped from v1 to v4. The `permissions: attestations: write` requirement still applies in v4. [ASSUMED: API unchanged]

---

## Standard Stack

### Core Workflows

| File | Purpose | Status |
|------|---------|--------|
| `.github/workflows/ci.yml` | Expanded 7-job PR gate | Rewrite existing single-job file |
| `.github/workflows/release.yml` | Multi-arch build + sign + SBOM + SLSA | New file |
| `.github/workflows/release-please.yml` | Opens release PRs on push to main | New file (or merged into release.yml) |
| `.github/workflows/cosign-verify.yml` | PR-gate: verify latest image is signed | New file |
| `.github/workflows/security-rescan.yml` | Daily Trivy scan + auto-issue | New file |
| `.github/workflows/dependabot-auto-merge.yml` | Auto-merge Dependabot PRs once CI green | New file |
| `.github/workflows/scorecard.yml` | Existing — extend with `.scorecard-exception.md` check | Update existing |

### Config Files

| File | Purpose | Status |
|------|---------|--------|
| `.release-please-config.json` | release-please package config | New |
| `.release-please-manifest.json` | Current version seed | New |
| `.github/dependabot.yml` | Ecosystem update config | Update (add grouping) |
| `.trivyignore` | CVE suppression with rationale+expiry | New (start empty) |
| `.scorecard-exception.md` | Deliberate Scorecard sub-check failures | New |

### Scripts

| File | Purpose | Status |
|------|---------|--------|
| `scripts/trivyignore-check.sh` | Enforce expiry+rationale grammar in CI | New |
| `scripts/benchmark-cold-start.sh` | Cold-start timing benchmark | New |

### Governance Files

| File | Purpose | Status |
|------|---------|--------|
| `.github/ISSUE_TEMPLATE/bug_report.yml` | GitHub structured issue form | New |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | GitHub structured issue form | New |
| `.github/PULL_REQUEST_TEMPLATE.md` | PR merge checklist | New |
| `SECURITY.md` | Already exists — update "planned" items to "live" | Update |
| `CONTRIBUTING.md` | Already exists — add `.trivyignore` rationale section | Update |
| `bitbucket-pipelines.yml` | Replace v1.x build+push pipeline with thin stub | Replace |
| `pipe.yml` | Updated by release-please on each release | No change needed in Phase 6 |

---

## Architecture Patterns

### System Architecture Diagram (Release Flow)

```
Push to main (feat:/fix:/chore:)
        │
        ▼
release-please-action (release-please.yml)
        │
        ├─► opens/updates Release PR
        │         │
        │         │  (Yves reviews + merges manually — D1)
        │         ▼
        │   Release PR merged → push to main with release tag
        │
        ▼
release.yml triggers on push tag v*
        │
        ├─ Job: release-please (runs on ubuntu-24.04)
        │       └─ googleapis/release-please-action → creates GitHub Release
        │
        └─ Job matrix: build (ubuntu-24.04 + ubuntu-24.04-arm)
                │
                ├─ actions/checkout
                ├─ docker/setup-buildx-action
                ├─ docker/login-action → ghcr.io
                ├─ docker/metadata-action → tags + OCI labels
                ├─ docker/build-push-action --platform linux/amd64 OR linux/arm64
                │        └─ outputs: image digest
                │
                └─ Fan-in Job: sign-and-attest (needs: build matrix)
                        ├─ sigstore/cosign-installer
                        ├─ cosign sign --bundle → Rekor
                        ├─ anchore/sbom-action (format: spdx-json) → sbom.spdx.json
                        ├─ anchore/sbom-action (format: cyclonedx-json) → sbom.cyclonedx.json
                        ├─ cosign attest --type spdxjson --predicate sbom.spdx.json
                        ├─ cosign attest --type cyclonedx --predicate sbom.cyclonedx.json
                        └─ actions/attest-build-provenance
```

### PR Gate Flow (ci.yml — D9 fan-out)

```
Pull Request → ci.yml triggers
        │
        ├─ lint-typecheck (ubuntu-24.04, ~30s)
        │     ruff check + ruff format --check + mypy --strict
        │
        ├─ unit-coverage (ubuntu-24.04, ~60s)
        │     pytest tests/unit --cov 100% line+branch
        │
        ├─ integration (ubuntu-24.04, ~3min)
        │     pytest tests/integration -m integration
        │
        ├─ trivy-image (ubuntu-24.04, ~1min)
        │     aquasecurity/trivy-action (image scan) → SARIF
        │
        ├─ trivy-dockerfile (ubuntu-24.04, ~30s)
        │     aquasecurity/trivy-action (config scan: Dockerfile + chart fixtures)
        │
        ├─ pip-audit (ubuntu-24.04, ~30s)
        │     scripts/pip-audit-with-stale-check.sh
        │
        └─ acceptance (ubuntu-24.04, ~1min)
              pytest tests/acceptance (Docker required)
```

### Recommended Project Structure (new files only)

```
.github/
├── ISSUE_TEMPLATE/
│   ├── bug_report.yml
│   └── feature_request.yml
├── PULL_REQUEST_TEMPLATE.md
└── workflows/
    ├── ci.yml                       # rewrite: 7-job fan-out
    ├── release.yml                  # new: multi-arch build + sign + attest
    ├── release-please.yml           # new: opens release PRs
    ├── cosign-verify.yml            # new: PR gate on image signature
    ├── security-rescan.yml          # new: daily Trivy + auto-issue
    └── dependabot-auto-merge.yml    # new: auto-merge dependabot PRs
.release-please-config.json          # new
.release-please-manifest.json        # new
.trivyignore                         # new (empty, with grammar header comment)
.scorecard-exception.md              # new
scripts/
├── trivyignore-check.sh             # new
└── benchmark-cold-start.sh          # new
tests/
└── structural/
    ├── test_ci_yml_structure.py     # new: asserts job names in ci.yml
    └── test_trivyignore_check.py    # new: unit tests for parsing logic
```

---

## Key Configuration Snippets

### release-please-config.json

[VERIFIED: official release-please docs + WebFetch on docs/customizing.md]

The `extra-files` entry for `pipe.yml` must use the `yaml` type with `jsonpath` pointing to the `$.image` field. release-please will rewrite that field to `ghcr.io/yves-vogl/aws-eks-helm-deploy:X.Y.Z`.

```json
{
  "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
  "release-type": "python",
  "package-name": "aws-eks-helm-deploy",
  "bump-minor-pre-major": false,
  "changelog-types": null,
  "extra-files": [
    {
      "type": "yaml",
      "path": "pipe.yml",
      "jsonpath": "$.image"
    }
  ]
}
```

**Note on pipe.yml image field:** The current value is `yvogl/aws-eks-helm-deploy:1.3.0` (Docker Hub). Phase 6 must update this to `ghcr.io/yves-vogl/aws-eks-helm-deploy:2.0.0` as a one-time manual change BEFORE the first release-please run. After that, release-please maintains the version suffix.

### .release-please-manifest.json

```json
{".": "2.0.0-rc.0"}
```

Seed with the current pre-release version. release-please reads this to determine the next version bump.

### Cosign + GHCR Permissions Block

[VERIFIED: official GitHub docs + WebSearch cross-check]

For the `sign-and-attest` job in `release.yml`:

```yaml
permissions:
  contents: read
  packages: write        # push to GHCR (image + cosign signature OCI artifact)
  id-token: write        # request OIDC token from GitHub → Fulcio cert issuance
  attestations: write    # persist SLSA attestation (actions/attest-build-provenance)
```

**The `id-token: write` permission MUST NOT be granted to PR-triggered jobs** (security boundary). The `cosign-verify.yml` PR gate only *verifies* — it does not sign, so it only needs `contents: read`.

Workflow-level permissions for the full `release.yml`:
```yaml
permissions:
  contents: write        # create GitHub Release
  packages: write
  id-token: write
  attestations: write
```

Per-job overrides then restrict to minimum needed for each job.

### Multi-arch Build Matrix Pattern

[VERIFIED: Docker buildx documentation + GitHub Actions matrix syntax]

```yaml
jobs:
  build:
    strategy:
      matrix:
        platform:
          - linux/amd64
          - linux/arm64
        include:
          - platform: linux/amd64
            runner: ubuntu-24.04
          - platform: linux/arm64
            runner: ubuntu-24.04-arm
    runs-on: ${{ matrix.runner }}
    steps:
      - uses: docker/setup-buildx-action@d7f5e7f509e45cec5c76c4d5afdd7de93d0b3df5 # v4.1.0
      - uses: docker/build-push-action@f9f3042f7e2789586610d6e8b85c8f03e5195baf # v7.2.0
        with:
          platforms: ${{ matrix.platform }}
          outputs: type=image,push-by-digest=true,name-canonical=true,push=true
          # push-by-digest=true prevents per-arch tags; manifest is merged in fan-in job
```

Fan-in job uses `docker buildx imagetools create` to assemble the manifest from individual arch digests.

### Dockerfile Multi-arch Download Pattern

The current `helm-fetch`, `cosign-fetch`, and `helm-diff-fetch` stages hardcode `linux-amd64`. Phase 6 must make them arch-aware. Use `TARGETARCH` build arg (auto-set by BuildKit):

```dockerfile
# For helm-fetch stage — replace hardcoded linux-amd64:
ARG TARGETARCH
RUN curl -fsSL "https://get.helm.sh/helm-v${HELM_VERSION}-linux-${TARGETARCH}.tar.gz" ...
    && tar -xz -f "..." && mv linux-${TARGETARCH}/helm /helm

# For cosign-fetch stage:
ARG TARGETARCH
RUN curl -fsSL "https://github.com/sigstore/cosign/releases/download/v${COSIGN_VERSION}/cosign-linux-${TARGETARCH}" ...

# For helm-diff-fetch stage:
ARG TARGETARCH
RUN curl -fsSL ".../helm-diff-linux-${TARGETARCH}.tgz" ...
```

**CRITICAL:** Checksum files must also use `TARGETARCH`. For helm: `helm-v${HELM_VERSION}-linux-${TARGETARCH}.tar.gz.sha256sum`. For cosign: `cosign_checksums.txt` already contains both `amd64` and `arm64` entries — the grep pattern is just `cosign-linux-${TARGETARCH}$`. For helm-diff: `helm-diff-linux-${TARGETARCH}.tgz$` in the checksums file.

### OCI Annotations via docker/metadata-action

Phase 6 adds OCI annotations via `docker/metadata-action` labels, not `LABEL` directives in the Dockerfile (matches the Dockerfile comment at line 155). The `metadata-action` output feeds `docker/build-push-action` via `labels: ${{ steps.meta.outputs.labels }}`.

Required annotation keys (IMAGE-05):
- `org.opencontainers.image.source`
- `org.opencontainers.image.revision`
- `org.opencontainers.image.version`
- `org.opencontainers.image.licenses` → `Apache-2.0`
- `org.opencontainers.image.title`
- `org.opencontainers.image.description`

`docker/metadata-action` auto-populates `source`, `revision`, `version`, `created`, and `title` from the Git context. Add `licenses` and `description` via `labels:` input override.

### anchore/sbom-action Configuration

[VERIFIED: anchore/sbom-action GitHub Marketplace + WebSearch]

Two separate steps in `sign-and-attest` job:

```yaml
- name: Generate SPDX SBOM
  uses: anchore/sbom-action@e22c389904149dbc22b58101806040fa8d37a610 # v0.24.0
  with:
    image: ${{ env.IMAGE_DIGEST }}
    format: spdx-json
    output-file: sbom.spdx.json

- name: Generate CycloneDX SBOM
  uses: anchore/sbom-action@e22c389904149dbc22b58101806040fa8d37a610 # v0.24.0
  with:
    image: ${{ env.IMAGE_DIGEST }}
    format: cyclonedx-json
    output-file: sbom.cyclonedx.json
```

Default upload: `sbom-action` also uploads the file as a workflow artifact. Keep `upload-artifact: false` if you don't want duplicates (cosign attestation is the canonical delivery).

Then attest via cosign:
```yaml
- name: Attest SPDX SBOM
  run: |
    cosign attest --yes --bundle sbom.spdx.bundle \
      --predicate sbom.spdx.json \
      --type spdxjson \
      ${{ env.IMAGE_DIGEST }}

- name: Attest CycloneDX SBOM
  run: |
    cosign attest --yes --bundle sbom.cyclonedx.bundle \
      --predicate sbom.cyclonedx.json \
      --type cyclonedx \
      ${{ env.IMAGE_DIGEST }}
```

### .trivyignore Grammar and Enforcement Script

**What Trivy actually parses:** [VERIFIED: trivy.dev/docs/latest/configuration/filtering]

The plain `.trivyignore` file format: one CVE ID per line; `#` starts a comment (both inline and full-line). Trivy also natively supports `exp:YYYY-MM-DD` as a whitespace-separated token on the same line as the CVE ID.

However, the CONTEXT.md D2 decision uses a **custom** comment grammar for human review hygiene — the `expires=YYYY-MM-DD` in `# expires=...` is a comment to humans, not parsed by Trivy itself. The `scripts/trivyignore-check.sh` enforces this custom grammar.

**Grammar:** `CVE-XXXX-NNNNN  # expires=YYYY-MM-DD rationale="…" reviewer=<handle>`

**Alternative to consider:** Use Trivy's native `exp:YYYY-MM-DD` token instead, which Trivy itself enforces at runtime (auto-expires entries). This is strictly better and eliminates the need for `trivyignore-check.sh` to enforce expiry. But D2 is locked — the script is required. The script and Trivy's native `exp:` token are compatible (put `exp:YYYY-MM-DD` as the Trivy-parsed expiry AND also add the comment grammar for the reviewer field).

**Sample `scripts/trivyignore-check.sh` (Python helper approach per D2):**

```python
# scripts/_trivyignore_parser.py — called by trivyignore-check.sh
import re, sys
from datetime import date, timedelta

LINE_RE = re.compile(
    r'^(?P<cve>CVE-\d{4}-\d+)\s+'
    r'#\s*expires=(?P<expires>\d{4}-\d{2}-\d{2})\s+'
    r'rationale="(?P<rationale>[^"]+)"\s+'
    r'reviewer=(?P<reviewer>\S+)'
)
MAX_DAYS = 180

def check(path: str) -> list[str]:
    errors = []
    today = date.today()
    with open(path) as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            cve = line.split()[0]
            if not cve.startswith('CVE-'):
                continue
            m = LINE_RE.match(line)
            if not m:
                errors.append(f"Line {i}: missing required grammar: {line!r}")
                continue
            exp = date.fromisoformat(m['expires'])
            if exp < today:
                errors.append(f"Line {i}: {cve} expiry {exp} is PAST — remove or extend")
            elif (exp - today).days > MAX_DAYS:
                errors.append(f"Line {i}: {cve} expiry {exp} is > 180 days — shorten")
            if not m['reviewer']:
                errors.append(f"Line {i}: {cve} missing reviewer")
    return errors
```

Shell wrapper (`scripts/trivyignore-check.sh`) calls `uv run python scripts/_trivyignore_parser.py .trivyignore` and exits non-zero if errors list is non-empty.

### security-rescan.yml Skeleton

```yaml
name: security-rescan
on:
  schedule:
    - cron: '0 5 * * *'  # daily 05:00 UTC
  workflow_dispatch:

permissions:
  contents: read
  security-events: write
  issues: write

jobs:
  trivy-rescan:
    runs-on: ubuntu-24.04
    strategy:
      matrix:
        tag: [latest, "2"]
    steps:
      - uses: actions/checkout@<sha> # vX.Y.Z
      - uses: aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25 # v0.36.0
        with:
          image-ref: ghcr.io/yves-vogl/aws-eks-helm-deploy:${{ matrix.tag }}
          format: sarif
          output: trivy-${{ matrix.tag }}.sarif
          severity: CRITICAL,HIGH
          exit-code: 0  # don't fail here; issue-creation handles it
      - uses: github/codeql-action/upload-sarif@dd903d2e4f5405488e5ef1422510ee31c8b32357 # v3
        with:
          sarif_file: trivy-${{ matrix.tag }}.sarif
      - name: Open issue on CRITICAL/HIGH (deduped)
        # Script reads trivy JSON output, checks open issues by label+title hash
        run: |
          uv run python scripts/rescan-issue-creator.py \
            --sarif trivy-${{ matrix.tag }}.sarif \
            --tag ${{ matrix.tag }} \
            --repo ${{ github.repository }}
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Issue-deduplication:** The `rescan-issue-creator.py` script (to be implemented in Plan 06-07) keys on `f"{digest}:{cve_id}"` by listing open issues with `area/security` label and checking title hash. `issues: write` permission is needed.

### .scorecard-exception.md Template (D3)

```markdown
---
exceptions:
  - check: Token-Permissions
    reason: "Scorecard workflow itself needs id-token:write for OIDC publishing"
    review_date: 2026-12-20
    owner: yves-vogl
---

This file documents OpenSSF Scorecard check results that are intentionally allowed
to score below 10/10, with time-bound rationale. Each entry must be reviewed before
`review_date`. CI enforces stale detection — a past `review_date` fails the build.
```

CI step in `scorecard.yml` extension:
```yaml
- name: Check scorecard-exception.md for stale entries
  run: |
    python scripts/scorecard-exception-check.py .scorecard-exception.md
```

---

## ARM Runner Availability

[VERIFIED: github.blog/changelog/2025-08-07-arm64-hosted-runners-for-public-repositories-are-now-generally-available]

- **`ubuntu-24.04-arm`** is **Generally Available** for public repositories as of 2025-08-07.
- Available for private repositories as of 2026-01-29.
- Specs: **4 vCPUs**, ARM64 architecture.
- **Free for public repositories** — no minute multiplier vs amd64 on public repos.
- Label: `ubuntu-24.04-arm` (also `ubuntu-22.04-arm` available).
- No deprecation notices as of 2026-06-20.

**Confirmed: D4 decision (`ubuntu-24.04-arm`) is correct and available.**

---

## Manual Maintainer Steps (Cannot Land via PR)

These actions require Yves to perform them directly as repo admin. Document in `docs/admin/repo-settings.md`.

### 1. Enable Private Vulnerability Reporting

[VERIFIED: docs.github.com/en/rest/repos/repos#enable-private-vulnerability-reporting]

```bash
gh api repos/yves-vogl/aws-eks-helm-deploy/private-vulnerability-reporting -X PUT
```

Returns HTTP 204 on success. Check status:
```bash
gh api repos/yves-vogl/aws-eks-helm-deploy/private-vulnerability-reporting
```

Note: `SECURITY.md` already exists and references this feature as "planned". After running the command, update `SECURITY.md` to remove the "(planned)" qualifier.

### 2. Branch Protection on `main`

```bash
# Set branch protection (required reviews, required checks, no direct push)
gh api repos/yves-vogl/aws-eks-helm-deploy/branches/main/protection \
  -X PUT \
  -f required_status_checks='{"strict":true,"contexts":["pre-commit (lint + typecheck + unit + secrets)","unit-coverage","integration","trivy-image","trivy-dockerfile","pip-audit","acceptance"]}' \
  -f enforce_admins=true \
  -f required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":false}' \
  -f restrictions=null \
  -f allow_force_pushes=false \
  -f allow_deletions=false
```

**Note:** Status check names in `contexts` must exactly match the `name:` field in the workflow jobs. After Phase 6 CI rewrite, the job names from D9 must be verified and this command re-run with the correct names.

### 3. Require GPG-Signed Commits

```bash
gh api repos/yves-vogl/aws-eks-helm-deploy/branches/main/protection/required_signatures \
  -X POST
```

Returns `{"url": "...", "enabled": true}`. This is a POST (not PATCH) per the REST API.

### 4. Create GitHub Project Board (v2.0 milestone)

Web UI: `https://github.com/users/yves-vogl/projects/new`

Columns: `Backlog → Ready → In Progress → In Review → Done`

Link to milestone `v2.0.0` via Project board auto-add filter.

No gh CLI equivalent for Project v2 board creation with column configuration as of 2026.

### 5. Label Taxonomy

```bash
# Core labels (adjust --color values as preferred)
for label in "area/auth" "area/chart" "area/ci" "area/docs" "area/helm" "area/oidc" "area/security"; do
  gh label create "$label" --color "0075ca" --repo yves-vogl/aws-eks-helm-deploy 2>/dev/null || true
done
for label in "type/bug" "type/feature" "type/chore" "type/docs" "type/security"; do
  gh label create "$label" --color "d93f0b" --repo yves-vogl/aws-eks-helm-deploy 2>/dev/null || true
done
for label in "priority/p0" "priority/p1" "priority/p2" "priority/p3"; do
  gh label create "$label" --color "e4e669" --repo yves-vogl/aws-eks-helm-deploy 2>/dev/null || true
done
gh label create "breaking-change" --color "b60205" --repo yves-vogl/aws-eks-helm-deploy 2>/dev/null || true
gh label create "good first issue" --color "7057ff" --repo yves-vogl/aws-eks-helm-deploy 2>/dev/null || true
gh label create "help wanted" --color "008672" --repo yves-vogl/aws-eks-helm-deploy 2>/dev/null || true
gh label create "dependencies" --color "0366d6" --repo yves-vogl/aws-eks-helm-deploy 2>/dev/null || true
gh label create "python" --color "2b67c6" --repo yves-vogl/aws-eks-helm-deploy 2>/dev/null || true
gh label create "docker" --color "0db7ed" --repo yves-vogl/aws-eks-helm-deploy 2>/dev/null || true
gh label create "ci" --color "f9d0c4" --repo yves-vogl/aws-eks-helm-deploy 2>/dev/null || true
```

### 6. Docker Hub README Update (D10/MIG-01)

Manual via Docker Hub web UI at `https://hub.docker.com/repository/docker/yvogl/aws-eks-helm-deploy`.

Content to set (verbatim from D10):
```
⚠ This repository is FROZEN at v1.3.0.
v2.0+ is published to GitHub Container Registry:
  ghcr.io/yves-vogl/aws-eks-helm-deploy:2

See https://github.com/yves-vogl/aws-eks-helm-deploy for migration.
```

---

## Bitbucket-side Thin Mirror (CI-04)

The current `bitbucket-pipelines.yml` is the v1.x build+push pipeline (uses `bitbucketpipelines/bitbucket-pipe-release:5.6.1` to push to Docker Hub). Phase 6 replaces it with a stub.

**Minimum needed for Bitbucket Pipe Marketplace:** The Marketplace reads `pipe.yml` (which is in the git repo). The `bitbucket-pipelines.yml` is Bitbucket's CI config — the Marketplace does NOT require it to exist or run. However, Bitbucket Pipe Marketplace expects a working `bitbucket-pipelines.yml` for listing validation. A minimal stub that exits 0 satisfies this:

```yaml
# bitbucket-pipelines.yml — thin mirror stub (Phase 6+)
# GitHub Actions is the source-of-truth for image builds and releases.
# This file satisfies the Bitbucket Pipe Marketplace listing requirement.
# Image is published to ghcr.io/yves-vogl/aws-eks-helm-deploy by GitHub Actions.
image: python:3.13-slim

pipelines:
  default:
    - step:
        name: "Marketplace listing stub (no-op)"
        script:
          - echo "Image builds are handled by GitHub Actions (release.yml)"
          - echo "See https://github.com/yves-vogl/aws-eks-helm-deploy"
          - exit 0
```

**pipe.yml `image` field update:** The `image` field currently points to `yvogl/aws-eks-helm-deploy:1.3.0` (Docker Hub). This must be manually updated to `ghcr.io/yves-vogl/aws-eks-helm-deploy:2.0.0` as a one-time change in the Phase 6 plan that bootstraps release-please. Thereafter, release-please maintains the version.

---

## Cold-Start Benchmark Methodology (IMAGE-06)

### `scripts/benchmark-cold-start.sh`

```bash
#!/usr/bin/env bash
# benchmark-cold-start.sh — measure image cold-start (image pre-pulled, container startup only)
set -euo pipefail

IMAGE="${1:-ghcr.io/yves-vogl/aws-eks-helm-deploy:latest}"
N="${2:-5}"
OUTPUT_JSON="${3:-/tmp/cold-start-results.json}"

echo "Benchmarking cold-start for $IMAGE ($N runs)"

# Pre-pull to exclude network time (this is the spec for IMAGE-06)
docker pull "$IMAGE" > /dev/null 2>&1

times=()
for i in $(seq 1 "$N"); do
  start_ns=$(date +%s%N)
  docker run --rm "$IMAGE" --help > /dev/null 2>&1
  end_ns=$(date +%s%N)
  elapsed_ms=$(( (end_ns - start_ns) / 1000000 ))
  times+=("$elapsed_ms")
  echo "  Run $i: ${elapsed_ms}ms"
done

# Compute median (sort + pick middle)
sorted=($(printf '%s\n' "${times[@]}" | sort -n))
median_idx=$(( N / 2 ))
median_ms="${sorted[$median_idx]}"

echo "Median cold-start: ${median_ms}ms"

# Machine-readable JSON for CI consumption
python3 -c "
import json, sys
times = $( IFS=,; echo "[${times[*]}]" )
median = sorted(times)[len(times) // 2]
result = {'image': '$IMAGE', 'runs': $N, 'times_ms': times, 'median_ms': median, 'target_ms': 10000, 'pass': median < 10000}
print(json.dumps(result, indent=2))
" > "$OUTPUT_JSON"

cat "$OUTPUT_JSON"

median_ms_check=$(python3 -c "import json; d=json.load(open('$OUTPUT_JSON')); sys.exit(0 if d['pass'] else 1)")
```

**CI integration (SC3 / IMAGE-06):** Should this gate the release or just warn?

The ROADMAP SC3 says "reports under 10 seconds" — it is a **documented benchmark**, not a hard gate. Recommendation: emit the result as a workflow artifact + print to summary. Only gate if > 30s (catastrophic regression). At < 10s threshold, use a warning annotation. This avoids blocking releases for uncontrollable CI runner jitter. [ASSUMED: based on ROADMAP wording "documented cold-start benchmark ... reports under 10 seconds"]

---

## Dependabot Grouping Update (D6 vs Existing File)

The existing `.github/dependabot.yml` is mostly aligned with D6 but is missing the explicit `groups:` config. Current file uses `commit-message: prefix: "fix"` for pip (D6 specifies `chore` for pip production, `chore` for dev). **Contradiction:** D6 specifies `commit-message: { prefix: chore }` for pip but existing file uses `prefix: "fix"` for pip. The SEC-08 requirement only cares about the **docker** ecosystem using `prefix: fix` (so Dependabot docker bumps → `fix(deps):` → release-please patch). Pip using `fix` would also trigger patches on every Python dep update, which may be intentional.

Planner should align the existing `dependabot.yml` with D6's explicit grouping by adding:
- `pip` groups: `python` group matching all runtime + dev deps
- `docker` groups: `docker-base` matching `["python", "debian*"]`
- `github-actions` groups: `actions` matching `["*"]`
- Auto-merge config: D6 specifies a separate `dependabot-auto-merge.yml` workflow

The `dependabot-auto-merge.yml` pattern:
```yaml
name: dependabot-auto-merge
on:
  pull_request:

permissions:
  contents: write
  pull-requests: write

jobs:
  auto-merge:
    if: github.actor == 'dependabot[bot]'
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@<sha>
      - name: Wait for required checks
        # gh pr checks waits for all required checks to pass
        run: gh pr checks --watch --interval 30 ${{ github.event.pull_request.number }}
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      - name: Approve and merge
        run: |
          gh pr review --approve ${{ github.event.pull_request.number }}
          gh pr merge --squash --auto ${{ github.event.pull_request.number }}
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Release versioning | Custom changelog + version-bump script | `googleapis/release-please-action` | Conventional Commits → semver is a solved problem with edge cases (pre-release, breaking change detection, manifest file updates) |
| SBOM generation | Custom Syft wrapper | `anchore/sbom-action` | Syft's SPDX/CycloneDX output is the industry standard; the action handles image attestation UX |
| SLSA provenance | Custom attestation | `actions/attest-build-provenance` | GitHub's native attestation store; verifiable with `gh attestation verify` |
| Image signing | Custom GPG workflow | Cosign keyless + `sigstore/cosign-installer` | GPG image signing is dead-tech; Sigstore keyless is the SLSA-aligned standard |
| Dependency scanning | Custom CVE scraper | `aquasecurity/trivy-action` | Trivy covers image, Dockerfile, config, secrets in one tool |
| Supply-chain scoring | Custom check suite | `ossf/scorecard-action` | OpenSSF Scorecard is the industry-standard 18-check suite |
| Multi-arch manifest assembly | `docker manifest push` | `docker buildx imagetools create` | buildx imagetools handles digest-based assembly correctly; legacy `docker manifest` is deprecated |

---

## Common Pitfalls

### Pitfall 1: `id-token: write` in pull_request jobs
**What goes wrong:** Granting `id-token: write` to jobs triggered by `pull_request` is a security antipattern — a malicious PR could extract the OIDC token.
**Why it happens:** Cargo-culting the signing job's permissions into the PR gate.
**How to avoid:** `id-token: write` appears ONLY in `release.yml` (on tag push) and `cosign-verify.yml` only needs `contents: read`.
**Warning signs:** Any `pull_request`-triggered job with `id-token: write`.

### Pitfall 2: QEMU multi-arch (project-specific)
**What goes wrong:** `docker buildx build --platform linux/amd64,linux/arm64` on a single `ubuntu-24.04` runner uses QEMU for arm64 emulation. The arm64 binary works syntactically but can have silent performance or syscall-compatibility failures invisible from amd64 CI tests.
**How to avoid:** D4 + D9 matrix: separate `ubuntu-24.04` and `ubuntu-24.04-arm` runners, each building only their native arch. Merge with `docker buildx imagetools create`.

### Pitfall 3: release-please-action `v4` vs `v5` schema difference
**What goes wrong:** The CONTEXT.md references `googleapis/release-please-action@v4`. The latest is `v5.0.0`. In release-please-action v4, configuration moved from action inputs to `.release-please-config.json`. In v5, there may be additional schema changes.
**How to avoid:** Use the v5 SHA (`45996ed1f6d02564a971a2fa1b5860e934307cf7`). The `.release-please-config.json` schema is defined by the `release-please` library (not the action), which is backward-compatible.
**Warning signs:** release-please action failing with "Unknown configuration key" errors.

### Pitfall 4: `cosign sign` without `--bundle` loses offline verifiability
**What goes wrong:** Without `--bundle`, verification requires Rekor (online). If Rekor is down at verify time, signatures cannot be verified.
**How to avoid:** Always `cosign sign --bundle sbom.bundle` (already in D8 decision for SBOM; apply same to image signing).

### Pitfall 5: `actions/attest-build-provenance` version drift
**What goes wrong:** CONTEXT.md says `@v1` but the current latest is `@v4`. The `permissions: attestations: write` requirement still applies.
**How to avoid:** Use the verified `v4.1.0` SHA (`a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32`). Verify `attestations: write` is in the job's permissions block.

### Pitfall 6: `docker buildx imagetools create` requires all arch digests to be on the same registry
**What goes wrong:** If the amd64 and arm64 jobs push to different registries or use different image names, `imagetools create` fails.
**How to avoid:** Both matrix jobs push `push-by-digest=true` to the same `ghcr.io/yves-vogl/aws-eks-helm-deploy` repo. The fan-in job reads the digests from job outputs and assembles the manifest.

### Pitfall 7: Dependabot PR `commit-message prefix` divergence from SEC-08
**What goes wrong:** If Dependabot uses `chore` prefix for docker ecosystem bumps, release-please won't cut a patch release, and the base-image CVE fix won't trigger a new image publish.
**How to avoid:** Docker ecosystem MUST use `commit-message: prefix: "fix"` per SEC-08 contract.

### Pitfall 8: Status check names in branch protection must match workflow job names exactly
**What goes wrong:** Branch protection `required_status_checks.contexts` is case-sensitive and must match the `name:` field in the workflow job. If ci.yml renames a job, the branch protection silently stops enforcing it.
**How to avoid:** After Phase 6 CI rewrite, run the `gh api` branch protection command with the exact final job names. Document the required check names in `docs/admin/repo-settings.md`.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1 (already configured) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/structural -q --no-cov` |
| Full suite command | `uv run pytest tests/ -q --no-cov` |

### Phase Requirements → Test Map

Phase 6 has no Python source changes. "Tests" are structural assertions on YAML/JSON/script files plus the workflow runs themselves.

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CI-01 (D9) | `ci.yml` has 7 named jobs with correct names | structural | `uv run pytest tests/structural/test_ci_yml_structure.py -x` | ❌ Wave 0 |
| SEC-04 (D2) | `.trivyignore` grammar check | unit | `uv run pytest tests/unit/test_trivyignore_check.py -x` | ❌ Wave 0 |
| SEC-10 (D3) | `.scorecard-exception.md` stale detection | unit | `uv run pytest tests/unit/test_scorecard_exception_check.py -x` | ❌ Wave 0 |
| IMAGE-04 | Multi-arch manifest has both arches | smoke (manual) | `docker buildx imagetools inspect ghcr.io/yves-vogl/aws-eks-helm-deploy:latest` | manual |
| SEC-01 | Image has valid cosign signature | smoke (manual) | `cosign verify ghcr.io/yves-vogl/aws-eks-helm-deploy:latest` | manual |
| CI-02 | `.release-please-config.json` is valid JSON with required fields | structural | `uv run pytest tests/structural/test_release_please_config.py -x` | ❌ Wave 0 |
| All workflows | Workflow YAML files are valid YAML and digest-pinned | structural | `uv run pytest tests/structural/test_workflow_digest_pins.py -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/structural -q --no-cov` (structural assertions, < 5s)
- **Per wave merge:** `uv run pytest tests/ -q` (full suite including unit)
- **Phase gate:** Full suite green + workflow runs pass on a smoke PR

### Wave 0 Gaps

- [ ] `tests/structural/test_ci_yml_structure.py` — asserts job names in ci.yml
- [ ] `tests/structural/test_workflow_digest_pins.py` — asserts all `uses:` in `.github/workflows/*.yml` contain `@<sha>` (40-char hex)
- [ ] `tests/structural/test_release_please_config.py` — asserts `.release-please-config.json` has required fields and `pipe.yml` in `extra-files`
- [ ] `tests/unit/test_trivyignore_check.py` — per D2 requirement
- [ ] `tests/unit/test_scorecard_exception_check.py` — per D3 requirement
- [ ] `scripts/_trivyignore_parser.py` — Python module called by shell script
- [ ] `scripts/scorecard-exception-check.py` — Python module for D3

---

## Security Domain

### Applicable ASVS Categories (ASVS Level 1)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A (CI infrastructure, not user auth) |
| V3 Session Management | No | N/A |
| V4 Access Control | Yes | `permissions:` blocks at workflow level (least-privilege) |
| V5 Input Validation | Yes | `.trivyignore` grammar check + `.scorecard-exception.md` schema |
| V6 Cryptography | Yes | Cosign keyless (Ed25519/ECDSA P-384) — never hand-roll |
| V9 Communications | Yes | All GitHub Action downloads over HTTPS; cosign certificate chain via Fulcio/Rekor |
| V10 Malicious Code | Yes | All actions pinned to SHA digest; Dependabot keeps them current |
| V14 Configuration | Yes | Secrets only via `secrets.*`; no `${{ secrets.* }}` in `if:` conditions |

### Known Threat Patterns for GitHub Actions Supply Chain

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Compromised action via mutable tag | Tampering | Pin all actions to commit SHA digest |
| Malicious `pull_request_target` elevation | Elevation of Privilege | Never use `pull_request_target`; use `pull_request` only |
| OIDC token exfiltration from PR | Information Disclosure | `id-token: write` ONLY in release-triggered jobs |
| Stale CVE suppressions masking real vulnerabilities | Tampering | `.trivyignore` expiry enforcement in CI |
| Postinstall script in npm/pip dep | Tampering | pip-audit gate; no new npm deps in this phase |
| Slopsquatted Python package via AI hallucination | Tampering | Package legitimacy audit below |

---

## Package Legitimacy Audit

Phase 6 installs **no new Python packages** — all work is in YAML workflow files and shell/Python scripts. The structural test files use the existing `pytest` + `pyyaml` already in `pyproject.toml`. No new `npm` packages.

| Package | Registry | Notes | Verdict | Disposition |
|---------|----------|-------|---------|-------------|
| `pytest` | PyPI | Already in pyproject.toml dev deps | OK | Already approved |
| `pyyaml` | PyPI | Already in pyproject.toml | OK | Already approved |

**No new packages to audit.** All GitHub Actions are pinned to verified commit SHAs — this is the supply-chain protection mechanism for GH Actions (equivalent to package pinning).

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| GPG-signed Docker images | Cosign keyless (Sigstore) | ~2022-2023 | GPG image signing is deprecated in OCI; Sigstore provides transparency log + SLSA alignment |
| `docker manifest create` (multi-arch) | `docker buildx imagetools create` | BuildKit 0.10+ | buildx imagetools handles digest-based assembly; legacy manifest create is deprecated |
| `release-please-action` inputs (v3 style) | `.release-please-config.json` (v4/v5 style) | release-please v4 | Config file is source-of-truth; action inputs deprecated |
| QEMU multi-arch emulation | Native ARM runners | GH Actions 2025 | Native runners produce real arm64 binaries; QEMU can silently produce broken arm64 |
| Manual SBOM generation | `anchore/sbom-action` + `cosign attest` | 2022-2024 | Industry-standard; SLSA-aligned; verifiable via `cosign verify-attestation` |

---

## Contradictions to Surface

These require planner awareness — CONTEXT.md assumptions that don't match ground truth:

### C1: `actions/attest-build-provenance@v1` — actually at v4
CONTEXT.md references `@v1`. The current latest is `v4.1.0` (SHA `a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32`). The API and `attestations: write` permission requirement are unchanged. **Resolution:** Use v4 SHA. No config changes needed.

### C2: `googleapis/release-please-action@v4` — actually at v5
CONTEXT.md references v4. The current latest is `v5.0.0` (SHA `45996ed1f6d02564a971a2fa1b5860e934307cf7`). The `.release-please-config.json` schema is backward-compatible (schema is in the `release-please` library, not the action). **Resolution:** Use v5 SHA. Verify config schema on first run.

### C3: Dependabot `pip` prefix — `fix` vs `chore`
CONTEXT.md D6 specifies `commit-message: { prefix: chore }` for pip, but the existing `dependabot.yml` uses `prefix: "fix"` for pip runtime deps and `prefix-development: "chore"` for dev deps. Using `fix` for pip runtime would also trigger release-please patch releases on every Python dep update (not just base-image bumps). This may be intentional (fresh image on any dep update) or a mistake. **For planner:** Align to D6 (`chore` for pip) to avoid release spam; `fix` stays only for docker ecosystem per SEC-08.

### C4: `upload-artifact` — CONTEXT.md says v4, scorecard.yml uses v7.0.1
The scorecard.yml already pins to `v7.0.1` (SHA `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`). This is the current latest version. **Resolution:** No contradiction — scorecard.yml is ahead of CONTEXT.md version reference. All new workflows should use v7.0.1.

### C5: `actions/checkout` — v7.0.0 is the latest, existing workflows pin v4.2.2
This is a minor version discrepancy. v4.2.2 is still valid and correctly pinned. **Resolution:** Planner decision — update all checkout pins to v7.0.0 (`9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0`) in Phase 6 as a housekeeping item, or leave them and let Dependabot handle it.

---

## Open Questions

1. **release-please-action v5 schema compatibility**
   - What we know: v5.0.0 is the latest; `.release-please-config.json` schema is in the `release-please` library (not the action)
   - What's unclear: Whether v5 action introduces any breaking changes vs the v4 config schema
   - Recommendation: Use v5; run `release-please --dry-run` validation before first live run

2. **`pipe.yml` image field initial update**
   - What we know: `pipe.yml` currently has `image: yvogl/aws-eks-helm-deploy:1.3.0` (Docker Hub)
   - What's unclear: Which plan updates this to `ghcr.io/yves-vogl/aws-eks-helm-deploy:2.0.0-rc.0` as the pre-release-please bootstrap
   - Recommendation: Plan 06-02 (release-please bootstrap) should include a one-time manual update of `pipe.yml` image field before release-please runs

3. **Cosign verify job: which image to verify against?**
   - What we know: D7 says verify `ghcr.io/yves-vogl/aws-eks-helm-deploy:latest` in the PR workflow
   - What's unclear: `latest` only exists after the first release. Before the first release, `cosign-verify.yml` would fail with "image not found"
   - Recommendation: Add a `if: github.event.pull_request.draft == false` guard and a pre-check that the image exists; skip gracefully if not

4. **`rescan-issue-creator.py` Python script for SEC-07**
   - What we know: It needs `issues: write` permission and must dedup by `(digest, cve_id)`
   - What's unclear: Whether to make it a full Python module (covered by 100% coverage rule) or a `tests/`-exempt script
   - Recommendation: Put in `scripts/` (not `src/`); it's infrastructure, not product code; exempt from 100% coverage rule (add to `omit` in `[tool.coverage.run]`)

5. **Bitbucket Marketplace listing validation**
   - What we know: Bitbucket Pipe Marketplace reads `pipe.yml` for the listing
   - What's unclear: Does Bitbucket actively validate `bitbucket-pipelines.yml` runs, or just parse `pipe.yml`?
   - Recommendation: The thin stub (no-op pipeline) is the safe approach regardless

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `gh` CLI | Admin steps, action digest resolution | ✓ | (authenticated) | None — required |
| Docker | acceptance tests, benchmark script | ✓ (local) | — | CI runners have Docker |
| `cosign` | Signing + verify | ✓ (via sigstore/cosign-installer in CI) | 2.6.3 (pinned in Dockerfile; CI installs via action) | None |
| `ubuntu-24.04-arm` runner | arm64 build | ✓ (GA for public repos since 2025-08-07) | 4 vCPU | None (no fallback; QEMU is explicitly rejected) |
| GHCR | Image push | ✓ (github.actor + packages:write) | — | None |
| Rekor | Cosign transparency log | ✓ (public Sigstore infrastructure) | — | `--bundle` provides offline fallback |

**No missing dependencies with no fallback** (all required external services are available).

---

## Sources

### Primary (HIGH confidence — verified via `gh api` or official changelog)

- `gh api repos/<owner>/<repo>/git/refs/tags/<tag>` — all action SHA digests verified 2026-06-20
- [github.blog/changelog/2025-08-07](https://github.blog/changelog/2025-08-07-arm64-hosted-runners-for-public-repositories-are-now-generally-available/) — ARM runner GA for public repos
- [github.blog/changelog/2026-01-29](https://github.blog/changelog/2026-01-29-arm64-standard-runners-are-now-available-in-private-repositories/) — ARM runner spec: 4 vCPU public / 2 vCPU private
- [trivy.dev/docs/latest/configuration/filtering](https://trivy.dev/docs/latest/configuration/filtering/) — `.trivyignore` format, native `exp:` support
- [docs.github.com REST API — enable private vulnerability reporting](https://docs.github.com/en/rest/repos/repos#enable-private-vulnerability-reporting-for-a-repository) — `PUT /repos/{owner}/{repo}/private-vulnerability-reporting`
- [github.com/googleapis/release-please/blob/main/docs/customizing.md](https://github.com/googleapis/release-please/blob/main/docs/customizing.md) — `extra-files` with `type: yaml` + `jsonpath`
- [github.com/actions/attest-build-provenance](https://github.com/actions/attest-build-provenance) — `attestations: write` permission required
- [github.com/anchore/sbom-action](https://github.com/anchore/sbom-action) — `output-file` + `format: spdx-json` / `cyclonedx-json`

### Secondary (MEDIUM confidence — cross-checked web search)

- WebSearch: cosign keyless + GHCR permissions (`id-token: write`, `packages: write`, `contents: read`)
- WebSearch: `PUT /repos/{owner}/{repo}/private-vulnerability-reporting` endpoint (confirmed via changelog)
- WebSearch: `gh api repos/…/branches/main/protection/required_signatures -X POST` for GPG enforcement

### Tertiary (ASSUMED — training knowledge not verified this session)

- release-please-action v5 backward compatibility with v4 config schema [ASSUMED]
- `docker buildx imagetools create` fan-in pattern for multi-arch manifests [ASSUMED]
- `actions/attest-build-provenance` v4 API unchanged from v1 [ASSUMED]

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | release-please-action v5 is backward-compatible with v4 `.release-please-config.json` schema | Action Digest table | Plan 06-02 may need schema updates; dry-run catches this before merge |
| A2 | `actions/attest-build-provenance` v4 has the same interface as v1; `attestations: write` still required | Permissions block | Job fails with permission error; caught in CI immediately |
| A3 | `docker buildx imagetools create` is the correct fan-in pattern for digest-based multi-arch manifest assembly | Multi-arch build pattern | Alternative: push with platform-specific tags and merge; not a blocking error |
| A4 | The thin `bitbucket-pipelines.yml` stub (no-op) satisfies Bitbucket Pipe Marketplace listing validation | Bitbucket thin mirror | Marketplace listing may go offline; recoverable by adding a real step |
| A5 | `rescan-issue-creator.py` in `scripts/` is exempt from 100% coverage rule | Validation Architecture | Coverage gate may fail; add to `omit` in `[tool.coverage.run]` |
| A6 | Cold-start benchmark < 10s is a documented target, not a hard CI gate | Benchmark methodology | If planner makes it a hard gate, runner jitter could flap |

---

## Metadata

**Confidence breakdown:**
- Action digest SHAs: HIGH — verified via `gh api` on 2026-06-20
- ARM runner availability: HIGH — verified via official GitHub changelog
- Permissions blocks: HIGH — verified via official GitHub docs
- Architecture patterns: MEDIUM — `buildx imagetools create` is standard but A3 is assumed
- release-please v5 compat: MEDIUM — A1 is assumed; dry-run verification recommended
- Script implementations: MEDIUM — patterns are well-established; exact implementation is discretion

**Research date:** 2026-06-20
**Valid until:** 2026-09-20 (90 days; action SHA digests should be refreshed via Dependabot)
