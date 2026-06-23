"""Settings module for aws-eks-helm-deploy.

Requirements traceability:
  - TOOL-02: src layout + pyproject.toml as single dep manifest
  - OBS-02: DEBUG field controls log verbosity (see logging.py, Plan D)

All configuration is read from environment variables via pydantic-settings.
Fields use Field(alias="ENV_VAR_NAME") to preserve the v1 env-var names from
pipe/schema.py while adding new v2-only variables (ACTION, DRY_RUN, LOG_FORMAT,
INJECT_BITBUCKET_METADATA).

Breaking change from v1:
  - NAMESPACE default changed from 'kube-public' (v1 bug) to 'default' (v2 fix)
  - INJECT_BITBUCKET_METADATA defaults to None (was False in v2.0b, unconditional in v1);
    None is the sentinel used by META-03 to distinguish "unset" from "explicit false".

Phase 4 additions: OIDC_AUDIENCE (AUTH-03); REPO_URL + CHART_VERSION (CHART-02);
REGISTRY_USERNAME + REGISTRY_PASSWORD (CHART-03 — password is SecretStr per R13);
CHART_VERIFY + CHART_VERIFY_CERTIFICATE_IDENTITY + CHART_VERIFY_CERTIFICATE_OIDC_ISSUER
(CHART-04).

Phase 5 additions: ACTION=diff/rollback (PIPE-02/04); POST_DIFF_AS_COMMENT + BITBUCKET_TOKEN
(PIPE-03 per D3); SAFE_UPGRADE (PIPE-05 per D5); REVISION (PIPE-04 per D5);
INJECT_BITBUCKET_METADATA flipped to bool | None per META-02/D4.
"""

from __future__ import annotations

import json
import types
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import Field, SecretStr
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict
from pydantic_settings.sources.providers.env import EnvSettingsSource


class _CommaListEnvSource(EnvSettingsSource):
    """Env source that accepts comma-separated strings for list[str] fields.

    pydantic-settings 2.x tries json.loads() on any "complex" (non-scalar)
    field value it reads from the environment. For list[str] fields this means
    only JSON arrays ("["a","b"]") are accepted out of the box.

    This subclass overrides decode_complex_value to also accept:
      - comma-separated strings  →  "a,b"   →  ["a", "b"]
      - empty string             →  ""       →  []
    JSON arrays are still handled first (via super()), so ["a","b"] keeps working.
    """

    def decode_complex_value(
        self,
        field_name: str,
        field: FieldInfo,
        value: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        """Decode env value for complex fields, accepting comma-separated lists.

        Handles list[str] and Optional[list[str]] (Union[list[str], None]) field annotations.
        """
        if isinstance(value, str) and field.annotation is not None:
            annotation = field.annotation
            origin = get_origin(annotation)
            # Unwrap Optional[list[str]]: handles both typing.Union and Python 3.10+ X | Y syntax
            if origin is Union or isinstance(annotation, types.UnionType):
                inner_args = get_args(annotation)
                is_list_field = any(get_origin(a) is list for a in inner_args)
            else:
                is_list_field = origin is list
            if is_list_field:
                if value == "":
                    return []
                if value.startswith("["):
                    try:
                        return json.loads(value)
                    except json.JSONDecodeError:
                        pass
                return [item.strip() for item in value.split(",") if item.strip()]
            return super().decode_complex_value(field_name, field, value)
        # Non-string values (e.g. already-parsed lists) are passed through as-is.
        return value


class Settings(BaseSettings):
    """Pipe configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=True,
        extra="ignore",
        populate_by_name=True,
    )

    # AWS credentials (required at runtime in Phase 2+; optional in Phase 1 skeleton)
    aws_region: str = Field(default="eu-central-1", alias="AWS_REGION")
    aws_access_key_id: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    aws_session_token: str | None = Field(default=None, alias="AWS_SESSION_TOKEN")
    role_arn: str | None = Field(default=None, alias="ROLE_ARN")
    session_name: str = Field(default="BitbucketPipe", alias="SESSION_NAME")

    # OIDC (AUTH-03) — Phase 4
    oidc_audience: str | None = Field(default=None, alias="OIDC_AUDIENCE")

    # Cluster + chart (required at runtime; optional for unit tests in Phase 1)
    cluster_name: str | None = Field(default=None, alias="CLUSTER_NAME")
    chart: str | None = Field(default=None, alias="CHART")
    release_name: str | None = Field(default=None, alias="RELEASE_NAME")

    # v1 had NAMESPACE default 'kube-public' — BUG FIXED to 'default' in v2
    namespace: str = Field(default="default", alias="NAMESPACE")
    create_namespace: bool = Field(default=False, alias="CREATE_NAMESPACE")
    set_values: list[str] = Field(default_factory=list, alias="SET")
    values_files: list[str] = Field(default_factory=list, alias="VALUES")
    wait: bool = Field(default=False, alias="WAIT")
    # CONTEXT D2: 600s default per Phase 3 corrections #5 (was "5m")
    timeout: str = Field(default="600s", alias="TIMEOUT")
    # CONTEXT D4 / closes #17: unset=no flag; 0=unlimited; N>=1=passthrough; ge=0 rejects negatives
    history_max: int | None = Field(default=None, ge=0, alias="HISTORY_MAX")

    # Repo + OCI chart sources (CHART-02, CHART-03) — Phase 4
    repo_url: str | None = Field(default=None, alias="REPO_URL")
    chart_version: str | None = Field(default=None, alias="CHART_VERSION")
    registry_username: str | None = Field(default=None, alias="REGISTRY_USERNAME")
    # SecretStr — prevents accidental leak via repr(settings) (RESEARCH §R13 / R4).
    # Unwrap with .get_secret_value() at the single call site in Plan 04-07's chart/oci.py.
    registry_password: SecretStr | None = Field(default=None, alias="REGISTRY_PASSWORD")

    # Cosign verify (CHART-04) — Phase 4; keyless only, no PUBKEY config var (per CONTEXT D5)
    chart_verify: bool = Field(default=False, alias="CHART_VERIFY")
    chart_verify_certificate_identity: str | None = Field(
        default=None,
        alias="CHART_VERIFY_CERTIFICATE_IDENTITY",
    )
    chart_verify_certificate_oidc_issuer: str | None = Field(
        default=None,
        alias="CHART_VERIFY_CERTIFICATE_OIDC_ISSUER",
    )

    # Action dispatch (v2 new fields); widened in Phase 5 to support diff + rollback (PIPE-02/04)
    action: Literal["upgrade", "diff", "rollback"] = Field(default="upgrade", alias="ACTION")
    dry_run: bool = Field(default=False, alias="DRY_RUN")

    # Observability (OBS-01 / OBS-02)
    log_format: Literal["human", "json"] = Field(default="human", alias="LOG_FORMAT")
    debug: bool = Field(default=False, alias="DEBUG")

    # Metadata injection (META-02 — tri-state: None=unset/META-03-detect, True=inject, False=skip)
    # Phase 5 breaking change: was bool=False; now bool|None=None so META-03 detector can fire
    # a one-time WARN when values.yaml references 'bitbucket:' but the flag was never set (D4).
    inject_bitbucket_metadata: bool | None = Field(default=None, alias="INJECT_BITBUCKET_METADATA")

    # ── Phase 5 additions ─────────────────────────────────────────────────────
    # PIPE-03 (D3): diff posted as Bitbucket PR comment
    post_diff_as_comment: bool = Field(default=False, alias="POST_DIFF_AS_COMMENT")
    # SecretStr prevents repr(settings) from leaking the token — R4/T-05-02 carry-forward.
    # Unwrap with .get_secret_value() at the single call site in bitbucket/pr_comment.py.
    bitbucket_token: SecretStr | None = Field(default=None, alias="BITBUCKET_TOKEN")
    # PIPE-05 (D5): adds --wait --rollback-on-failure --description "pipe:safe-upgrade" to helm
    # upgrade argv. (Helm 3 used --atomic; helm 4 renamed it to --rollback-on-failure — issue #70.)
    safe_upgrade: bool = Field(default=False, alias="SAFE_UPGRADE")
    # PIPE-04 (D5): target revision for ACTION=rollback; ge=0 mirrors history_max constraint
    revision: int | None = Field(default=None, ge=0, alias="REVISION")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Replace EnvSettingsSource with _CommaListEnvSource; restore all standard sources."""
        return (
            init_settings,
            _CommaListEnvSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )
