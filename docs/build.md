# Building the v2.0 image (local dev)

This document is the canonical reference for building `aws-eks-helm-deploy` locally.
Phase 6's GitHub Actions release pipeline mirrors this command via `docker/metadata-action@v5`
and `docker/build-push-action@v6`.

---

## Quick command

```bash
docker buildx build \
  --platform linux/amd64 \
  --annotation "manifest:org.opencontainers.image.source=https://github.com/yves-vogl/aws-eks-helm-deploy" \
  --annotation "manifest:org.opencontainers.image.revision=$(git rev-parse HEAD)" \
  --annotation "manifest:org.opencontainers.image.version=2.0.0-dev" \
  --annotation "manifest:org.opencontainers.image.licenses=Apache-2.0" \
  --annotation "manifest:org.opencontainers.image.title=AWS EKS Helm Deploy" \
  --annotation "manifest:org.opencontainers.image.description=Deploy Helm charts to AWS EKS from Bitbucket Pipelines" \
  --load \
  -t aws-eks-helm-deploy:dev \
  .
```

The `--load` flag writes the image into the local Docker daemon (`docker images` will show it).
Omit `--load` if you are pushing directly to a registry with `--push`.

---

## Why `--annotation` instead of `LABEL` (IMAGE-05)

`LABEL` instructions in a Dockerfile embed metadata in the **image config** (the JSON blob
describing the image's filesystem layers, environment variables, and entrypoint). This is the
wrong location for `org.opencontainers.image.*` metadata: the OCI Image Spec (v1.1, 2024)
requires those fields to be attached to the **image manifest** — the document that describes
the image's content-addressable layers and their media types.

`docker buildx build --annotation` places metadata directly on the OCI manifest (or index).
Tools that implement the OCI Distribution Spec, including `docker buildx imagetools inspect`,
`crane`, and ORAS, surface manifest-level annotations correctly. Labels embedded in the image
config are NOT visible in `imagetools inspect`'s `Annotations:` output and are not read by
supply-chain tools that parse OCI annotations for provenance or signing.

Using `--annotation` rather than `LABEL` is the correct approach for OCI compliance and is
required so that `docker buildx imagetools inspect aws-eks-helm-deploy:dev` shows all six
`org.opencontainers.image.*` fields.

---

## Why the `manifest:` prefix

The `--annotation` flag accepts an optional target specifier before the key: `manifest:`,
`index:`, or `manifest-descriptor:`. Without a prefix, buildx defaults to the manifest
descriptor — which is correct for single-arch images but ambiguous in multi-arch builds.

The `manifest:` prefix is explicit: **apply this annotation to the image manifest** (the
content-addressable manifest describing this image's layers), not to the OCI index (the
multi-arch "fat manifest" used in Phase 6) and not to an individual layer.

For Phase 1's single-arch `linux/amd64` build, `manifest:` and the bare annotation are
equivalent. Using `manifest:` explicitly is future-proof: when Phase 6 introduces the
multi-arch matrix (`linux/amd64` + `linux/arm64`), the `manifest:` prefix attaches
annotations to each per-arch manifest rather than only to the OCI index, which is what
supply-chain tools (Cosign, Rekor) expect.

---

## The six required OCI annotations

| Annotation key | Value | Rationale |
|---|---|---|
| `org.opencontainers.image.source` | `https://github.com/yves-vogl/aws-eks-helm-deploy` | Links the image to its source repository |
| `org.opencontainers.image.revision` | `$(git rev-parse HEAD)` | Exact commit SHA for supply-chain traceability |
| `org.opencontainers.image.version` | `2.0.0-dev` (dev) / semver tag on release | Image version per release-please tagging |
| `org.opencontainers.image.licenses` | `Apache-2.0` | SPDX license expression; matches `LICENSE.txt` |
| `org.opencontainers.image.title` | `AWS EKS Helm Deploy` | Human-readable image name |
| `org.opencontainers.image.description` | `Deploy Helm charts to AWS EKS from Bitbucket Pipelines` | Short purpose description |

---

## Verifying the annotations

After a successful `docker buildx build --annotation ... --load` run:

```bash
docker buildx imagetools inspect aws-eks-helm-deploy:dev
```

The `Annotations:` block in the output must contain all six `org.opencontainers.image.*`
fields. Example output (abbreviated):

```
Annotations:
  org.opencontainers.image.description:  Deploy Helm charts to AWS EKS from Bitbucket Pipelines
  org.opencontainers.image.licenses:     Apache-2.0
  org.opencontainers.image.revision:     <commit-sha>
  org.opencontainers.image.source:       https://github.com/yves-vogl/aws-eks-helm-deploy
  org.opencontainers.image.title:        AWS EKS Helm Deploy
  org.opencontainers.image.version:      2.0.0-dev
```

> **Note:** A plain `docker build` (without `buildx`) does not support `--annotation`. The
> quick command above requires Docker 27+ with the bundled `buildx` plugin.

---

## Simple build (no annotations, local dev only)

If you only need a runnable local image and do not need OCI annotation verification:

```bash
docker build -t aws-eks-helm-deploy:dev .
```

This is the command used by `tests/acceptance/conftest.py` for the acceptance test tier.
It does not attach OCI annotations but otherwise produces an identical runtime image.

---

## Multi-arch (Phase 6)

Phase 1 ships a single-arch `linux/amd64` image. The Dockerfile targets `linux-amd64` in the
`helm-fetch` stage's `curl` URL explicitly; running a plain `docker build` on an Apple Silicon
Mac produces an `arm64` image (via Docker Desktop's transparent QEMU emulation) — this is
acceptable for local testing but is NOT the production target.

Phase 6 introduces the multi-arch matrix build via native ARM runners (no QEMU emulation —
see `PITFALLS.md #5` for why QEMU is problematic for `uv` builds). When Phase 6 lands, the
annotation mechanics are reproduced via the following GH Actions snippet:

```yaml
- uses: docker/metadata-action@v5
  id: meta
  with:
    images: |
      ghcr.io/yves-vogl/aws-eks-helm-deploy
    tags: |
      type=semver,pattern={{version}}
      type=semver,pattern={{major}}.{{minor}}
      type=semver,pattern={{major}}

- uses: docker/build-push-action@v6
  with:
    platforms: linux/amd64,linux/arm64
    push: true
    annotations: ${{ steps.meta.outputs.annotations }}
    labels: ${{ steps.meta.outputs.labels }}
    tags: ${{ steps.meta.outputs.tags }}
```

`docker/metadata-action@v5` produces both `annotations:` (manifest-level) and `labels:`
(image-config level) from the same metadata source. `docker/build-push-action@v6` with
`annotations:` passes the `--annotation manifest:...` flags automatically.

Phase 6's release pipeline references this document as the source-of-truth for the six
required annotation keys rather than duplicating the list.

---

## uv version pin

uv is pinned to a specific minor for reproducibility; Dependabot bumps in Phase 6 will keep it current.

---

## Acceptance check

The automated image smoke tests live in `tests/acceptance/test_image_smoke.py` (Plan B).
They gate non-root execution, uid >= 10000, python/helm/helm-diff reachability, and clean
error handling on missing env vars.

The `--annotation` invocation and the resulting `imagetools inspect` output are **not** covered
by an automated test in Phase 1. This is the only Phase 1 acceptance gap and it is explicitly
deferred: Phase 6's release pipeline gates it definitively as part of the multi-arch manifest
attestation workflow. For local verification, run `docker buildx imagetools inspect
aws-eks-helm-deploy:dev` after the quick command above and confirm the six annotations appear
in the output.
