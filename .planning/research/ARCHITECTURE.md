# Architecture Research

**Domain:** Typed Python CI-Pipe container (Bitbucket Pipelines Pipe, OCI-distributed CLI wrapping `helm` + AWS APIs)
**Researched:** 2026-06-16
**Confidence:** HIGH (project structure, auth strategy, test pyramid, multi-arch build — all converge on a single state-of-the-art answer in 2026); MEDIUM (docs site choice — mkdocs-material is recommended but README-only is defensible)

## Standard Architecture

### System Overview

A CI Pipe container is a single-shot CLI. There is no daemon, no request loop. The architecture is a **linear pipeline driven by env vars**, with a small set of orthogonal collaborators behind clean ports.

```
┌──────────────────────────────────────────────────────────────────────┐
│                     Pipe Entry Point (cli.py)                         │
│  - parse env vars → typed Settings (pydantic) via PipeAdapter         │
│  - dispatch to Action handler                                         │
│  - write success/fail to stdout via bitbucket-pipes-toolkit           │
└────────┬─────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       Action Layer (actions/)                         │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐      │
│  │  UpgradeAction   │ │   DiffAction     │ │ RollbackAction   │      │
│  │ (upgrade --inst) │ │ (helm diff up.)  │ │ (helm rollback)  │      │
│  └────────┬─────────┘ └────────┬─────────┘ └─────────┬────────┘      │
└───────────┼────────────────────┼───────────────────────┼─────────────┘
            │                    │                       │
            ▼                    ▼                       ▼
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│   AuthStrategy       │  │     ChartSource      │  │      HelmClient      │
│   (Protocol)         │  │     (Protocol)       │  │   (typed wrapper)    │
│ ┌──────────────────┐ │  │ ┌──────────────────┐ │  │ - upgrade_install()  │
│ │ StaticKeysAuth   │ │  │ │ LocalPathSource  │ │  │ - diff_upgrade()     │
│ │ AssumeRoleAuth   │ │  │ │ HelmRepoSource   │ │  │ - rollback()         │
│ │ OidcWebIdentity  │ │  │ │ OciRegistrySrc   │ │  │ - history()          │
│ └──────────────────┘ │  │ └──────────────────┘ │  │ (subprocess + JSON)  │
└──────────┬───────────┘  └──────────┬───────────┘  └──────────┬───────────┘
           │                          │                         │
           ▼                          ▼                         ▼
┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│   AWS Adapter        │   │   chart fetched      │   │   helm binary        │
│ (boto3 sessions,     │   │   (path on disk      │   │   (incl. helm-diff   │
│  EKS describe-cluster│   │   or OCI ref string) │   │   plugin in image)   │
│  STS, presigned URL  │   └──────────────────────┘   └──────────────────────┘
│  EKS token gen)      │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  KubeconfigWriter — writes a tempfile kubeconfig from cluster        │
│  metadata + per-call EKS token; sets KUBECONFIG env for HelmClient   │
└──────────────────────────────────────────────────────────────────────┘
```

Key insight: **`HelmClient` never knows how auth works**. It only ever sees a `KUBECONFIG` env var on its subprocess. The `AuthStrategy` produces an `AwsCredentials` object → `AwsAdapter` produces a `ClusterAccess` value object → `KubeconfigWriter` produces a kubeconfig file. The helm path is identical for static keys, `ROLE_ARN`, and OIDC. **Adding a fourth auth strategy = new file, zero changes elsewhere.**

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `cli` | Entry point. Parse env, dispatch action, emit pipe success/fail. No business logic. | `python -m aws_eks_helm_deploy` |
| `settings` | Typed, validated env-var schema. Single source of truth for variable names, defaults, coercion. | `pydantic-settings` `BaseSettings` |
| `pipe_io` | Thin adapter over `bitbucket-pipes-toolkit` (`success`/`fail`/`log_info`). Isolates the toolkit dependency. | Wraps `bitbucket_pipes_toolkit.Pipe` |
| `actions` | One module per `ACTION`. Orchestrates auth → chart → helm. Knows nothing about subprocess. | `UpgradeAction.run(settings) -> Result` |
| `auth` | `AuthStrategy` Protocol + concrete strategies. Produces `AwsCredentials`. | `Protocol` + 3 classes |
| `aws` | Boto3 wrapper. `describe_cluster`, EKS token generation (presigned STS URL → base64). | Pure `boto3`, no `awscli` |
| `kube` | Renders a kubeconfig file from `ClusterAccess`. Returns a context manager (tempfile cleanup). | Jinja2 template or hand-rolled dict→YAML |
| `chart` | `ChartSource` Protocol. Resolves `CHART` env (`./path`, `repo://`, `oci://`) to a concrete `ResolvedChart`. | 3 concrete sources |
| `helm` | Typed wrapper around the `helm` binary. One method per subcommand. Returns parsed results. | `subprocess.run` + stdout parsing |
| `metadata` | Builds Bitbucket-metadata `--set` injection list. Toggled by `INJECT_BITBUCKET_METADATA`. | Pure function |
| `errors` | Typed exception hierarchy. Maps internal errors to pipe-friendly exit messages. | Plain `Exception` subclasses |
| `logging` | Structured logging (`structlog` or stdlib `logging` with JSON formatter). Honours `DEBUG`. | stdlib + JSON renderer |

## Recommended Project Structure

```
aws-eks-helm-deploy/
├── pyproject.toml                          # uv-managed; src layout, ruff, mypy, pytest config
├── uv.lock
├── README.md
├── CHANGELOG.md                            # release-please generated
├── LICENSE                                 # Apache-2.0
├── pipe.yml                                # Bitbucket Pipes Marketplace manifest
├── Dockerfile                              # multi-stage, multi-arch
├── .dockerignore
│
├── src/
│   └── aws_eks_helm_deploy/
│       ├── __init__.py                     # __version__ (read from package metadata)
│       ├── __main__.py                     # `python -m aws_eks_helm_deploy` → cli.main()
│       ├── cli.py                          # entry point: build Settings, dispatch action
│       ├── settings.py                     # pydantic-settings BaseSettings (env schema)
│       ├── pipe_io.py                      # bitbucket-pipes-toolkit adapter
│       ├── errors.py                       # exception hierarchy
│       ├── logging.py                      # structured logging setup
│       │
│       ├── actions/                        # one module per ACTION
│       │   ├── __init__.py                 # ACTIONS: dict[str, type[Action]]
│       │   ├── base.py                     # Action ABC / Protocol
│       │   ├── upgrade.py                  # ACTION=upgrade (default): helm upgrade --install
│       │   ├── diff.py                     # DRY_RUN=true or ACTION=diff: helm diff upgrade
│       │   └── rollback.py                 # ACTION=rollback: helm rollback REVISION
│       │
│       ├── auth/                           # auth strategy abstraction
│       │   ├── __init__.py                 # select_strategy(settings) → AuthStrategy
│       │   ├── base.py                     # AuthStrategy Protocol, AwsCredentials dataclass
│       │   ├── static_keys.py              # StaticKeysStrategy
│       │   ├── assume_role.py              # AssumeRoleStrategy (chained on top of static or OIDC)
│       │   └── oidc.py                     # OidcWebIdentityStrategy (Bitbucket OIDC → STS)
│       │
│       ├── aws/                            # pure boto3, no awscli
│       │   ├── __init__.py
│       │   ├── session.py                  # build Session from AwsCredentials
│       │   ├── eks.py                      # describe_cluster, ClusterAccess value object
│       │   └── eks_token.py                # presigned STS URL → base64 EKS token (replaces awscli internal import)
│       │
│       ├── kube/
│       │   ├── __init__.py
│       │   └── kubeconfig.py               # write_kubeconfig(cluster_access, token) -> ContextManager[Path]
│       │
│       ├── chart/                          # chart source abstraction
│       │   ├── __init__.py                 # resolve(settings) → ChartSource → ResolvedChart
│       │   ├── base.py                     # ChartSource Protocol, ResolvedChart dataclass
│       │   ├── local.py                    # ./relative/path
│       │   ├── repo.py                     # repo://name/chart with REPO_URL + CHART_VERSION
│       │   └── oci.py                      # oci://registry/chart with CHART_VERSION
│       │
│       ├── helm/
│       │   ├── __init__.py
│       │   ├── client.py                   # HelmClient: typed subprocess wrapper
│       │   ├── args.py                     # ArgBuilder: builds argv from ResolvedChart + values + flags
│       │   └── exceptions.py               # HelmError, HelmTimeoutError, ChartNotFoundError
│       │
│       └── metadata/
│           ├── __init__.py
│           └── bitbucket.py                # build --set bitbucket.* from env (if INJECT_BITBUCKET_METADATA)
│
├── tests/
│   ├── conftest.py                         # shared fixtures (fake AWS session, fake helm bin)
│   ├── unit/                               # pytest, fully mocked, 100% line+branch
│   │   ├── test_settings.py
│   │   ├── test_cli.py
│   │   ├── auth/
│   │   │   ├── test_static_keys.py
│   │   │   ├── test_assume_role.py
│   │   │   └── test_oidc.py
│   │   ├── aws/
│   │   │   ├── test_eks.py
│   │   │   └── test_eks_token.py           # critical: presigned URL must equal awscli's reference output
│   │   ├── chart/
│   │   │   ├── test_local.py
│   │   │   ├── test_repo.py
│   │   │   └── test_oci.py
│   │   ├── helm/
│   │   │   ├── test_args.py
│   │   │   └── test_client.py              # subprocess mocked
│   │   ├── actions/
│   │   │   ├── test_upgrade.py
│   │   │   ├── test_diff.py
│   │   │   └── test_rollback.py
│   │   └── test_metadata.py
│   │
│   ├── integration/                        # real helm against kind/k3d, mocked AWS (moto or LocalStack)
│   │   ├── conftest.py                     # kind cluster lifecycle, helm binary discovery
│   │   ├── test_upgrade_install.py
│   │   ├── test_diff_upgrade.py
│   │   ├── test_rollback.py
│   │   ├── test_oci_chart.py               # against a local OCI registry container
│   │   └── test_repo_chart.py
│   │
│   └── acceptance/                         # docker build + docker run; exercises real toolkit + entrypoint
│       ├── conftest.py                     # build image once per session
│       ├── test_pipe_upgrade.py
│       ├── test_pipe_dry_run.py
│       ├── test_pipe_rollback.py
│       └── fixtures/
│           ├── helm-stub                   # tiny shell stub replacing /usr/local/bin/helm for hermetic runs
│           └── charts/                     # minimal test chart
│
├── docs/                                   # mkdocs-material site, deployed to GitHub Pages
│   ├── mkdocs.yml                          # mike-aware versioned docs config
│   ├── overrides/                          # mkdocs-material partial overrides if needed
│   ├── index.md
│   ├── quickstart.md
│   ├── reference/
│   │   ├── variables.md                    # generated from settings.py (script in scripts/)
│   │   ├── actions.md
│   │   └── auth.md
│   ├── guides/
│   │   ├── oidc-setup.md
│   │   ├── oci-charts.md
│   │   └── dry-run.md
│   ├── migration/
│   │   └── v1-to-v2.md
│   ├── adr/                                # ADRs (also linked from root README)
│   │   ├── 0001-github-primary-forge.md
│   │   ├── 0002-oidc-over-static-keys.md
│   │   ├── 0003-boto3-only-eks-token.md
│   │   ├── 0004-cosign-keyless-signing.md
│   │   ├── 0005-mkdocs-material-versioned.md
│   │   └── 0006-helm-version-pinning.md
│   └── v1/                                 # frozen snapshot of v1.x README + variables
│       └── …
│
├── examples/
│   ├── basic.bitbucket-pipelines.yml
│   ├── oidc.bitbucket-pipelines.yml
│   ├── oci-chart.bitbucket-pipelines.yml
│   ├── multi-env.bitbucket-pipelines.yml
│   └── dry-run-on-pr.bitbucket-pipelines.yml
│
├── scripts/
│   ├── generate-variables-doc.py           # introspect settings.py → docs/reference/variables.md
│   └── verify-pipe-yml.py                  # ensure pipe.yml variables ⊆ settings.py
│
└── .github/
    ├── workflows/
    │   ├── ci.yml                          # lint + type + unit + integration on every PR
    │   ├── acceptance.yml                  # acceptance tests (Docker image) on PR + main
    │   ├── release.yml                     # release-please + buildx + cosign + ghcr + dockerhub
    │   ├── docs.yml                        # mkdocs build + mike deploy to gh-pages
    │   ├── security.yml                    # trivy + grype + pip-audit on schedule + PR
    │   └── dependabot-auto-merge.yml
    ├── dependabot.yml
    ├── ISSUE_TEMPLATE/
    │   ├── bug_report.yml
    │   └── feature_request.yml
    ├── PULL_REQUEST_TEMPLATE.md
    └── CODEOWNERS
```

### Structure Rationale

- **`src/` layout:** Forces the test suite to import the *installed* package, not the working copy. Catches missing `__init__.py`, missing `MANIFEST.in`-style packaging bugs, and import-order quirks before they hit users. Standard in 2026 for any published Python package.
- **`actions/` as a folder, one module per `ACTION`:** The dispatch table is `ACTIONS = {"upgrade": UpgradeAction, "diff": DiffAction, "rollback": RollbackAction}`. Adding `helm uninstall` later is one new file + one dict entry. The entry point stays five lines.
- **`auth/`, `chart/` as Protocol-backed packages:** These are the two real polymorphism points. Each has a `base.py` defining the Protocol + value object, and one file per concrete strategy. **You can write a new strategy without touching any other file.**
- **`aws/` separate from `auth/`:** `auth/` produces `AwsCredentials`; `aws/` *consumes* them to call EKS/STS. This split lets you unit-test EKS token generation against a recorded STS response without dragging the strategy hierarchy into the fixture.
- **`helm/` isolates the subprocess boundary:** Every other module talks to `HelmClient` via typed methods. Only `helm/client.py` calls `subprocess.run`. Mocking is trivial; replacing the binary with a stub in acceptance tests is trivial.
- **Three test tiers in separate folders:** `unit/` is the dev-loop tier (millisecond feedback, full mocking, target 100%). `integration/` runs real helm against `kind`/`k3d` with mocked AWS (`moto`) — proves the helm argv builder produces working invocations. `acceptance/` runs the actual Docker image — proves the toolkit contract is honoured. Each tier has its own conftest, its own dependencies, and is selectable via `pytest -m unit` etc.
- **`docs/` with `mkdocs-material` + `mike`:** Versioned docs are non-negotiable when v1.x users coexist with v2.x users. `mike` is the canonical mkdocs versioning plugin (`mike deploy 2.0`, `mike set-default 2.0`). v1 docs are a frozen snapshot under `docs/v1/`; the README in the repo root points to the docs site and surfaces a short quickstart for marketplace browsers.
- **`scripts/generate-variables-doc.py`:** The env-var schema is defined exactly once in `settings.py`. The reference docs and the `pipe.yml` `variables:` block are *generated* from it. No more drift between README and `pipe.yml` (which is how the v1 `NAMESPACE` bug happened).
- **`examples/`:** Marketplace consumers copy-paste from here. Each file is a complete, runnable `bitbucket-pipelines.yml`.

## Architectural Patterns

### Pattern 1: AuthStrategy via `Protocol`

**What:** A single `Protocol` (`AuthStrategy`) with one method `resolve(session_factory) -> AwsCredentials`. Concrete strategies are independent classes; selection is a pure function of `Settings`.

**When to use:** Always — this is the central abstraction that makes the Pipe extensible without touching the helm path.

**Trade-offs:** Slightly more indirection than a chain of `if/elif` in `cli.py`. Worth it because (a) v2.0 has three strategies on day one, (b) mocking is trivial, (c) the next strategy (e.g. EKS Pod Identity for self-hosted runners) is purely additive.

**Example:**

```python
# src/aws_eks_helm_deploy/auth/base.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True, slots=True)
class AwsCredentials:
    access_key_id: str
    secret_access_key: str
    session_token: str | None
    region: str

class AuthStrategy(Protocol):
    def resolve(self) -> AwsCredentials: ...

# src/aws_eks_helm_deploy/auth/__init__.py
def select_strategy(settings: Settings) -> AuthStrategy:
    base: AuthStrategy
    if settings.bitbucket_step_oidc_token:           # OIDC takes precedence
        base = OidcWebIdentityStrategy(settings)
    elif settings.aws_access_key_id:
        base = StaticKeysStrategy(settings)
    else:
        raise ConfigurationError("no AWS credentials configured")
    if settings.role_arn:                            # ROLE_ARN composes on top
        return AssumeRoleStrategy(base, settings.role_arn)
    return base
```

The `AssumeRoleStrategy` *wraps* another `AuthStrategy` — composition, not inheritance. `ROLE_ARN` works with both static keys and OIDC out of the box.

### Pattern 2: Action Dispatch (Command pattern, trivial form)

**What:** `ACTION` env var selects one of `{"upgrade", "diff", "rollback"}`. Each action implements a uniform `run(settings, deps) -> ActionResult` contract. `DRY_RUN=true` is sugar that rewrites `ACTION` to `"diff"` at the CLI layer.

**When to use:** As soon as you have more than one verb. v1 only had upgrade; v2 has three on day one and `uninstall` is a likely v2.1.

**Trade-offs:** vs. a single `do_helm()` function with flags: actions are explicit, testable in isolation, and the success/fail message can be specialised per action.

**Example:**

```python
# src/aws_eks_helm_deploy/actions/base.py
class Action(Protocol):
    name: str
    def run(self, settings: Settings, deps: Deps) -> ActionResult: ...

# src/aws_eks_helm_deploy/cli.py
def main(argv: list[str] | None = None) -> int:
    settings = Settings()  # reads env via pydantic-settings
    pipe = PipeIO()
    try:
        action_name = "diff" if settings.dry_run else settings.action
        action_cls = ACTIONS[action_name]
        deps = build_deps(settings)             # wires AuthStrategy, ChartSource, HelmClient
        result = action_cls().run(settings, deps)
        pipe.success(result.message)
        return 0
    except PipeError as exc:
        pipe.fail(str(exc))
        return exc.exit_code
```

### Pattern 3: ChartSource Protocol

**What:** Mirrors `AuthStrategy`. `ChartSource.resolve() -> ResolvedChart` returns either a local path or an OCI/repo reference string + version. `HelmClient` accepts a `ResolvedChart` and renders the right argv.

**When to use:** From day one — v2 supports `./path`, `repo://name/chart`, and `oci://reg/chart` simultaneously.

**Trade-offs:** A tagged-union with `match` would be terser; the Protocol gives you a place to put the "add helm repo first" side-effect that only the `HelmRepoSource` needs.

```python
# src/aws_eks_helm_deploy/chart/base.py
@dataclass(frozen=True, slots=True)
class ResolvedChart:
    reference: str          # "./chart" | "oci://…/chart" | "repo-alias/chart"
    version: str | None     # passed as --version
    repo_setup: RepoSetup | None  # if not None, run `helm repo add` before upgrade

class ChartSource(Protocol):
    def resolve(self) -> ResolvedChart: ...
```

### Pattern 4: Typed `HelmClient` (one method per verb)

**What:** Replace `subprocess.run(["helm", ...])` + `BaseException` with a class whose every public method is named after a helm subcommand and accepts typed parameters. Returns a parsed `HelmResult` (release name, revision, status). Failures raise typed exceptions.

**When to use:** Always — this is the surface that the v1 `BaseException` catch-all hid behind.

**Trade-offs:** More code than `subprocess.run`. But: every helm flag is now a named, type-checked parameter; every error has a typed exception; every method is mockable in unit tests with one `MagicMock`; and the JSON output of `helm` (where available) is parsed into dataclasses, so action code never deals with stdout strings.

```python
# src/aws_eks_helm_deploy/helm/client.py
class HelmClient:
    def __init__(self, binary: str = "helm", env: Mapping[str, str] | None = None) -> None: ...

    def upgrade_install(
        self,
        release: str,
        chart: ResolvedChart,
        *,
        namespace: str,
        create_namespace: bool = False,
        values_files: Sequence[Path] = (),
        set_values: Sequence[tuple[str, str]] = (),
        wait: bool = False,
        timeout: str = "5m",
        history_max: int | None = None,
    ) -> HelmResult: ...

    def diff_upgrade(self, release: str, chart: ResolvedChart, **kwargs: Any) -> DiffResult: ...

    def rollback(self, release: str, revision: int, *, wait: bool = False, timeout: str = "5m") -> HelmResult: ...

    def history(self, release: str, *, max_entries: int = 10) -> list[HistoryEntry]: ...
```

`actions/upgrade.py`, `actions/diff.py`, `actions/rollback.py` each call exactly one of these methods. **Adding a new action means adding a new method on `HelmClient` and a new file in `actions/`** — same pattern, no surprises.

### Pattern 5: Dependency injection via a `Deps` dataclass

**What:** `cli.py` calls a `build_deps(settings) -> Deps` factory that returns a frozen dataclass holding `auth`, `chart_source`, `helm_client`, `pipe_io`, `clock`. Actions accept `Deps` as a parameter. In tests, `Deps(...)` is constructed with fakes.

**When to use:** Always for testability. This is what makes unit-testing actions trivial without monkeypatching.

**Trade-offs:** Mild boilerplate vs. module-level globals. Worth it 1000×.

## Data Flow

### Invocation Flow (Bitbucket → cluster)

```
Bitbucket Pipelines runner
    │   (sets BITBUCKET_*, AWS_*, CLUSTER_NAME, CHART, … in container env)
    ▼
docker run yvogl/aws-eks-helm-deploy:2.0
    │
    ▼
ENTRYPOINT: python -m aws_eks_helm_deploy
    │
    ▼
cli.main()
    │  Settings() — pydantic-settings reads & validates all env vars
    ▼
select_strategy(settings) ───────────► AuthStrategy
    │                                   │ .resolve()
    │                                   ▼
    │                                  AwsCredentials  (one of: static / STS-assumed / OIDC-exchanged)
    │
    ▼
build_deps(settings) ───► AwsSession (boto3.Session with creds)
    │                       │
    │                       ▼
    │                     eks.describe_cluster(CLUSTER_NAME)
    │                       │
    │                       ▼
    │                     ClusterAccess(endpoint, ca_data, name, region)
    │                       │
    │                       ▼
    │                     eks_token.generate(cluster_name, session)
    │                       │  (signs presigned STS GetCallerIdentity URL,
    │                       │   base64-url encodes with "k8s-aws-v1." prefix)
    │                       ▼
    │                     EksAuthToken(value=..., expires_at=...)
    │                       │
    │                       ▼
    │                     kubeconfig.write(ClusterAccess, EksAuthToken)
    │                       │
    │                       ▼
    │                     Path(/tmp/kubeconfig-XXXX)  (context-managed; deleted on exit)
    │
    ▼
chart.resolve(settings) ───► ChartSource ─► ResolvedChart
    │                                        │
    │                                        ▼ (if HelmRepoSource) helm repo add NAME URL
    │
    ▼
action = ACTIONS[settings.action or "diff" if dry_run]
    │
    ▼
action.run(settings, deps)
    │
    │ UpgradeAction:
    │     helm_client.upgrade_install(release, chart, namespace=…, …)
    │ DiffAction:
    │     helm_client.diff_upgrade(release, chart, …)
    │ RollbackAction:
    │     helm_client.rollback(release, revision, …)
    │
    ▼
HelmClient.<method>()
    │  subprocess.run(["helm", "upgrade", "--install", release, chart.reference,
    │                  "--namespace", ns, …],
    │                  env={**os.environ, "KUBECONFIG": str(kubeconfig_path)},
    │                  check=False, capture_output=True, text=True, timeout=…)
    │
    ▼
HelmResult(release=…, revision=N, status="deployed", stdout=…, stderr=…)
    │
    ▼
pipe.success(f"Deployed release {release} (rev {revision}) to {cluster_name}/{namespace}")
    │
    ▼
exit 0
```

### Error Flow

```
Any layer raises PipeError subclass
    │  - ConfigurationError       (exit 1)  — bad/missing env var
    │  - AuthenticationError      (exit 2)  — STS/OIDC failed
    │  - ClusterAccessError       (exit 3)  — describe-cluster failed
    │  - ChartResolutionError     (exit 4)  — chart not found / version missing
    │  - HelmError                (exit 5)  — helm exited non-zero (with parsed stderr)
    │  - HelmTimeoutError         (exit 6)  — wait timed out
    ▼
cli.main() catches PipeError
    ▼
pipe.fail(error.user_message)   # bitbucket-pipes-toolkit emits styled red output
    ▼
exit error.exit_code
```

Bare `Exception` (anything unexpected) → exit 99 with stack trace in logs, generic message to user.

### State

**There is no persistent state.** The Pipe is a single-shot CLI. The only "state" is:
- The tempfile kubeconfig (lifetime: one invocation, deleted on exit).
- Helm's own release history, which lives in the cluster as Secrets — out of our concern.

This is why scaling is a non-issue: every invocation is independent.

## Build Order Implications for v2.0

The dependency graph dictates the phase ordering. **Build the abstractions before the second concrete implementation of each.**

```
Phase 0: Toolchain bootstrap
    pyproject.toml + uv + ruff + mypy --strict + pytest skeleton
    src/ layout with empty __init__.py
    │
    ▼
Phase 1: Settings + PipeIO + errors + logging  (the spine)
    settings.py (pydantic-settings) covering all v1 vars
    pipe_io.py wrapping bitbucket-pipes-toolkit
    errors.py with typed hierarchy
    logging.py
    │
    ▼
Phase 2: AWS layer — pure boto3 EKS token (kill awscli dependency)
    aws/session.py, aws/eks.py, aws/eks_token.py
    Golden test: token matches `aws eks get-token` output byte-for-byte
    │
    ▼
Phase 3: AuthStrategy abstraction + StaticKeys + AssumeRole
    auth/base.py, auth/static_keys.py, auth/assume_role.py
    (parity with v1 — no behavioural change yet, just typed)
    │
    ▼
Phase 4: Kube + HelmClient (typed wrapper) + UpgradeAction
    kube/kubeconfig.py, helm/client.py, helm/args.py
    actions/upgrade.py — replicates v1 upgrade --install behaviour
    Integration tests against kind
    ───────────────────────────────────────────────
    ★ At this point v2 has v1 parity, fully typed, fully tested ★
    ───────────────────────────────────────────────
    │
    ▼
Phase 5: OIDC strategy   (additive — auth/oidc.py only)
    auth/oidc.py — exchanges BITBUCKET_STEP_OIDC_TOKEN at STS
    Composes with AssumeRoleStrategy for free
    │
    ▼
Phase 6: ChartSource abstraction + LocalPath + HelmRepo + OCI
    chart/base.py, chart/local.py, chart/repo.py, chart/oci.py
    HelmClient learns to handle ResolvedChart
    │
    ▼
Phase 7: DiffAction + RollbackAction + HISTORY_MAX
    actions/diff.py (requires helm-diff plugin in image)
    actions/rollback.py
    │
    ▼
Phase 8: INJECT_BITBUCKET_METADATA flip (breaking)
    metadata/bitbucket.py, default=false
    │
    ▼
Phase 9: Multi-arch image + Cosign + SBOM + Trivy in CI
    Dockerfile multi-stage; buildx amd64+arm64; release.yml
    │
    ▼
Phase 10: Docs site (mkdocs-material + mike) + migration guide + examples
    Variable reference auto-generated from settings.py
```

**Critical ordering invariants:**
1. **Settings before everything.** Every module's signature depends on the typed shape of settings. Getting `Settings` wrong cascades.
2. **AuthStrategy abstraction (Phase 3) before OIDC (Phase 5).** Build the Protocol with two strategies first; OIDC is then a pure addition. If you build OIDC inline and refactor later, you re-derive the abstraction from one example — bad shape risk.
3. **HelmClient + UpgradeAction (Phase 4) before DiffAction/RollbackAction (Phase 7).** The wrapper's shape stabilises against the most-used verb first.
4. **ChartSource (Phase 6) is independent of OIDC (Phase 5).** These two can run in parallel sub-phases if you have the bandwidth — they touch disjoint files.
5. **Multi-arch image (Phase 9) after the code is feature-complete.** Multi-arch buildx is slow to iterate on; do it once when the source has stopped changing for a moment.

## Docker Image Architecture

### Multi-Stage Multi-Arch Dockerfile

```dockerfile
# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.13
ARG HELM_VERSION=3.16.4
ARG HELM_DIFF_VERSION=3.10.0

# ── Stage 1: builder ──────────────────────────────────────────────────
FROM --platform=$BUILDPLATFORM python:${PYTHON_VERSION}-alpine AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /build
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
# Resolves and installs into a venv (cross-arch safe — pure Python)
RUN uv sync --frozen --no-dev --compile-bytecode

# ── Stage 2: helm fetch (per target arch) ─────────────────────────────
FROM --platform=$TARGETPLATFORM alpine:3.20 AS helm
ARG HELM_VERSION
ARG TARGETARCH
RUN apk add --no-cache curl tar \
 && curl -fsSL "https://get.helm.sh/helm-v${HELM_VERSION}-linux-${TARGETARCH}.tar.gz" \
    | tar -xz -C /tmp \
 && mv "/tmp/linux-${TARGETARCH}/helm" /helm \
 && chmod +x /helm

# ── Stage 3: runtime ──────────────────────────────────────────────────
FROM --platform=$TARGETPLATFORM python:${PYTHON_VERSION}-alpine AS runtime
ARG HELM_DIFF_VERSION
RUN apk add --no-cache git ca-certificates  # git: helm-diff plugin install
COPY --from=builder /build/.venv /opt/venv
COPY --from=helm /helm /usr/local/bin/helm
ENV PATH="/opt/venv/bin:${PATH}" \
    HELM_PLUGINS=/root/.local/share/helm/plugins \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN helm plugin install https://github.com/databus23/helm-diff --version "v${HELM_DIFF_VERSION}"
# OCI annotations are added at buildx time via --label / --annotation

ENTRYPOINT ["python", "-m", "aws_eks_helm_deploy"]
```

### Multi-Arch Build (GitHub Actions)

```yaml
# .github/workflows/release.yml (excerpt)
- uses: docker/setup-qemu-action@v3
- uses: docker/setup-buildx-action@v3
- uses: docker/build-push-action@v6
  with:
    context: .
    platforms: linux/amd64,linux/arm64
    push: true
    provenance: mode=max
    sbom: true
    tags: |
      yvogl/aws-eks-helm-deploy:2.0
      yvogl/aws-eks-helm-deploy:latest
      ghcr.io/yves-vogl/aws-eks-helm-deploy:2.0
      ghcr.io/yves-vogl/aws-eks-helm-deploy:latest
    annotations: |
      index:org.opencontainers.image.source=https://github.com/yves-vogl/aws-eks-helm-deploy
      index:org.opencontainers.image.licenses=Apache-2.0
      index:org.opencontainers.image.description=Deploy Helm charts to AWS EKS from Bitbucket Pipelines
- uses: sigstore/cosign-installer@v3
- run: cosign sign --yes ghcr.io/yves-vogl/aws-eks-helm-deploy@${{ steps.build.outputs.digest }}
```

**Why this shape:**
- **`--platform=$BUILDPLATFORM` on the Python builder stage:** Python wheel resolution runs once on the native architecture, not under QEMU emulation. Cuts build time roughly in half on amd64-only CI runners doing arm64 cross-build.
- **`--platform=$TARGETPLATFORM` on the helm fetch and runtime stages:** these stages contain arch-specific binaries.
- **Helm fetched in a separate stage:** clean copy, no curl/tar in final image.
- **`helm-diff` plugin baked in:** required for `DRY_RUN`; installing at runtime would add 5–10s and require network access.
- **`uv sync --frozen --compile-bytecode`:** lockfile-pinned, pre-compiled `.pyc`, no `pip` in the final image.
- **`provenance: mode=max` + `sbom: true`:** SLSA build provenance + SPDX SBOM, both attached as OCI attestations. Cosign signs the index, which transitively covers both arches.
- **OCI annotations on the index (not just the manifests):** so `docker buildx imagetools inspect` shows the metadata.

## Test Strategy

### Test Pyramid

```
                            ┌─────────────────────┐
                            │   Acceptance (~10)  │   docker build + docker run
                            │   GitHub Actions    │   real toolkit, stubbed helm
                            └─────────────────────┘
                       ┌──────────────────────────────┐
                       │      Integration (~30)        │   real helm against kind/k3d
                       │      GitHub Actions matrix    │   mocked AWS (moto), local OCI registry
                       └──────────────────────────────┘
              ┌───────────────────────────────────────────────┐
              │                Unit (~250)                     │   pytest, full mocking
              │           pre-commit + every CI run            │   target: 100% line + branch
              └───────────────────────────────────────────────┘
```

| Tier | What it proves | Tooling | Where it runs | How long |
|------|----------------|---------|----------------|----------|
| Unit | Every module's logic is correct in isolation. Argv builders. EKS token byte-for-byte. Settings validation. Strategy selection. Action orchestration with fake `Deps`. | `pytest`, `pytest-cov` (line+branch, fail-under=100), `pytest-mock`, `freezegun`. AWS mocked at boto3 layer or with `moto`. Helm mocked at `HelmClient` layer. | Locally + GitHub Actions on every PR | <10s |
| Integration | The helm argv we build actually drives a real helm against a real cluster. OCI charts pull. Repo charts pull. Rollback restores. Diff produces sensible output. | `pytest`, `kind` (or `k3d`), real `helm` binary, `moto` for AWS, ephemeral local OCI registry (`registry:2` container) | GitHub Actions matrix (kind on amd64; arm64 on best-effort) | ~3–5 min |
| Acceptance | The packaged Docker image, invoked as a real Pipe, honours the toolkit contract: env vars in, success/fail message out, exit code correct. | `pytest`, `docker build`, `docker run`, a shell stub for `helm` mounted at `/usr/local/bin/helm` for hermeticity. Image is built once per pytest session. | GitHub Actions (post-build); the original v1 acceptance tests inside Bitbucket Pipelines also retained as a final sanity check. | ~2 min |

**Boundary discipline:**
- Unit tests **must not** spawn subprocesses, hit the network, or touch the filesystem outside `tmp_path`.
- Integration tests **must not** require Docker (kind runs in `dind` on Actions but tests just need `kubectl`/`helm` clients).
- Acceptance tests **must** build the image — no shortcuts via `python -m aws_eks_helm_deploy` outside the container. They are the only tier that validates `Dockerfile` correctness, `pipe.yml` correctness, and the toolkit wiring.

**Markers (`pyproject.toml`):**

```toml
[tool.pytest.ini_options]
markers = [
  "unit: fast, no I/O, default tier",
  "integration: requires kind + helm binary",
  "acceptance: requires docker; builds image",
]
addopts = "-m 'unit' --cov=aws_eks_helm_deploy --cov-branch --cov-fail-under=100"
```

`pytest -m integration` and `pytest -m acceptance` opt into the heavier tiers.

## Documentation Architecture

**Recommendation: `mkdocs-material` + `mike` (versioned), deployed to GitHub Pages.**

- README in the repo root stays short: tagline, badges, quickstart, links to the docs site, marketplace link.
- `docs/` is the authoritative source.
- `mike` provides per-version subpaths (`/v1/`, `/v2/`, `/latest/`). Default points to `/v2/`. v1 docs are frozen.
- **Migration guide (`docs/migration/v1-to-v2.md`)** is the most-visited page on day one — it gets a top-level nav entry and a banner on `/v1/`.
- **Variable reference is generated** (`scripts/generate-variables-doc.py`) from `settings.py` to guarantee zero drift.
- ADRs live under `docs/adr/` and are also rendered as a docs-site section.

Why not README-only:
- Versioning v1 vs v2 docs in a single README is hostile to consumers.
- The variable reference, examples, ADRs, and migration guide together are far too much for one file.
- `mkdocs-material` is the de-facto standard in 2026 for Python-project docs; build is fast, search is built in, and GitHub Pages deployment is one workflow step.

## Component Dependency Graph

```
              ┌──────────────┐
              │   __main__   │
              └──────┬───────┘
                     ▼
              ┌──────────────┐
              │     cli      │
              └──┬──┬───┬─┬──┘
                 │  │   │ │
        ┌────────┘  │   │ └────────┐
        ▼           ▼   ▼          ▼
   ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐
   │settings │ │ pipe_io │ │  errors  │ │ logging  │
   └────┬────┘ └─────────┘ └──────────┘ └──────────┘
        │                       ▲ (raised by everything)
        │
        │              ┌────────┴────────────────────────────┐
        ▼              │                                      │
   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐ │
   │ actions  │──▶│   auth   │──▶│   aws    │──▶│   kube   │ │
   │          │   │ Protocol │   │ (boto3)  │   │  config  │ │
   └────┬─────┘   └──────────┘   └──────────┘   └─────┬────┘ │
        │                                              │      │
        │  ┌──────────┐                                │      │
        ├─▶│  chart   │                                │      │
        │  │ Protocol │                                │      │
        │  └──────────┘                                │      │
        │                                              │      │
        ▼                                              ▼      │
   ┌──────────┐                                  KUBECONFIG=… │
   │   helm   │◀─────────────────────────────────────────────┘
   │  client  │
   └────┬─────┘
        │ subprocess
        ▼
    [helm binary]
```

Arrows are "imports / depends on". Notice:
- `auth`, `chart`, `helm` are **siblings** under `actions`. They do not know about each other.
- `helm` only depends on `errors` (for its exceptions) and reads `KUBECONFIG` from its env. It is auth-agnostic and chart-source-agnostic.
- Every leaf module is independently testable.

## Anti-Patterns

### Anti-Pattern 1: Threading auth decisions through `HelmClient`

**What people do:** Pass `oidc_token` / `role_arn` into the helm wrapper so it can "set up auth" before calling helm.
**Why it's wrong:** Every new auth strategy now requires modifying the helm path. The v1 code drifted toward this; it's why adding OIDC was never finished.
**Do this instead:** Auth produces `AwsCredentials` → AWS layer produces `EksAuthToken` → kube layer writes a kubeconfig → helm sees `KUBECONFIG`. The boundary is `KUBECONFIG`, not credentials.

### Anti-Pattern 2: `subprocess.run` scattered across modules

**What people do:** Call `subprocess.run(["helm", …])` from `pipe.py`, again from `eks/`, again from `actions/`.
**Why it's wrong:** Mocking requires patching every call site. Error handling diverges. Timeouts are inconsistent.
**Do this instead:** One `HelmClient` class. One `subprocess.run`. Typed exceptions. The rest of the code never imports `subprocess`.

### Anti-Pattern 3: Catching `BaseException`

**What people do:** v1 does this in several places (and subclasses it for custom errors).
**Why it's wrong:** Catches `KeyboardInterrupt`, `SystemExit`, `MemoryError`. Hides real failures during tests. PEP 8 explicit no.
**Do this instead:** Catch `Exception` only. Define a `PipeError(Exception)` root for all custom errors. Let `KeyboardInterrupt` propagate.

### Anti-Pattern 4: Reading env vars in module bodies / function bodies

**What people do:** `os.environ.get("CLUSTER_NAME")` sprinkled across modules.
**Why it's wrong:** Untestable without monkeypatching `os.environ`. No validation. No type coercion. No central documentation.
**Do this instead:** All env vars on a single `Settings(BaseSettings)` class. Pass `settings` (or a sliced view) into anything that needs it.

### Anti-Pattern 5: Importing helm/awscli internals

**What people do:** v1 does `from awscli.customizations.eks.get_token import TokenGenerator` — an undocumented internal import that has broken across `awscli` versions.
**Why it's wrong:** Not a public API. Will break silently.
**Do this instead:** Implement the ~30 lines of EKS token generation directly with `boto3` + the presigned-URL helper. Cover it with a golden test that compares against `aws eks get-token` output.

### Anti-Pattern 6: Mixing the test pyramid

**What people do:** Put everything under `test/` and rely on naming conventions to skip slow tests.
**Why it's wrong:** Slow tests leak into the dev loop. Coverage gates can't distinguish "unit branch coverage" from "integration smoke coverage".
**Do this instead:** Three folders. Three markers. Three CI jobs. Unit is the default; opt in to the others.

### Anti-Pattern 7: Generating `pipe.yml` variables block by hand

**What people do:** Edit `README.md`, `pipe.yml`, and `settings.py` separately.
**Why it's wrong:** Exactly how v1's `NAMESPACE` default ended up as `kube-public` in README and `default` in `pipe.yml`.
**Do this instead:** One source of truth (`settings.py`). A `scripts/generate-variables-doc.py` script writes both the docs reference and a `pipe.yml` fragment. CI fails if the generated output differs from what's committed.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| AWS STS | `boto3` `client('sts').assume_role` / `assume_role_with_web_identity` | OIDC path uses `BITBUCKET_STEP_OIDC_TOKEN`; do not log the token |
| AWS EKS | `boto3` `client('eks').describe_cluster` for endpoint+CA; presigned STS URL for token | Token is base64url-encoded `k8s-aws-v1.` prefix; expires in 14 min by default — fine for single-shot Pipe |
| Bitbucket Pipelines runtime | env vars (`BITBUCKET_*`, `BITBUCKET_STEP_OIDC_TOKEN`) + `bitbucket-pipes-toolkit` for output formatting | Toolkit is the only Bitbucket-specific dep. Wrap it in `pipe_io.py` for testability |
| Helm registry / OCI | `helm registry login` then `helm pull oci://…` / `helm upgrade oci://…` directly | OCI auth via `REPO_USERNAME` / `REPO_PASSWORD` env vars; do not write to `~/.docker/config.json` permanently |
| Helm repo (classic) | `helm repo add NAME URL` once at action start; `helm upgrade NAME/CHART --version X` | Repo cache lives in the container; cleared on exit (single-shot) |
| Kubernetes cluster | `helm` binary uses `KUBECONFIG` env var pointing at our tempfile | We never call `kubectl` — helm has its own Kubernetes client |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `cli` ↔ `actions` | Function call, `Deps` dataclass passed in | One-way: cli builds deps, action runs |
| `actions` ↔ `auth` | `auth.select_strategy(settings).resolve()` → `AwsCredentials` | Action does not know about strategies |
| `actions` ↔ `chart` | `chart.resolve(settings)` → `ResolvedChart` | Action does not know about source types |
| `actions` ↔ `helm` | `HelmClient.upgrade_install(...)` etc. | Typed args; no string-building outside `helm/args.py` |
| `aws` ↔ `kube` | `kube.write(cluster_access, token)` → `Path` | Tempfile context-managed; lifetime = invocation |
| `helm` ↔ `kube` | `KUBECONFIG` env var on subprocess | The only coupling between auth-stack and helm |
| everything ↔ `errors` | Raise `PipeError` subclasses; `cli` catches | Exit code is a property of the exception class |

## Sources

- The `src/` layout convention: standard Python Packaging Authority guidance, ubiquitous in 2026 Python projects.
- `pydantic-settings`: official pydantic project for env-var-backed config — replaces ad-hoc `os.environ` parsing.
- `Protocol` for strategy abstraction: PEP 544, structural subtyping — preferred over ABCs when behaviour is the contract.
- `mike` for mkdocs versioning: standard plugin for the mkdocs-material ecosystem.
- `docker buildx` multi-arch + `--platform=$BUILDPLATFORM` cross-compile trick: standard Docker docs pattern for Python images.
- `cosign` keyless signing with GitHub OIDC + `sigstore` ecosystem: standard supply-chain pattern in 2026.
- EKS token format (presigned STS GetCallerIdentity URL, base64url, `k8s-aws-v1.` prefix, 15-minute exclusive cluster name header): documented in the `aws-iam-authenticator` repository and the EKS authentication docs.
- `helm-diff` plugin: `github.com/databus23/helm-diff` — the canonical dry-run plugin in the Helm ecosystem.
- `kind` and `k3d` for in-CI Kubernetes: standard choices; `kind` slightly more common for GitHub Actions.
- `moto` for AWS mocking in integration tests: standard `boto3` mocking library.

Confidence is HIGH on every recommendation in this document with the exception of:
- **mkdocs-material vs README-only:** MEDIUM. README-only is defensible for a small CLI; mkdocs-material wins on versioning support, which is the deciding factor given v1/v2 coexistence.
- **`kind` vs `k3d`:** MEDIUM. Both work; `kind` is recommended for amd64+arm64 GitHub Actions parity.

---
*Architecture research for: typed Python CI-Pipe container (Bitbucket Pipelines Pipe for AWS EKS + Helm)*
*Researched: 2026-06-16*
