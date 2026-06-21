---
status: accepted
date: 2026-06-21
decision-makers: yves-vogl
consulted: claude-code (planning)
informed: documentation contributors, future v2.1 maintainers
---

# mkdocs-material 9.x for v2.0; migrate to Zensical at v2.1+

## Context and Problem Statement

v2.0 needs a documentation site (DOC-01..DOC-07) covering quick-start, configuration reference, migration guide, ADRs, and admin/runbook content. The natural default — mkdocs-material — entered maintenance mode on 2025-11-06 (squidfunk/mkdocs-material#8523), with critical-fix support through November 2026. Zensical is the announced successor from the same maintainer but is not yet stable. We must pick a documentation platform that ships v2.0 on time without committing to a tool that will be unmaintained inside our security-support window.

## Decision Drivers

* Stability today — v2.0 must ship its docs site at tag-cut; no platform churn allowed in the release window.
* GitHub Pages compatibility — the docs site is published from `gh-pages` via the existing `docs.yml` workflow.
* Ecosystem familiarity — mkdocs-material is the most widely-deployed Python project documentation platform; contributors do not need to learn a new toolchain.
* 12-18 month maintenance horizon — mkdocs-material's critical-fix support through Nov 2026 comfortably exceeds the v1.x 6-month security window (D10) and gives us until v2.1+ to migrate to Zensical.
* Theme + plugin maturity — `mike` for versioned docs, `pymdown-extensions`, `mkdocstrings-python` (for the settings-doc autogeneration in Plan 07-03) are all mkdocs-material-native.

## Considered Options

* mkdocs-material 9.7.6 now; migrate to Zensical when Zensical is stable.
* Zensical now (immature; tracking issues open).
* Sphinx with a modern theme (Furo / sphinx-book-theme).
* Docusaurus (Node toolchain).

## Decision Outcome

Chosen option: **"mkdocs-material 9.7.6 now; migrate to Zensical when stable"**, because mkdocs-material is the only option that satisfies stability + GitHub-Pages-compatibility + ecosystem-familiarity + the maintenance-horizon requirement on the v2.0 release date. The Zensical migration is tracked as DOC-NEXT-01 in the requirements register for v2.1+ — we will migrate once Zensical reaches a stable release and has migration tooling from mkdocs-material.

### Consequences

* Good, because v2.0 docs ship on time with the mature, well-known toolchain.
* Good, because every plugin we need (`mike`, `pymdown-extensions`, `mkdocstrings-python`) is mkdocs-material-native.
* Good, because the maintenance horizon (Nov 2026 critical fixes) exceeds the v1.x 6-month security window — we have runway.
* Bad, because we commit to a planned migration at v2.1+; that migration is real work we owe.
* Bad, because if Zensical's migration tooling is poor, the v2.1 migration will be expensive.

## Pros and Cons of the Options

### mkdocs-material 9.7.6 now

* Good, because stable today; ships v2.0 on time.
* Good, because every required plugin works.
* Neutral, because maintenance mode is real but ends after our v2.0 security-support window.
* Bad, because we owe a Zensical migration at v2.1+.

### Zensical now

* Good, because future-aligned with the maintainer's roadmap.
* Bad, because not stable; risks v2.0 ship slip.
* Bad, because plugin ecosystem (mike, mkdocstrings-python integration) is not yet ported.
* Bad, because community familiarity is near-zero.

### Sphinx + modern theme

* Good, because Sphinx is the python.org documentation standard and is not in maintenance mode.
* Bad, because the toolchain (reStructuredText or MyST, conf.py, sphinx-build) is more complex than mkdocs.
* Bad, because the migration cost from the existing mkdocs-friendly source is non-trivial.
* Bad, because `mkdocstrings-python` is mkdocs-native; the Sphinx equivalent is a different config surface.

### Docusaurus

* Good, because actively maintained with a polished React-based UI.
* Bad, because introduces a Node toolchain into a pure-Python project (contradicts the "Python rewrite" simplification narrative).
* Bad, because doc authors must learn JSX-flavored Markdown (MDX).

## More Information

* Sources: [Phase 7 CONTEXT](https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/.planning/phases/07-documentation-site-migration-guide/07-CONTEXT.md) D1 (mkdocs choice), 07-RESEARCH.md Q1 (mkdocs-material 9.7.6 PyPI pin), Q10 Pitfall #2 (maintenance-mode through Nov 2026), DOC-NEXT-01 (Zensical migration tracked for v2.1+).
* Cross-references: ADR-0002 (clean break — the docs site is part of v2.x; v1.x has no docs site to migrate).
* NIH check: mkdocs-material is the upstream maintained tool. We are not building a custom static-site generator. The planned Zensical migration is following the upstream maintainer's published successor, not branching off independently.
