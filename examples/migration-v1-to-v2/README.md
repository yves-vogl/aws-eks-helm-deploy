# Migration v1 → v2 — Before/After Diff

This directory pairs a v1 reference pipeline (`before.yml`) with the v2 equivalent (`after.yml`). Use the `diff -u before.yml after.yml` view alongside [`docs/migration/v1-to-v2.md`](../../docs/migration/v1-to-v2.md) for the prose explanation of each change.

## Line-level changes

| before.yml | after.yml | Change | Reference |
|------------|-----------|--------|-----------|
| `pipe: docker://yvogl/aws-eks-helm-deploy:1.3.0` | `pipe: docker://ghcr.io/yves-vogl/aws-eks-helm-deploy:2.0.0` | Image registry: Docker Hub → GHCR. Pin to `:2.0.0` (or `:2` rolling). | MIG-01 / `docs/migration/v1-to-v2.md` "Distribution change" |
| implicit `NAMESPACE` (v1 default = `kube-public`) | `NAMESPACE: production` (explicit) | v1 had a BUG defaulting NAMESPACE to `kube-public`. v2 defaults to `default`. Always set it explicitly. | `docs/migration/v1-to-v2.md` "NAMESPACE correction" |
| implicit `INJECT_BITBUCKET_METADATA` (= injected) | `INJECT_BITBUCKET_METADATA: "true"` (explicit opt-in) | v1 unconditionally injected `bitbucket.*` values; v2 defaults to unset. Set `true` ONLY if your chart references `.Values.bitbucket.*`. | META-02 / `docs/migration/v1-to-v2.md` "INJECT_BITBUCKET_METADATA" |
| `SET: "image.tag=v1.2.3 replicaCount=3"` (if used) | `SET: "image.tag=v1.2.3,replicaCount=3"` | v1 accepted space-separated; v2 requires comma-separated (or JSON array). v2 emits a startup WARN if a v1-style value is detected. | MIG-02 / `docs/migration/v1-to-v2.md` "SET and VALUES env var syntax" |
| n/a | comment header block | Every example file opens with `# Example:`, `# Prerequisites:`, `# Expected outcome:`. | DOC-08 |

## Trying it locally

```bash
diff -u before.yml after.yml
```

## OIDC migration (optional)

Drop the static-key variables and add `OIDC_AUDIENCE` + `ROLE_ARN` per [`docs/guides/oidc-setup.md`](../../docs/guides/oidc-setup.md). The trust policy template scopes the role to `BITBUCKET_WORKSPACE_UUID` + `BITBUCKET_REPO_UUID` to prevent cross-repo misuse.

See [`examples/oidc-only/bitbucket-pipelines.yml`](../oidc-only/bitbucket-pipelines.yml) for the full OIDC pipeline.
