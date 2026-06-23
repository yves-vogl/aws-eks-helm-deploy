# Bitbucket Pipelines OIDC setup

OIDC removes the need for long-lived AWS access keys in your `bitbucket-pipelines.yml`.
Bitbucket signs a short-lived JWT (the `BITBUCKET_STEP_OIDC_TOKEN`) once per step; the pipe
exchanges it for AWS STS credentials via `AssumeRoleWithWebIdentity`, scoped to the role you
configure on the AWS side.

This guide covers the **two pieces you need to provision on AWS** before the pipe can use OIDC:

1. The **OIDC provider** — one per AWS account, registers Bitbucket as a trusted issuer.
2. The **IAM role's trust policy** — the consumer-side gate that constrains which Bitbucket
   workspace + repository can assume the role.

The pipe's runtime path (`src/aws_eks_helm_deploy/auth/oidc.py`) is the matching strategy that
calls STS once the IAM role is in place.

!!! tip "Already running v1.x with static keys?"
    Jump to the [Migrating from static keys](#migrating-from-static-keys) section at the
    bottom — same role concept, no keys to rotate, fewer secrets to store in Bitbucket.

## Step 1 — Register the Bitbucket OIDC provider on AWS

This is a one-shot per AWS account. Skip if a Bitbucket OIDC provider already exists in the
target account (check `aws iam list-open-id-connect-providers`).

### Option A — Terraform (recommended)

```hcl
data "tls_certificate" "bitbucket_oidc" {
  url = "https://api.bitbucket.org/2.0/workspaces/${var.bitbucket_workspace_slug}/pipelines-config/identity/oidc/.well-known/openid-configuration"
}

resource "aws_iam_openid_connect_provider" "bitbucket" {
  url             = "https://api.bitbucket.org/2.0/workspaces/${var.bitbucket_workspace_slug}/pipelines-config/identity/oidc"
  client_id_list  = [var.bitbucket_oidc_audience]   # ari:cloud:bitbucket::workspace/<UUID>
  thumbprint_list = [data.tls_certificate.bitbucket_oidc.certificates[0].sha1_fingerprint]
}
```

### Option B — `aws iam create-open-id-connect-provider`

```bash
WORKSPACE="mycompany"
OIDC_AUDIENCE="ari:cloud:bitbucket::workspace/<WORKSPACE_UUID>"
THUMBPRINT=$(echo | openssl s_client \
  -servername api.bitbucket.org -connect api.bitbucket.org:443 2>/dev/null \
  | openssl x509 -fingerprint -noout -sha1 | sed 's/://g' | cut -d= -f2 | tr 'A-Z' 'a-z')

aws iam create-open-id-connect-provider \
  --url "https://api.bitbucket.org/2.0/workspaces/${WORKSPACE}/pipelines-config/identity/oidc" \
  --client-id-list "${OIDC_AUDIENCE}" \
  --thumbprint-list "${THUMBPRINT}"
```

## Step 2 — IAM role trust policy

1. Copy the JSON block below (or the Terraform snippet that follows).
2. Replace the 5 placeholders with values from your AWS account + Bitbucket workspace:
   - `<ACCOUNT_ID>` — your AWS 12-digit account ID.
   - `<WORKSPACE>` — your Bitbucket workspace slug (e.g. `mycompany`).
   - `<OIDC_AUDIENCE>` — the audience value from **Repository settings → Pipelines → OpenID
     Connect → Audience**. Form: `ari:cloud:bitbucket::workspace/<WORKSPACE_UUID>`.
   - `<BITBUCKET_WORKSPACE_UUID>` — your Bitbucket workspace UUID (curly-braced UUID form).
     Find via the same Pipelines OpenID Connect page.
   - `<BITBUCKET_REPO_UUID>` — your Bitbucket repository UUID (curly-braced UUID form).
3. Paste the result into the IAM role's trust-policy editor (AWS IAM console → Roles → your
   role → Trust relationships → Edit trust policy) OR into your Terraform
   `aws_iam_role.assume_role_policy` JSON value.

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

### Terraform companion

```hcl
resource "aws_iam_role" "deploy" {
  name = "bitbucket-pipelines-eks-deploy"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.bitbucket.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "api.bitbucket.org/2.0/workspaces/${var.bitbucket_workspace_slug}/pipelines-config/identity/oidc:aud" = var.bitbucket_oidc_audience
        }
        StringLike = {
          "api.bitbucket.org/2.0/workspaces/${var.bitbucket_workspace_slug}/pipelines-config/identity/oidc:sub" = "{${var.bitbucket_workspace_uuid}}:{${var.bitbucket_repo_uuid}}:*"
        }
      }
    }]
  })
}

# Attach whatever managed/inline policies your deploy needs — typically EKS access entries
# and any `aws-auth` group mappings the chart references. The pipe itself only needs to call
# `eks:DescribeCluster` (token generation) plus whatever Kubernetes API access the Helm
# release requires (gated via EKS access entries or the legacy aws-auth ConfigMap).
```

## Why `StringLike` (not `StringEquals`) for `sub`

Bitbucket emits the `sub` claim as `{<WORKSPACE_UUID>}:{<REPO_UUID>}:<step-UUID>` — with
literal curly braces and the step UUID as the third segment. IAM only treats `*` as a wildcard
under `StringLike`, NOT under `StringEquals`. The template above uses `StringLike` with
`{<BITBUCKET_WORKSPACE_UUID>}:{<BITBUCKET_REPO_UUID>}:*` so any step within the named workspace
+ repo can assume the role; constraining at the step level is impractical (step UUIDs are
ephemeral). If a downstream consumer wants step-level scoping, they can replace `*` with the
exact step UUID and switch the condition back to `StringEquals`.

## Step 3 — Wire the pipe step

With the role provisioned, the `bitbucket-pipelines.yml` step looks like:

```yaml
- step:
    name: Deploy to EKS
    deployment: production
    oidc: true                                       # Bitbucket emits BITBUCKET_STEP_OIDC_TOKEN
    script:
      - pipe: docker://ghcr.io/yves-vogl/aws-eks-helm-deploy:2
        variables:
          OIDC_AUDIENCE: $OIDC_AUDIENCE              # ari:cloud:bitbucket::workspace/<UUID>
          ROLE_ARN: $DEPLOY_ROLE_ARN
          AWS_REGION: eu-central-1
          CLUSTER_NAME: my-eks-cluster
          CHART: ./charts/my-app
          RELEASE_NAME: my-app
          NAMESPACE: production
          WAIT: "true"
          TIMEOUT: 10m
```

The `oidc: true` step setting is what tells Bitbucket to mint the OIDC token. Store
`OIDC_AUDIENCE` and `DEPLOY_ROLE_ARN` as repository or deployment variables; neither is a
secret in the cryptographic sense (the audience is per-workspace public; the role ARN is
trivial to discover from AWS) but keeping them in Bitbucket variables makes per-environment
overrides clean.

## Migrating from static keys

If you're on v1.x today with `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` in repo variables:

1. Stand up the OIDC provider (Step 1) and the IAM role with the trust policy (Step 2). Give
   the role **the same managed/inline policies** that the IAM user behind your access keys had.
2. Update one pipeline step to use the OIDC pattern (Step 3); leave the rest on static keys.
3. Verify a deploy succeeds on the OIDC step. Inspect the WARN log
   `auth.precedence.static_keys_won_over_oidc` — this surfaces only when **both** static keys
   AND the OIDC token are present in the same step. Static keys win (mirrors the botocore
   default-chain order). To switch to OIDC, **unset** `AWS_ACCESS_KEY_ID` +
   `AWS_SECRET_ACCESS_KEY` in the step.
4. Roll the remaining steps. Once all steps are on OIDC, delete the IAM user + access keys
   from AWS and remove the secured Bitbucket variables.

## Reference

- The pipe does NOT re-validate the JWT — STS validates the `aud` claim against the
  trust-policy condition above.
- The `Principal.Federated` URL is the OIDC provider ARN; the OIDC provider itself must be
  created once per AWS account (Step 1 above).
- Source: `src/aws_eks_helm_deploy/auth/oidc.py` (`OidcWebIdentityStrategy`).
- ADR: [`0006-oidc-default-precedence.md`](../adr/0006-oidc-default-precedence.md).
