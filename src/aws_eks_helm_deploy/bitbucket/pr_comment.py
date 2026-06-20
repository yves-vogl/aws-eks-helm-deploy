"""Idempotent Bitbucket PR-comment poster for helm diff output (PIPE-03).

Requirements traceability:
    PIPE-03    — posts the redacted helm diff as a single, idempotent comment on
                 the Bitbucket Cloud PR when POST_DIFF_AS_COMMENT=true.

Architecture (CONTEXT D3 + 05-RESEARCH "CONTRADICTION 1"):
    HTTP is via stdlib ``urllib.request`` only. ``bitbucket-pipes-toolkit`` 6.2.0
    does NOT expose a PR-comments wrapper, and its ``HttpRequestsHandler`` calls
    ``fail()`` on HTTP errors — directly violating the D3 "4xx-tolerant,
    warning-only" contract. ``urllib.request`` gives full control over error
    handling with zero additional dependencies.

D6 invariant: NO ``subprocess`` import is present in this module. The token is
passed as a function-local ``str`` and placed in an HTTP ``Authorization: Bearer``
header inside ``_api_request``. It never touches subprocess argv.

Idempotency contract (D3):
    1. GET  /2.0/repositories/{ws}/{repo}/pullrequests/{pr_id}/comments?pagelen=100
    2. Search each comment body for the marker ``<!-- aws-eks-helm-deploy:diff -->``.
    3. If found  → PUT  .../comments/{comment_id}   (replace existing body)
       If not    → POST .../comments                (create new comment)
    4xx/5xx responses are logged as WARN (with token-scrubbed body) and the
    function returns — PR-comment posting is observability, not critical path.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Final

from aws_eks_helm_deploy.logging import get_logger

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

MARKER: Final[str] = "<!-- aws-eks-helm-deploy:diff -->"
BITBUCKET_API_BASE: Final[str] = "https://api.bitbucket.org/2.0"
_AUTH_HEADER_LINE: Final[re.Pattern[str]] = re.compile(r"^[Aa]uthorization:.*$", re.MULTILINE)
_HTTP_TIMEOUT_SECONDS: Final[int] = 10

__all__: list[str] = ["post_diff_comment"]

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _sanitize_response_body(body: str, token: str) -> str:
    """Strip token literal and Authorization header lines from a response body.

    Applied BEFORE any ``logger.warning(... body=...)`` call to prevent
    BITBUCKET_TOKEN values from appearing in logs (T-05-02 mitigation).

    Args:
        body:  Raw HTTP response body string (may be empty).
        token: The literal token value to redact (may be empty).

    Returns:
        Scrubbed copy of ``body`` with token occurrences replaced by
        ``"<redacted-token>"`` and ``Authorization:`` lines replaced by
        ``"[Authorization: <redacted>]"``.
    """
    # Always strip Authorization header lines regardless of token value.
    scrubbed = _AUTH_HEADER_LINE.sub("[Authorization: <redacted>]", body)

    # Only replace token substring when token is truthy (non-empty).
    if token and token in scrubbed:
        scrubbed = scrubbed.replace(token, "<redacted-token>")

    return scrubbed


def _api_request(
    method: str,
    url: str,
    token: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, str]:
    """Execute a single Bitbucket API request and return (status, response_body).

    Handles ``urllib.error.HTTPError`` (API-level errors, status >= 400) and
    ``urllib.error.URLError`` (network-level errors) without raising — callers
    inspect the returned status code to decide how to log and whether to return
    early.

    Args:
        method: HTTP verb (``"GET"``, ``"POST"``, ``"PUT"``).
        url:    Full Bitbucket API URL.
        token:  Bearer token for the ``Authorization`` header.
        body:   Optional JSON-serialisable request body dict.

    Returns:
        Tuple of ``(http_status_code, response_body_string)``.
        On ``URLError``, status is ``0`` and the body is the reason string.
    """
    headers: dict[str, str] = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data: bytes | None = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)  # noqa: S310 — URL is constructed from BITBUCKET_API_BASE (static https) + path; no http:// schemes possible.

    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_SECONDS) as resp:  # noqa: S310 — URL is constructed from BITBUCKET_API_BASE (static https) + caller-provided path segments; no http:// possible.
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        return 0, str(exc.reason)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def post_diff_comment(
    workspace: str,
    repo_slug: str,
    pr_id: str,
    diff_text: str,
    token: str,
) -> None:
    """Post (or update) the helm diff as a single idempotent Bitbucket PR comment.

    Implements the D3 GET-then-POST-or-PUT idempotency algorithm. The function
    is fire-and-forget: all HTTP error paths emit a WARN log and return without
    raising — PR-comment posting is observability, not critical path (D3 R2
    mitigation).

    The ``diff_text`` MUST already be redacted (D1) before being passed to this
    function. The caller (``DiffAction.run``) is responsible for that invariant.

    Args:
        workspace: Bitbucket workspace slug (from ``BITBUCKET_WORKSPACE`` env var).
        repo_slug: Repository slug (from ``BITBUCKET_REPO_SLUG`` env var).
        pr_id:     Pull-request ID string (from ``BITBUCKET_PR_ID`` env var).
        diff_text: Redacted diff text to embed in the comment body.
        token:     Bitbucket App Password or access token (plain string after
                   SecretStr unwrap at the single call site in ``DiffAction``).
    """
    comments_url = (
        f"{BITBUCKET_API_BASE}/repositories/{workspace}/{repo_slug}"
        f"/pullrequests/{pr_id}/comments?pagelen=100"
    )

    # Step 1: GET existing comments (first page — 100 comments is sufficient for
    # Phase 5 v2.0; paginated ``next`` iteration is a follow-up if needed).
    status, body = _api_request("GET", comments_url, token)
    if status >= 400:
        logger.warning(
            "bitbucket.pr_comment.api_error",
            phase="get",
            status=status,
            body=_sanitize_response_body(body, token),
        )
        return

    # Step 2: Parse response and search for the idempotency marker.
    try:
        payload: dict[str, Any] = json.loads(body)
    except json.JSONDecodeError:
        logger.warning(
            "bitbucket.pr_comment.api_error",
            phase="get_parse",
            status=status,
            body=_sanitize_response_body(body, token),
        )
        return

    existing_id: int | None = None
    for comment in payload.get("values", []):
        raw_body: str = comment.get("content", {}).get("raw", "")
        if MARKER in raw_body:
            existing_id = comment["id"]
            break

    # Step 3: Build the comment body (marker on line 1 per D3 contract).
    comment_payload: dict[str, Any] = {
        "content": {
            "raw": (f"{MARKER}\n## helm diff for release on cluster\n\n```diff\n{diff_text}\n```")
        }
    }

    # Step 4: POST (new) or PUT (update existing).
    if existing_id is None:
        status, body = _api_request("POST", comments_url, token, comment_payload)
    else:
        comment_url = (
            f"{BITBUCKET_API_BASE}/repositories/{workspace}/{repo_slug}"
            f"/pullrequests/{pr_id}/comments/{existing_id}"
        )
        status, body = _api_request("PUT", comment_url, token, comment_payload)

    # Step 5: Handle API errors on POST/PUT — warning-only, never raise.
    if status >= 400:
        logger.warning(
            "bitbucket.pr_comment.api_error",
            phase="post" if existing_id is None else "put",
            status=status,
            body=_sanitize_response_body(body, token),
        )
        return

    # Step 6: Success log.
    logger.info(
        "bitbucket.pr_comment.posted",
        action="put" if existing_id else "post",
        pr_id=pr_id,
    )
