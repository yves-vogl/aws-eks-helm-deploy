---
status: accepted
date: 2026-06-21
decision-makers: yves-vogl
consulted: claude-code (planning)
informed: consumers configuring both static AWS keys and OIDC tokens
---

# When BOTH static keys AND OIDC token are present, static keys WIN (mirrors botocore default chain)

## Context and Problem Statement

Phase 4 originally specified that when consumers configure both `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` AND an OIDC token source (`AWS_WEB_IDENTITY_TOKEN_FILE` or a workflow-injected token), the OIDC path would win. Yves corrected this after consulting the underlying `botocore` default credential resolver: in `botocore`'s built-in chain, static environment-variable credentials precede web-identity / role-assumption sources. Diverging from `botocore`'s default produces "the AWS CLI behaves one way, this pipe behaves another way" surprise — exactly the failure mode we want to avoid for an EKS-deploy tool.

## Decision Drivers

* Principle of least surprise — consumers' mental model is `botocore`'s default chain (because they have been running `awscli` and `boto3`-based tools for years).
* Predictable troubleshooting — if static keys are leaked into the environment, the consumer can `unset AWS_ACCESS_KEY_ID` and the OIDC path takes over, matching the `awscli` behavior.
* One-time WARN log makes the precedence audible — consumers who accidentally configure both can see WHY their OIDC token was ignored.
* No silent OIDC-fallback when static keys fail authentication — that would mask credential bugs.

## Considered Options

* OIDC wins (the original Phase 4 spec, before the boto3 default was rechecked).
* Static keys win, matching `botocore`'s default credential resolver chain.
* Explicit env-var (`AUTH_STRATEGY=static|oidc`) — consumer must opt-in to a strategy.

## Decision Outcome

Chosen option: **"Static keys win, matching `botocore`'s default credential resolver chain"**, because matching the established AWS tooling behavior eliminates a class of "why is this different from the AWS CLI" support tickets, and the WARN log surfaces the precedence so the behavior is discoverable. The static-keys-win behavior is enforced in `src/aws_eks_helm_deploy/auth/resolver.py` and verified by an acceptance test that asserts the WARN log fires exactly once per process when both auth sources are present.

### Consequences

* Good, because consumer mental model matches `awscli` / `boto3` defaults.
* Good, because the WARN log `auth.precedence.static_keys_won_over_oidc` is a single, greppable signal — once per process, never spammed.
* Good, because misconfigurations are visible in the deploy log rather than hidden behind silent path selection.
* Bad, because consumers who *expected* OIDC to win (e.g., based on the Phase 4 pre-revision text) need to read the WARN log and either unset their static keys or accept the static-key path.
* Bad, because the WARN log is one-shot per process; a long-running pipeline only sees it once at startup.

## Pros and Cons of the Options

### OIDC wins (Phase 4 original)

* Good, because OIDC is the modern, keyless story — winning it by default would push consumers toward the secure path.
* Bad, because contradicts the `botocore` default chain — produces "why is this different from `aws sts get-caller-identity`?" surprise.
* Bad, because masks credential leaks — a leaked `AWS_ACCESS_KEY_ID` in the environment goes unused but also unflagged.

### Static keys win (`botocore` default)

* Good, because matches established AWS tooling behavior.
* Good, because explicit WARN log makes the precedence audible.
* Good, because credential leaks are surfaced rather than masked.
* Neutral, because consumers who want OIDC to win must unset static keys (mechanically simple).

### Explicit `AUTH_STRATEGY` env var

* Good, because no implicit precedence — consumer chooses.
* Bad, because adds a new env var to every pipeline config.
* Bad, because doubles the test matrix (each behavior × explicit-flag-set / explicit-flag-unset).
* Bad, because if the flag is unset, we are back to the original question.

## More Information

* Sources: [Phase 4 CONTEXT](https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/.planning/phases/04-oidc-chart-source-extensions/04-CONTEXT.md) D1 (the corrected precedence), REQUIREMENTS.md AUTH-04 (revised 2026-06-18 to match `botocore` default).
* Cross-references: ADR-0004 (boto3-only — the same `botocore` chain is in play for token generation).
* NIH check: we use `boto3` / `botocore`'s built-in credential resolver chain rather than implementing a custom one. The pipe adds one diagnostic WARN log on top of the upstream behavior; it does not replace it.
