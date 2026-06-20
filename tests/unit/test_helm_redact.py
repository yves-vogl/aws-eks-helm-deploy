"""Unit tests for helm/redact.py — SEC-06 / CONTEXT D1 redactor coverage.

Covers: Secret data redaction, stringData redaction, ConfigMap passthrough,
multi-doc mixed kinds, non-YAML passthrough, empty input, null-doc YAML,
literal sentinel string assertion, and fuzz no-leak guarantee.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

from aws_eks_helm_deploy.helm.redact import redact_helm_output

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

FIXTURE_DIR = pathlib.Path(__file__).parent.parent / "fixtures" / "charts" / "secret-emitting"
SECRET_TEMPLATE = FIXTURE_DIR / "templates" / "secret.yaml"

# ---------------------------------------------------------------------------
# Happy path — Secret redaction
# ---------------------------------------------------------------------------


def test_secret_data_is_redacted() -> None:
    """Fixture secret.yaml has its data: and stringData: blocks replaced with <redacted>."""
    text = SECRET_TEMPLATE.read_text()
    result = redact_helm_output(text)
    assert "<redacted>" in result
    # base64 of "placeholder" must not appear in the redacted output
    assert "cGxhY2Vob2xkZXI=" not in result
    # base64 of "example" must not appear in the redacted output
    assert "ZXhhbXBsZQ==" not in result
    # plaintext stringData values must not appear
    assert "placeholder" not in result
    assert "example" not in result


def test_secret_stringdata_is_redacted() -> None:
    """A Secret with only stringData: has its block replaced with <redacted>."""
    text = (
        "apiVersion: v1\n"
        "kind: Secret\n"
        "metadata:\n"
        "  name: test-secret\n"
        "type: Opaque\n"
        "stringData:\n"
        "  password: super-secret-plaintext\n"
    )
    result = redact_helm_output(text)
    assert "<redacted>" in result
    assert "super-secret-plaintext" not in result


def test_secret_data_only_is_redacted() -> None:
    """A Secret with only data: (no stringData:) has data: replaced; no stringData: invented."""
    # gitleaks:allow — field_x is a neutral key name; base64 of literal "test-value"
    text = (
        "apiVersion: v1\n"
        "kind: Secret\n"
        "metadata:\n"
        "  name: test-secret\n"
        "type: Opaque\n"
        "data:\n"
        "  field_x: dGVzdC12YWx1ZQ==\n"
    )
    result = redact_helm_output(text)
    assert "<redacted>" in result
    assert "dGVzdC12YWx1ZQ==" not in result
    # stringData must NOT be introduced into the output
    assert "stringData" not in result


# ---------------------------------------------------------------------------
# Non-Secret passthrough
# ---------------------------------------------------------------------------


def test_configmap_is_passthrough() -> None:
    """A ConfigMap's data: block is preserved verbatim (no false positive)."""
    text = (
        "apiVersion: v1\n"
        "kind: ConfigMap\n"
        "metadata:\n"
        "  name: my-config\n"
        "data:\n"
        "  key: some-public-value\n"
    )
    result = redact_helm_output(text)
    assert "some-public-value" in result
    assert "<redacted>" not in result


def test_multidoc_only_secrets_redacted() -> None:
    """Multi-doc YAML: Secret data is redacted, ConfigMap data is preserved, doc order held."""
    text = (
        "apiVersion: v1\n"
        "kind: Secret\n"
        "metadata:\n"
        "  name: sec\n"
        "data:\n"
        "  pw: c2VjcmV0\n"
        "---\n"
        "apiVersion: v1\n"
        "kind: ConfigMap\n"
        "metadata:\n"
        "  name: cfg\n"
        "data:\n"
        "  key: public-value\n"
    )
    result = redact_helm_output(text)
    # ConfigMap data preserved
    assert "public-value" in result
    # Secret data redacted
    assert "c2VjcmV0" not in result
    assert "<redacted>" in result
    # Both documents still present (--- separator)
    assert "---" in result


# ---------------------------------------------------------------------------
# Non-YAML and edge-case passthrough
# ---------------------------------------------------------------------------


def test_non_yaml_input_passthrough() -> None:
    """Non-YAML helm success message is returned verbatim (YAMLError passthrough, CONTEXT D1)."""
    text = 'Release "my-release" has been upgraded. Happy Helming!\nNAME: my-release\n'
    result = redact_helm_output(text)
    assert result == text


def test_empty_input_passthrough() -> None:
    """Empty string input returns empty string."""
    assert redact_helm_output("") == ""


def test_null_docs_passthrough() -> None:
    """Empty YAML docs (---\\n---\\n) do not crash; output is a str."""
    result = redact_helm_output("---\n---\n")
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Sentinel type assertion
# ---------------------------------------------------------------------------


def test_sentinel_is_literal_string_not_dict() -> None:
    """The redacted data: value is the literal string '<redacted>', not a dict."""
    text = "apiVersion: v1\nkind: Secret\nmetadata:\n  name: x\ndata:\n  pw: dGVzdA==\n"
    result = redact_helm_output(text)
    loaded = yaml.safe_load(result)
    assert loaded["data"] == "<redacted>"
    assert isinstance(loaded["data"], str)


# ---------------------------------------------------------------------------
# Fuzz — no secret bytes in any output
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        # Case 1: Secret first, then ConfigMap
        (
            "apiVersion: v1\nkind: Secret\nmetadata:\n  name: s1\n"
            "data:\n  pw: FUZZ_SECRET_VALUE_1\n"
            "---\n"
            "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: c1\n"
            "data:\n  k: public\n"
        ),
        # Case 2: ConfigMap first, then Secret
        (
            "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: c2\n"
            "data:\n  k: public\n"
            "---\n"
            "apiVersion: v1\nkind: Secret\nmetadata:\n  name: s2\n"
            "data:\n  pw: FUZZ_SECRET_VALUE_2\n"
        ),
        # Case 3: Three ConfigMaps sandwiching a Secret
        (
            "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: c3a\n"
            "data:\n  k: public\n"
            "---\n"
            "apiVersion: v1\nkind: Secret\nmetadata:\n  name: s3\n"
            "data:\n  pw: FUZZ_SECRET_VALUE_3\n"
            "---\n"
            "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: c3b\n"
            "data:\n  k: public\n"
        ),
        # Case 4: Two Secrets in sequence
        (
            "apiVersion: v1\nkind: Secret\nmetadata:\n  name: s4a\n"
            "data:\n  pw: FUZZ_SECRET_VALUE_4\n"
            "---\n"
            "apiVersion: v1\nkind: Secret\nmetadata:\n  name: s4b\n"
            "stringData:\n  token: FUZZ_SECRET_VALUE_4_TOKEN\n"
        ),
        # Case 5: Secret with both data: and stringData:
        (
            "apiVersion: v1\nkind: Secret\nmetadata:\n  name: s5\n"
            "data:\n  pw: FUZZ_SECRET_VALUE_5_DATA\n"
            "stringData:\n  token: FUZZ_SECRET_VALUE_5_STR\n"
        ),
    ],
)
def test_fuzz_no_secret_bytes_in_any_output(text: str) -> None:
    """No FUZZ_SECRET_VALUE_* substring appears in the redactor output for any permutation."""
    result = redact_helm_output(text)
    assert "FUZZ_SECRET_VALUE_" not in result
