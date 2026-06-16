"""Unit tests for aws_eks_helm_deploy.__init__.

Tests cover:
  - __version__ is a non-empty string when package is installed
  - PackageNotFoundError fallback sets __version__ = "0.0.0-dev"
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import patch

import pytest


@pytest.mark.unit
def test_version_is_string() -> None:
    """__version__ is a non-empty string in the installed dev environment."""
    import aws_eks_helm_deploy

    assert isinstance(aws_eks_helm_deploy.__version__, str)
    assert aws_eks_helm_deploy.__version__ != ""


@pytest.mark.unit
def test_version_fallback_on_package_not_found() -> None:
    """When the package is not installed, __version__ falls back to '0.0.0-dev'.

    The try/except block in __init__.py runs at module import time, so we must
    evict the cached module and reload with the patched importlib.metadata.version.
    """
    from importlib.metadata import PackageNotFoundError

    # Remove cached module so reload re-executes the try/except block
    sys.modules.pop("aws_eks_helm_deploy", None)

    with patch(
        "importlib.metadata.version",
        side_effect=PackageNotFoundError("aws-eks-helm-deploy"),
    ):
        import aws_eks_helm_deploy as pkg

        assert pkg.__version__ == "0.0.0-dev"

    # Restore the real module so subsequent tests are unaffected
    sys.modules.pop("aws_eks_helm_deploy", None)
    importlib.import_module("aws_eks_helm_deploy")
