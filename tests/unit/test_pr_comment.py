"""Unit tests for aws_eks_helm_deploy.bitbucket.pr_comment.

Requirements traceability:
    PIPE-03:  POST/PUT idempotency via marker, 4xx/5xx tolerance, token scrub.
    T-05-02:  Tests 4+5 are the load-bearing regression gates -- asserts no token
              bytes appear in WARN log when the API returns a 401/4xx error.

Coverage target: 100% line + branch on src/aws_eks_helm_deploy/bitbucket/pr_comment.py.
"""

from __future__ import annotations

import io
import json
import urllib.error
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import structlog

from aws_eks_helm_deploy.bitbucket.pr_comment import (
    MARKER,
    _sanitize_response_body,
    post_diff_comment,
)

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

_WORKSPACE = "my-workspace"
_REPO = "my-repo"
_PR_ID = "42"
_TOKEN = "my-bitbucket-token-XYZ"  # noqa: S105 -- test fixture value, not a real credential
_DIFF = "+++ added\n--- removed\n"


def _make_urlopen_response(status: int, body: str) -> MagicMock:
    """Build a MagicMock that acts as urllib.request.urlopen context manager."""
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = body.encode("utf-8")
    resp.__enter__ = lambda self: self
    resp.__exit__ = lambda self, exc_type, exc, tb: None
    return resp


def _make_http_error(status: int, body: str) -> urllib.error.HTTPError:
    """Build a urllib.error.HTTPError with the given status and body."""
    fp = io.BytesIO(body.encode("utf-8"))
    return urllib.error.HTTPError(
        url="https://api.bitbucket.org/2.0/test",
        code=status,
        msg="Error",
        hdrs={},  # type: ignore[arg-type]
        fp=fp,
    )


def _empty_comments_response() -> str:
    """GET response with no existing comments."""
    return json.dumps({"values": [], "pagelen": 100, "page": 1, "size": 0})


def _comments_with_marker(comment_id: int = 99) -> str:
    """GET response with one comment that contains the idempotency marker."""
    return json.dumps(
        {
            "values": [
                {
                    "id": comment_id,
                    "content": {"raw": f"{MARKER}\n## old diff\n\n```diff\n-old\n```"},
                }
            ],
            "pagelen": 100,
            "page": 1,
            "size": 1,
        }
    )


def _created_response() -> str:
    """POST/PUT 201 response body."""
    return json.dumps({"id": 100, "content": {"raw": "ok"}})


# ---------------------------------------------------------------------------
# Test 1: GET returns empty -> POST is called (new comment)
# ---------------------------------------------------------------------------


def test_post_when_no_existing_comment() -> None:
    """When GET returns no comments, POST must be issued to create a new one."""
    get_resp = _make_urlopen_response(200, _empty_comments_response())
    post_resp = _make_urlopen_response(201, _created_response())

    with patch("urllib.request.urlopen", side_effect=[get_resp, post_resp]) as urlopen_mock:
        post_diff_comment(
            workspace=_WORKSPACE,
            repo_slug=_REPO,
            pr_id=_PR_ID,
            diff_text=_DIFF,
            token=_TOKEN,
        )

    # Two calls: GET then POST
    assert urlopen_mock.call_count == 2
    post_req = urlopen_mock.call_args_list[1][0][0]
    assert post_req.method == "POST"
    # POST URL ends with /comments?pagelen=100
    assert post_req.full_url.endswith("/comments?pagelen=100")


# ---------------------------------------------------------------------------
# Test 2: GET returns existing comment with marker -> PUT is called
# ---------------------------------------------------------------------------


def test_put_when_marker_comment_found() -> None:
    """When GET returns a comment with the marker, PUT must update it (not POST)."""
    existing_id = 99
    get_resp = _make_urlopen_response(200, _comments_with_marker(existing_id))
    put_resp = _make_urlopen_response(200, _created_response())

    with patch("urllib.request.urlopen", side_effect=[get_resp, put_resp]) as urlopen_mock:
        post_diff_comment(
            workspace=_WORKSPACE,
            repo_slug=_REPO,
            pr_id=_PR_ID,
            diff_text=_DIFF,
            token=_TOKEN,
        )

    assert urlopen_mock.call_count == 2
    put_req = urlopen_mock.call_args_list[1][0][0]
    assert put_req.method == "PUT"
    # PUT URL must include the comment id (not end with /comments?pagelen=100)
    assert f"/comments/{existing_id}" in put_req.full_url
    assert "pagelen" not in put_req.full_url


# ---------------------------------------------------------------------------
# Test 3: PUT body contains new diff, not the old one
# ---------------------------------------------------------------------------


def test_put_body_contains_new_diff() -> None:
    """When updating, the PUT request body must contain the NEW diff text."""
    existing_id = 77
    new_diff = "+++ brand new diff\n"
    get_resp = _make_urlopen_response(200, _comments_with_marker(existing_id))
    put_resp = _make_urlopen_response(200, _created_response())

    with patch("urllib.request.urlopen", side_effect=[get_resp, put_resp]) as urlopen_mock:
        post_diff_comment(
            workspace=_WORKSPACE,
            repo_slug=_REPO,
            pr_id=_PR_ID,
            diff_text=new_diff,
            token=_TOKEN,
        )

    put_req = urlopen_mock.call_args_list[1][0][0]
    assert put_req.data is not None
    body_parsed: dict[str, Any] = json.loads(put_req.data.decode("utf-8"))
    assert new_diff in body_parsed["content"]["raw"]
    assert MARKER in body_parsed["content"]["raw"]


# ---------------------------------------------------------------------------
# Test 4 (T-05-02 gate): 401 on GET -- token MUST NOT appear in WARN log
# ---------------------------------------------------------------------------


def test_401_get_token_is_scrubbed_from_warn_log() -> None:
    """When GET returns 401 with token in body, WARN log must not contain the token.

    T-05-02 regression gate: asserts '<redacted-token>' IS present and
    the literal token value is NOT present anywhere in the log entry.
    """
    body_with_token = f"Unauthorized: invalid token {_TOKEN} for request"
    exc = _make_http_error(401, body_with_token)

    with (
        patch("urllib.request.urlopen", side_effect=[exc]),
        structlog.testing.capture_logs() as captured,
    ):
        result = post_diff_comment(
            workspace=_WORKSPACE,
            repo_slug=_REPO,
            pr_id=_PR_ID,
            diff_text=_DIFF,
            token=_TOKEN,
        )

    assert result is None  # must return, not raise
    warn_entries = [c for c in captured if c["log_level"] == "warning"]
    assert len(warn_entries) == 1
    assert warn_entries[0]["event"] == "bitbucket.pr_comment.api_error"
    assert warn_entries[0]["status"] == 401
    # Load-bearing T-05-02 assertion: token bytes must be absent
    assert _TOKEN not in str(warn_entries[0])
    # Sentinel must be present
    assert "<redacted-token>" in warn_entries[0]["body"]


# ---------------------------------------------------------------------------
# Test 5 (T-05-02 gate): 401 -- Authorization header line stripped from log body
# ---------------------------------------------------------------------------


def test_401_get_authorization_header_stripped_from_warn_log() -> None:
    """WARN body must not contain 'Authorization: Bearer' (header scrub)."""
    body_with_auth_header = "Authorization: Bearer some-token\nfoo: bar\nmore text"
    exc = _make_http_error(401, body_with_auth_header)

    with (
        patch("urllib.request.urlopen", side_effect=[exc]),
        structlog.testing.capture_logs() as captured,
    ):
        post_diff_comment(
            workspace=_WORKSPACE,
            repo_slug=_REPO,
            pr_id=_PR_ID,
            diff_text=_DIFF,
            token="some-token",
        )

    warn_entries = [c for c in captured if c["log_level"] == "warning"]
    assert len(warn_entries) == 1
    logged_body: str = warn_entries[0]["body"]
    # The original "Authorization: Bearer some-token" line must be replaced with the sentinel.
    assert "Authorization: Bearer" not in logged_body
    assert "[Authorization: <redacted>]" in logged_body


# ---------------------------------------------------------------------------
# Test 6: 500 on POST -- WARN emitted, function returns None
# ---------------------------------------------------------------------------


def test_500_on_post_emits_warn_and_returns() -> None:
    """When POST returns 500, WARN is emitted and DiffAction can continue."""
    get_resp = _make_urlopen_response(200, _empty_comments_response())
    post_exc = _make_http_error(500, "Internal Server Error")

    with (
        patch("urllib.request.urlopen", side_effect=[get_resp, post_exc]),
        structlog.testing.capture_logs() as captured,
    ):
        result = post_diff_comment(
            workspace=_WORKSPACE,
            repo_slug=_REPO,
            pr_id=_PR_ID,
            diff_text=_DIFF,
            token=_TOKEN,
        )

    assert result is None
    warn_entries = [c for c in captured if c["log_level"] == "warning"]
    assert len(warn_entries) == 1
    assert warn_entries[0]["event"] == "bitbucket.pr_comment.api_error"
    assert warn_entries[0]["status"] == 500
    assert warn_entries[0]["phase"] == "post"


# ---------------------------------------------------------------------------
# Test 7: network failure (URLError) -- WARN emitted, function returns None
# ---------------------------------------------------------------------------


def test_urlopen_urleerror_emits_warn_and_returns() -> None:
    """When GET raises URLError, WARN with status=0 is emitted, no exception bubbles up."""
    url_err = urllib.error.URLError(reason="Connection refused")

    with (
        patch("urllib.request.urlopen", side_effect=[url_err]),
        structlog.testing.capture_logs() as captured,
    ):
        result = post_diff_comment(
            workspace=_WORKSPACE,
            repo_slug=_REPO,
            pr_id=_PR_ID,
            diff_text=_DIFF,
            token=_TOKEN,
        )

    assert result is None
    warn_entries = [c for c in captured if c["log_level"] == "warning"]
    assert len(warn_entries) == 1
    assert warn_entries[0]["status"] == 0


# ---------------------------------------------------------------------------
# Test 8: malformed JSON in GET response -- WARN emitted, function returns None
# ---------------------------------------------------------------------------


def test_malformed_json_in_get_response_emits_warn_and_returns() -> None:
    """When GET returns 2xx with a non-JSON body, WARN is emitted and function returns."""
    bad_get_resp = _make_urlopen_response(200, "not json at all {{{")

    with (
        patch("urllib.request.urlopen", side_effect=[bad_get_resp]),
        structlog.testing.capture_logs() as captured,
    ):
        result = post_diff_comment(
            workspace=_WORKSPACE,
            repo_slug=_REPO,
            pr_id=_PR_ID,
            diff_text=_DIFF,
            token=_TOKEN,
        )

    assert result is None
    warn_entries = [c for c in captured if c["log_level"] == "warning"]
    assert len(warn_entries) == 1
    assert warn_entries[0]["event"] == "bitbucket.pr_comment.api_error"
    assert warn_entries[0]["phase"] == "get_parse"


# ---------------------------------------------------------------------------
# Tests 9-11: _sanitize_response_body direct unit tests
# ---------------------------------------------------------------------------


def test_sanitize_response_body_scrubs_token_and_auth_header() -> None:
    """Given a body with token literal + Authorization header, both must be scrubbed."""
    body = "token=my-tok\nAuthorization: Bearer my-tok\nrest of body"
    result = _sanitize_response_body(body, "my-tok")

    assert "my-tok" not in result
    assert "<redacted-token>" in result
    # "Authorization: Bearer my-tok" line is replaced with the scrub sentinel
    assert "Authorization: Bearer" not in result
    assert "[Authorization: <redacted>]" in result
    assert "rest of body" in result


def test_sanitize_response_body_empty_body_returns_empty() -> None:
    """Empty string + any token -> empty string returned."""
    result = _sanitize_response_body("", "any-token")
    assert result == ""


def test_sanitize_response_body_empty_token_scrubs_auth_header_only() -> None:
    """Non-empty body + empty token -> only Authorization-line scrub applied."""
    body = "Authorization: Bearer hunter2\nno-secret-here"
    result = _sanitize_response_body(body, "")

    # Authorization line is scrubbed -- "Authorization: Bearer hunter2" replaced
    assert "Authorization: Bearer" not in result
    assert "[Authorization: <redacted>]" in result
    # No token replacement was attempted (token was empty)
    assert "<redacted-token>" not in result
    # Non-sensitive content preserved
    assert "no-secret-here" in result


# ---------------------------------------------------------------------------
# Test: POST when existing comments have no marker -> POST is issued
# ---------------------------------------------------------------------------


def test_post_when_existing_comment_has_no_marker() -> None:
    """When GET returns a comment WITHOUT the marker, a new POST must be issued."""
    # A comment that does NOT contain MARKER -- so existing_id stays None -> POST
    get_body = json.dumps(
        {
            "values": [{"id": 55, "content": {"raw": "Just a normal comment with no marker"}}],
            "pagelen": 100,
            "page": 1,
            "size": 1,
        }
    )
    get_resp = _make_urlopen_response(200, get_body)
    post_resp = _make_urlopen_response(201, _created_response())

    with patch("urllib.request.urlopen", side_effect=[get_resp, post_resp]) as urlopen_mock:
        post_diff_comment(
            workspace=_WORKSPACE,
            repo_slug=_REPO,
            pr_id=_PR_ID,
            diff_text=_DIFF,
            token=_TOKEN,
        )

    assert urlopen_mock.call_count == 2
    post_req = urlopen_mock.call_args_list[1][0][0]
    assert post_req.method == "POST"


# ---------------------------------------------------------------------------
# Test: POST body contains MARKER verbatim
# ---------------------------------------------------------------------------


def test_post_body_contains_marker() -> None:
    """The POST request body must contain the idempotency marker on line 1."""
    get_resp = _make_urlopen_response(200, _empty_comments_response())
    post_resp = _make_urlopen_response(201, _created_response())

    with patch("urllib.request.urlopen", side_effect=[get_resp, post_resp]) as urlopen_mock:
        post_diff_comment(
            workspace=_WORKSPACE,
            repo_slug=_REPO,
            pr_id=_PR_ID,
            diff_text=_DIFF,
            token=_TOKEN,
        )

    post_req = urlopen_mock.call_args_list[1][0][0]
    body: dict[str, Any] = json.loads(post_req.data.decode("utf-8"))
    raw: str = body["content"]["raw"]
    assert raw.startswith(MARKER), f"MARKER must be on line 1 of body; got: {raw[:80]!r}"
    assert _DIFF in raw


# ---------------------------------------------------------------------------
# Test: diff text appears in POST body
# ---------------------------------------------------------------------------


def test_post_body_contains_diff_text() -> None:
    """The POST body must embed the diff_text passed to post_diff_comment."""
    diff = "custom-diff-output-unique-abc123"
    get_resp = _make_urlopen_response(200, _empty_comments_response())
    post_resp = _make_urlopen_response(201, _created_response())

    with patch("urllib.request.urlopen", side_effect=[get_resp, post_resp]) as urlopen_mock:
        post_diff_comment(
            workspace=_WORKSPACE,
            repo_slug=_REPO,
            pr_id=_PR_ID,
            diff_text=diff,
            token=_TOKEN,
        )

    post_req = urlopen_mock.call_args_list[1][0][0]
    body: dict[str, Any] = json.loads(post_req.data.decode("utf-8"))
    assert diff in body["content"]["raw"]
