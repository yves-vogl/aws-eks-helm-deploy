"""Unit tests for ChartSource Protocol + ResolvedChart frozen dataclass (chart/base.py).

Requirements traceability:
    CHART-02: ChartSource Protocol that RepoChart will implement (Plan 04-06).
    CHART-03: ChartSource Protocol that OciChart will implement (Plan 04-07).
    CHART-01: LocalChart (refactored) implements ChartSource — verified via runtime_checkable.
"""

from __future__ import annotations

import contextlib
import dataclasses
import pathlib
import types

import pytest

from aws_eks_helm_deploy.chart.base import ChartSource, ResolvedChart

# ---------------------------------------------------------------------------
# ResolvedChart tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_resolved_chart_is_frozen_dataclass() -> None:
    """ResolvedChart is a frozen dataclass — mutation raises FrozenInstanceError."""
    assert dataclasses.is_dataclass(ResolvedChart)
    assert ResolvedChart.__dataclass_params__.frozen  # type: ignore[attr-defined]

    chart = ResolvedChart(name="x", version="1.0.0", source_path=pathlib.Path("/x"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        chart.name = "y"  # type: ignore[misc]


@pytest.mark.unit
def test_resolved_chart_has_required_fields_in_order() -> None:
    """ResolvedChart fields are name:str, version:str, source_path:pathlib.Path — in that order."""
    fields = dataclasses.fields(ResolvedChart)
    assert len(fields) == 3
    assert fields[0].name == "name"
    assert fields[0].type == "str"  # forward-ref string from __future__ annotations
    assert fields[1].name == "version"
    assert fields[1].type == "str"
    assert fields[2].name == "source_path"
    assert fields[2].type == "pathlib.Path"


# ---------------------------------------------------------------------------
# ChartSource Protocol test
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_chart_source_protocol_is_runtime_checkable() -> None:
    """A duck-typed object with .resolve() satisfies isinstance(obj, ChartSource) at runtime.

    This proves the @runtime_checkable decorator is active and the factory's
    downstream type-check use will work for LocalChart / RepoChart / OciChart.
    """
    fake_resolved = ResolvedChart(name="x", version="1", source_path=pathlib.Path("/x"))
    duck = types.SimpleNamespace(resolve=lambda: contextlib.nullcontext(fake_resolved))
    assert isinstance(duck, ChartSource)

    # A plain namespace without .resolve does NOT satisfy the Protocol
    no_resolve = types.SimpleNamespace()
    assert not isinstance(no_resolve, ChartSource)
