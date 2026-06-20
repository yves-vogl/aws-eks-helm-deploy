"""Pure-Python redactor for helm output streams (SEC-06).

REQ traceability:
    SEC-06     — replaces ``data:`` and ``stringData:`` blocks of every
                 ``kind: Secret`` YAML document with the literal sentinel
                 string ``<redacted>`` before the text is returned to any
                 caller (logs, PR comments, stdout).

Architecture (CONTEXT D1):
    This module is pure Python (yaml + re only). NO subprocess is imported.
    The D6 invariant of exactly 2 subprocess-importing files (helm/client.py
    and chart/oci.py) is preserved — this module adds no third import.

    This redactor is content-filter-only: it handles the raw text payload
    that flows into PR comments and stdout. structlog's ``bind_safe_context``
    (Phase 2 convention) handles structured-kwargs redaction at the logger
    boundary. Both layers remain independent — defense in depth.

YAMLError passthrough contract (CONTEXT D1):
    If ``yaml.safe_load_all()`` raises ``yaml.YAMLError`` (e.g., helm wrote a
    non-YAML progress message to stderr), the input string is returned
    unchanged. The redactor is a content filter, not a parser of last resort.
"""

from __future__ import annotations

from typing import Any, Final

import yaml

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

REDACTED_SENTINEL: Final[str] = "<redacted>"

__all__: list[str] = ["redact_helm_output"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def redact_helm_output(text: str) -> str:
    """Redact ``data:`` and ``stringData:`` blocks from ``kind: Secret`` YAML docs.

    Parses ``text`` as multi-document YAML via ``yaml.safe_load_all``.  For
    each document whose ``kind`` is ``"Secret"``, the ``data`` and
    ``stringData`` values are replaced with the literal sentinel string
    ``"<redacted>"``.  All other documents are passed through unchanged.

    Args:
        text: Raw stdout or stderr string captured from a helm subprocess.

    Returns:
        Re-serialised YAML string with Secret payloads replaced by the
        sentinel, or the original ``text`` verbatim if it cannot be parsed
        as YAML.
    """
    try:
        # T-05-03 mitigation: SafeLoader rejects alias-expansion / billion-laughs attacks.
        docs: list[Any] = list(yaml.safe_load_all(text))
    except yaml.YAMLError:
        # CONTEXT D1: passthrough for non-YAML helm output (e.g., progress messages on stderr).
        return text

    redacted = False
    for doc in docs:
        if isinstance(doc, dict) and doc.get("kind") == "Secret":
            if "data" in doc:
                doc["data"] = REDACTED_SENTINEL
                redacted = True
            if "stringData" in doc:
                doc["stringData"] = REDACTED_SENTINEL
                redacted = True

    if not redacted:
        # No Secret docs found — return the original text verbatim to avoid
        # YAML re-serialization artefacts (e.g. appended '...\n' for scalar docs).
        return text

    return yaml.safe_dump_all(docs, sort_keys=False)
