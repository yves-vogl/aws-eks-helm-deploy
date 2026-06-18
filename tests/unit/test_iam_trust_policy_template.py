"""Unit tests for the IAM trust-policy template at docs/guides/oidc-setup.md.

Requirements traceability:
  - AUTH-05: ships a documented IAM trust-policy template scoped to BITBUCKET_WORKSPACE_UUID
             and BITBUCKET_REPO_UUID; the unit test below enforces structural correctness.

Per CONTEXT D4 + RESEARCH §2 + §R-erratum: the `sub` condition MUST use `StringLike`
(NOT `StringEquals`) because the value contains a literal `*` wildcard for the step UUID,
and IAM only treats `*` as a wildcard under `StringLike`.
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

DOC_PATH = pathlib.Path("docs/guides/oidc-setup.md")
REQUIRED_PLACEHOLDERS = (
    "<ACCOUNT_ID>",
    "<WORKSPACE>",
    "<OIDC_AUDIENCE>",
    "<BITBUCKET_WORKSPACE_UUID>",
    "<BITBUCKET_REPO_UUID>",
)


def _extract_policy_json() -> dict:  # type: ignore[type-arg]
    """Pull the first ```jsonc fenced block out of the markdown file and parse it.

    Returns the parsed dict. Raises ValueError if no block found.
    """
    text = DOC_PATH.read_text()
    match = re.search(r"```jsonc?\n(.*?)\n```", text, re.DOTALL)
    if match is None:
        raise ValueError(f"no fenced ```jsonc block found in {DOC_PATH}")
    # Strip JSONC line comments (// ...) — none in our template, but defensive.
    block = re.sub(r"^\s*//.*$", "", match.group(1), flags=re.MULTILINE)
    return json.loads(block)  # type: ignore[no-any-return]


@pytest.mark.unit
def test_template_has_all_required_placeholders() -> None:
    """All 5 placeholders appear verbatim in the doc (CONTEXT D4 Plan-Check obligation)."""
    text = DOC_PATH.read_text()
    missing = [ph for ph in REQUIRED_PLACEHOLDERS if ph not in text]
    assert not missing, f"missing placeholders: {missing}"


@pytest.mark.unit
def test_template_parses_as_valid_json() -> None:
    """The fenced block is valid JSON after JSONC comment stripping."""
    data = _extract_policy_json()
    assert data["Version"] == "2012-10-17"
    assert isinstance(data["Statement"], list)
    assert len(data["Statement"]) == 1


@pytest.mark.unit
def test_sub_condition_uses_string_like_not_string_equals() -> None:
    """RESEARCH §2 + CONTEXT D4 erratum: the wildcard `*` requires StringLike.

    Catches the trap where a future PR converts `sub` back to StringEquals
    (which would silently allow `*` to be treated as a literal asterisk,
    not a wildcard — under-constraining the policy to literally one
    invalid sub value).
    """
    data = _extract_policy_json()
    statement = data["Statement"][0]
    condition = statement["Condition"]
    # sub key MUST live under StringLike
    assert "StringLike" in condition, (
        "sub condition must live under StringLike (RESEARCH §2 erratum)"
    )
    sub_key = next(
        (k for k in condition["StringLike"] if k.endswith(":sub")),
        None,
    )
    assert sub_key is not None, "no `*:sub` key found under StringLike"
    sub_value = condition["StringLike"][sub_key]
    assert "<BITBUCKET_WORKSPACE_UUID>" in sub_value
    assert "<BITBUCKET_REPO_UUID>" in sub_value
    assert sub_value.endswith(":*"), "sub value must end with `:*` wildcard"
    # And sub MUST NOT live under StringEquals (the erratum)
    if "StringEquals" in condition:
        for key in condition["StringEquals"]:
            assert not key.endswith(":sub"), (
                f"sub key {key!r} found under StringEquals"
                " — must be under StringLike per RESEARCH §2 erratum"
            )


@pytest.mark.unit
def test_aud_condition_uses_string_equals_with_placeholder() -> None:
    """aud is an exact-match — StringEquals is correct here."""
    data = _extract_policy_json()
    statement = data["Statement"][0]
    condition = statement["Condition"]
    assert "StringEquals" in condition
    aud_key = next(
        (k for k in condition["StringEquals"] if k.endswith(":aud")),
        None,
    )
    assert aud_key is not None, "no `*:aud` key found under StringEquals"
    assert condition["StringEquals"][aud_key] == "<OIDC_AUDIENCE>"


@pytest.mark.unit
def test_action_is_assume_role_with_web_identity() -> None:
    """Action MUST be exactly sts:AssumeRoleWithWebIdentity (CONTEXT D4)."""
    data = _extract_policy_json()
    statement = data["Statement"][0]
    assert statement["Action"] == "sts:AssumeRoleWithWebIdentity"


@pytest.mark.unit
def test_federated_principal_matches_bitbucket_oidc_issuer_pattern() -> None:
    """Principal.Federated must reference the canonical Bitbucket OIDC provider ARN.

    Canonical form per RESEARCH §2 (Atlassian docs retrieved 2026-06-18):
      arn:aws:iam::<ACCOUNT_ID>:oidc-provider/api.bitbucket.org/2.0/workspaces/<WORKSPACE>/pipelines-config/identity/oidc
    """
    data = _extract_policy_json()
    statement = data["Statement"][0]
    federated = statement["Principal"]["Federated"]
    expected_substring = (
        "api.bitbucket.org/2.0/workspaces/<WORKSPACE>/pipelines-config/identity/oidc"
    )
    assert expected_substring in federated, (
        f"Principal.Federated `{federated}` does not match the Bitbucket OIDC issuer pattern"
    )
    # And it must be the OIDC provider ARN (not a federated user, role, etc.)
    assert federated.startswith("arn:aws:iam::<ACCOUNT_ID>:oidc-provider/")
