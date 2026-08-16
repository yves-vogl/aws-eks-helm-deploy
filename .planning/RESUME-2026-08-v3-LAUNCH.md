# Resume — v3.0.0 Launch (August 2026)

> **Pause-Marker:** Session vom 2026-06-24 hat v2.1.0 published und PR #77 (v3.0.0 release) rebased + ready-to-merge auf `release-blocker:august-2026` Label geparkt. Diese Datei ist der Pickup-Punkt.

## Was beim Resume zu tun ist

```
1. PR #77 mergen (squash). Subject:
   feat(helm)!: helm 3.18.6 → 4.2.2 + cosign 2.6.3 → 3.1.1 + v3.0.0 release (#77)

2. Tag pushen:
   git fetch origin main
   git tag -a v3.0.0 origin/main -m "v3.0.0"
   git push origin v3.0.0

3. release.yml feuert auf den Tag → multi-arch build + cosign keyless sign +
   SPDX/CycloneDX SBOM + SLSA build provenance auf GHCR. :3.0.0 + :3 + :latest
   aktualisieren auf den neuen Manifest-Digest.

4. Verify:
   cosign verify \
     --certificate-identity-regexp '^https://github.com/yves-vogl/aws-eks-helm-deploy/' \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com \
     ghcr.io/yves-vogl/aws-eks-helm-deploy:3.0.0

5. Issue #75 abarbeiten (Cleanup-PR): bootstrap-sha + release-as aus
   .release-please-config.json droppen.

6. Optional vor #1: rc.0 publishen wenn Issue #72 als yes entschieden.
```

## Aktueller Stand beim Pause-Beginn (2026-06-24)

| Item | Status |
|---|---|
| v2.0.0 | published 2026-06-23 |
| v2.1.0 | published 2026-06-24 (final v2.x line, frozen bis Helm v3 EOL 2026-11-11) |
| v3.0.0 | PR #77 held bis August, CI grün, rebased + refreshed, ready-to-merge |
| Security-Tab | clean (6 Scorecard heuristics dismissed, Dependabot #1 fix merged in #83) |
| Issues offen | #72 (rc.0 optional) + #75 (post-v3 config cleanup, blocked-by August) |

## Wichtige Daten

- **August 2026** — v3.0.0 Launch-Window (PR #77 merge + tag push)
- **2026-11-11** — Helm v3 EOL — `:2` Tag wird ab da nicht mehr maintained
- **2026-12-20** — `.trivyignore` 10 entries expire (180-day max) — Review trigger;
  Dependabot bumpt helm 4.x automatisch wenn ein neuerer Release Go ≥ 1.26.4
  mitbringt

## Was zwischen Pause und Resume monitorisch im Auge bleiben sollte

- **Dependabot alerts** auf `main` + `release-please--branches--main--components--aws-eks-helm-deploy` (PR #77 branch). Neue HIGH/CRITICAL CVEs gegen helm 4.2.2 oder cosign 3.1.1 würden ein Refresh-PR auf #77 erfordern bevor August-Merge.
- **Trivy DB updates** — `.trivyignore`-Suppressions sind alle für Go 1.26.3 stdlib ausgestellt. Wenn helm 4.x mit Go ≥ 1.26.4 released wird, werden die Suppressions stale (CI's stale-check würde dann meckern).
- **Helm v4 patch releases** — helm 4.3.x oder 4.2.3 wenn published. Dependabot's docker-group würde einen fix(deps)-PR aufmachen; den auf #77's branch cherry-picken oder PR #77 erneut rebasen.

## Cross-Refs

- **PR #77** (v3.0.0 release, held): https://github.com/yves-vogl/aws-eks-helm-deploy/pull/77
- **Issue #72** (optional rc.0): https://github.com/yves-vogl/aws-eks-helm-deploy/issues/72
- **Issue #75** (config cleanup, blocked-by August): https://github.com/yves-vogl/aws-eks-helm-deploy/issues/75
- **Discussion #79** (v3.0.0 launching August announcement): https://github.com/yves-vogl/aws-eks-helm-deploy/discussions/79
- **Discussion #82** (v2.1.0 release announcement): https://github.com/yves-vogl/aws-eks-helm-deploy/discussions/82
- **ADR-0010** (Helm v3 → v4 migration decision): docs/adr/0010-helm-v4-migration.md
- **v2 → v3 migration guide**: docs/migration/v2-to-v3.md
- **CONTRIBUTING.md** §"Release cadence and version-line freezes" — August Lock-Policy
