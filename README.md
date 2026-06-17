# Bitbucket Pipelines Pipe: AWS EKS Helm Deploy

[![License](https://img.shields.io/github/license/yves-vogl/aws-eks-helm-deploy)](LICENSE)
[![GitHub release](https://img.shields.io/github/v/release/yves-vogl/aws-eks-helm-deploy?label=release&sort=semver)](https://github.com/yves-vogl/aws-eks-helm-deploy/releases)
[![CI](https://github.com/yves-vogl/aws-eks-helm-deploy/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/yves-vogl/aws-eks-helm-deploy/actions/workflows/ci.yml)
[![CodeQL](https://github.com/yves-vogl/aws-eks-helm-deploy/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/yves-vogl/aws-eks-helm-deploy/actions/workflows/codeql.yml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/yves-vogl/aws-eks-helm-deploy/badge)](https://securityscorecards.dev/viewer/?uri=github.com/yves-vogl/aws-eks-helm-deploy)
[![GitHub stars](https://img.shields.io/github/stars/yves-vogl/aws-eks-helm-deploy?style=flat)](https://github.com/yves-vogl/aws-eks-helm-deploy/stargazers)
[![Open issues](https://img.shields.io/github/issues/yves-vogl/aws-eks-helm-deploy)](https://github.com/yves-vogl/aws-eks-helm-deploy/issues)
[![Sponsor](https://img.shields.io/badge/Sponsor-%E2%9D%A4-ea4aaa?logo=githubsponsors&logoColor=white)](https://github.com/sponsors/yves-vogl)

Deploy [Helm](https://helm.sh) charts to [AWS Elastic Kubernetes Service (EKS)](https://docs.aws.amazon.com/eks/latest/userguide/what-is-eks.html) from [Bitbucket Pipelines](https://bitbucket.org/product/features/pipelines) — a thin, opinionated wrapper around `helm upgrade --install` that handles EKS authentication for you.

![Logo](logo.png)

---

## What this pipe does

- Resolves AWS credentials (static keys, optionally with `ROLE_ARN` assumption via STS).
- Builds a kubeconfig for your EKS cluster on the fly — **no `kubectl` install required in your pipeline image**.
- Runs `helm upgrade --install` against the cluster with the variables you provide.
- Injects Bitbucket build metadata (build number, commit, tag, …) as Helm values so your charts can reference them.

This pipe is purpose-built for **Bitbucket Pipelines**. For GitHub Actions, use upstream actions such as [`aws-actions/configure-aws-credentials`](https://github.com/aws-actions/configure-aws-credentials) combined with a Helm action.

> **Status:** v1.3.0 is the current stable release, published on Docker Hub (`yvogl/aws-eks-helm-deploy`). **v2.0 is in active development** and will publish exclusively to GitHub Container Registry (`ghcr.io/yves-vogl/aws-eks-helm-deploy`) — see [Milestone `v2.0.0`](https://github.com/yves-vogl/aws-eks-helm-deploy/milestones) for tracked work (OIDC/IRSA, OCI chart support, history pruning, dry-run, signed images, ADRs, 100% test coverage). Docker Hub is frozen at v1.3.0 as the v1.x archive.

---

## Quick start

Drop the following step into your `bitbucket-pipelines.yml`:

```yaml
image: atlassian/default-image:4

pipelines:
  branches:
    main:
      - step:
          name: Deploy to EKS
          deployment: production
          script:
            - pipe: docker://yvogl/aws-eks-helm-deploy:1.3.0
              variables:
                AWS_ACCESS_KEY_ID: $AWS_ACCESS_KEY_ID
                AWS_SECRET_ACCESS_KEY: $AWS_SECRET_ACCESS_KEY
                AWS_REGION: eu-central-1
                CLUSTER_NAME: my-eks-cluster
                CHART: ./charts/my-app
                RELEASE_NAME: my-app
                NAMESPACE: production
                CREATE_NAMESPACE: "true"
                WAIT: "true"
                TIMEOUT: "10m"
```

Pin the pipe to a specific tag (e.g. `:1.3.0`). Consumers that pin to `:latest` get whatever was last pushed — avoid that in production.

---

## Variables

| Variable                  | Required | Default          | Description                                                                 |
| ------------------------- | :------: | ---------------- | --------------------------------------------------------------------------- |
| `AWS_ACCESS_KEY_ID`       |    ✓     | —                | AWS access key ID.                                                          |
| `AWS_SECRET_ACCESS_KEY`   |    ✓     | —                | AWS secret access key.                                                      |
| `CLUSTER_NAME`            |    ✓     | —                | Name of the target EKS cluster.                                             |
| `CHART`                   |    ✓     | —                | Path or name of the Helm chart to deploy.                                   |
| `AWS_REGION`              |          | `eu-central-1`   | AWS region the cluster lives in.                                            |
| `ROLE_ARN`                |          | —                | IAM role to assume via STS before talking to EKS.                           |
| `SESSION_NAME`            |          | —                | STS session name when assuming `ROLE_ARN`.                                  |
| `RELEASE_NAME`            |          | `$CHART`         | Name of the Helm release.                                                   |
| `NAMESPACE`               |          | `default`        | Target Kubernetes namespace.                                                |
| `CREATE_NAMESPACE`        |          | `false`          | Pass `--create-namespace` to Helm.                                          |
| `SET`                     |          | `[]`             | List of values forwarded to Helm as `--set` arguments.                      |
| `VALUES`                  |          | `[]`             | Local values YAML files forwarded to Helm as `--values` arguments.          |
| `WAIT`                    |          | `false`          | Wait for resources to become ready (`helm --wait`).                         |
| `TIMEOUT`                 |          | `5m`             | Helm timeout, Go duration syntax (e.g. `30s`, `5m`, `1h`).                  |
| `DEBUG`                   |          | `false`          | Verbose logging.                                                            |

The pipe also injects the following Bitbucket build metadata as `--set` values, so your chart templates can reference them: `bitbucket.bitbucket_build_number`, `bitbucket.bitbucket_repo_slug`, `bitbucket.bitbucket_commit`, `bitbucket.bitbucket_tag`, `bitbucket.bitbucket_step_triggerer_uuid`.

> Charts with strict `values.schema.json` validation may reject these fields. An opt-out flag is tracked for v2.0 in [#16](https://github.com/yves-vogl/aws-eks-helm-deploy/issues/16).

---

## Authentication

Today the pipe authenticates using **static AWS access keys**, optionally combined with `ROLE_ARN` assumption via STS. Store keys as [secured repository or deployment variables](https://support.atlassian.com/bitbucket-cloud/docs/variables-and-secrets/) — never commit them.

**Native OIDC / IRSA (Bitbucket OIDC → STS `AssumeRoleWithWebIdentity`)** support is on the v2.0 roadmap — see [#3](https://github.com/yves-vogl/aws-eks-helm-deploy/issues/3). OIDC eliminates long-lived AWS keys in your pipeline and is the recommended pattern for production deployments going forward.

---

## Version matrix

The `yvogl/aws-eks-helm-deploy:1.3.0` image bundles:

| Component                      | Version           | Notes                                                                  |
| ------------------------------ | ----------------- | ---------------------------------------------------------------------- |
| Base image                     | `python:3-alpine` | Latest 3.x at image build time.                                        |
| Helm                           | `3.15.1`          | Copied from `alpine/helm:3.15.1`. Compatible with EKS Kubernetes versions supported by Helm 3.15 — see the [Helm version skew policy](https://helm.sh/docs/topics/version_skew/). |
| `kubectl`                      | not bundled       | The pipe generates a kubeconfig and lets Helm talk to the EKS API directly. |
| `awscli`                       | `~=1.32`          | Used for EKS token generation (`TokenGenerator`).                      |
| `bitbucket-pipes-toolkit`      | `~=4.4`           | Pipe scaffolding, schema validation, logging.                          |
| Jinja2                         | `~=3.1`           | Kubeconfig templating.                                                 |

Tooling versions are advanced in lockstep with each release. See [`CHANGELOG.md`](CHANGELOG.md) for the per-release upgrade history.

---

## Examples

### Basic

```yaml
script:
  - pipe: docker://yvogl/aws-eks-helm-deploy:1.3.0
    variables:
      AWS_ACCESS_KEY_ID: $AWS_ACCESS_KEY_ID
      AWS_SECRET_ACCESS_KEY: $AWS_SECRET_ACCESS_KEY
      CLUSTER_NAME: my-cluster
      CHART: ./charts/my-app
```

### Pull secrets from AWS Secrets Manager, then deploy with a different IAM role

```yaml
script:
  - step:
      name: Fetch secrets
      image: amazon/aws-cli
      deployment: Development
      caches:
        - docker
      script:
        - yum install -y -q jq
        - aws configure set aws_access_key_id $AWS_ACCESS_KEY_ID --profile default
        - aws configure set aws_secret_access_key $AWS_SECRET_ACCESS_KEY --profile default
        - aws configure set region eu-central-1 --profile default
        - aws configure set role_arn $VAULT_ROLE_ARN --profile vault
        - aws configure set source_profile default --profile vault
        - aws configure set region eu-central-1 --profile vault
        - aws secretsmanager get-secret-value --secret-id application/secret --profile vault | jq -r ".SecretString" > secrets.yaml
  - pipe: docker://yvogl/aws-eks-helm-deploy:1.3.0
    variables:
      AWS_ACCESS_KEY_ID: $AWS_ACCESS_KEY_ID
      AWS_SECRET_ACCESS_KEY: $AWS_SECRET_ACCESS_KEY
      ROLE_ARN: $KUBERNETES_USER_ROLE_ARN
      CLUSTER_NAME: a-cluster-name
      CHART: path-to-helm-chart
      RELEASE_NAME: my-example-release
      NAMESPACE: default
      SET: [
        'replicaCount=3',
        'image.version=1.0.2-${BITBUCKET_BUILD_NUMBER}',
        'env.foo_from_repository_or_deployment_variable=${BAR}',
      ]
      VALUES: [
        secrets.yaml
      ]
```

---

## Roadmap

The **[v2.0.0 milestone](https://github.com/yves-vogl/aws-eks-helm-deploy/milestones)** tracks the planned modernization:

- Native AWS OIDC / IRSA authentication
- Helm OCI registry and `repo://` chart support
- `helm --history-max` integration for release history pruning ([#17](https://github.com/yves-vogl/aws-eks-helm-deploy/issues/17))
- Opt-out for injected Bitbucket metadata ([#16](https://github.com/yves-vogl/aws-eks-helm-deploy/issues/16))
- Multi-architecture image (`linux/amd64` + `linux/arm64`), native ARM runners
- Cosign keyless signing + SBOM (SPDX + CycloneDX) + SLSA provenance
- 100% test coverage (unit + integration + acceptance tiers)
- GitHub Actions release pipeline (release-please v4)
- **Published exclusively to GitHub Container Registry (`ghcr.io/yves-vogl/aws-eks-helm-deploy`)** — Docker Hub frozen at v1.3.0 as the v1.x archive

---

## Support and contributing

- **Questions or bug reports** → open a [GitHub issue](https://github.com/yves-vogl/aws-eks-helm-deploy/issues/new/choose). Please include the pipe version, your `bitbucket-pipelines.yml` snippet, and the relevant log output.
- **Security reports** → please report privately rather than via a public issue; see `SECURITY.md` once available (tracked for v2.0).
- **Pull requests welcome** — contribution guidelines (`CONTRIBUTING.md`) and PR template are tracked for v2.0.

## Sponsor

If this pipe saves you time or production headaches, consider [sponsoring the work on GitHub Sponsors](https://github.com/sponsors/yves-vogl). Sponsorships fund v2.0 modernization (OIDC, multi-arch, Cosign keyless, 100% test coverage, versioned docs) and ongoing v1.x security maintenance.

Maintained by [Yves Vogl](https://github.com/yves-vogl) · [Sponsor](https://github.com/sponsors/yves-vogl).

---

## License

[Apache License 2.0](LICENSE.txt).
