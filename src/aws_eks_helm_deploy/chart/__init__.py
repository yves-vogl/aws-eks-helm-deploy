"""chart subpackage — ChartSource Protocol + LocalChart / RepoChart / OciChart resolvers.

Phase 4 factory: select_chart_source(settings) -> ChartSource routes by settings.chart prefix.
  - oci://   -> OciChart (Phase 4 — Plan 04-07 shipped)
  - repo://  -> RepoChart (Phase 4 — Plan 04-06 shipped)
  - else     -> LocalChart (degenerate context-manager — Phase 3 + Plan 04-05-02 refactor)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aws_eks_helm_deploy.chart.base import ChartSource, ResolvedChart
from aws_eks_helm_deploy.chart.local import LocalChart
from aws_eks_helm_deploy.errors import ConfigurationError

if TYPE_CHECKING:
    from aws_eks_helm_deploy.settings import Settings

__all__: list[str] = ["ChartSource", "LocalChart", "ResolvedChart", "select_chart_source"]


def select_chart_source(settings: Settings) -> ChartSource:
    """Route settings.chart to the matching ChartSource implementation.

    Decision tree (per CONTEXT D3):
        if chart.startswith("oci://"):   return OciChart(...)  -- Plan 04-07
        if chart.startswith("repo://"):  return RepoChart(...) -- Plan 04-06; requires REPO_URL
        else:                            return LocalChart(chart_spec=chart)
    """
    chart = settings.chart
    if chart is None:
        raise ConfigurationError("CHART is required (set the chart spec env var)")

    if chart.startswith("oci://"):
        return _build_oci_chart(settings, chart)

    if chart.startswith("repo://"):
        name, _, chart_name = chart.removeprefix("repo://").partition("/")
        if not name or not chart_name:
            raise ConfigurationError("CHART=repo:// must be 'repo://<repo-name>/<chart>'")
        if not settings.repo_url:
            raise ConfigurationError("CHART=repo://… requires REPO_URL")
        return _build_repo_chart(
            name=name,
            chart_name=chart_name,
            repo_url=settings.repo_url,
            version=settings.chart_version,
        )

    return LocalChart(chart_spec=chart, repo_root=None)


def _build_oci_chart(settings: Settings, chart: str) -> ChartSource:
    """Construct OciChart — shipped in Plan 04-07."""
    from aws_eks_helm_deploy.chart.oci import OciChart

    return OciChart(
        reference=chart.removeprefix("oci://"),
        version=settings.chart_version,
        registry_username=settings.registry_username,
        registry_password=settings.registry_password,
        verify=settings.chart_verify,
        verify_identity=settings.chart_verify_certificate_identity,
        verify_oidc_issuer=settings.chart_verify_certificate_oidc_issuer,
    )


def _build_repo_chart(
    name: str,
    chart_name: str,
    repo_url: str,
    version: str | None,
) -> ChartSource:
    """Construct RepoChart — shipped in Plan 04-06."""
    from aws_eks_helm_deploy.chart.repo import RepoChart

    return RepoChart(
        name=name,
        chart=chart_name,
        repo_url=repo_url,
        version=version,
    )
