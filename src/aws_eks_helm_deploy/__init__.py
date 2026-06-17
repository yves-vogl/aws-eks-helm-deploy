from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__: str = version("aws-eks-helm-deploy")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

__all__ = ["__version__"]
