# Phase 5 — Discussion Log

**Date:** 2026-06-20
**Mode:** discuss (interactive, single-pass)
**Participants:** Yves Vogl (decisions), Claude Opus 4.7 (gray-area analysis)
**Phase:** 05-log-masking-diff-rollback-metadata-flip

For canonical decisions see `05-CONTEXT.md`. This log is human-reference only (audit, retrospective). Downstream agents (researcher, planner, executor) do NOT consume this file.

---

## Round 1 — Gray-area triage

**Claude presented 5 candidate gray areas:**

1. Redaction implementation strategy (SEC-06)
2. helm-diff plugin distribution
3. PR-comment posting idempotency + error semantics
4. META-02/03 v1-chart detection mechanism
5. Rollback safety pre-flight strictness

Claude consolidated to 4 (max for single-prompt UI) and explicitly pre-locked rollback safety (D5) as mechanical — locked without interactive discussion because ROADMAP SC3 + Pitfall #3 dictate the contract.

**User selected (multiSelect):** all 4 — redaction, helm-diff plugin, PR-comment, META detection.

**Rationale captured:** User did not redirect or reject the pre-lock on rollback safety.

---

## Round 2 — Four decisions in one salvo

| Area | Question | Options offered | User pick |
|---|---|---|---|
| Redaction | How should the redactor process Helm output? | YAML-parse-then-redact (Recommended) / Regex-pass / Both combined | YAML-parse-then-redact |
| helm-diff plugin | Build-time vs runtime install? | Build-time in Dockerfile (Recommended) / Runtime install / Hybrid | Build-time in Dockerfile |
| PR-comment | Idempotency + 4xx behaviour? | Single-per-PR + 4xx-tolerant (Recommended) / Append + 4xx-tolerant / Single-per-PR + 4xx-FATAL | Single-per-PR + 4xx-tolerant |
| META detection | How to detect v1-style charts? | Static grep values.yaml (Recommended) / helm-template-then-search / No detect | Static grep values.yaml |

All four recommendations accepted unchanged. No counter-proposals, no follow-up scoping discussion needed — the recommended options were each rooted in carry-forward decisions from Phase 4 (D3 tempdir-isolation, D5 subprocess-scoping, D8 cosign-pin pattern) which the user had already locked.

---

## Carry-forward applied (not re-asked)

- **Module boundary discipline (Phase 4 D5):** subprocess scoped to `helm/client.py` + `chart/oci.py`. New helm subcommands (diff, rollback, history) extend `HelmClient`, not new subprocess sites.
- **Tempdir isolation pattern (Phase 4 D3):** any tempdir state for helm-diff/rollback follows the same context-manager + 4-env-var-isolation pattern.
- **Cosign-pin Dockerfile pattern (Phase 4 D8):** helm-diff-fetch stage mirrors cosign-fetch verbatim — `ARG VERSION` + SHA256 verify + COPY --from.
- **structlog + bind_safe_context (Phase 2 CONTEXT):** logger boundary continues to mask structured kwargs; D1 redactor handles the orthogonal raw-text payload.
- **bitbucket-pipes-toolkit (global CLAUDE.md NIH rule):** prefer over a hand-rolled HTTP client.

---

## Deferred ideas captured (out of scope for Phase 5)

- Template-scan for `bitbucket.*` references in `templates/*.yaml` → v2.1 if false-negatives surface.
- `PrCommentError` dedicated exception class → introduce only when first requirement asks for fail-on-comment semantics.
- Append-comment mode → simpler UX wins for v2.0 launch.
- Bitbucket Data Center / Server support → v2.1+ (Cloud only at launch).
- helm-diff `--output json` → Phase 7 docs-site refinement.

---

## Out-of-phase items redirected

None. User did not propose scope creep.

---

## Claude's discretion items (not asked, locked unilaterally)

- **D5 Rollback safety pre-flight:** locked via mechanical reading of ROADMAP SC3 + Pitfall #3. `helm history --output json` parsed; target revision rejected if not `--wait`-tracked.
- **D6 Module boundary carry-forward:** locked by reference to Phase 4 D5 — no new subprocess sites.
- **bitbucket-pipes-toolkit preference:** locked by global CLAUDE.md NIH rule (researcher may downgrade to stdlib `urllib.request` if toolkit surface is over-heavy).
- **structlog wiring orthogonality:** D1 explicitly states `bind_safe_context` and `redact_helm_output` are independent layers — defense in depth, neither replaces the other.

If any of these warrants discussion, raise it before `gsd-plan-phase 5`.
