"""Unit tests for aws_eks_helm_deploy.settings.

Tests cover:
  - Default values (all fields, including the NAMESPACE v1 bug fix)
  - Env-var loading (CLUSTER_NAME, DEBUG, LOG_FORMAT)
  - Regression test for the v1 kube-public NAMESPACE bug
"""

from __future__ import annotations

import pytest

from aws_eks_helm_deploy.settings import Settings


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
    assert s.timeout == "5m"
    assert s.action == "upgrade"
    assert s.dry_run is False
    assert s.log_format == "human"
    assert s.debug is False
    assert s.inject_bitbucket_metadata is False


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
def test_invalid_action_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import ValidationError

    monkeypatch.setenv("ACTION", "bogus")
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    # pydantic reports the alias (ACTION) in the error message
    assert "ACTION" in str(exc_info.value)


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
