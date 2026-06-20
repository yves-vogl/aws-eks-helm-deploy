"""Unit tests for aws_eks_helm_deploy.settings.

Tests cover:
  - Default values (all fields, including the NAMESPACE v1 bug fix)
  - Env-var loading (CLUSTER_NAME, DEBUG, LOG_FORMAT)
  - Regression test for the v1 kube-public NAMESPACE bug
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from aws_eks_helm_deploy.settings import Settings, _CommaListEnvSource


@pytest.mark.unit
def test_settings_defaults() -> None:
    """Settings() with no env vars produces correct defaults for all fields."""
    s = Settings()
    assert s.aws_region == "eu-central-1"
    assert s.aws_access_key_id is None
    assert s.aws_secret_access_key is None
    assert s.role_arn is None
    assert s.session_name == "BitbucketPipe"
    assert s.cluster_name is None
    assert s.chart is None
    assert s.release_name is None
    assert s.namespace == "default"
    assert s.create_namespace is False
    assert s.set_values == []
    assert s.values_files == []
    assert s.wait is False
    assert s.timeout == "600s"
    assert s.action == "upgrade"
    assert s.dry_run is False
    assert s.log_format == "human"
    assert s.debug is False
    assert s.inject_bitbucket_metadata is None


@pytest.mark.unit
def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings() reads CLUSTER_NAME, DEBUG, and LOG_FORMAT from env when set."""
    monkeypatch.setenv("CLUSTER_NAME", "my-cluster")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("LOG_FORMAT", "json")
    s = Settings()
    assert s.cluster_name == "my-cluster"
    assert s.debug is True
    assert s.log_format == "json"


@pytest.mark.unit
def test_set_values_accepts_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SET", "image.tag=v1,replica=3")
    s = Settings()
    assert s.set_values == ["image.tag=v1", "replica=3"]


@pytest.mark.unit
def test_set_values_accepts_json_array(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SET", '["image.tag=v1","replica=3"]')
    s = Settings()
    assert s.set_values == ["image.tag=v1", "replica=3"]


@pytest.mark.unit
def test_set_values_accepts_single_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SET", "image.tag=v1")
    s = Settings()
    assert s.set_values == ["image.tag=v1"]


@pytest.mark.unit
def test_set_values_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SET", "")
    s = Settings()
    assert s.set_values == []


@pytest.mark.unit
def test_values_files_accepts_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VALUES", "values.yaml,prod.yaml")
    s = Settings()
    assert s.values_files == ["values.yaml", "prod.yaml"]


@pytest.mark.unit
def test_values_files_accepts_json_array(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VALUES", '["values.yaml","prod.yaml"]')
    s = Settings()
    assert s.values_files == ["values.yaml", "prod.yaml"]


@pytest.mark.unit
def test_values_files_accepts_single_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VALUES", "values.yaml")
    s = Settings()
    assert s.values_files == ["values.yaml"]


@pytest.mark.unit
def test_values_files_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VALUES", "")
    s = Settings()
    assert s.values_files == []


@pytest.mark.unit
def test_invalid_log_format_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import ValidationError

    monkeypatch.setenv("LOG_FORMAT", "jsn")
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    # pydantic reports the alias (LOG_FORMAT) in the error message
    assert "LOG_FORMAT" in str(exc_info.value)


@pytest.mark.unit
def test_action_accepts_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    """ACTION=diff is accepted after Phase 5 Literal widening (PIPE-02)."""
    monkeypatch.setenv("ACTION", "diff")
    s = Settings()
    assert s.action == "diff"


@pytest.mark.unit
def test_action_accepts_rollback(monkeypatch: pytest.MonkeyPatch) -> None:
    """ACTION=rollback is accepted after Phase 5 Literal widening (PIPE-04)."""
    monkeypatch.setenv("ACTION", "rollback")
    s = Settings()
    assert s.action == "rollback"


@pytest.mark.unit
def test_invalid_action_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import ValidationError

    monkeypatch.setenv("ACTION", "bogus")
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    # pydantic reports the alias (ACTION) in the error message
    assert "ACTION" in str(exc_info.value)


@pytest.mark.unit
def test_comma_list_env_source_falls_through_for_non_list_annotation() -> None:
    """_CommaListEnvSource.decode_complex_value delegates to super() for non-list fields.

    When field.annotation.__origin__ is not list (e.g., a dict field or a plain
    string-typed field), the custom source must not intercept the value and must
    delegate to the parent EnvSettingsSource.decode_complex_value.
    """
    from unittest.mock import MagicMock

    source = _CommaListEnvSource(Settings)
    # Simulate a field whose annotation has __origin__ == dict (not list)
    field = MagicMock()
    field.annotation = dict[str, str]

    # dict values are expected to be JSON-parseable; a plain JSON dict string
    # should fall through to the parent implementation (json.loads)
    result = source.decode_complex_value("some_field", field, '{"a": "b"}')
    assert result == {"a": "b"}


@pytest.mark.unit
def test_comma_list_env_source_passes_through_non_string_value() -> None:
    """_CommaListEnvSource.decode_complex_value returns non-string values unchanged.

    When the value is already a list (e.g., from explode_env_vars), the custom
    source must bypass all str-splitting logic and return the value as-is.
    """
    from unittest.mock import MagicMock

    source = _CommaListEnvSource(Settings)
    # list[str] annotation — but value is already a list, not a str
    field = MagicMock()
    field.annotation = list[str]

    result = source.decode_complex_value("set_values", field, ["already", "parsed"])
    assert result == ["already", "parsed"]


@pytest.mark.unit
def test_comma_list_source_handles_optional_list_str() -> None:
    """_CommaListEnvSource handles Optional[list[str]] annotation."""
    from unittest.mock import MagicMock

    source = _CommaListEnvSource(Settings)
    field = MagicMock()
    field.annotation = list[str] | None
    result = source.decode_complex_value("x", field, "a,b")
    assert result == ["a", "b"]


@pytest.mark.unit
def test_set_values_handles_bracket_prefixed_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    """SET='[a,b]' falls back to CSV split when json.loads fails."""
    monkeypatch.setenv("SET", "[a,b]")
    s = Settings()
    assert s.set_values == ["[a", "b]"]


@pytest.mark.unit
def test_set_values_handles_invalid_quoted_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """SET='["a"' (unclosed JSON array) falls through to CSV split."""
    monkeypatch.setenv("SET", '["a"')
    s = Settings()
    assert s.set_values == ['["a"']


@pytest.mark.unit
def test_settings_accepts_init_kwargs() -> None:
    """Settings(aws_region='us-west-2') honors the kwarg even without env var."""
    s = Settings(aws_region="us-west-2")
    assert s.aws_region == "us-west-2"


@pytest.mark.unit
def test_timeout_default_is_600s() -> None:
    """Settings().timeout == '600s' per Phase 3 corrections #5 (was '5m' in Phase 2)."""
    s = Settings()
    assert s.timeout == "600s"


@pytest.mark.unit
def test_history_max_default_is_none() -> None:
    """Settings().history_max is None when HISTORY_MAX env var is unset."""
    s = Settings()
    assert s.history_max is None


@pytest.mark.unit
def test_history_max_accepts_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """HISTORY_MAX=0 is valid; passes --history-max 0 (unlimited) at the helm layer."""
    monkeypatch.setenv("HISTORY_MAX", "0")
    s = Settings()
    assert s.history_max == 0


@pytest.mark.unit
def test_history_max_accepts_positive_integer(monkeypatch: pytest.MonkeyPatch) -> None:
    """HISTORY_MAX=5 is valid and passes --history-max 5 at the helm layer."""
    monkeypatch.setenv("HISTORY_MAX", "5")
    s = Settings()
    assert s.history_max == 5


@pytest.mark.unit
def test_history_max_rejects_negative_integer(monkeypatch: pytest.MonkeyPatch) -> None:
    """HISTORY_MAX=-1 raises pydantic ValidationError (ge=0 constraint). Closes #17."""
    import pydantic

    monkeypatch.setenv("HISTORY_MAX", "-1")
    with pytest.raises(pydantic.ValidationError):
        Settings()


@pytest.mark.unit
def test_history_max_rejects_non_integer(monkeypatch: pytest.MonkeyPatch) -> None:
    """HISTORY_MAX=not-a-number raises pydantic ValidationError (pydantic int coercion)."""
    import pydantic

    monkeypatch.setenv("HISTORY_MAX", "not-a-number")
    with pytest.raises(pydantic.ValidationError):
        Settings()


@pytest.mark.unit
def test_settings_namespace_v1_bug_fixed() -> None:
    """Regression: NAMESPACE default must be 'default', not 'kube-public'.

    v1 bug: pipe/schema.py line 33 had 'NAMESPACE': {'default': 'kube-public'}.
    v2 fixes this definitively to 'default'. The README also said 'kube-public'
    inconsistently — all references are corrected in v2.
    See: PROJECT.md 'NAMESPACE default inconsistency' and PATTERNS.md Critical Anti-Pattern 2.
    """
    s = Settings()
    assert s.namespace == "default", (
        "NAMESPACE must default to 'default', not 'kube-public' (v1 regression)"
    )


# ---------------------------------------------------------------------------
# Phase 4 — new fields (AUTH-03, CHART-02, CHART-03, CHART-04)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_oidc_audience_default_none() -> None:
    """Settings().oidc_audience is None when OIDC_AUDIENCE env var is unset."""
    s = Settings()
    assert s.oidc_audience is None


@pytest.mark.unit
def test_oidc_audience_via_alias() -> None:
    """Settings(OIDC_AUDIENCE=...) resolves the alias correctly."""
    s = Settings(OIDC_AUDIENCE="ari:cloud:bitbucket::workspace/abc-123")
    assert s.oidc_audience == "ari:cloud:bitbucket::workspace/abc-123"


@pytest.mark.unit
def test_repo_url_default_none() -> None:
    """Settings().repo_url is None when REPO_URL env var is unset."""
    s = Settings()
    assert s.repo_url is None


@pytest.mark.unit
def test_repo_url_via_alias() -> None:
    """Settings(REPO_URL=...) resolves the alias correctly."""
    s = Settings(REPO_URL="https://charts.example.com/")
    assert s.repo_url == "https://charts.example.com/"


@pytest.mark.unit
def test_chart_version_default_none() -> None:
    """Settings().chart_version is None when CHART_VERSION env var is unset."""
    s = Settings()
    assert s.chart_version is None


@pytest.mark.unit
def test_chart_version_via_alias() -> None:
    """Settings(CHART_VERSION=...) resolves the alias correctly."""
    s = Settings(CHART_VERSION="1.2.3")
    assert s.chart_version == "1.2.3"


@pytest.mark.unit
def test_registry_username_default_none() -> None:
    """Settings().registry_username is None when REGISTRY_USERNAME env var is unset."""
    s = Settings()
    assert s.registry_username is None


@pytest.mark.unit
def test_registry_username_via_alias() -> None:
    """Settings(REGISTRY_USERNAME=...) resolves the alias correctly."""
    s = Settings(REGISTRY_USERNAME="myuser")
    assert s.registry_username == "myuser"


@pytest.mark.unit
def test_registry_password_default_none() -> None:
    """Settings().registry_password is None when REGISTRY_PASSWORD env var is unset."""
    s = Settings()
    assert s.registry_password is None


@pytest.mark.unit
def test_registry_password_via_alias_returns_secret_str() -> None:
    """Settings(REGISTRY_PASSWORD=...) returns a SecretStr instance (not plain str)."""
    s = Settings(REGISTRY_PASSWORD="hunter2")
    assert isinstance(s.registry_password, SecretStr)
    assert s.registry_password.get_secret_value() == "hunter2"


@pytest.mark.unit
def test_registry_password_repr_masks_value() -> None:
    """repr(settings) must NOT expose the registry password verbatim (R13 mitigation)."""
    s = Settings(REGISTRY_PASSWORD="hunter2")
    assert "hunter2" not in repr(s)
    assert s.registry_password is not None
    assert "**********" in repr(s.registry_password)


@pytest.mark.unit
def test_chart_verify_default_false() -> None:
    """Settings().chart_verify is False when CHART_VERIFY env var is unset."""
    s = Settings()
    assert s.chart_verify is False


@pytest.mark.unit
def test_chart_verify_via_alias_true_string() -> None:
    """Settings(CHART_VERIFY='true') coerces the string to True (pydantic bool coercion)."""
    s = Settings(CHART_VERIFY="true")
    assert s.chart_verify is True


@pytest.mark.unit
def test_chart_verify_certificate_identity_default_none() -> None:
    """Settings().chart_verify_certificate_identity is None when env var is unset."""
    s = Settings()
    assert s.chart_verify_certificate_identity is None


@pytest.mark.unit
def test_chart_verify_certificate_identity_via_alias() -> None:
    """Settings(CHART_VERIFY_CERTIFICATE_IDENTITY=...) resolves the alias correctly."""
    s = Settings(CHART_VERIFY_CERTIFICATE_IDENTITY="https://github.com/actions/runner")
    assert s.chart_verify_certificate_identity == "https://github.com/actions/runner"


@pytest.mark.unit
def test_chart_verify_certificate_oidc_issuer_default_none() -> None:
    """Settings().chart_verify_certificate_oidc_issuer is None when env var is unset."""
    s = Settings()
    assert s.chart_verify_certificate_oidc_issuer is None


@pytest.mark.unit
def test_chart_verify_certificate_oidc_issuer_via_alias() -> None:
    """Settings(CHART_VERIFY_CERTIFICATE_OIDC_ISSUER=...) resolves the alias correctly."""
    s = Settings(CHART_VERIFY_CERTIFICATE_OIDC_ISSUER="https://token.actions.githubusercontent.com")
    assert s.chart_verify_certificate_oidc_issuer == "https://token.actions.githubusercontent.com"


# ---------------------------------------------------------------------------
# Phase 5 — new/changed fields (META-02, PIPE-03, PIPE-04, PIPE-05)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_inject_bitbucket_metadata_default_is_none() -> None:
    """Settings().inject_bitbucket_metadata is None (META-02/D4 tri-state flip from bool=False).

    None is the sentinel that lets the META-03 detector distinguish 'unset' (fire WARN)
    from 'explicit false' (do nothing silently) when values.yaml references 'bitbucket:'.
    """
    s = Settings()
    assert s.inject_bitbucket_metadata is None


@pytest.mark.unit
def test_inject_bitbucket_metadata_env_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """INJECT_BITBUCKET_METADATA=true explicitly opts in to bitbucket metadata injection."""
    monkeypatch.setenv("INJECT_BITBUCKET_METADATA", "true")
    s = Settings()
    assert s.inject_bitbucket_metadata is True


@pytest.mark.unit
def test_inject_bitbucket_metadata_env_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """INJECT_BITBUCKET_METADATA=false is an explicit opt-out (distinct from unset=None)."""
    monkeypatch.setenv("INJECT_BITBUCKET_METADATA", "false")
    s = Settings()
    assert s.inject_bitbucket_metadata is False


@pytest.mark.unit
def test_post_diff_as_comment_default_is_false() -> None:
    """Settings().post_diff_as_comment is False when POST_DIFF_AS_COMMENT env var is unset."""
    s = Settings()
    assert s.post_diff_as_comment is False


@pytest.mark.unit
def test_post_diff_as_comment_env_true_sets_field_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST_DIFF_AS_COMMENT=true enables PR-comment posting (PIPE-03/D3)."""
    monkeypatch.setenv("POST_DIFF_AS_COMMENT", "true")
    s = Settings()
    assert s.post_diff_as_comment is True


@pytest.mark.unit
def test_bitbucket_token_default_is_none() -> None:
    """Settings().bitbucket_token is None when BITBUCKET_TOKEN env var is unset."""
    s = Settings()
    assert s.bitbucket_token is None


@pytest.mark.unit
def test_bitbucket_token_env_sets_secretstr_and_get_secret_value_returns_plaintext(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BITBUCKET_TOKEN is stored as SecretStr; get_secret_value() returns the plaintext."""
    monkeypatch.setenv("BITBUCKET_TOKEN", "xyz-token")
    s = Settings()
    assert isinstance(s.bitbucket_token, SecretStr)
    assert s.bitbucket_token.get_secret_value() == "xyz-token"


@pytest.mark.unit
def test_bitbucket_token_repr_does_not_leak_plaintext(monkeypatch: pytest.MonkeyPatch) -> None:
    """repr(settings) MUST NOT contain the BITBUCKET_TOKEN plaintext (T-05-02/R4 regression gate).

    This test is the load-bearing anti-leak assertion: if a future contributor re-types
    bitbucket_token as plain str, this test will fail, catching the regression before it ships.
    """
    monkeypatch.setenv("BITBUCKET_TOKEN", "MY-SECRET-TOKEN")
    s = Settings()
    assert "MY-SECRET-TOKEN" not in repr(s)


@pytest.mark.unit
def test_safe_upgrade_default_is_false() -> None:
    """Settings().safe_upgrade is False when SAFE_UPGRADE env var is unset."""
    s = Settings()
    assert s.safe_upgrade is False


@pytest.mark.unit
def test_safe_upgrade_env_true_sets_field_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """SAFE_UPGRADE=true adds --wait --atomic --description to helm upgrade argv (PIPE-05/D5)."""
    monkeypatch.setenv("SAFE_UPGRADE", "true")
    s = Settings()
    assert s.safe_upgrade is True


@pytest.mark.unit
def test_revision_default_is_none() -> None:
    """Settings().revision is None when REVISION env var is unset."""
    s = Settings()
    assert s.revision is None


@pytest.mark.unit
def test_revision_env_positive_int_sets_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """REVISION=5 coerces to int 5 (target revision for ACTION=rollback, PIPE-04)."""
    monkeypatch.setenv("REVISION", "5")
    s = Settings()
    assert s.revision == 5


@pytest.mark.unit
def test_revision_env_zero_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """REVISION=0 is valid; ge=0 constraint permits zero (mirrors history_max=0 pattern)."""
    monkeypatch.setenv("REVISION", "0")
    s = Settings()
    assert s.revision == 0


@pytest.mark.unit
def test_revision_env_negative_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """REVISION=-1 raises pydantic ValidationError (ge=0 constraint mirrors history_max)."""
    import pydantic

    monkeypatch.setenv("REVISION", "-1")
    with pytest.raises(pydantic.ValidationError):
        Settings()
