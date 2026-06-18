# Phase 4 RESEARCH — OIDC & Chart Source Extensions

**Researched:** 2026-06-18
**Phase:** 4 — OIDC & Chart Source Extensions (closes #3, #7)
**REQs covered:** AUTH-03, AUTH-04 (revised per CONTEXT D1), AUTH-05, AUTH-06, CHART-02, CHART-03, CHART-04
**Stack pin (do NOT touch in Phase 4):** Python 3.13 · `boto3 ~= 1.43` (locked to 1.43.31) · helm 3.18.6 · helm-diff 3.10.0 · uv 0.11.21 · linux/amd64 only.
**Scope statement:** This RESEARCH.md answers the six open questions raised in `04-CONTEXT.md` and provides implementation cookbooks for the planner. The four locked decisions D1–D8 are non-negotiable; this document answers HOW to implement them safely, not WHETHER.

---

## §1 — botocore default credential resolver chain (boto3 1.43.31)

**Source:** [botocore `credentials.py` at the pinned tag `1.43.31`](https://github.com/boto/botocore/blob/1.43.31/botocore/credentials.py), inspected directly via `create_credential_resolver` — `[VERIFIED: botocore@1.43.31]`.

The resolver is assembled in three blocks: `pre_profile + profile_providers + post_profile`. The full ordered list for the default profile (no `AWS_PROFILE` override):

| Position | Provider class | Triggered by |
|---|---|---|
| 1 | `EnvProvider` | `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` (± `AWS_SESSION_TOKEN`) |
| 2 | `AssumeRoleProvider` | Profile-level `role_arn` in `~/.aws/config` |
| 3 | **`AssumeRoleWithWebIdentityProvider`** | `AWS_WEB_IDENTITY_TOKEN_FILE` + `AWS_ROLE_ARN` |
| 4 | `SSOProvider` | Profile-level SSO config |
| 5 | `SharedCredentialProvider` | `~/.aws/credentials` |
| 6 | `LoginProvider` | Profile-level login config |
| 7 | `ProcessProvider` | Profile-level `credential_process` |
| 8 | `ConfigProvider` | Profile-level static keys |
| 9 | `OriginalEC2Provider` | Legacy EC2 metadata env vars |
| 10 | `BotoProvider` | Legacy `~/.boto` |
| 11 | `ContainerProvider` | `AWS_CONTAINER_CREDENTIALS_RELATIVE_URI` / `…_FULL_URI` |
| 12 | `InstanceMetadataProvider` | IMDS reachable |

**Critical consequence for D1:** position 1 (env-var static keys) is **strictly above** position 3 (web-identity). When both `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` AND `BITBUCKET_STEP_OIDC_TOKEN` are present, the canonical AWS chain returns static keys. The pipe MUST mirror this — `[VERIFIED: botocore@1.43.31 source]`.

**Version annotation:** the precedence (env → assume-role → web-identity → SSO → shared-credentials → …) has been stable since boto3 1.20+ (~Q4 2021 when SSO joined). No change is anticipated in the `boto3 ~= 1.43` range. **D1 does not need a version annotation beyond "matches boto3 1.43+ defaults"** — `[CITED: github.com/boto/botocore/blob/1.43.31/botocore/credentials.py]`.

**WARN-log signal (D1 mitigation):** when `select_strategy()` returns `StaticKeysStrategy` AND `os.environ.get("BITBUCKET_STEP_OIDC_TOKEN")` is non-empty, emit:

```python
logger.warning(
    "auth.precedence.static_keys_won_over_oidc",
    reason="AWS_ACCESS_KEY_ID is set and takes precedence per botocore chain order",
    hint="Unset AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY in pipe.yml to use OIDC",
)
```

The check is one-time at strategy-selection time (not on every credential refresh — `select_strategy()` is called exactly once per pipe run per Phase 2's Phase 3 contract).

---

## §2 — Bitbucket OIDC issuer URL & condition-key format (current canonical form)

**Source:** [Atlassian Support — Deploy on AWS using Bitbucket Pipelines OpenID Connect](https://support.atlassian.com/bitbucket-cloud/docs/deploy-on-aws-using-bitbucket-pipelines-openid-connect/) — `[CITED]`.

### IAM Principal ARN (Federated)

```
arn:aws:iam::<ACCOUNT_ID>:oidc-provider/api.bitbucket.org/2.0/workspaces/<WORKSPACE>/pipelines-config/identity/oidc
```

The host+path forming the OIDC issuer URL is:

```
api.bitbucket.org/2.0/workspaces/<WORKSPACE>/pipelines-config/identity/oidc
```

This is the **current canonical form** — the older `api.bitbucket.org/2.0/workspaces/<WORKSPACE>/pipelines-config/identity` (without trailing `/oidc`) was used in 2021 docs and is no longer surfaced. Stick with the `/oidc` suffix `[CITED: Atlassian support docs, retrieved 2026-06-18]`.

### Condition-key format (`aud` + `sub`)

AWS condition keys for an OIDC IdP are constructed as `<issuer-url-without-scheme>:<claim-name>`. For Bitbucket:

```
api.bitbucket.org/2.0/workspaces/<WORKSPACE>/pipelines-config/identity/oidc:aud
api.bitbucket.org/2.0/workspaces/<WORKSPACE>/pipelines-config/identity/oidc:sub
```

### `aud` claim value (what consumers put in OIDC_AUDIENCE)

The `aud` value Bitbucket signs into the JWT is:

```
ari:cloud:bitbucket::workspace/<WORKSPACE_UUID>
```

This is the value the consumer copies from `Repository settings → Pipelines → OpenID Connect → Audience`. The IAM trust policy `StringEquals` condition for `aud` must match this value verbatim `[CITED]`.

### `sub` claim format

Bitbucket emits `sub` as:

```
{<WORKSPACE_UUID>}:{<REPO_UUID>}:*
```

— with literal curly braces around the UUIDs, colon separators, and `*` as the step-UUID wildcard. IAM trust policies typically use `StringLike` (not `StringEquals`) because of the `*` wildcard. `[CITED]`

### Final D4 trust-policy template (researcher-ratified)

```jsonc
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/api.bitbucket.org/2.0/workspaces/<WORKSPACE>/pipelines-config/identity/oidc"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "api.bitbucket.org/2.0/workspaces/<WORKSPACE>/pipelines-config/identity/oidc:aud": "<OIDC_AUDIENCE>"
      },
      "StringLike": {
        "api.bitbucket.org/2.0/workspaces/<WORKSPACE>/pipelines-config/identity/oidc:sub": "{<BITBUCKET_WORKSPACE_UUID>}:{<BITBUCKET_REPO_UUID>}:*"
      }
    }
  }]
}
```

**Diff vs CONTEXT D4 draft:** the draft put the `sub` constraint under `StringEquals` — that is wrong because of the literal `*` in the value. Change to `StringLike`. This is the only deviation; placeholder names (`<ACCOUNT_ID>`, `<WORKSPACE>`, `<OIDC_AUDIENCE>`, `<BITBUCKET_WORKSPACE_UUID>`, `<BITBUCKET_REPO_UUID>`) are preserved verbatim per D4's Plan-Check obligation.

**Unit-test additions:** the existing 4-assertion list in D4 stands, plus a fifth: assert the `sub` constraint lives under `StringLike` (not `StringEquals`).

---

## §3 — Cosign 2.x keyless invocation, pinning, env vars

### Version pin

`cosign 2.6.3` (released 2026-04-06) is the current stable head of the 2.x line `[CITED: github.com/sigstore/cosign/releases]`. Use this in the Dockerfile builder stage; Dependabot's `docker` ecosystem will keep it current under the same `fix(deps): bump cosign …` convention used for helm.

```dockerfile
ARG COSIGN_VERSION=2.6.3
```

### `COSIGN_EXPERIMENTAL=1` — NOT required

In cosign 1.x, keyless mode required `COSIGN_EXPERIMENTAL=1`. **Cosign 2.0 made keyless the default — the env var is silently ignored (and was deprecated)** `[CITED: docs.sigstore.dev/cosign/verifying/verify/ + sigstore/cosign README]`. The pipe's Dockerfile MUST NOT set `COSIGN_EXPERIMENTAL=1` — leaving it unset is the correct, forward-compatible choice. Do not even export it as a documented pipe variable.

### Canonical CLI form

**Unconstrained (signature-validity only):**

```bash
cosign verify <oci-ref>
```

**Constrained (signer identity + issuer):** the canonical fully-qualified form, per official docs:

```bash
cosign verify \
  --certificate-identity-regexp '<IDENTITY_RE>' \
  --certificate-oidc-issuer '<ISSUER_URL>' \
  <oci-ref>
```

All four constraint flags exist and are documented `[CITED: github.com/sigstore/cosign/blob/main/doc/cosign_verify.md]`:

- `--certificate-identity` (exact match)
- `--certificate-identity-regexp`
- `--certificate-oidc-issuer` (exact match)
- `--certificate-oidc-issuer-regexp`

### Documented env-var equivalents

Cosign 2.0+ documents env-var equivalents for the two most common flags `[CITED: Sigstore Cosign 2.0 release notes + chainguard.dev/cosign docs]`:

| Env var | CLI flag | Notes |
|---|---|---|
| `COSIGN_CERTIFICATE_IDENTITY` | `--certificate-identity` | Exact-match identity |
| `COSIGN_CERTIFICATE_OIDC_ISSUER` | `--certificate-oidc-issuer` | Exact-match issuer URL |

**`COSIGN_CERTIFICATE_IDENTITY_REGEXP` and `COSIGN_CERTIFICATE_OIDC_ISSUER_REGEXP` are NOT documented as official env vars** as of cosign 2.6.3 — they are CLI flags only. `[ASSUMED]` that cosign may accept them internally, but do not rely on it.

### Recommendation for the pipe's Phase 4 env-var surface

**SHIP NOW** — add two pipe-level env vars (mirroring cosign's official ones for consumer familiarity):

| Pipe env var | Forwarded as cosign flag | Behavior |
|---|---|---|
| `CHART_VERIFY_CERTIFICATE_IDENTITY` | `--certificate-identity <value>` | Exact identity |
| `CHART_VERIFY_CERTIFICATE_OIDC_ISSUER` | `--certificate-oidc-issuer <value>` | Exact issuer |

The pipe converts its own typed setting → CLI flag inside `chart/oci.py` (rather than passing `COSIGN_CERTIFICATE_IDENTITY` through `env`). Reason: the pipe builds argv anyway via `subprocess.run`, so flags are clearer than env-var inheritance, and behavior is identical regardless of the cosign version.

**Deferred to v2.1** — regexp variants. Naming reservation (do NOT use yet):
- `CHART_VERIFY_CERTIFICATE_IDENTITY_REGEXP`
- `CHART_VERIFY_CERTIFICATE_OIDC_ISSUER_REGEXP`

Justification: cosign's own env-var support for regexp variants is undocumented; exposing them now risks shipping a feature whose upstream contract is unstable. Phase 4 lands the two exact-match vars and a WARN-log when CHART_VERIFY=true is set without either constraint.

### WARN-log when CHART_VERIFY runs unconstrained

When `CHART_VERIFY=true` but neither `CHART_VERIFY_CERTIFICATE_IDENTITY` nor `CHART_VERIFY_CERTIFICATE_OIDC_ISSUER` is set:

```python
logger.warning(
    "chart.verify.unconstrained_identity",
    reason="cosign verify will succeed for ANY valid Sigstore signature",
    hint="Set CHART_VERIFY_CERTIFICATE_IDENTITY and CHART_VERIFY_CERTIFICATE_OIDC_ISSUER "
         "to pin the trusted signer",
)
```

One-time at chart-resolution time (not per-call — there is only one verify per pipe run).

---

## §4 — `helm pull oci://` unpack behavior and directory name

**Source:** [helm v3.18.6 `cmd/helm/pull.go`](https://github.com/helm/helm/blob/v3.18.6/cmd/helm/pull.go) + [`pkg/chartutil/expand.go`](https://github.com/helm/helm/blob/v3.18.6/pkg/chartutil/expand.go) — `[VERIFIED: helm@v3.18.6 source]`.

### Default: `.tgz` tarball, NOT untarred

`helm pull oci://...` defaults to saving the chart as `<destination>/<chart>-<version>.tgz`. **The `--untar` flag is required** to get an unpacked directory.

### Unpacked directory name

When `--untar` is specified, the chart is extracted via `chartutil.ExpandFile(dest, tgzpath)`. The extracted subdirectory is named after the **chart's `name:` field inside its own `Chart.yaml`** — NOT the tgz filename, NOT the OCI ref's last path component.

```go
// chartutil/expand.go
chartdir, err := securejoin.SecureJoin(dir, chartName)  // chartName from Chart.yaml
```

**Implication for `OciChart.resolve()`:** after `helm pull oci://… --untar --untar-dir <tmpdir>/unpacked --destination <tmpdir>`:

- The tgz lands at `<tmpdir>/<chart>-<version>.tgz` (still present after untar — helm does not delete it).
- The unpacked chart lands at `<tmpdir>/unpacked/<chart-name>/` where `<chart-name>` matches `name:` inside the extracted `Chart.yaml`.

**Discovery strategy** (resolver-side, after `helm pull --untar`):

```python
unpack_root = tmpdir / "unpacked"
candidates = [p for p in unpack_root.iterdir() if p.is_dir()]
if len(candidates) != 1:
    raise ChartResolutionError(
        f"expected exactly one chart dir in {unpack_root}, found {len(candidates)}"
    )
chart_dir = candidates[0]
```

This is **the same single-subdir-discovery pattern** that `RepoChart` uses (helm repo pull behaves identically). Cleaner than reading `Chart.yaml` first then constructing the expected path — `Chart.yaml`'s `name:` might disagree with the tgz filename, and helm respects the `Chart.yaml` value.

### Recommended argv for `helm pull oci://`

```python
[
    "helm", "pull", f"oci://{reference}",
    "--version", version,                 # only if set
    "--destination", str(tmpdir),
    "--untar",
    "--untar-dir", str(tmpdir / "unpacked"),
]
```

### Recommended argv for `helm pull <repo>/<chart>` (RepoChart)

Same idea, with the repo+chart shorthand:

```python
[
    "helm", "pull", f"{repo_name}/{chart_name}",
    "--version", version,                 # only if set
    "--destination", str(tmpdir),
    "--untar",
    "--untar-dir", str(tmpdir / "unpacked"),
]
```

---

## §5 — `helm registry login` + `HELM_REGISTRY_CONFIG` isolation

**Source:** [helm `helm` command docs (env var reference)](https://helm.sh/docs/helm/helm/) + [helm v3.18.6 `pkg/registry/client.go`](https://github.com/helm/helm/blob/v3.18.6/pkg/registry/client.go) — `[CITED] + [VERIFIED]`.

### What `HELM_REGISTRY_CONFIG` does

Helm documents:

> **`HELM_REGISTRY_CONFIG`** — set the path to the registry config file. Default: `~/.config/helm/registry/config.json`.

When set, this fully **overrides** the default path. Helm does **NOT** read both locations simultaneously — the registry config is a single-file pointer (not a layered search). `[CITED: helm.sh/docs/helm/helm/]`

### Isolation contract for Phase 4

The CONTEXT D6 design — point `HELM_REGISTRY_CONFIG=<tmpdir>/registry-config.json` for the lifetime of the `OciChart.resolve()` context — **works as designed**:

- `helm registry login` writes credentials to the tempfile inside the per-chart tempdir.
- `helm pull oci://...` reads from the same tempfile (since the env var is inherited by the subprocess).
- No credentials touch `~/.config/helm/registry/config.json` or any other persistent location.
- `shutil.rmtree(tmpdir)` in the `finally` block removes the credentials atomically with the chart workspace.

### Fallback caveat (small risk)

Helm 3 falls back to **Docker's** credentials store if the helm-specific config is empty (`fallback to Docker` is referenced in the helm v3.18.6 registry-client source `[VERIFIED]`). For the pipe this is a non-issue because:

1. The container runs as the `pipe` user with no `~/.docker/config.json` populated at runtime (the Dockerfile does not write one).
2. The `helm registry login` call always **writes** the credential to the helm-config path before `helm pull` runs — the Docker fallback path is only consulted when the helm path is unreadable / empty.

**Belt-and-braces:** the planner should also set `DOCKER_CONFIG=<tmpdir>/docker-config` for the subprocess env. This is **defense in depth** against a future helm change that consults Docker first — if there is no docker config to find, fallback can't leak. Cost: ~5 lines of code. Recommend including.

### Recommended subprocess env additions for `OciChart`

```python
env = os.environ.copy()
env["HELM_REGISTRY_CONFIG"] = str(tmpdir / "registry-config.json")
env["DOCKER_CONFIG"] = str(tmpdir / "docker-config")  # belt-and-braces
# Optional: also isolate repo + cache to keep tempdir self-contained
env["HELM_REPOSITORY_CONFIG"] = str(tmpdir / "repositories.yaml")
env["HELM_REPOSITORY_CACHE"] = str(tmpdir / "cache")
```

These four overrides keep the chart-resolution lifecycle **fully tempdir-scoped** — nothing leaks into the runtime image's home directory, even on crash.

### `helm registry login` argv (D5 helper)

```python
[
    "helm", "registry", "login",
    registry_host,                # extracted from oci:// reference
    "--username", username,
    "--password-stdin",            # password via stdin, not argv (T-04-XX)
]
```

Pass the password via `stdin=` to `subprocess.run` — not via `--password <value>` which would surface in `ps ax`. This is a NEW load-bearing security pattern for Phase 4 (Phase 3's kubeconfig token-via-file pattern is the closest analog).

---

## §6 — Cosign binary distribution + SHA256 checksum URLs

**Source:** [github.com/sigstore/cosign/releases/tag/v2.6.3](https://github.com/sigstore/cosign/releases/tag/v2.6.3) via `gh release view`. Asset listing confirmed `[VERIFIED: gh release API]`.

### Linux/amd64 binary URL pattern

```
https://github.com/sigstore/cosign/releases/download/v${COSIGN_VERSION}/cosign-linux-amd64
```

### SHA256 checksum file URL pattern

```
https://github.com/sigstore/cosign/releases/download/v${COSIGN_VERSION}/cosign_checksums.txt
```

This file is a multi-line `<sha256>  <filename>` listing for all assets (mirrors helm's `helm-v3.18.6-linux-amd64.tar.gz.sha256sum` pattern; only the filename differs).

### Dockerfile stage — drop-in addition

Add a new stage between `helm-fetch` and `runtime`, mirroring `helm-fetch`:

```dockerfile
ARG COSIGN_VERSION=2.6.3

# ── Stage 2.5: Cosign binary fetch ────────────────────────────────────────────
FROM debian:bookworm-slim@${DEBIAN_BASE_DIGEST} AS cosign-fetch

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG COSIGN_VERSION

# linux/amd64 only — multi-arch lands Phase 6 alongside helm-fetch
RUN curl -fsSL "https://github.com/sigstore/cosign/releases/download/v${COSIGN_VERSION}/cosign-linux-amd64" \
        -o "/tmp/cosign-linux-amd64" \
    && curl -fsSL "https://github.com/sigstore/cosign/releases/download/v${COSIGN_VERSION}/cosign_checksums.txt" \
        -o "/tmp/cosign_checksums.txt" \
    && cd /tmp \
    && grep "  cosign-linux-amd64$" cosign_checksums.txt | sha256sum -c \
    && mv cosign-linux-amd64 /cosign \
    && chmod +x /cosign \
    && rm -f cosign-linux-amd64 cosign_checksums.txt
```

And in the `runtime` stage, add a single `COPY`:

```dockerfile
COPY --from=cosign-fetch /cosign /usr/local/bin/cosign
```

**Why `grep …  cosign-linux-amd64$ | sha256sum -c`** instead of plain `sha256sum -c cosign_checksums.txt`: the checksum file contains entries for ~115 assets (sboms, sigs, other arches). Passing the whole file fails because most listed files are absent. Grepping the single line we care about is the documented pattern from Sigstore's own install docs and is the minimum-surface choice.

**Dependabot:** the `docker` ecosystem in `.github/dependabot.yml` already keeps `ARG HELM_VERSION` current. Adding `ARG COSIGN_VERSION` will be tracked the same way — no `dependabot.yml` change is required. The Phase 6 (or earlier) `fix(deps): bump cosign 2.6.3 → 2.6.4` flow is automatic.

---

## §7 — Implementation cookbook (concrete patterns)

### §7.1 — `OidcWebIdentityStrategy` (auth/oidc.py)

```python
"""OIDC web-identity strategy — AssumeRoleWithWebIdentity backed by Bitbucket Pipelines OIDC token."""
from __future__ import annotations

import boto3
import boto3.session
import botocore.config
import botocore.exceptions
from mypy_boto3_sts.type_defs import CredentialsTypeDef

from aws_eks_helm_deploy.auth.base import AwsCredentials
from aws_eks_helm_deploy.errors import AuthenticationError

__all__: list[str] = ["OidcWebIdentityStrategy"]


class OidcWebIdentityStrategy:
    """Exchange a Bitbucket Pipelines OIDC JWT for STS credentials.

    Satisfies the AuthStrategy Protocol structurally (no inheritance).

    Note: audience is NOT passed to AssumeRoleWithWebIdentity — STS validates the
    `aud` claim inside the JWT against the IAM trust-policy condition key. The
    audience constructor argument is recorded for traceability/debug logging
    and for documentation alignment with the IAM trust-policy template (D4).
    """

    def __init__(
        self,
        oidc_token: str,
        role_arn: str,
        audience: str,
        session_name: str,
        region: str,
    ) -> None:
        self._oidc_token = oidc_token
        self._role_arn = role_arn
        self._audience = audience  # informational only
        self._session_name = session_name
        self._region = region

    def get_credentials(self) -> AwsCredentials:
        # Unauthenticated session — STS AssumeRoleWithWebIdentity is the credential source.
        session = boto3.session.Session(region_name=self._region)
        sts = session.client(
            "sts",
            endpoint_url=f"https://sts.{self._region}.amazonaws.com",
            config=botocore.config.Config(
                retries={"max_attempts": 3, "mode": "standard"},
                signature_version=botocore.UNSIGNED,  # AssumeRoleWithWebIdentity is unauthenticated
            ),
        )
        try:
            response = sts.assume_role_with_web_identity(
                RoleArn=self._role_arn,
                RoleSessionName=self._session_name,
                WebIdentityToken=self._oidc_token,
            )
        except botocore.exceptions.ClientError as exc:
            code = exc.response["Error"]["Code"]
            message = exc.response["Error"]["Message"]
            raise AuthenticationError(
                f"STS AssumeRoleWithWebIdentity failed [{code}]: {message}"
            ) from exc

        creds: CredentialsTypeDef = response["Credentials"]
        return AwsCredentials(
            access_key_id=creds["AccessKeyId"],
            secret_access_key=creds["SecretAccessKey"],
            session_token=creds["SessionToken"],
            expiration=creds["Expiration"],
        )
```

**Note on `botocore.UNSIGNED`:** the import is `from botocore import UNSIGNED` — verify the planner threads this correctly. Without it, boto3 will raise `NoCredentialsError` before sending the STS request, because the default Session tries to sign the call. `AssumeRoleWithWebIdentity` is an unauthenticated STS API; signing is unnecessary and counterproductive.

### §7.2 — `select_strategy()` integration (auth/__init__.py)

Drop into the existing function at the `# Phase 4: insert OIDC check here` marker, keeping the Phase 2/3 logic intact. The order is **after env-var static keys** (per D1):

```python
def select_strategy(settings: Settings) -> AuthStrategy:
    # 1. Env-var static keys win (mirrors botocore EnvProvider precedence — see CONTEXT D1).
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        # Defensive WARN if an OIDC token is also present (consumer probably set both
        # by accident and expected OIDC to win — explain the AWS-canonical precedence).
        if os.environ.get("BITBUCKET_STEP_OIDC_TOKEN"):
            logger.warning(
                "auth.precedence.static_keys_won_over_oidc",
                hint="AWS_ACCESS_KEY_ID is set and takes precedence per botocore chain order; "
                     "unset it to use OIDC",
            )
        base: AuthStrategy = StaticKeysStrategy(
            settings.aws_access_key_id,
            settings.aws_secret_access_key,
            settings.aws_session_token,
        )
        if settings.role_arn:
            session_name = _derive_session_name(settings)
            return AssumeRoleStrategy(base, settings.role_arn, session_name, settings.aws_region)
        return base

    # 2. OIDC web-identity (after env vars per botocore chain).
    oidc_token = os.environ.get("BITBUCKET_STEP_OIDC_TOKEN")
    if oidc_token:
        if not settings.role_arn:
            raise ConfigurationError(
                "BITBUCKET_STEP_OIDC_TOKEN is set but ROLE_ARN is missing — "
                "OIDC requires ROLE_ARN to assume"
            )
        if not settings.oidc_audience:
            raise ConfigurationError(
                "BITBUCKET_STEP_OIDC_TOKEN is set but OIDC_AUDIENCE is missing — "
                "set OIDC_AUDIENCE to the Bitbucket workspace ARI"
            )
        session_name = _derive_session_name(settings)
        return OidcWebIdentityStrategy(
            oidc_token=oidc_token,
            role_arn=settings.role_arn,
            audience=settings.oidc_audience,
            session_name=session_name,
            region=settings.aws_region,
        )

    # 3. Misconfiguration — ROLE_ARN without base credentials (AUTH-06).
    if settings.role_arn:
        raise ConfigurationError(
            "ROLE_ARN requires AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY, "
            "or BITBUCKET_STEP_OIDC_TOKEN + OIDC_AUDIENCE"
        )

    # 4. No credentials at all.
    raise ConfigurationError(
        "No valid credential configuration: set AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY, "
        "or BITBUCKET_STEP_OIDC_TOKEN + OIDC_AUDIENCE + ROLE_ARN"
    )
```

**`os.environ.get("BITBUCKET_STEP_OIDC_TOKEN")` outside settings.py:** documented deviation in the same shape as Phase 2's `BITBUCKET_PIPELINE_UUID` / `BITBUCKET_BUILD_NUMBER` reads inside `_derive_session_name` — a Bitbucket-platform-supplied variable consumed by the composition root for routing only. The pipe DOES NOT put `BITBUCKET_STEP_OIDC_TOKEN` into `Settings` because (a) it would tempt callers to log the whole settings object, leaking the token; (b) it bypasses pydantic's masking; (c) it carries no useful default beyond "present or absent".

### §7.3 — `ChartSource` Protocol (chart/base.py)

```python
"""ChartSource Protocol + ResolvedChart value object — uniform interface for all chart sources."""
from __future__ import annotations

import contextlib
import dataclasses
import pathlib
from collections.abc import Iterator
from typing import Protocol, runtime_checkable

__all__: list[str] = ["ChartSource", "ResolvedChart"]


@dataclasses.dataclass(frozen=True)
class ResolvedChart:
    """Immutable resolved chart descriptor — same shape as Phase 3."""
    name: str
    version: str
    source_path: pathlib.Path


@runtime_checkable
class ChartSource(Protocol):
    """Protocol satisfied by LocalChart, RepoChart, OciChart.

    .resolve() yields a ResolvedChart whose source_path is valid only inside
    the with-block. Implementations clean up tempdirs on context exit.
    """

    def resolve(self) -> contextlib.AbstractContextManager[ResolvedChart]:
        ...
```

### §7.4 — `OciChart.resolve()` — full cookbook (D5 + D6)

```python
"""OCI chart source — helm pull oci://... + optional cosign verify."""
from __future__ import annotations

import contextlib
import os
import pathlib
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager

from aws_eks_helm_deploy.chart.base import ResolvedChart
from aws_eks_helm_deploy.errors import ChartResolutionError
from aws_eks_helm_deploy.helm.client import HelmClient  # registry_login + pull_oci methods
from aws_eks_helm_deploy.logging import get_logger

logger = get_logger(__name__)


class OciChart:
    def __init__(
        self,
        reference: str,
        version: str | None = None,
        registry_username: str | None = None,
        registry_password: str | None = None,
        verify: bool = False,
        verify_identity: str | None = None,         # CHART_VERIFY_CERTIFICATE_IDENTITY
        verify_oidc_issuer: str | None = None,      # CHART_VERIFY_CERTIFICATE_OIDC_ISSUER
    ) -> None:
        self._reference = reference
        self._version = version
        self._registry_username = registry_username
        self._registry_password = registry_password
        self._verify = verify
        self._verify_identity = verify_identity
        self._verify_oidc_issuer = verify_oidc_issuer

    @contextmanager
    def resolve(self) -> Iterator[ResolvedChart]:
        tmpdir = pathlib.Path(tempfile.mkdtemp(prefix="aws-eks-helm-deploy-chart-"))
        try:
            unpack_dir = tmpdir / "unpacked"
            unpack_dir.mkdir()

            # Isolated subprocess env (registry creds + repo cache scoped to tmpdir)
            env = os.environ.copy()
            env["HELM_REGISTRY_CONFIG"] = str(tmpdir / "registry-config.json")
            env["DOCKER_CONFIG"] = str(tmpdir / "docker-config")
            env["HELM_REPOSITORY_CONFIG"] = str(tmpdir / "repositories.yaml")
            env["HELM_REPOSITORY_CACHE"] = str(tmpdir / "cache")

            # 1. Optional registry login (writes to HELM_REGISTRY_CONFIG only)
            if self._registry_username and self._registry_password:
                registry_host = self._reference.split("/", 1)[0]
                self._run_helm_registry_login(env, registry_host)

            # 2. Optional Cosign verify — BEFORE pull, against the OCI ref.
            #    Verify against ref, NOT the pulled tarball — cosign verifies the
            #    signed digest in the registry, not the local file.
            if self._verify:
                self._run_cosign_verify()

            # 3. helm pull oci://... --untar --untar-dir <unpack_dir>
            self._run_helm_pull(env, tmpdir, unpack_dir)

            # 4. Discover the single subdirectory (chart name from Chart.yaml)
            candidates = [p for p in unpack_dir.iterdir() if p.is_dir()]
            if len(candidates) != 1:
                raise ChartResolutionError(
                    f"expected exactly one unpacked chart dir in {unpack_dir}, "
                    f"found {len(candidates)}"
                )
            chart_dir = candidates[0]

            # 5. Parse Chart.yaml for name + version (reuse helper from chart/local.py).
            from aws_eks_helm_deploy.chart.local import _parse_chart_yaml  # noqa: PLC0415
            data = _parse_chart_yaml(chart_dir)
            yield ResolvedChart(
                name=str(data.get("name", chart_dir.name)),
                version=str(data.get("version", "")),
                source_path=chart_dir,
            )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _run_helm_registry_login(self, env: dict[str, str], registry_host: str) -> None:
        """helm registry login <host> --username <u> --password-stdin"""
        argv = [
            "helm", "registry", "login", registry_host,
            "--username", self._registry_username,
            "--password-stdin",
        ]
        try:
            subprocess.run(  # noqa: S603
                argv,
                input=self._registry_password,
                capture_output=True,
                text=True,
                check=True,
                env=env,
                timeout=60,
            )
        except subprocess.CalledProcessError as exc:
            raise ChartResolutionError(
                f"helm registry login failed for {registry_host}: {exc.stderr[-1024:]}"
            ) from exc

    def _run_helm_pull(
        self, env: dict[str, str], dest: pathlib.Path, unpack_dir: pathlib.Path
    ) -> None:
        argv = [
            "helm", "pull", f"oci://{self._reference}",
            "--destination", str(dest),
            "--untar",
            "--untar-dir", str(unpack_dir),
        ]
        if self._version:
            argv.extend(["--version", self._version])
        try:
            subprocess.run(  # noqa: S603
                argv, capture_output=True, text=True, check=True, env=env, timeout=600,
            )
        except subprocess.CalledProcessError as exc:
            raise ChartResolutionError(
                f"helm pull oci://{self._reference} failed: {exc.stderr[-1024:]}"
            ) from exc

    def _run_cosign_verify(self) -> None:
        # WARN if running unconstrained
        if not self._verify_identity and not self._verify_oidc_issuer:
            logger.warning(
                "chart.verify.unconstrained_identity",
                hint="Set CHART_VERIFY_CERTIFICATE_IDENTITY and "
                     "CHART_VERIFY_CERTIFICATE_OIDC_ISSUER to pin the trusted signer",
            )
        argv = ["cosign", "verify"]
        if self._verify_identity:
            argv.extend(["--certificate-identity", self._verify_identity])
        if self._verify_oidc_issuer:
            argv.extend(["--certificate-oidc-issuer", self._verify_oidc_issuer])
        argv.append(f"{self._reference}")
        try:
            subprocess.run(  # noqa: S603
                argv, capture_output=True, text=True, check=True, timeout=120,
            )
        except subprocess.CalledProcessError as exc:
            raise ChartResolutionError(
                f"cosign verify failed for {self._reference}: {exc.stderr[-1024:]}"
            ) from exc
```

**Decision: where does `subprocess.run` for cosign live?**

Per CONTEXT D5: in `chart/oci.py`, NOT in `helm/client.py`. Cosign is a non-helm binary; the chart-source module owns its full lifecycle (download + verify). The "only helm/client.py calls subprocess" Phase 3 invariant is **scoped to helm subcommands**.

**Decision: where do new helm subcommands (`registry login`, `pull`) live?**

Tension: Phase 3 D1 says "`helm/client.py` is the ONLY module that calls subprocess for helm." Phase 4 needs `helm registry login` and `helm pull`. Two options:

- **(A)** Extend `HelmClient` with `registry_login()` and `pull()` typed methods; `OciChart` calls into HelmClient.
- **(B)** `OciChart` calls `subprocess.run(["helm", ...])` directly for its lifecycle commands; HelmClient stays purely for `upgrade_install` + `history`.

**Recommendation: (B), with explicit doc-comment override in CONTEXT D5.** The Phase 3 invariant is about preserving testability of the **upgrade** path (argv snapshot tests via syrupy). The pull + registry-login commands are lifecycle plumbing — their argv is uninteresting from a snapshot-test perspective, and routing them through HelmClient adds two more typed methods (and tests) for zero benefit. The chart-source module owns its full lifecycle (cosign verify + helm pull + registry login) atomically.

**If (A) is preferred by the planner** (consistency wins over module-cohesion), the API additions to `HelmClient` are:

```python
def registry_login(self, registry: str, username: str, password: str, env: dict[str, str]) -> None: ...
def pull_oci(self, reference: str, destination: pathlib.Path, untar_dir: pathlib.Path, version: str | None, env: dict[str, str]) -> None: ...
def repo_add(self, name: str, url: str, env: dict[str, str]) -> None: ...
def repo_update(self, env: dict[str, str]) -> None: ...
def pull_repo(self, repo_chart: str, destination: pathlib.Path, untar_dir: pathlib.Path, version: str | None, env: dict[str, str]) -> None: ...
```

Plan-Checker decides. The cookbook above shows option (B); switching to (A) is mechanical.

### §7.5 — `RepoChart.resolve()` — full cookbook

Identical lifecycle, swap `helm registry login` + `helm pull oci://` for `helm repo add` + `helm repo update` + `helm pull <name>/<chart>`. Per-isolation env vars stay the same.

```python
@contextmanager
def resolve(self) -> Iterator[ResolvedChart]:
    tmpdir = pathlib.Path(tempfile.mkdtemp(prefix="aws-eks-helm-deploy-chart-"))
    try:
        unpack_dir = tmpdir / "unpacked"
        unpack_dir.mkdir()
        env = os.environ.copy()
        env["HELM_REPOSITORY_CONFIG"] = str(tmpdir / "repositories.yaml")
        env["HELM_REPOSITORY_CACHE"] = str(tmpdir / "cache")
        # No HELM_REGISTRY_CONFIG needed — repo:// charts are HTTP/HTTPS, not OCI.

        # helm repo add <name> <url>
        subprocess.run(  # noqa: S603
            ["helm", "repo", "add", self._name, self._repo_url],
            capture_output=True, text=True, check=True, env=env, timeout=60,
        )
        # helm repo update <name>
        subprocess.run(  # noqa: S603
            ["helm", "repo", "update", self._name],
            capture_output=True, text=True, check=True, env=env, timeout=120,
        )
        # helm pull <name>/<chart> --version --untar --untar-dir
        argv = [
            "helm", "pull", f"{self._name}/{self._chart}",
            "--destination", str(tmpdir), "--untar", "--untar-dir", str(unpack_dir),
        ]
        if self._version:
            argv.extend(["--version", self._version])
        subprocess.run(argv, capture_output=True, text=True, check=True, env=env, timeout=600)  # noqa: S603

        candidates = [p for p in unpack_dir.iterdir() if p.is_dir()]
        if len(candidates) != 1:
            raise ChartResolutionError(f"expected 1 chart dir, found {len(candidates)}")
        chart_dir = candidates[0]
        data = _parse_chart_yaml(chart_dir)
        yield ResolvedChart(
            name=str(data.get("name", chart_dir.name)),
            version=str(data.get("version", "")),
            source_path=chart_dir,
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
```

### §7.6 — `Settings` additions

```python
# OIDC (AUTH-03)
oidc_audience: str | None = Field(default=None, alias="OIDC_AUDIENCE")

# Repo + OCI chart sources (CHART-02, CHART-03)
repo_url: str | None = Field(default=None, alias="REPO_URL")
chart_version: str | None = Field(default=None, alias="CHART_VERSION")
registry_username: str | None = Field(default=None, alias="REGISTRY_USERNAME")
registry_password: str | None = Field(default=None, alias="REGISTRY_PASSWORD")

# Cosign verify (CHART-04)
chart_verify: bool = Field(default=False, alias="CHART_VERIFY")
chart_verify_certificate_identity: str | None = Field(
    default=None, alias="CHART_VERIFY_CERTIFICATE_IDENTITY",
)
chart_verify_certificate_oidc_issuer: str | None = Field(
    default=None, alias="CHART_VERIFY_CERTIFICATE_OIDC_ISSUER",
)
```

**Note on `registry_password`:** pydantic-settings will gladly log this if a consumer or test calls `repr(settings)`. Phase 4 should add a custom `__repr__` to `Settings` that masks `*_password`, `*_token`, `*_secret*` fields — or at minimum a `SecretStr` from pydantic. The current `Settings` has no masking. **Recommendation:** use `pydantic.SecretStr` for `registry_password` and unwrap with `.get_secret_value()` at the single call site in `OciChart`. Cost: ~2 lines. Mitigation against the same class of leak the `AwsCredentials.__repr__` already handles.

---

## §8 — Test fixtures (`kind` + `registry:2` + signed test chart)

### §8.1 — `kind` cluster (already wired in Phase 3)

No change. Existing fixture at `tests/integration/conftest.py` brings up a kind cluster and exposes the kubeconfig path.

### §8.2 — `registry:2` (local OCI registry for CHART-03/04 tests)

Add a session-scoped fixture that runs a `registry:2` container alongside the kind cluster:

```python
@pytest.fixture(scope="session")
def oci_registry() -> Iterator[str]:
    """Spawn a local docker registry on 127.0.0.1:5555 for OCI chart tests."""
    container_id = subprocess.run(
        ["docker", "run", "-d", "--rm", "-p", "5555:5000", "registry:2"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    try:
        # wait for registry to accept connections (poll /v2/)
        for _ in range(30):
            r = subprocess.run(
                ["curl", "-sf", "http://127.0.0.1:5555/v2/"],
                capture_output=True,
            )
            if r.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("registry:2 did not become ready")
        yield "127.0.0.1:5555"
    finally:
        subprocess.run(["docker", "stop", container_id], check=False, capture_output=True)
```

### §8.3 — Test chart at `tests/fixtures/charts/minimal/`

Already exists from Phase 3 (`Chart.yaml` + `templates/configmap.yaml`). Reuse for OCI tests by packaging it on-demand:

```bash
helm package tests/fixtures/charts/minimal/ -d /tmp/
helm push /tmp/minimal-0.1.0.tgz oci://127.0.0.1:5555/charts
```

### §8.4 — Cosign-signed test chart (CHART-04 integration test)

Tests fall in two tiers based on cost:

**Unit tier (cheap, default):** mock the cosign subprocess. Assert argv shape, env-var propagation, error mapping. Use `pytest-mock`'s `mocker.patch("subprocess.run", ...)`.

**Integration tier (gated, opt-in):** run real cosign against a real registry. Requires:

1. `cosign` binary on the test host (`make integration-test` already requires helm; cosign joins this list).
2. Sign the test chart at test-setup time using a **one-shot ephemeral OIDC** (cosign supports `--identity-token <jwt>` for CI; locally consumers run `cosign sign` interactively).
3. Verify with matching `--certificate-identity` + `--certificate-oidc-issuer`.

Recommend: gate integration cosign tests behind a `pytest.mark.skipif(shutil.which("cosign") is None, reason="cosign not installed")` decorator. They are **opt-in** by tag (`@pytest.mark.cosign`), separate from the existing `integration` mark.

### §8.5 — Snapshot tests for argv (D9 carry-over)

The Phase 3 syrupy convention extends to Phase 4. Snapshot every new argv-construction function:

- `_OidcWebIdentityStrategy_build_sts_request_kwargs` (if extracted as a pure function)
- `_OciChart_build_helm_pull_argv`
- `_OciChart_build_cosign_verify_argv`
- `_RepoChart_build_helm_pull_argv`
- `_RepoChart_build_repo_add_argv`

Each new snapshot file lives at `tests/unit/__snapshots__/<module>.ambr`.

### §8.6 — IAM trust-policy template test

```python
def test_iam_trust_policy_template_has_required_placeholders():
    template_path = pathlib.Path("docs/guides/oidc-setup.md")
    text = template_path.read_text()
    # Extract first ```json block
    json_block = re.search(r"```jsonc?\n(.*?)\n```", text, re.DOTALL).group(1)
    data = json.loads(json_block)
    stmt = data["Statement"][0]
    # 1. aud condition uses literal placeholder
    aud_key = next(k for k in stmt["Condition"]["StringEquals"] if k.endswith(":aud"))
    assert stmt["Condition"]["StringEquals"][aud_key] == "<OIDC_AUDIENCE>"
    # 2. sub condition uses StringLike (not StringEquals) — researcher correction
    assert "StringLike" in stmt["Condition"]
    sub_key = next(k for k in stmt["Condition"]["StringLike"] if k.endswith(":sub"))
    assert "<BITBUCKET_WORKSPACE_UUID>" in stmt["Condition"]["StringLike"][sub_key]
    assert "<BITBUCKET_REPO_UUID>" in stmt["Condition"]["StringLike"][sub_key]
    # 3. Action is AssumeRoleWithWebIdentity
    assert stmt["Action"] == "sts:AssumeRoleWithWebIdentity"
    # 4. Federated principal matches Bitbucket OIDC issuer pattern
    fed: str = stmt["Principal"]["Federated"]
    assert "api.bitbucket.org/2.0/workspaces/<WORKSPACE>/pipelines-config/identity/oidc" in fed
```

---

## §9 — Risks the planner must mitigate (concrete plan-checker obligations)

### R1 — ROADMAP + REQUIREMENTS edit MUST be the first commit of Phase 4

CONTEXT D1 is explicit: the ROADMAP SC1 + AUTH-04 wording is superseded by D1. The first Phase 4 plan MUST be the doc-edit, atomic with the OIDC strategy code change. The Plan-Checker enforces:
- One plan (likely 04-01) contains the edits to `.planning/ROADMAP.md` (Phase 4 SC1 + a "Phase 4 revision 2026-06-18" note) AND `.planning/REQUIREMENTS.md` AUTH-04 wording AND the new `OidcWebIdentityStrategy` skeleton.
- All in one commit. Do not let the planner emit "plan-checker verifies docs are updated" as a deferred check — that turns into a late discovery in `gsd-verify-work` and blocks the merge.

### R2 — `select_strategy` precedence regression

Phase 2's `select_strategy` returns early on static keys. Adding the OIDC branch in the wrong place flips precedence (OIDC wins) — violating D1. Plan-Checker MUST verify the OIDC branch lives **after** the static-keys branch.

**Snapshot test obligation:** add a unit test that sets BOTH static keys and `BITBUCKET_STEP_OIDC_TOKEN` env vars, asserts the returned strategy is `StaticKeysStrategy` (not `OidcWebIdentityStrategy`), AND asserts the WARN log was emitted.

### R3 — `botocore.UNSIGNED` import path

Easy to miss. The import is `from botocore import UNSIGNED`. If the planner copies the AssumeRoleStrategy shape verbatim (which passes static keys to `boto3.session.Session`), the OIDC version will fail at runtime with `NoCredentialsError` before the STS call. Plan-Checker reads the `OidcWebIdentityStrategy.get_credentials` implementation and verifies the unsigned config is present.

### R4 — Registry password leaking via process listing OR settings repr

Two leak surfaces:
1. `helm registry login --password <value>` puts the password in argv. **Mitigation:** the cookbook uses `--password-stdin`. Plan-Checker verifies neither RepoChart nor OciChart calls helm with `--password` positionally.
2. `repr(settings)` would print the password. **Mitigation:** use `pydantic.SecretStr` for `registry_password`, unwrap at the single call site. Plan-Checker verifies the type annotation.

### R5 — Cosign verify against pulled tarball instead of OCI ref

Cosign verifies the signed digest **as it exists in the registry** — passing it a local file is a different operation (`cosign verify-blob`). Plan-Checker verifies `cosign verify` is called with the `oci://...` reference (or just `<registry>/<chart>:<tag>` form — both work), NOT with `<tmpdir>/chart.tgz`.

### R6 — Cosign verify ordering: BEFORE pull, NOT after

The cookbook (§7.4 step 2) does `cosign verify` *before* `helm pull`. If verify fails, the pull is skipped entirely — saves bandwidth and prevents an attacker-controlled tarball from sitting on disk. Plan-Checker verifies the call order.

### R7 — `helm pull --untar` directory discovery

The unpacked subdirectory name is the chart name from `Chart.yaml`, not the tgz filename. If the planner hardcodes the expected path (e.g. `tmpdir/unpacked/<reference>`), the resolver will `FileNotFoundError` on charts whose published name differs from the OCI path component. Plan-Checker verifies the resolver uses the "iterate the directory and assert exactly-one subdir" pattern from §7.4 step 4.

### R8 — Tempdir cleanup on cosign verify failure

The `finally: shutil.rmtree(tmpdir, ignore_errors=True)` is load-bearing — if cosign raises BEFORE the `yield`, the contextmanager's `__exit__` is not called by Python's `with`-block protocol, but the `try/finally` inside the generator still runs because the generator is garbage-collected. Plan-Checker verifies the cookbook's exact `try/finally` shape and that `cosign verify` is called inside the `try`.

### R9 — D5 doc-comment override (cosign in `chart/oci.py`, not `helm/client.py`)

The "only helm/client.py shells out" Phase 3 invariant is being **scoped** in Phase 4 to helm subcommands only. The CONTEXT D5 Plan-Check obligation already covers this — Plan-Checker MUST NOT flag the cosign subprocess call in `chart/oci.py` as a layering violation. This is an EXPECTED deviation from Phase 3 D1, documented in CONTEXT 04 D5.

### R10 — `Plan-Checker` AUTH-04 verification path

The verifier in Phase 4 must check AUTH-04 against the **revised** wording from D1, NOT the original ROADMAP SC1. Plan-Checker's instructions for `gsd-verify-work` should include an explicit pointer:

> AUTH-04 success = `select_strategy()` returns `StaticKeysStrategy` when both static keys and OIDC token are present, AND emits the `auth.precedence.static_keys_won_over_oidc` WARN log.

NOT:

> AUTH-04 success = OIDC wins.

The Plan-Checker also checks that the doc-edit task (R1) lands in plan 04-01 and is atomic with the OIDC strategy code.

### R11 — `oidc_audience` env var → settings field rename consistency

The CONTEXT uses both `OIDC_AUDIENCE` (env var) and `oidc_audience` (attribute). Plan-Checker verifies the alias mapping is exactly:

```python
oidc_audience: str | None = Field(default=None, alias="OIDC_AUDIENCE")
```

— and that all references in `select_strategy` and `OidcWebIdentityStrategy` use the attribute name `oidc_audience` (not `audience` ambiguity).

### R12 — Dockerfile multi-stage ordering

The new `cosign-fetch` stage MUST come BEFORE the `runtime` stage's `COPY --from=cosign-fetch` instruction (Docker's stage ordering is by appearance, not by name reference). Add it between `helm-fetch` and `runtime` (§6 cookbook). Plan-Checker verifies the new `ARG COSIGN_VERSION=2.6.3` lives at the top alongside `ARG HELM_VERSION`, and the `COPY --from=cosign-fetch` line in the `runtime` stage is added BEFORE the `USER pipe` line so root owns the binary placement.

### R13 — Settings password field type

The `registry_password` field MUST be `pydantic.SecretStr | None`, NOT `str | None`. Plan-Checker verifies the type annotation in `settings.py` and that the single unwrap (`.get_secret_value()`) lives in `OciChart.__init__` or `_run_helm_registry_login`.

---

## Sources

### Primary (HIGH confidence — direct upstream source inspection)
- [botocore@1.43.31 — botocore/credentials.py](https://github.com/boto/botocore/blob/1.43.31/botocore/credentials.py) — credential resolver chain order verified line-by-line.
- [helm@v3.18.6 — cmd/helm/pull.go](https://github.com/helm/helm/blob/v3.18.6/cmd/helm/pull.go) — `--untar` default + flag semantics.
- [helm@v3.18.6 — pkg/chartutil/expand.go](https://raw.githubusercontent.com/helm/helm/v3.18.6/pkg/chartutil/expand.go) — directory name derived from `Chart.yaml` `name:`.
- [helm@v3.18.6 — pkg/registry/client.go](https://github.com/helm/helm/blob/v3.18.6/pkg/registry/client.go) — registry-config single-file pointer semantics.
- [cosign@v2.6.3 release assets](https://github.com/sigstore/cosign/releases/tag/v2.6.3) — verified via `gh release view`: `cosign-linux-amd64` + `cosign_checksums.txt`.

### Secondary (MEDIUM confidence — official docs / live)
- [Atlassian Support — Deploy on AWS using Bitbucket Pipelines OpenID Connect](https://support.atlassian.com/bitbucket-cloud/docs/deploy-on-aws-using-bitbucket-pipelines-openid-connect/) — IAM principal ARN, condition-key format, `aud` value.
- [Atlassian Support — Integrate Pipelines with resource servers using OIDC](https://support.atlassian.com/bitbucket-cloud/docs/integrate-pipelines-with-resource-servers-using-oidc/) — `oidc: true` pipeline-step semantics.
- [Sigstore Cosign docs — Verifying Signatures](https://docs.sigstore.dev/cosign/verifying/verify/) — canonical CLI form, identity flags.
- [cosign main — doc/cosign_verify.md](https://github.com/sigstore/cosign/blob/main/doc/cosign_verify.md) — full flag listing.
- [helm.sh — helm env vars](https://helm.sh/docs/helm/helm/) — `HELM_REGISTRY_CONFIG`, `HELM_REPOSITORY_CONFIG`, `HELM_REPOSITORY_CACHE` defaults.

### Tertiary (LOW confidence — corroboration only)
- [Cosign 2.0 release notes blog posts](https://www.wiz.io/blog/cosign-2-keyless) — confirmation that `COSIGN_EXPERIMENTAL=1` is no longer required for keyless `[ASSUMED]` and corroborated by docs absence; safe to omit.
- WebSearch corroboration for `COSIGN_CERTIFICATE_IDENTITY` / `COSIGN_CERTIFICATE_OIDC_ISSUER` env-var equivalents in cosign 2.x — corroborated across multiple sources but `[ASSUMED]` for the regexp variants which the official docs do NOT mention.

---

## Confidence breakdown

| Section | Level | Reason |
|---|---|---|
| §1 (botocore chain) | HIGH | Verified against pinned botocore@1.43.31 source. |
| §2 (Bitbucket OIDC URL + condition keys + `aud`) | HIGH | Quoted from current Atlassian docs verbatim; `sub` `StringLike` fix is researcher-validated. |
| §3 (cosign CLI + env vars) | HIGH for flags / MEDIUM for env-var equivalents | Flags from official `cosign_verify.md`; env vars from sources beyond the verify.md file. |
| §4 (helm pull --untar dir name) | HIGH | Verified against helm@v3.18.6 `expand.go` source. |
| §5 (HELM_REGISTRY_CONFIG isolation) | HIGH | Helm env-var docs explicit + source confirms single-file pointer. |
| §6 (cosign download URLs + checksum pattern) | HIGH | `gh release view` confirmed asset names; URL pattern is GitHub's stable `releases/download/<tag>/<asset>`. |

**Research valid through:** 2026-08-18 (60-day window — boto3 minor releases on 1.43 line are stable; helm 3.18.x is stable until helm 4 GA which is unannounced as of 2026-06; cosign 2.6.x stable; Bitbucket OIDC URL format unchanged since Q2 2023).

**Research date:** 2026-06-18.
