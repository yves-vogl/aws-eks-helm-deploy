# CII / OpenSSF Best Practices — paste-ready answer sheet

**Target tier:** passing
**Form URL:** <https://www.bestpractices.dev/>
**Repo URL to register:** `https://github.com/yves-vogl/aws-eks-helm-deploy`

**Locked decisions** (per Yves, 2026-06-18):
1. GitHub Discussions: **enabled** (just turned on via API). Use the Discussions URL for "Discussion mechanism".
2. Release notes: link **CHANGELOG.md** with a note that release-please populates v2 entries from Phase 6.
3. Dynamic analysis: **Met** — pip-audit + CodeQL fulfil it for the passing tier.

---

## Workflow

1. Open <https://www.bestpractices.dev/>, sign in with GitHub.
2. Click **+ Add Project**.
3. Project URL + Repo URL: both `https://github.com/yves-vogl/aws-eks-helm-deploy`.
4. Project name: `aws-eks-helm-deploy`.
5. Description: copy the GitHub repo description verbatim — `Bitbucket Pipe for deploying Helm Charts to AWS Elastic Kubernetes Service`.
6. Save → you receive a numeric **project ID**. Note it down.
7. Walk through the questionnaire using the table below.
8. After 100% Met → grab the badge URL `https://www.bestpractices.dev/projects/<ID>/badge` and open a one-line PR `docs: add OpenSSF Best Practices badge to README`.

---

## Answers (passing tier — every "MUST" question)

| Section | Question | Answer | Justification URL (use these verbatim) |
|---------|----------|--------|----------------------------------------|
| **Basics** | Project website | Met | `https://github.com/yves-vogl/aws-eks-helm-deploy` |
| Basics | License | Met | `https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/LICENSE` |
| Basics | FLOSS license (OSI-approved) | Met | Apache-2.0 — listed at <https://opensource.org/licenses/Apache-2.0> |
| Basics | License location | Met | top of repo as `LICENSE` |
| Basics | Documentation basics | Met | `https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/README.md` |
| Basics | Documentation interface | Met | README.md "Quick start" + variable reference section |
| Basics | Discussion mechanism | Met | `https://github.com/yves-vogl/aws-eks-helm-deploy/discussions` (Discussions enabled 2026-06-18) |
| Basics | English | Met | All artifacts are in English |
| **Change control** | Public version-controlled source | Met | GitHub repo URL above |
| Change control | Interim version-controlled source | Met | All changes flow through PRs visible in git history |
| Change control | Release notes | Met | `https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/CHANGELOG.md` — v1 entries present; v2 entries auto-populated by release-please (Phase 6) |
| Change control | Unique version numbering | Met | SemVer per `.planning/PROJECT.md` Key Decisions table |
| **Reporting** | Report process (general) | Met | `https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/SECURITY.md` |
| Reporting | Report response | Met | SECURITY.md states 5-day acknowledgement, 14-day initial assessment |
| Reporting | Enhancement responses | Met | CONTRIBUTING.md says maintainer responds within 5 working days; GitHub Issues |
| Reporting | Report archive | Met | `https://github.com/yves-vogl/aws-eks-helm-deploy/security/advisories` |
| Reporting | Vulnerability report process | Met | SECURITY.md links to GitHub Private Vulnerability Reporting |
| Reporting | Vulnerability report private | Met | GitHub PVR is the canonical channel; private by design |
| Reporting | Vulnerability report response | Met | SECURITY.md: 14-day initial assessment, 90-day max disclosure |
| **Quality** | Working build system | Met | `Dockerfile` + `Makefile` (`make all`, `uv sync --frozen`) |
| Quality | Automated test suite | Met | `tests/` 3-tier with `pytest`, 100% line+branch coverage gate |
| Quality | New functionality testing | Met | CONTRIBUTING.md requires tests; coverage gate enforces |
| Quality | Warning flags | Met | ruff + mypy --strict via pre-commit + CI |
| Quality | Warning flags clean | Met | `.github/workflows/ci.yml` requires exit 0 on every PR |
| **Security** | Secure development knowledge | Met | Per-phase threat models in `.planning/phases/*/PLAN.md` STRIDE tables |
| Security | Basic good cryptographic practices | Met | All HTTPS endpoints; AWS SigV4 for STS auth; GPG-signed commits on `main` (enforced by Branch Protection) |
| Security | Secured delivery against MITM | Met | All transports HTTPS (helm download SHA256-verified, Docker Hub HTTPS, GHCR HTTPS) |
| Security | Public vulnerability tracking | Met | GitHub Security Advisories + Code Scanning (CodeQL + Scorecard SARIF) |
| Security | Vulnerability response | Met | SECURITY.md defines acknowledgement window + disclosure timeline |
| **Analysis** | Static analysis | Met | ruff (security S-rules) + mypy --strict + `.github/workflows/codeql.yml` |
| Analysis | Static analysis common vulnerabilities | Met | CodeQL `security-extended` query suite |
| Analysis | Dynamic analysis | Met | pip-audit (every push, with stale-ignore detection) + CodeQL data-flow analysis |
| **Other** | Acknowledgement | Met | Project maintained by [@yves-vogl](https://github.com/yves-vogl); credited in README |
| Other | Future commitment | Met | v2.0 active development; roadmap in `.planning/ROADMAP.md` |

---

## After badge issuance

1. Note the **project ID** from your dashboard.
2. Add the badge to `README.md` — insert between the Scorecard badge and the Stars badge:
   ```markdown
   [![OpenSSF Best Practices](https://www.bestpractices.dev/projects/<ID>/badge)](https://www.bestpractices.dev/projects/<ID>)
   ```
3. One-line PR: `docs: add OpenSSF Best Practices badge to README`.
4. The next Scorecard run (Mon 06:00 UTC, or `gh workflow run scorecard.yml`) picks it up and `CII-Best-Practices` jumps 0 → 10.

## Things to remember (quarterly re-verify)

- The badge live-updates: if any answer flips from Met to Unmet, the badge silently downgrades to `in_progress`. Set a quarterly reminder to log in and skim the criteria.
- If repo metadata changes (description, license file rename, etc.), refresh the corresponding answer immediately.

## Defer to silver/gold tier (NOT this round)

- **Formal security review** — needs a third-party audit; planned post-v2.0
- **Fuzzing** — Phase 6 (Atheris + Hypothesis on `_CommaListEnvSource` + EKS token parser)
- **Continuous integration matrix expansion** — Phase 6 CI-01

Aiming higher than passing in this sprint is wasted effort. Passing today; silver after v2.0 ships with Cosign + SBOM + first GitHub Release.
