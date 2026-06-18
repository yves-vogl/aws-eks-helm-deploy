"""ChartSource Protocol + ResolvedChart value object.

Uniform interface for LocalChart, RepoChart, OciChart.

Requirements traceability:
  - CHART-02 (Phase 4): RepoChart will implement this Protocol.
  - CHART-03 (Phase 4): OciChart will implement this Protocol.
  - CHART-01 (Phase 3): LocalChart (refactored from resolve_local_chart) implements this Protocol.
  - CHART-05 (Phase 3): ResolvedChart.name + .version surface in the success message.

Promoted from chart/local.py — Phase 3's ResolvedChart frozen dataclass moves here unchanged
so all three ChartSource implementations can share it.
"""

from __future__ import annotations

import contextlib
import dataclasses
import pathlib
from typing import Protocol, runtime_checkable

__all__: list[str] = ["ChartSource", "ResolvedChart"]


@dataclasses.dataclass(frozen=True)
class ResolvedChart:
    """Immutable resolved chart descriptor — same shape as Phase 3."""

    name: str
    version: str
    source_path: pathlib.Path


@runtime_checkable
class ChartSource(Protocol):
    """Protocol satisfied by LocalChart, RepoChart, OciChart.

    .resolve() yields a ResolvedChart whose source_path is valid only inside
    the with-block. Implementations clean up tempdirs on context exit.
    LocalChart's resolve() is degenerate — yields the on-disk path; no cleanup.
    """

    def resolve(self) -> contextlib.AbstractContextManager[ResolvedChart]: ...
