# Architecture Decision Records

This project uses [MADR 4.0](https://adr.github.io/madr/) as the ADR template. Every architectural decision shipped in v2.0 has an ADR here. The template is committed verbatim at [`0000-template.md`](0000-template.md) — upstream blob SHA `08dac30ed895cf728fc7da95f9702ca4dd5ab900` from MADR tag `4.0.0`, CC0-1.0.

New ADRs are append-only: status transitions are documented in-file (`accepted` → `deprecated` → `superseded by ADR-NNNN`); we never delete or rewrite past ADRs.

## Archive

| # | Title | One-line summary |
|---|-------|------------------|
| [ADR-0001](0001-github-primary-forge.md) | GitHub primary forge | v2 development happens on GitHub; Bitbucket Pipe Marketplace listing stays for v1.x compatibility (Docker Hub frozen at v1.3.0). |
| [ADR-0002](0002-v2-clean-break.md) | v1.x → v2.x clean break | No runtime compatibility shim layer; v1.x stays frozen on Docker Hub at v1.3.0, v2.x is a Python rewrite on GHCR, migration is documented. |
| [ADR-0003](0003-cosign-keyless-over-gpg.md) | Cosign keyless over GPG | Image signing uses Cosign keyless (OIDC → Fulcio → Rekor) — no long-lived signing keys, transparency-log proof, composes with SLSA build provenance. |
| [ADR-0004](0004-boto3-only-over-awscli.md) | boto3-only EKS auth | EKS tokens are generated in ~40 lines of Python against `boto3` STS presign; bundled `awscli` is dropped (~120 MB image weight reclaimed). |
| [ADR-0005](0005-release-please-over-semversioner.md) | release-please over semversioner | release-please-action v4 (`release-type: python`) replaces `.changes/`-fragment ceremony; release-PR model + Conventional Commits enforce semver mechanically. |
| [ADR-0006](0006-oidc-default-precedence.md) | OIDC default precedence (static wins) | When both static AWS keys and an OIDC token are present, static keys win — matches the `botocore` default credential resolver chain; a one-shot WARN log surfaces the precedence. |
| [ADR-0007](0007-multi-arch-native-runners.md) | Multi-arch native runners (no QEMU) | `linux/amd64` builds on `ubuntu-24.04`, `linux/arm64` builds on `ubuntu-24.04-arm`; manifest fan-in via `docker buildx imagetools create`. No QEMU emulation — eliminates silent broken-arm64 builds. |
| [ADR-0008](0008-mkdocs-material-now-zensical-later.md) | mkdocs-material now, Zensical later | mkdocs-material 9.7.6 ships v2.0 docs; Zensical migration tracked as DOC-NEXT-01 for v2.1+ (mkdocs-material maintenance-mode critical fixes through Nov 2026). |
| [ADR-0009](0009-src-layout-no-compat-shims.md) | src/-layout, no v1 compat shims | v2 Python package uses `src/aws_eks_helm_deploy/`; no `aws_eks_helm_deploy.v1` shim namespace (v1 was a shell pipe, not a Python package). |
| [ADR-0010](0010-helm-v4-migration.md) | Helm v3 → v4 migration before EOL | Bundled Helm bumped 3.x → 4.2.2 ahead of the 2026-11-11 v3 EOL; pipe bumps to v3.0.0 to signal the kstatus-wait operational change; `:2` floating tag frozen at the last helm-3 build through EOL. |

## How to add a new ADR

1. Copy [`0000-template.md`](0000-template.md) to `NNNN-{title-slug}.md` (4-digit zero-padded next index).
2. Fill in the MADR sections. Keep the front-matter (`status`, `date`, `decision-makers`).
3. Update this index with the new row.
4. Open a PR. Substantial architectural changes should ship the ADR alongside (or before) the implementation PR — see [CONTRIBUTING.md](https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/CONTRIBUTING.md).

## Related references

- [MADR upstream](https://github.com/adr/madr) — the template source.
- [REQUIREMENTS.md](https://github.com/yves-vogl/aws-eks-helm-deploy/blob/main/.planning/REQUIREMENTS.md) — every REQ ID referenced from ADRs lives here.
- [Phase planning archive](https://github.com/yves-vogl/aws-eks-helm-deploy/tree/main/.planning/phases) — every ADR cites its source phase's CONTEXT.md for traceability.
