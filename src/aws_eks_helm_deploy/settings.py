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
  - INJECT_BITBUCKET_METADATA defaults to False (was unconditional in v1)
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Pipe configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=True,
        extra="ignore",
    )

    # AWS credentials (required at runtime in Phase 2+; optional in Phase 1 skeleton)
    aws_region: str = Field(default="eu-central-1", alias="AWS_REGION")
    aws_access_key_id: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    role_arn: str | None = Field(default=None, alias="ROLE_ARN")
    session_name: str = Field(default="BitbucketPipe", alias="SESSION_NAME")

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
    timeout: str = Field(default="5m", alias="TIMEOUT")

    # Action dispatch (v2 new fields)
    action: str = Field(default="upgrade", alias="ACTION")
    dry_run: bool = Field(default=False, alias="DRY_RUN")

    # Observability (OBS-01 / OBS-02)
    log_format: str = Field(default="human", alias="LOG_FORMAT")  # "human" | "json"
    debug: bool = Field(default=False, alias="DEBUG")

    # Metadata injection (v2 default=False — breaking change vs v1 which was unconditional)
    inject_bitbucket_metadata: bool = Field(default=False, alias="INJECT_BITBUCKET_METADATA")
