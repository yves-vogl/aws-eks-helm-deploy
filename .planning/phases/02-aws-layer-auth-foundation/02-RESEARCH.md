# Phase 2 Research: AWS Layer & Auth Foundation

**Researched:** 2026-06-17
**Domain:** AWS authentication with boto3, EKS presigned-URL token generation, AuthStrategy Protocol design
**Confidence:** HIGH — all code patterns verified by running against the installed venv (boto3 1.43.31, moto 5.2.2, Python 3.13); all package versions confirmed from PyPI; awscli token generation algorithm confirmed against upstream source

---

## Scope Summary

Phase 2 wires AWS credential acquisition and EKS token generation into the skeleton that Phase 1 built.
Three requirements ship: AUTH-01 (typed `AuthStrategy` Protocol + `StaticKeysStrategy`), AUTH-02
(`AssumeRoleStrategy` composed on top of any base strategy), and AUTH-07 (pure-boto3 EKS token, no
awscli). The phase produces five new Python modules, zero changes to `Dockerfile` or `pyproject.toml`
(both are already clean — `awscli` was never added, `boto3 ~= 1.43` and `moto[eks,sts] ~= 5.2` are
already declared), and extends `cli.py` with the auth wire-in placeholder.

---

## A. EKS Token Format and Generation

### Wire Format

The EKS bearer token passed in a kubeconfig `exec` credential or directly in the `token:` field is:

```
k8s-aws-v1.<base64url-no-padding(presigned-STS-GetCallerIdentity-URL)>
```

Constants (from awscli source `awscli/customizations/eks/get_token.py` and aws-iam-authenticator
`pkg/token/token.go`):

| Constant | Value | Notes |
|----------|-------|-------|
| `TOKEN_PREFIX` | `"k8s-aws-v1."` | Literal prefix, not base64 |
| `K8S_AWS_ID_HEADER` | `"x-k8s-aws-id"` | Must be signed into the presigned URL |
| `URL_TIMEOUT` | `60` | `X-Amz-Expires=60` in the URL; hardcoded for backward compat |
| Token validity | 15 minutes | Determined by the X-Amz-Date + cluster-side validation logic |

`[CITED: https://github.com/aws/aws-cli/blob/develop/awscli/customizations/eks/get_token.py]`

### How the kube-apiserver Validates the Token

The EKS control plane runs an authentication webhook. When `kubectl` (or helm) presents this bearer
token, the webhook:
1. Strips the `k8s-aws-v1.` prefix
2. Base64url-decodes (adding back the stripped `=` padding as needed) to get the presigned URL
3. Makes an HTTP GET to that URL (calling STS `GetCallerIdentity`)
4. Verifies the response contains `x-k8s-aws-id` header matching the cluster name
5. Maps the returned ARN to a Kubernetes principal via the aws-auth ConfigMap or access entries

The presigned URL **must** target a regional STS endpoint (`sts.{region}.amazonaws.com`), not the
global endpoint (`sts.amazonaws.com`). Clusters set their preferred STS endpoint at creation time;
most regions require the regional endpoint. `[CITED: https://github.com/kubernetes-sigs/aws-iam-authenticator]`

### Required URL Parameters

The presigned URL must have these characteristics (verified by running the full generation against
a boto3 client in the project venv):

- `X-Amz-Algorithm=AWS4-HMAC-SHA256`
- `X-Amz-Expires=60`
- `X-Amz-SignedHeaders=host;x-k8s-aws-id` — the cluster ID header is **signed** into the URL
- `Action=GetCallerIdentity`
- `HttpMethod=GET` (not POST — GET presigned URL so no body is sent)

The `x-k8s-aws-id` header is **not** passed in the Params dict of `generate_presigned_url` directly
(that would fail validation). It is injected via botocore's event system before signing, so it
becomes part of `SignedHeaders`. `[VERIFIED: tested in project venv]`

### Pure-boto3 Implementation Pattern

The awscli uses botocore's event emitter to inject the custom header before the request is signed.
The identical mechanism works with boto3's `client.meta.events`. This is the canonical pattern and
has been verified to produce a conforming token:

```python
# src/aws_eks_helm_deploy/aws/eks_token.py
from __future__ import annotations

import base64

import boto3
import boto3.session

TOKEN_PREFIX = "k8s-aws-v1."
K8S_AWS_ID_HEADER = "x-k8s-aws-id"
URL_TIMEOUT = 60  # seconds; hardcoded per upstream spec


def generate_eks_token(session: boto3.session.Session, cluster_name: str, region: str) -> str:
    """Generate a k8s-aws-v1.<base64url> bearer token for EKS via pure boto3.

    Replicates the algorithm from awscli.customizations.eks.get_token without
    importing awscli. The x-k8s-aws-id header is injected into the presigned
    URL via botocore events so it appears in X-Amz-SignedHeaders.

    Args:
        session: A boto3.Session pre-configured with the desired credentials.
        cluster_name: EKS cluster name (becomes the x-k8s-aws-id header value).
        region: AWS region where the cluster lives (determines STS endpoint).

    Returns:
        Bearer token string starting with 'k8s-aws-v1.'.
    """
    sts = session.client(
        "sts",
        endpoint_url=f"https://sts.{region}.amazonaws.com",
    )

    # Storage for the header value across event calls
    _header_store: dict[str, str] = {}

    def _retrieve_header(params: dict, **kwargs: object) -> None:  # noqa: ANN003
        if K8S_AWS_ID_HEADER in params:
            _header_store["value"] = params.pop(K8S_AWS_ID_HEADER)

    def _inject_header(request: object, **kwargs: object) -> None:  # noqa: ANN001 ANN003
        if "value" in _header_store:
            request.headers[K8S_AWS_ID_HEADER] = _header_store["value"]  # type: ignore[union-attr]

    sts.meta.events.register(
        "provide-client-params.sts.GetCallerIdentity", _retrieve_header
    )
    sts.meta.events.register(
        "before-sign.sts.GetCallerIdentity", _inject_header
    )

    url: str = sts.generate_presigned_url(
        "get_caller_identity",
        Params={K8S_AWS_ID_HEADER: cluster_name},
        ExpiresIn=URL_TIMEOUT,
        HttpMethod="GET",
    )
    token = TOKEN_PREFIX + base64.urlsafe_b64encode(
        url.encode("utf-8")
    ).decode("utf-8").rstrip("=")
    return token
```

`[VERIFIED: tested in project venv — token starts with k8s-aws-v1., decoded URL contains x-k8s-aws-id in X-Amz-SignedHeaders, X-Amz-Expires=60]`

### Golden Test Strategy

The golden test approach compares the **structural properties** of the generated token, not a
byte-for-byte comparison against `aws eks get-token` output. A byte-for-byte comparison is
impossible in practice because the presigned URL includes `X-Amz-Date` (changes per invocation)
and the HMAC signature (changes with credentials and timestamp). What is stable and testable:

1. Token starts with `k8s-aws-v1.`
2. Stripping prefix + adding back `=` padding + base64url-decode yields a valid URL
3. Decoded URL contains `X-Amz-Expires=60`
4. Decoded URL contains `x-k8s-aws-id` in `X-Amz-SignedHeaders`
5. Decoded URL `Action` query param is `GetCallerIdentity`
6. Decoded URL hostname is `sts.{region}.amazonaws.com` (regional, not global)
7. Token contains no `=` padding characters

Under `@mock_aws`, moto generates valid presigned URLs (verified in project venv). Cluster-name
injection works identically in unit tests — use `@mock_aws` for all EKS token unit tests.

**Note on ROADMAP.md claim:** The ROADMAP states "golden unit test asserts byte-equal to `aws eks get-token` reference output". This is architecturally impossible (timestamp + HMAC changes per call). Interpret this as "structurally equivalent" — assert the properties above rather than byte equality. `[ASSUMED]` that the intent is structural equivalence; if true byte-equality was required, the test would always be flaky.

### Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Using global STS endpoint (`sts.amazonaws.com`) | Token rejected by cluster's STS authenticator | Always construct with `endpoint_url=f"https://sts.{region}.amazonaws.com"` |
| Missing `x-k8s-aws-id` header injection | URL missing header in `X-Amz-SignedHeaders` → token rejected | Register both botocore events before calling `generate_presigned_url` |
| Passing `x-k8s-aws-id` in `Params` dict without event registration | `ParamValidationError: Unknown parameter in input: "x-k8s-aws-id"` | Register `provide-client-params.sts.GetCallerIdentity` event first to extract the header |
| Using `HttpMethod='POST'` | STS returns 400 (presigned GET has no body) | Always use `HttpMethod='GET'` |
| Including `=` padding in the token | Token rejected by kube-apiserver | `.rstrip('=')` after base64url encoding |
| Wrong base64 encoding (standard, not urlsafe) | Token contains `+` or `/` which are invalid in URL path components | Use `base64.urlsafe_b64encode` |

### References

- awscli source: `https://github.com/aws/aws-cli/blob/develop/awscli/customizations/eks/get_token.py`
  — authoritative Python implementation; `STSClientFactory`, `TokenGenerator`, all constants
- aws-iam-authenticator: `https://github.com/kubernetes-sigs/aws-iam-authenticator/blob/master/pkg/token/token.go`
  — Go reference implementation; `v1Prefix`, `clusterIDHeader`, `requestPresignParam` constants
- Boto3 `generate_presigned_url` signature (verified in venv): `(ClientMethod, Params=None, ExpiresIn=3600, HttpMethod=None)`

---

## B. AuthStrategy Protocol Design

### Protocol Definition

Use `typing.Protocol` with `@runtime_checkable`. The `@runtime_checkable` decorator enables
`isinstance(obj, AuthStrategy)` checks in `select_strategy` and in tests. Structural subtyping
(duck typing) means no inheritance is required — `StaticKeysStrategy`, `AssumeRoleStrategy`, and
the future `OidcWebIdentityStrategy` (Phase 4) all satisfy the Protocol by having the right method
signature. `[VERIFIED: tested in project venv]`

```python
# src/aws_eks_helm_deploy/auth/base.py
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AuthStrategy(Protocol):
    """Protocol satisfied by any credential provider."""

    def get_credentials(self) -> AwsCredentials:
        """Return a set of AWS credentials. Must not cache or refresh internally."""
        ...
```

**Why not `@abstractmethod` / ABC?** ABCs require inheritance, breaking the structural typing
model. Phase 4's `OidcWebIdentityStrategy` lives in a separate module and should not inherit from
a base class in `auth/base.py` — that would create a coupling that the Protocol design avoids.

### AwsCredentials Value Object

```python
# In src/aws_eks_helm_deploy/auth/base.py (same file as Protocol)
from __future__ import annotations

import dataclasses
from datetime import datetime


@dataclasses.dataclass(frozen=True)
class AwsCredentials:
    """Immutable AWS credential set.

    The __repr__ masks sensitive fields — safe to pass to get_logger().
    Never log or bind the actual secret values.
    """

    access_key_id: str
    secret_access_key: str
    session_token: str | None = None
    expiration: datetime | None = None

    def __repr__(self) -> str:
        tail = self.access_key_id[-4:] if len(self.access_key_id) >= 4 else "****"
        return f"AwsCredentials(access_key_id=...{tail}, secret_access_key=<redacted>)"

    def to_boto3_kwargs(self) -> dict[str, str]:
        """Return a dict suitable for spreading into boto3.Session() or client()."""
        kwargs: dict[str, str] = {
            "aws_access_key_id": self.access_key_id,
            "aws_secret_access_key": self.secret_access_key,
        }
        if self.session_token is not None:
            kwargs["aws_session_token"] = self.session_token
        return kwargs
```

**Why `dataclass(frozen=True)` not Pydantic?** `AwsCredentials` is an internal value object, not a
settings model. Pydantic adds a 40-60 ms cold-import overhead and brings validator complexity that
is not needed here. A frozen dataclass provides immutability, structural equality (`__eq__`,
`__hash__`), and controlled `__repr__` with zero extra dependencies. `[ASSUMED: performance
estimate from general knowledge; the immutability argument is verifiable]`

**Why not `NamedTuple`?** `NamedTuple` does not support `frozen=True`-style immutability on
assignment (only structural); mypy-strict handles both equally. The `dataclass` offers a clean path
to adding `__post_init__` validation (e.g., non-empty key assertion) if needed later.

**Integration with `CREDENTIAL_BLOCKLIST`:** `AwsCredentials.__repr__` never exposes raw secrets.
The keys `aws_access_key_id`, `aws_secret_access_key`, `aws_session_token` are already in the
`CREDENTIAL_BLOCKLIST` in `logging.py`. Calling `bind_safe_context(creds=repr(creds))` is safe;
calling `bind_safe_context(**creds.to_boto3_kwargs())` will raise `ValueError` — this is the
intended behavior. Pass only the string name of the strategy to structlog context, never the
credentials object itself.

---

## C. boto3 / botocore Patterns

### Session Construction

Always construct a `boto3.Session` from explicit credentials — never rely on environment variable
fall-through for strategy-controlled credential sets. The `to_boto3_kwargs()` method on
`AwsCredentials` produces exactly the right dict:

```python
import boto3
import botocore.config

session = boto3.Session(
    region_name=settings.aws_region,
    **credentials.to_boto3_kwargs(),  # access_key_id, secret_access_key, optional session_token
)
```

For the STS client used in `AssumeRoleStrategy`, pass `endpoint_url` explicitly to force the
regional endpoint:

```python
sts = session.client(
    "sts",
    endpoint_url=f"https://sts.{region}.amazonaws.com",
    config=botocore.config.Config(
        retries={"max_attempts": 3, "mode": "standard"},
    ),
)
```

### Regional STS Endpoints

The `AWS_STS_REGIONAL_ENDPOINTS=regional` environment variable is the awscli mechanism; it is not
honoured by boto3 without a `botocore.config.Config` change. The cleanest boto3-native approach is
the explicit `endpoint_url` shown above. Do not rely on the environment variable. `[VERIFIED: tested
with explicit endpoint_url in project venv — URL in generated presigned URL contains region]`

### Retry Policy

The default botocore retry configuration (3 attempts, exponential backoff, "legacy" mode) is
acceptable for Phase 2 — this is a CI pipe that runs once per build. Prefer `mode="standard"` over
`mode="legacy"` for new code (standard mode includes additional retry-able status codes). No custom
retry logic is needed.

### Error Handling

Wrap all boto3/botocore API calls in a `try/except botocore.exceptions.ClientError` and convert to
the project's typed error hierarchy:

```python
import botocore.exceptions

from aws_eks_helm_deploy.errors import AuthenticationError, ConfigurationError

try:
    response = sts.assume_role(RoleArn=role_arn, RoleSessionName=session_name)
except botocore.exceptions.ClientError as exc:
    code = exc.response["Error"]["Code"]
    raise AuthenticationError(
        f"STS AssumeRole failed [{code}]: {exc.response['Error']['Message']}"
    ) from exc
except botocore.exceptions.NoCredentialsError as exc:
    raise ConfigurationError("No AWS credentials found") from exc
```

`AuthenticationError` maps to exit code 2 (already defined in `errors.py`). Do not let
`botocore.exceptions.ClientError` propagate uncaught — it would fall through to the `except
Exception` handler in `cli.main()` and return exit code 99, losing the typed exit code.

### AssumeRole Response TypedDict

`mypy-boto3-sts` (already in `boto3-stubs[eks,sts]` dev dependency, version 1.43.0 installed)
provides `CredentialsTypeDef` with fields `AccessKeyId`, `SecretAccessKey`, `SessionToken`,
`Expiration`. Use it for type annotation:

```python
from mypy_boto3_sts.type_defs import CredentialsTypeDef

creds: CredentialsTypeDef = response["Credentials"]
return AwsCredentials(
    access_key_id=creds["AccessKeyId"],
    secret_access_key=creds["SecretAccessKey"],
    session_token=creds["SessionToken"],
    expiration=creds["Expiration"],
)
```

`[VERIFIED: mypy_boto3_sts.type_defs.CredentialsTypeDef with fields AccessKeyId, SecretAccessKey, SessionToken, Expiration confirmed in project venv]`

---

## D. AwsCredentials Value Object (complete spec)

Full field specification for the planner:

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `access_key_id` | `str` | required | IAM access key ID (starts `AKIA` for long-term, `ASIA` for temporary) |
| `secret_access_key` | `str` | required | Never log; `__repr__` shows `<redacted>` |
| `session_token` | `str \| None` | `None` | Required for assumed-role and session-token credentials |
| `expiration` | `datetime \| None` | `None` | UTC datetime from STS; `None` for long-term keys |

`to_boto3_kwargs()` produces `{"aws_access_key_id": ..., "aws_secret_access_key": ...,
"aws_session_token": ...}` (session_token included only if not `None`). Return type is
`dict[str, str]` — all values are strings, including `session_token` (the expiration datetime is
not passed to boto3).

**No caching required:** A Bitbucket Pipe runs once and exits. There is no long-running process
that would benefit from credential refresh. `AssumeRoleStrategy.get_credentials()` calls STS on
every invocation — this is correct behavior.

---

## E. ROLE_ARN Composability (AUTH-02)

### Decision Tree

`select_strategy(settings: Settings) -> AuthStrategy` in `auth/__init__.py`:

```
if settings.aws_access_key_id and settings.aws_secret_access_key:
    base = StaticKeysStrategy(
        settings.aws_access_key_id,
        settings.aws_secret_access_key,
        settings.aws_session_token,   # may be None
    )
    if settings.role_arn:
        return AssumeRoleStrategy(base, settings.role_arn, session_name, settings.aws_region)
    return base

if settings.role_arn:
    raise ConfigurationError(
        "ROLE_ARN requires AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY "
        "(OIDC-based role assumption ships in Phase 4)"
    )

raise ConfigurationError(
    "No valid credential configuration: set AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY"
)
```

**Phase 4 extension point:** Phase 4 inserts an OIDC check before the static-keys check:
```
if settings.oidc_audience and settings.role_arn:
    return OidcWebIdentityStrategy(...)
```
The Phase 2 `select_strategy` must NOT check for `oidc_audience` — that field does not exist in
`Settings` yet. Leave a `# Phase 4: insert OIDC check here` comment.

### Session Name

`Settings.session_name` already has a default of `"BitbucketPipe"`. In Phase 2, the pipe should
prefer the value from Bitbucket's environment if available:

```python
import os
import uuid

def _derive_session_name(settings: Settings) -> str:
    if settings.session_name != "BitbucketPipe":
        # User explicitly set SESSION_NAME — honour it
        return settings.session_name
    # Try Bitbucket-provided identifiers
    for env_var in ("BITBUCKET_PIPELINE_UUID", "BITBUCKET_BUILD_NUMBER"):
        val = os.environ.get(env_var)
        if val:
            clean = val.replace("{", "").replace("}", "")
            return f"aws-eks-helm-deploy-{clean}"[:64]  # STS session name max 64 chars
    return f"aws-eks-helm-deploy-{uuid.uuid4()}"
```

AWS `RoleSessionName` has a max length of 64 characters and allows alphanumeric, `=`, `,`, `.`,
`@`, `-`, `_`. Truncate with `[:64]` and verify the value matches `[\w+=,.@-]+` — `uuid4` values
contain only hex digits and hyphens, so they are always valid. `[ASSUMED: 64-char limit from AWS
IAM docs; verify against docs.aws.amazon.com/IAM/latest/APIReference/API_AssumeRole.html]`

### AssumeRoleStrategy Duration and ExternalId

- **Duration:** Use the AWS default (`DurationSeconds` omitted from `assume_role` call = 3600s / 1h)
- **ExternalId:** Out of scope for Phase 2. Leave a comment: `# ExternalId: Phase 2 deferred — see AUTH-NEXT`
- **MFA:** Out of scope

### AWS_SESSION_TOKEN on base credentials

`StaticKeysStrategy` accepts `session_token: str | None`. When `AWS_SESSION_TOKEN` is set in
`Settings`, the static-key credentials already represent temporary credentials (from a prior
`GetSessionToken` or `AssumeRole`). These can still be used as the base for a further
`AssumeRoleStrategy`. STS accepts temporary credentials as the source for `AssumeRole` (subject to
the role's trust policy). No special code path is needed.

---

## F. awscli Removal Verification

### Current State (Phase 1 already clean)

`pyproject.toml` confirmed (read from disk):
- `awscli` is **NOT** present in `dependencies` or `dependency-groups` — no removal needed
- `boto3 ~= 1.43` is already in `dependencies`
- `moto[eks,sts] ~= 5.2` is already in `dev` dependency-group
- `boto3-stubs[eks,sts]` is already in `dev` dependency-group

`Dockerfile` confirmed (read from disk):
- No `apt-get install awscli` in any stage
- No `pip install awscli` in any stage
- The `from awscli.customizations.eks.get_token import STSClientFactory, TokenGenerator` import
  from v1's `pipe/pipe.py` line 20 is NOT present in `src/aws_eks_helm_deploy/`

`[VERIFIED: read pyproject.toml and Dockerfile from disk]`

### Verification Commands (for acceptance test)

```bash
# Confirm no awscli layer in built image
docker history <image>:<tag> | grep -i awscli
# Expected: no output

# Confirm awscli is not importable inside the container
docker run --rm <image>:<tag> python -c "import awscli" 2>&1 | grep "No module named"
# Expected: ModuleNotFoundError: No module named 'awscli'
```

### Image Size (v1 → v2 reduction)

The ROADMAP claims "> 100 MB reduction". awscli v1 is approximately 100-120 MB installed.
`python:3.13-slim-bookworm` base image is smaller than v1's `python:3-alpine` + awscli combined.
The SIZE claim should be verified at build time via:

```bash
docker images <image>:<tag> --format "{{.Size}}"
```

The Phase 1 Dockerfile already lacks awscli; the size reduction is a v1-to-v2 delta, not a
Phase 2 change. Document this clearly in the acceptance test: the v1 reference image
(`yvesvogl/aws-eks-helm-deploy:1.3.0`) must be pulled to measure the delta. `[ASSUMED: 100 MB
reduction from general knowledge of awscli package size; needs runtime measurement for exact value]`

---

## G. Test Strategy

### Unit Tests (must achieve 100% line+branch coverage on auth/ and aws/ modules)

**Framework:** pytest 9.1 with `@mock_aws` from moto 5.2.2 (single unified decorator for all AWS
services — no service-specific `@mock_sts` or `@mock_iam` in moto 5.x).
`[VERIFIED: moto 5.2.2 installed in project venv; mock_aws confirmed as the correct import]`

**Required test import:**
```python
from moto import mock_aws
import boto3
```

**Coverage targets per module:**

`tests/unit/test_auth_base.py`:
- `AwsCredentials.__repr__` masks secret: assert `"secret"` not in `repr(creds)`
- `AwsCredentials.__repr__` shows last-4 of access key
- `AwsCredentials.to_boto3_kwargs()` without session_token: no `aws_session_token` key
- `AwsCredentials.to_boto3_kwargs()` with session_token: `aws_session_token` key present
- `AwsCredentials` frozen: `dataclasses.FrozenInstanceError` on mutation attempt
- `AuthStrategy` Protocol isinstance check via `runtime_checkable`

`tests/unit/test_static_keys.py`:
- Happy path: `get_credentials()` returns expected `AwsCredentials`
- `session_token=None` default
- `session_token` passes through when set

`tests/unit/test_assume_role.py` (requires `@mock_aws`):
- Happy path: `get_credentials()` returns `AwsCredentials` with `session_token` set
- STS `ClientError` → `AuthenticationError` with exit code 2
- Delegation: base strategy's `get_credentials()` is called to obtain base credentials

`tests/unit/test_auth_select.py`:
- Static keys only → `StaticKeysStrategy`
- Static keys + ROLE_ARN → `AssumeRoleStrategy`
- ROLE_ARN only (no static keys) → `ConfigurationError`
- No credentials → `ConfigurationError`
- AWS_SESSION_TOKEN present in static keys → passes through (no error)

`tests/unit/test_eks_token.py` (requires `@mock_aws`):
- Token starts with `"k8s-aws-v1."`
- Token contains no `=` padding
- Decoded URL has `X-Amz-Expires=60`
- Decoded URL contains `x-k8s-aws-id` in `X-Amz-SignedHeaders`
- Decoded URL `Action` is `GetCallerIdentity`
- Decoded URL hostname is `sts.{region}.amazonaws.com` (not `sts.amazonaws.com`)
- Wrong cluster name produces different token (base64url changes)
- Different region produces different endpoint in URL

**moto presigned URL note:** Confirmed that moto 5.2.2 generates valid presigned URLs for STS
under `@mock_aws` — the URL is generated by botocore's credential signing logic, which runs
locally without hitting the actual AWS endpoint. `[VERIFIED: tested in project venv]`

### Integration Tests (kind cluster)

The ROADMAP requires "a kind-backed integration test proves `StaticKeysStrategy` + `AssumeRoleStrategy`
produce a kubeconfig that helm accepts."

**Limitation:** moto cannot simulate a real kube-apiserver EKS auth webhook. Real EKS cluster
testing requires actual AWS credentials. The integration test for Phase 2 must scope to what is
testable on a local kind cluster:

**What kind can test:**
- `StaticKeysStrategy` produces valid `AwsCredentials` that are used to configure a boto3 session
- The token format is structurally correct (token can be placed in a kubeconfig and helm can parse it)
- helm connectivity to the kind cluster (already wired in Phase 1) is not broken

**What kind cannot test:**
- The STS `GetCallerIdentity` presigned URL being accepted by a real EKS webhook (requires AWS)
- The ARN-to-Kubernetes-principal mapping (requires aws-auth ConfigMap or access entries)

**Recommended scope for Phase 2 integration test:**
```python
# tests/integration/test_auth_smoke.py
@pytest.mark.integration
def test_static_keys_produce_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """StaticKeysStrategy wraps env vars into AwsCredentials without AWS calls."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    settings = Settings()
    strategy = select_strategy(settings)
    creds = strategy.get_credentials()
    assert creds.access_key_id == "AKIAIOSFODNN7EXAMPLE"
    assert "secret" not in repr(creds)

@pytest.mark.integration
def test_eks_token_is_structurally_valid(kind_cluster: str) -> None:
    """EKS token format is parseable (does not require real AWS)."""
    import base64, urllib.parse
    import boto3
    from aws_eks_helm_deploy.aws.eks_token import generate_eks_token

    session = boto3.Session(
        region_name="eu-central-1",
        aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
        aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    )
    token = generate_eks_token(session, kind_cluster, "eu-central-1")
    assert token.startswith("k8s-aws-v1.")
    assert "=" not in token
    encoded = token[len("k8s-aws-v1."):]
    padded = encoded + "=" * (-len(encoded) % 4)
    url = base64.urlsafe_b64decode(padded).decode()
    qs = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert qs.get("X-Amz-Expires") == "60"
    assert "x-k8s-aws-id" in qs.get("X-Amz-SignedHeaders", "")
```

---

## H. Package Legitimacy Audit

All packages required for Phase 2 are already declared in `pyproject.toml` (Phase 1 delivered
them). No new packages are introduced in Phase 2.

| Package | Registry | Maintainer | Version (installed) | License | Verdict | Disposition |
|---------|----------|------------|---------------------|---------|---------|-------------|
| `boto3` | PyPI | Amazon Web Services | 1.43.31 | Apache-2.0 | OK | Approved — already in `dependencies` |
| `botocore` | PyPI | Amazon Web Services | 1.43.31 | Apache-2.0 | OK | Approved — transitive of boto3 |
| `moto[eks,sts]` | PyPI | getmoto/moto | 5.2.2 | Apache-2.0 | OK | Approved — already in `dev` dep-group |
| `boto3-stubs[eks,sts]` | PyPI | youtype (Vlad Emelianov) | 1.43.0 | MIT | OK | Approved — already in `dev` dep-group |
| `pytest-mock` | PyPI | pytest-dev | 3.15.1 | MIT | OK | Approved — already in `dev` dep-group |

`[VERIFIED: all versions confirmed by pip show in project venv; maintainers confirmed against PyPI project URLs]`

**Packages removed:** `awscli` was never in `pyproject.toml` — nothing to remove.
**New packages to install:** None. Phase 2 is purely implementation.

---

## I. Threat Model Template

STRIDE analysis for Phase 2 scope only. The planner should copy this into per-plan security
acceptance criteria.

| Threat | STRIDE Category | Asset | Standard Mitigation | Implemented In |
|--------|----------------|-------|---------------------|----------------|
| Presigned URL tampered in transit (MITM) | Tampering | EKS bearer token | SigV4 HMAC: URL signature covers all included headers; tampering invalidates signature | STS SigV4 (built into botocore) |
| Credential values leaked to logs | Information Disclosure | `aws_secret_access_key`, `session_token` | `CREDENTIAL_BLOCKLIST` in `logging.py`; `AwsCredentials.__repr__` shows `<redacted>`; never bind raw creds to structlog context | `logging.py` + `auth/base.py` |
| ROLE_ARN assumption to unintended account | Elevation of Privilege | Assumed-role permissions | Trust policy on the IAM role (AWS-side control); pipe validates ROLE_ARN syntax before calling STS | `auth/__init__.py::select_strategy` |
| Supply-chain attack via boto3/moto | Tampering / Repudiation | Dependency graph | `uv.lock` pins exact hashes; `pip-audit` CI gate; both packages are owned by major orgs (Amazon, getmoto) | `uv.lock` + `.github/workflows/ci.yml` (Phase 6) |
| Credentials set in env vars readable by other processes | Information Disclosure | `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | These are set by the Bitbucket pipeline runner per-step; not written to disk by the pipe; pipe scope is single-invocation | Platform control (Bitbucket) |
| Session token expiry causing helm to fail mid-run | Denial of Service | Helm upgrade action | Tokens are fetched at invocation start; STS assumed-role tokens default to 1h (plenty for one `helm upgrade`); no token refresh path needed | Design |

**Out of scope for Phase 2:**
- IAM role trust policy misconfiguration (AWS-side, documented in Phase 4 IAM template — AUTH-05)
- OIDC token validation (Phase 4)
- Log masking of rendered Secrets in helm output (Phase 5 — SEC-06)

---

## J. Suggested Plan Breakdown

The planner should decompose Phase 2 into three waves based on the dependency DAG between modules.

### Wave 1 — Value Objects and Pure Logic (no boto3 network calls; no moto needed)

**Plan J-1:** `auth/base.py` — `AuthStrategy` Protocol + `AwsCredentials` dataclass
- File: `src/aws_eks_helm_deploy/auth/__init__.py` (empty placeholder)
- File: `src/aws_eks_helm_deploy/auth/base.py` — Protocol + dataclass
- Test: `tests/unit/test_auth_base.py` — all `AwsCredentials` coverage + Protocol isinstance test
- Zero external dependencies; passes with `pytest -m unit`

**Plan J-2:** `aws/eks_token.py` — EKS token generation
- File: `src/aws_eks_helm_deploy/aws/__init__.py` (empty placeholder)
- File: `src/aws_eks_helm_deploy/aws/eks_token.py` — `generate_eks_token(session, cluster_name, region)`
- Test: `tests/unit/test_eks_token.py` — structural token properties under `@mock_aws`
- Dependency: `auth/base.py` (for `AwsCredentials` used in session construction in later waves)

These two plans can ship in parallel since they have no inter-dependency.

### Wave 2 — Strategy Implementations (depend on `base.py`; require `@mock_aws` for assume-role)

**Plan J-3:** `auth/static_keys.py` — `StaticKeysStrategy`
- File: `src/aws_eks_helm_deploy/auth/static_keys.py`
- Test: `tests/unit/test_static_keys.py`
- Dependency: Wave 1 (`auth/base.py`)

**Plan J-4:** `auth/assume_role.py` — `AssumeRoleStrategy`
- File: `src/aws_eks_helm_deploy/auth/assume_role.py`
- Test: `tests/unit/test_assume_role.py` (requires `@mock_aws`)
- Dependencies: Wave 1 (`auth/base.py`), Wave 2 (`auth/static_keys.py` or any `AuthStrategy`-conforming base)

Plans J-3 and J-4 can ship in parallel since `AssumeRoleStrategy` depends on the `AuthStrategy`
Protocol (defined in Wave 1), not on `StaticKeysStrategy` specifically.

### Wave 3 — Composition and Wire-In (depend on all of Wave 2)

**Plan J-5:** `auth/__init__.py::select_strategy()` + `cli.py` wire-in
- File: `src/aws_eks_helm_deploy/auth/__init__.py` — `select_strategy(settings: Settings) -> AuthStrategy`
- Edit: `src/aws_eks_helm_deploy/cli.py` — call `select_strategy(settings)` in `main()`, bind `auth_strategy` name to structlog context via `bind_safe_context(auth_strategy=type(strategy).__name__)`
- Test: `tests/unit/test_auth_select.py` — all decision-tree branches
- Dependencies: all of Wave 2

**Plan J-6:** Integration test + acceptance verification
- Test: `tests/integration/test_auth_smoke.py`
- Verify: `docker history` check; image size delta measurement
- Dependencies: Wave 3 (all modules complete)

---

## K. Module File Layout

```
src/aws_eks_helm_deploy/
├── auth/
│   ├── __init__.py          # select_strategy(settings) — Wave 3
│   ├── base.py              # AuthStrategy Protocol + AwsCredentials — Wave 1
│   ├── static_keys.py       # StaticKeysStrategy — Wave 2
│   └── assume_role.py       # AssumeRoleStrategy — Wave 2
└── aws/
    ├── __init__.py          # empty — Wave 1
    └── eks_token.py         # generate_eks_token() — Wave 1

tests/unit/
├── test_auth_base.py        # Wave 1
├── test_eks_token.py        # Wave 1
├── test_static_keys.py      # Wave 2
├── test_assume_role.py      # Wave 2
└── test_auth_select.py      # Wave 3

tests/integration/
└── test_auth_smoke.py       # Wave 3
```

---

## L. Coding Conventions (from Phase 1 PATTERNS.md)

All new modules must follow the established Phase 1 patterns:

1. `from __future__ import annotations` as first non-docstring line in every `src/` file
2. Docstrings on all public classes and functions (ruff `ANN` rule is enforced)
3. Raise typed `PipeError` subclasses; catch only in `cli.main()`
4. Never call `os.environ.get(...)` outside `settings.py`
5. Never bind raw credential values to structlog context — use `bind_safe_context()` only
6. `@pytest.mark.unit` is the default tier (via `addopts = "-m 'unit'"` in `pyproject.toml`)
7. Integration tests need `@pytest.mark.integration` decorator
8. mypy strict mode: `src/` must pass `mypy --strict src/` — annotate all function signatures

**ruff rule note:** The ruff config includes `"BLE"` (blind except) and `"S"` (bandit). Ensure
`except botocore.exceptions.ClientError` is always followed by re-raising as a `PipeError`
subclass (not swallowed). The `"ANN"` rule requires return type annotations on all public methods.

---

## References

### Primary Sources

- **awscli EKS get_token source** — `https://github.com/aws/aws-cli/blob/develop/awscli/customizations/eks/get_token.py`
  Authoritative Python implementation. Defines `TOKEN_PREFIX`, `K8S_AWS_ID_HEADER`, `URL_TIMEOUT`,
  `TOKEN_EXPIRATION_MINS`, `STSClientFactory` event-injection pattern, `TokenGenerator` class.

- **aws-iam-authenticator Go source** — `https://github.com/kubernetes-sigs/aws-iam-authenticator/blob/master/pkg/token/token.go`
  Reference Go implementation. Confirms `v1Prefix = "k8s-aws-v1."`, `clusterIDHeader = "x-k8s-aws-id"`,
  `requestPresignParam = 60`, `base64.RawURLEncoding` (no padding).

- **moto getting started** — `https://docs.getmoto.org/en/latest/docs/getting_started.html`
  Confirms `from moto import mock_aws` as the correct moto 5.x import; `@mock_aws` as unified decorator.

- **moto STS docs** — `https://docs.getmoto.org/en/latest/docs/services/sts.html`
  Confirms `assume_role`, `get_caller_identity` supported. Presigned URL generation works via
  botocore local signing (verified experimentally).

- **STS GetCallerIdentity API** — `https://docs.aws.amazon.com/STS/latest/APIReference/API_GetCallerIdentity.html`
  Confirms no IAM permissions required for GetCallerIdentity.

### Verified in Project Venv

- boto3 1.43.31 + botocore 1.43.31: `generate_presigned_url` signature confirmed
- moto 5.2.2: `@mock_aws` works for STS assume_role, get_caller_identity, EKS describe_cluster,
  and presigned URL generation
- `mypy_boto3_sts.type_defs.CredentialsTypeDef` fields: `AccessKeyId`, `SecretAccessKey`,
  `SessionToken`, `Expiration`
- EKS token generation via botocore event injection: confirmed `X-Amz-SignedHeaders=host;x-k8s-aws-id`
  and `X-Amz-Expires=60` in generated URL

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | "Golden test" means structural equivalence (token format properties), not byte-for-byte comparison | A | Low — bytes can never be equal across invocations (timestamp + HMAC vary) |
| A2 | RoleSessionName max length is 64 chars | E | Low — truncation to [:64] is safe regardless |
| A3 | v1 awscli adds ~100-120 MB to the image | F | Low — image size claim is informational, measured at build time |
| A4 | `dataclass(frozen=True)` cold-import is ~40-60 ms cheaper than Pydantic | D | Negligible — this is a style justification, not a performance gate |

---

## Confidence Breakdown

| Area | Level | Reason |
|------|-------|--------|
| EKS token algorithm | HIGH | Verified by running exact code in project venv; confirmed against awscli upstream source |
| AuthStrategy Protocol design | HIGH | Verified Protocol structural subtyping, frozen dataclass, repr masking in project venv |
| moto 5.x API | HIGH | Confirmed `mock_aws` decorator, STS and EKS support in installed moto 5.2.2 |
| boto3 event injection pattern | HIGH | Verified generates correct `X-Amz-SignedHeaders` including `x-k8s-aws-id` |
| Package legitimacy | HIGH | All packages already installed and validated in Phase 1 |
| Integration test scope | MEDIUM | kind-cluster test coverage of auth is necessarily limited without real AWS |
| Image size reduction claim | MEDIUM | Structural claim verified (awscli absent from Dockerfile); exact MB requires build-time measurement |
