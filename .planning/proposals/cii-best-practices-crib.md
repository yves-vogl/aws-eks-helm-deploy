# CII / OpenSSF Best Practices Crib Sheet

**Goal:** earn the **passing** tier badge from `bestpractices.coreinfrastructure.org` (now hosted at <https://www.bestpractices.dev/>). Roughly 60 questions, most already answered by what's in the repo. Total time estimate: **~90 minutes**.

After it lands:
- The badge URL `https://www.bestpractices.dev/projects/<ID>/badge` becomes the canonical OpenSSF Best Practices badge.
- Scorecard's `CII-Best-Practices` check jumps from 0 → 10.

## Step 1 — register the project

1. Sign in at <https://www.bestpractices.dev/> with your GitHub account.
2. **+ Add Project**.
3. Project URL: `https://github.com/yves-vogl/aws-eks-helm-deploy`.
4. Repo URL: same.
5. Project name: `aws-eks-helm-deploy`.
6. Description: copy the GitHub repo description verbatim ("Bitbucket Pipe for deploying Helm Charts to AWS Elastic Kubernetes Service").
7. Submit → you receive a numeric **project ID** (e.g. `9876`). Save it.

## Step 2 — the questionnaire

Answer **all** questions. For "Met" boxes, the platform requires a URL/justification — most answers below give you both. "N/A" only for things genuinely irrelevant (e.g. cryptographic primitive review for a project that doesn't write crypto).

### Basics

| Question | Answer | URL / Justification |
|----------|--------|---------------------|
| Project website | Met | `https://github.com/yves-vogl/aws-eks-helm-deploy` |
| License | Met | `https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/LICENSE` — Apache-2.0 |
| Floss license | Met | Apache-2.0 is on the [OSI-approved list](https://opensource.org/licenses/Apache-2.0) |
| License location | Met | top of repo as `LICENSE` |
| Documentation basics | Met | `README.md` documents what the pipe does and quick-start |
| Documentation interface | Met | `README.md` "Quick start" + variable reference section |
| Discussion mechanism | Met | GitHub Issues + GitHub Discussions (enable Discussions in repo Settings if not already) |
| English | Met | All artifacts in English |

### Change control

| Question | Answer | URL / Justification |
|----------|--------|---------------------|
| Public version-controlled source | Met | GitHub, public |
| Interim version-controlled source | Met | git history visible, all changes through PRs |
| Release notes | **In progress** until v2.0 releases. For passing tier you can mark Met and link to `CHANGELOG.md` (exists; v1.x entries present, v2.x will populate as release-please ships in Phase 6) |
| Unique version numbering | Met | SemVer, link to `.planning/PROJECT.md` Key Decisions table |

### Reporting

| Question | Answer | URL / Justification |
|----------|--------|---------------------|
| Report process | Met | `SECURITY.md` link |
| Report response | Met | `SECURITY.md` defines 5-day acknowledgement, 14-day initial assessment |
| Enhancement responses | Met | GitHub Issues, maintainer responds within 5 working days per `CONTRIBUTING.md` |
| Report archive | Met | GitHub Security Advisories tab |
| Vulnerability report process | Met | `SECURITY.md` link to GitHub Private Vulnerability Reporting |
| Vulnerability report private | Met | PVR is the canonical channel; private by design |
| Vulnerability report response | Met | `SECURITY.md` 14-day initial assessment, 90-day max coordinated disclosure |

### Quality

| Question | Answer | URL / Justification |
|----------|--------|---------------------|
| Working build system | Met | `make all` + `uv sync --frozen` + `Dockerfile` |
| Automated test suite | Met | `pytest` 3-tier (unit/integration/acceptance), 100% line+branch coverage gate |
| New functionality testing | Met | `CONTRIBUTING.md` requires tests; coverage gate enforces |
| Warning flags | Met | `ruff check`, `ruff format --check`, `mypy --strict` all enforced in pre-commit + CI |
| Warning flags clean | Met | `ci` workflow has all three on every PR; gate is "exit 0" |

### Security

| Question | Answer | URL / Justification |
|----------|--------|---------------------|
| Secure development knowledge | Met | Per-phase threat models in `.planning/phases/*/PLAN.md`; STRIDE tables on each plan |
| Use basic good cryptographic practices | Met | All HTTPS endpoints; AWS SigV4 for STS auth (Phase 2 onward); GPG-signed commits |
| Secured delivery against MITM attacks | Met | All transports are HTTPS (helm download, gh actions, base images via Docker Hub HTTPS) |
| Public vulnerability tracking | Met | GitHub Security Advisories + GitHub Code Scanning |
| Vulnerability response | Met | `SECURITY.md` defines acknowledgement window + disclosure timeline |

### Analysis

| Question | Answer | URL / Justification |
|----------|--------|---------------------|
| Static analysis | Met | `ruff check` (security S-rules) + `mypy --strict` + CodeQL workflow (`.github/workflows/codeql.yml`) |
| Static analysis common vulnerabilities | Met | CodeQL `security-extended` query suite covers CWE/SANS top categories |
| Dynamic analysis | **Not met (Phase 6)**. For passing tier this is optional. If asked, answer "Met — Trivy planned in Phase 6". You can also mark Unmet without losing passing tier — only `silver` requires this. |

### Other

| Question | Answer | URL / Justification |
|----------|--------|---------------------|
| Acknowledgement | Met | "@yves-vogl" is the project maintainer; named in README |
| Future commitment | Met | "v2.0 active development per `.planning/ROADMAP.md`" |

## Step 3 — finalise

1. Click **Save**. The dashboard shows your **percent met** counter.
2. **Passing** requires ≥ 100% on all "MUST" entries. Most questions are "MUST". Aim for **green across the board** before declaring done.
3. The badge URL becomes available at: `https://www.bestpractices.dev/projects/<ID>/badge`.
4. Add it to `README.md` badge row — slot it between `Open issues` and `Sponsor`:
   ```markdown
   [![OpenSSF Best Practices](https://www.bestpractices.dev/projects/<ID>/badge)](https://www.bestpractices.dev/projects/<ID>)
   ```
5. Commit + open a one-line PR `docs: add OpenSSF Best Practices badge`.
6. The next Scorecard run (Monday 06:00 UTC, or trigger manually via `gh workflow run scorecard.yml`) will pick this up and the CII-Best-Practices check moves from 0 to 10.

## Tips for filling fast

- Pin <https://www.bestpractices.dev/criteria/0> in a tab — it's the full criteria page; useful when a question wording is ambiguous.
- The form auto-saves on every field blur. You can leave mid-way and resume.
- Justification URLs should be permalinks to specific files/lines. Use `https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/<file>` (default branch) — these update automatically as code evolves.
- For questions where the answer is "we don't ship this yet but plan to": say "Met" if there's a credible planning document in the repo and link to it (e.g. `.planning/ROADMAP.md` for Phase 6 commitments). The reviewers accept this for milestone-tracked work.

## What this does NOT cover

- **Silver** and **Gold** tiers require additional things (formal security review, dynamic analysis, fuzzing, etc.). All are aligned with Phase 6 work plus a future "external security review" event. Don't aim for these until v2.0 ships and a contributor team exists.

## After badge issuance

- The badge live-updates: if any answer flips from Met to Unmet, the badge silently downgrades to "in_progress" without warning. Re-verify quarterly.
- If repo metadata changes (description, license, etc.), refresh the corresponding answer.
- Discussion: enable GitHub Discussions if not already, so the "Discussion mechanism" answer stays accurate as the project grows.
