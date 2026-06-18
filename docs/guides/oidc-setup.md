# Bitbucket Pipelines OIDC — IAM Trust-Policy Template

> Draft. Polished in Phase 7 alongside the mkdocs site.

This page ships the AWS IAM trust-policy template the pipe expects when it authenticates to AWS
via Bitbucket Pipelines OIDC (`AUTH-03`). The template is the **consumer-side** gate that
constrains which Bitbucket workspace + repository can assume the role; the pipe's runtime path
(`auth/oidc.py`) is the matching strategy that exchanges the OIDC JWT for STS credentials via
`AssumeRoleWithWebIdentity`.

## How to use

1. Copy the JSON block below.
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

## Why `StringLike` (not `StringEquals`) for `sub`

Bitbucket emits the `sub` claim as `{<WORKSPACE_UUID>}:{<REPO_UUID>}:<step-UUID>` — with
literal curly braces and the step UUID as the third segment. IAM only treats `*` as a wildcard
under `StringLike`, NOT under `StringEquals`. The template above uses `StringLike` with
`{<BITBUCKET_WORKSPACE_UUID>}:{<BITBUCKET_REPO_UUID>}:*` so any step within the named workspace
+ repo can assume the role; constraining at the step level is impractical (step UUIDs are
ephemeral). If a downstream consumer wants step-level scoping, they can replace `*` with the
exact step UUID and switch the condition back to `StringEquals`.

## Notes

- The pipe does NOT re-validate the JWT — STS validates the `aud` claim against the
  trust-policy condition above.
- The `Principal.Federated` URL is the OIDC provider ARN; the OIDC provider itself must be
  created once per AWS account (typically via Terraform `aws_iam_openid_connect_provider`).
  The Phase 7 docs site will ship the full Terraform setup alongside the trust policy.
- The pipe's WARN log `auth.precedence.static_keys_won_over_oidc` (Phase 4, AUTH-04 revised)
  surfaces when a consumer has both static AWS keys AND `BITBUCKET_STEP_OIDC_TOKEN` set —
  static keys win per the boto3 default chain order. To use OIDC instead, unset
  `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` in your `bitbucket-pipelines.yml`.

## Polish coming in Phase 7

- mkdocs-material rendering (`docs/guides/oidc-setup.md` lands in the published v2 site).
- Companion Terraform snippet (`aws_iam_role` + `data.tls_certificate` patterns).
- Migration notes for v1 → v2 OIDC setup.
