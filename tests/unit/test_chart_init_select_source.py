"""Unit tests for select_chart_source factory in chart/__init__.py.

Requirements traceability:
    CHART-02: RepoChart branch (skip-marked; ships in Plan 04-06)
    CHART-03: OciChart branch (skip-marked; ships in Plan 04-07)
    CHART-01: LocalChart branch fully operational in this plan
"""

from __future__ import annotations

import pytest

from aws_eks_helm_deploy.chart import LocalChart, select_chart_source
from aws_eks_helm_deploy.errors import ConfigurationError
from aws_eks_helm_deploy.settings import Settings


def _make_settings(**overrides: object) -> Settings:
    """Build a minimal Settings with required fields."""
    defaults: dict[str, object] = dict(
        aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
        aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        aws_region="eu-central-1",
    )
    return Settings(**(defaults | overrides))


# ---------------------------------------------------------------------------
# LocalChart (fully operational in Plan 04-05)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_select_chart_source_returns_local_chart_for_bare_path() -> None:
    """select_chart_source returns LocalChart for a plain path (no scheme prefix)."""
    s = _make_settings(chart="/tmp/charts/foo")

    source = select_chart_source(s)

    assert isinstance(source, LocalChart)


@pytest.mark.unit
def test_select_chart_source_chart_none_raises_config_error() -> None:
    """select_chart_source raises ConfigurationError when settings.chart is None."""
    s = _make_settings()  # no CHART

    with pytest.raises(ConfigurationError) as exc_info:
        select_chart_source(s)

    assert "CHART is required" in str(exc_info.value)
    assert exc_info.value.exit_code == 1


# ---------------------------------------------------------------------------
# repo:// validation (the routing logic exists; RepoChart ships in Plan 04-06)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_select_chart_source_repo_without_repo_url_raises_config_error() -> None:
    """select_chart_source raises ConfigurationError for repo:// without REPO_URL."""
    s = _make_settings(chart="repo://stable/postgres")  # no REPO_URL

    with pytest.raises(ConfigurationError) as exc_info:
        select_chart_source(s)

    assert "requires REPO_URL" in str(exc_info.value)
    assert exc_info.value.exit_code == 1


@pytest.mark.unit
def test_select_chart_source_repo_malformed_raises_config_error() -> None:
    """select_chart_source raises ConfigurationError for malformed repo:// spec."""
    s = _make_settings(chart="repo://", repo_url="https://charts.example.com")

    with pytest.raises(ConfigurationError) as exc_info:
        select_chart_source(s)

    assert "repo://<repo-name>/<chart>" in str(exc_info.value)
    assert exc_info.value.exit_code == 1


# ---------------------------------------------------------------------------
# Future branches — skip until the implementing plan lands
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_select_chart_source_routes_repo_prefix_to_repo_chart() -> None:
    """select_chart_source returns RepoChart for repo:// prefix (Plan 04-06)."""
    from aws_eks_helm_deploy.chart.repo import RepoChart

    s = _make_settings(
        chart="repo://bitnami/redis",
        repo_url="https://charts.bitnami.com/bitnami",
        chart_version="18.5.0",
    )
    source = select_chart_source(s)
    assert isinstance(source, RepoChart)
    assert source._name == "bitnami"
    assert source._chart == "redis"
    assert source._version == "18.5.0"


@pytest.mark.unit
@pytest.mark.skip(reason="Plan 04-07 OciChart not yet landed in this plan")
def test_select_chart_source_routes_oci_prefix_to_oci_chart() -> None:
    # UNSKIP: Plan 04-07 ships OciChart
    """select_chart_source returns OciChart for oci:// prefix (Plan 04-07)."""
    from aws_eks_helm_deploy.chart.oci import OciChart  # type: ignore[import-not-found]

    s = _make_settings(
        chart="oci://ghcr.io/org/chart",
        chart_version="1.0.0",
    )
    source = select_chart_source(s)
    assert isinstance(source, OciChart)
