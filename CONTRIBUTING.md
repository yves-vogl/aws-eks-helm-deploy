# Contributing to aws-eks-helm-deploy

Thanks for considering a contribution. This project is a Bitbucket Pipelines Pipe that deploys Helm charts to AWS EKS. v2.x is the active line; v1.x is frozen.

## How to file an issue

- For **bugs**, open a [GitHub issue](https://github.com/yves-vogl/aws-eks-helm-deploy/issues) with: the pipe version, the relevant `pipe.yml` snippet (with secrets redacted), the failure mode, and the logs (with credentials redacted).
- For **feature requests**, open an issue describing the use case before submitting a PR — small fixes can skip this, but anything touching the public env-var contract should be discussed first.
- For **security vulnerabilities**, **do not open a public issue.** Use [GitHub Private Vulnerability Reporting](https://github.com/yves-vogl/aws-eks-helm-deploy/security) — see [SECURITY.md](SECURITY.md).

## How to submit a pull request

1. Fork the repo and create a branch from `main`.
2. Run `make bootstrap` to install `uv`, then `uv sync --all-extras --frozen` to set up the development environment.
3. Make your changes. Keep the diff focused — one concern per PR.
4. Verify locally:
   - `make lint` — `ruff check` and `ruff format --check` must exit 0
   - `make typecheck` — `mypy --strict src` must exit 0
   - `make test` — `pytest` with the 100% line+branch coverage gate must pass
   - `make integration-test` — kind + helm smoke (requires Docker and `kind`)
   - `make acceptance-test` — Docker image smoke (requires Docker)
5. Run `uv run pre-commit run --all-files` and `uv run pre-commit run --hook-stage pre-push --all-files` — both must exit 0.
6. Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) — `feat(scope): …`, `fix(scope): …`, `docs(scope): …`, `chore(scope): …`. The scope is usually the phase number (`feat(02): …`) for milestone work, or the area (`feat(auth): …`) for cross-cutting work.
7. Commits should be GPG-signed. `commit.gpgsign=true` should be set in your local `git config`.
8. Open the PR against `main`. The PR template (when present) walks you through the checklist; otherwise include: motivation, what changed, how it was verified, and any deliberate scope omissions.
9. CI must pass (the `ci` workflow runs the pre-commit suite + `pip-audit`). A CODEOWNERS-driven review is requested automatically.

## What to expect from the maintainer

- Initial response within 5 working days for issues and PRs.
- For PRs that don't follow the conventions above, expect specific feedback rather than a silent close — the goal is to land your change, not bounce it.
- Substantial features may require an [ADR](./.planning/) before implementation. The maintainer will say so explicitly.

## What gets rejected

- PRs that change behavior without tests, or that lower the coverage gate.
- PRs that bundle unrelated changes ("while I was in there I also refactored X").
- PRs that introduce a new dependency without justifying why an existing one can't do the job (see the project's NIH-avoidance preference — prefer well-maintained existing tools over reinventing them).
- PRs that add AI-generated co-author attribution to commits.
- PRs that disable pre-commit hooks or use `--no-verify`.

## Project structure

- `src/aws_eks_helm_deploy/` — Python sources (v2.x)
- `pipe/` — v1.x legacy code (frozen, not touched in v2)
- `tests/unit/`, `tests/integration/`, `tests/acceptance/` — three tiers, unit is the default `pytest` run
- `.planning/` — GSD planning artifacts (phase plans, research, validation matrices, deferrals)
- `docs/` — operator-facing documentation
- `Dockerfile` — multi-stage build producing the runtime image

## License

By submitting a contribution, you agree to license it under the Apache License 2.0 (the same license as the project).
