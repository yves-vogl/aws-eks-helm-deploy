"""Thin adapter around bitbucket-pipes-toolkit for success/fail output.

STUB MODULE: This is a deliberate Phase 1 placeholder. The Pipe instance is
initialized lazily without schema validation. Phase 2 will replace this with
a schema-driven adapter using Pipe(pipe_metadata=..., schema=...) once the
CLUSTER_NAME-required schema exists.

The only consumer-facing contract is:
  - success(message: str) -> None
  - fail(message: str) -> None
"""

from __future__ import annotations

import bitbucket_pipes_toolkit  # type: ignore[import-untyped]
from bitbucket_pipes_toolkit import Pipe


class PipeIO:
    """Adapter around bitbucket-pipes-toolkit Pipe for success/fail messaging."""

    def __init__(self, *, pipe_metadata_path: str = "pipe.yml") -> None:
        """Initialise the adapter. The Pipe instance is created lazily on first use."""
        self._pipe_metadata_path = pipe_metadata_path
        self._pipe: Pipe | None = None

    def _get_pipe(self) -> Pipe:
        if self._pipe is None:
            self._pipe = Pipe(pipe_metadata=self._pipe_metadata_path, schema={})
        return self._pipe

    def success(self, message: str) -> None:
        """Emit a success message via the bitbucket-pipes-toolkit success channel."""
        self._get_pipe().success(message=message)

    def fail(self, message: str) -> None:
        """Emit a failure message via the bitbucket-pipes-toolkit fail channel."""
        self._get_pipe().fail(message=message)


__all__ = ["PipeIO"]

# Silence the unused import — bitbucket_pipes_toolkit is imported for side effects
# (toolkit registration) and to verify 3.13 compat at module load time.
_ = bitbucket_pipes_toolkit
