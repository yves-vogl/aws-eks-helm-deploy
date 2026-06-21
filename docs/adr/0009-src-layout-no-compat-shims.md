---
status: accepted
date: 2026-06-21
decision-makers: yves-vogl
consulted: claude-code (planning)
informed: project contributors, package maintainers, v1 consumers
---

# `src/`-layout for v2.x Python package; no v1.x import-path compatibility shims

## Context and Problem Statement

Phase 1 adopted the `src/aws_eks_helm_deploy/` layout for the v2 Python package. v1.x had no Python package — it was a shell pipe with a flat `pipe/` directory containing helper scripts. There is no v1 Python import path to preserve. However, we still face a packaging-layout choice for v2 itself: flat-layout (`aws_eks_helm_deploy/` at repo root) or src-layout (`src/aws_eks_helm_deploy/`). And we need to be explicit that the v1 `pipe/` directory's runtime behavior is NOT re-exported under any v2 import path.

## Decision Drivers

* Modern Python packaging practice — `src/` layout is the documented default in the Python Packaging Guide and prevents accidental imports from the working directory during development.
* Clear v1 / v2 boundary — v2 has its own package namespace; v1 stays on Docker Hub frozen at v1.3.0 with its shell-based architecture.
* No accidental dual-import bugs — flat-layout sometimes lets tests import from the working tree even when the install is missing, hiding install-time bugs.
* Matches the "v2 is a clean break" decision (ADR-0002) at the package level — there is no `aws_eks_helm_deploy.v1.*` shim namespace.

## Considered Options

* Flat-layout — `aws_eks_helm_deploy/` directly at repo root.
* `src/`-layout — `src/aws_eks_helm_deploy/` with `pyproject.toml` declaring `[tool.hatch.build.targets.wheel] packages = ["src/aws_eks_helm_deploy"]`.
* `src/`-layout + v1 compat shim package — `src/aws_eks_helm_deploy/v1/` re-exports a Python-emulation of v1 behavior.

## Decision Outcome

Chosen option: **"`src/`-layout, no compat shim"**, because the `src/` layout is the modern packaging default, removes the "accidentally importable from the working tree" failure mode, and aligns with the v2-clean-break decision (ADR-0002). v1 consumers continue running the Docker Hub image at v1.3.0 unchanged; v2 consumers use the new GHCR image with the `aws_eks_helm_deploy` package namespace. There is no Python-level shim because there is no Python v1 to shim.

### Consequences

* Good, because tests cannot accidentally import from the working tree — every import goes through the installed package, surfacing missing-install bugs during CI.
* Good, because `src/` layout aligns with PyPA's documented modern default.
* Good, because the v1/v2 boundary stays at the image / registry level (v1 = Docker Hub shell pipe; v2 = GHCR Python package), not at the Python import-path level.
* Bad, because contributors new to `src/`-layout may need a `pip install -e .` reminder before tests work (mitigated by `uv sync` in CONTRIBUTING.md).
* Neutral, because the slightly deeper path (`src/aws_eks_helm_deploy/`) is a one-time IDE configuration cost.

## Pros and Cons of the Options

### Flat-layout

* Good, because slightly shorter file paths.
* Bad, because allows accidental working-tree imports; CI may pass with a broken install.
* Bad, because contradicts PyPA's documented modern default.

### `src/`-layout

* Good, because matches the PyPA documented modern default.
* Good, because forces tests to import from the installed package.
* Good, because surfaces packaging bugs during CI rather than after publish.
* Neutral, because requires `pip install -e .` / `uv sync` before tests work locally.

### `src/`-layout + v1 compat shim

* Good, because v1 users could theoretically `pip install aws_eks_helm_deploy` and get familiar APIs.
* Bad, because v1 has no Python API to begin with — there is nothing to shim.
* Bad, because would force v2 to carry a fictional v1 emulation layer.
* Bad, because contradicts ADR-0002 (clean break — no compat shims).

## More Information

* Sources: [Phase 1 CONTEXT](https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/.planning/phases/01-toolchain-spine/01-CONTEXT.md), REQUIREMENTS.md TOOL-02 (src-layout adopted), and the cross-reference to ADR-0002 (clean break).
* Cross-references: ADR-0002 (clean break — this ADR is the package-level corollary), ADR-0004 (boto3-only — lives under `src/aws_eks_helm_deploy/eks/token.py`).
* NIH check: `src/` layout is the upstream PyPA-documented standard; this ADR adopts an established practice rather than inventing one.
