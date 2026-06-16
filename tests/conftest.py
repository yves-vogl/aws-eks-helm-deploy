"""Top-level pytest configuration for the aws-eks-helm-deploy test suite.

This module auto-applies the ``unit`` marker to any test collected under
``tests/unit/`` that carries neither the ``integration`` nor the ``acceptance``
marker.  This makes the ``addopts = "-m 'unit'"`` default in pyproject.toml
work transparently even when individual test functions omit the explicit
``@pytest.mark.unit`` decorator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Sequence


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-mark tests in tests/unit/ as ``unit`` when unmarked."""
    unit_mark = pytest.mark.unit
    tier_marks: Sequence[str] = ("unit", "integration", "acceptance")

    for item in items:
        # Only apply auto-mark to items physically inside tests/unit/
        node_path = str(item.fspath)
        if "/tests/unit/" not in node_path:
            continue
        has_tier_mark = any(item.get_closest_marker(m) for m in tier_marks)
        if not has_tier_mark:
            item.add_marker(unit_mark, append=False)
