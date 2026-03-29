"""Tests for the HTTP fetcher — TDD phase."""

import pytest
import requests
from unittest.mock import MagicMock, patch
from crawler.fetcher import Fetcher
from crawler.models import ErrorType


@pytest.fixture
def mock_session():
    return MagicMock(spec=requests.Session)


def make_response(status_code, text="<html/>", ok=None):
    """Helper — builds a mock HTTP response."""
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    response.ok = (status_code < 400) if ok is None else ok
    response.url = "https://example.com"
    response.headers = {}
    return response


# ---------------------------------------------------------------------------
# Existing happy-path tests (unchanged)
# ---------------------------------------------------------------------------

def test_returns_html_and_status_on_success(mock_session):
    mock_session.get.return_value = make_response(200, "<html><body>Hello</body></html>")

    fetcher = Fetcher(session=mock_session)
    html, status_code, error, error_type = fetcher.fetch("https://example.com")

    assert html == "<html><body>Hello</body></html>"
    assert status_code == 200
    assert error is None
    assert error_type is None


def test_accepts_injected_session(mock_session):
    mock_session.get.return_value = make_response(200)

    fetcher = Fetcher(session=mock_session)
    fetcher.fetch("https://example.com")

    mock_session.get.assert_called_with("https://example.com", timeout=10)


# ---------------------------------------------------------------------------
# Non-retryable errors — give up immediately, no retries
# ---------------------------------------------------------------------------

def test_404_is_not_retried(mock_session):
    """404 means the page doesn't exist — retrying won't help."""
    mock_session.get.return_value = make_response(404)

    fetcher = Fetcher(session=mock_session, max_retries=3)
    html, status_code, error, error_type = fetcher.fetch("https://example.com/missing")

    assert html is None
    assert status_code == 404
    assert error_type == ErrorType.NOT_FOUND
    assert mock_session.get.call_count == 1  # tried exactly once, no retries


def test_403_is_not_retried(mock_session):
    """403 means we're forbidden — retrying won't help."""
    mock_session.get.return_value = make_response(403)

    fetcher = Fetcher(session=mock_session, max_retries=3)
    html, status_code, error, error_type = fetcher.fetch("https://example.com/secret")

    assert error_type == ErrorType.FORBIDDEN
    assert mock_session.get.call_count == 1


# ---------------------------------------------------------------------------
# Retryable errors — should retry up to max_retries
# ---------------------------------------------------------------------------

def test_500_is_retried_up_to_max(mock_session):
    """500 server error is transient — we should retry."""
    mock_session.get.return_value = make_response(500)

    fetcher = Fetcher(session=mock_session, max_retries=3, backoff_base=0)
    html, status_code, error, error_type = fetcher.fetch("https://example.com")

    assert html is None
    assert error_type == ErrorType.SERVER_ERROR
    assert mock_session.get.call_count == 4  # 1 original + 3 retries


def test_succeeds_after_transient_500(mock_session):
    """If the server recovers, we should return the successful response."""
    mock_session.get.side_effect = [
        make_response(500),
        make_response(500),
        make_response(200, "<html>ok</html>"),
    ]

    fetcher = Fetcher(session=mock_session, max_retries=3, backoff_base=0)
    html, status_code, error, error_type = fetcher.fetch("https://example.com")

    assert html == "<html>ok</html>"
    assert error is None
    assert error_type is None
    assert mock_session.get.call_count == 3


def test_connection_error_is_retried(mock_session):
    """Network blips should be retried."""
    mock_session.get.side_effect = requests.ConnectionError("refused")

    fetcher = Fetcher(session=mock_session, max_retries=2, backoff_base=0)
    html, status_code, error, error_type = fetcher.fetch("https://example.com")

    assert html is None
    assert error_type == ErrorType.CONNECTION
    assert mock_session.get.call_count == 3  # 1 original + 2 retries


def test_timeout_error_is_retried(mock_session):
    """Timeouts are transient — retry."""
    mock_session.get.side_effect = requests.Timeout("timed out")

    fetcher = Fetcher(session=mock_session, max_retries=2, backoff_base=0)
    html, status_code, error, error_type = fetcher.fetch("https://example.com")

    assert error_type == ErrorType.TIMEOUT
    assert mock_session.get.call_count == 3


# ---------------------------------------------------------------------------
# 429 Too Many Requests — retry after waiting
# ---------------------------------------------------------------------------

def test_429_respects_retry_after_header(mock_session):
    """When server says 429 with Retry-After: 2, we wait 2 seconds then retry."""
    rate_limited = make_response(429)
    rate_limited.headers = {"Retry-After": "2"}
    success = make_response(200, "<html>ok</html>")
    mock_session.get.side_effect = [rate_limited, success]

    fetcher = Fetcher(session=mock_session, max_retries=3, backoff_base=0)

    with patch("time.sleep") as mock_sleep:
        html, _, error, error_type = fetcher.fetch("https://example.com")

    assert html == "<html>ok</html>"
    assert error is None
    mock_sleep.assert_any_call(2.0)  # respected the Retry-After header


def test_429_exhausted_retries_returns_rate_limited_error(mock_session):
    """If 429 keeps coming after all retries, return RATE_LIMITED error type."""
    mock_session.get.return_value = make_response(429)

    fetcher = Fetcher(session=mock_session, max_retries=2, backoff_base=0)
    with patch("time.sleep"):
        html, status_code, error, error_type = fetcher.fetch("https://example.com")

    assert html is None
    assert error_type == ErrorType.RATE_LIMITED


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def test_logs_debug_on_each_request_attempt(mock_session, caplog):
    """Every attempt should be logged at DEBUG so we can trace what happened."""
    import logging
    mock_session.get.side_effect = [make_response(500), make_response(200)]

    fetcher = Fetcher(session=mock_session, max_retries=1, backoff_base=0)
    with caplog.at_level(logging.DEBUG, logger="crawler.fetcher"):
        fetcher.fetch("https://example.com")

    debug_msgs = [r.message for r in caplog.records if r.levelno == logging.DEBUG]
    assert any("https://example.com" in m for m in debug_msgs)


def test_logs_warning_on_retry(mock_session, caplog):
    """Each retry should produce a WARNING so operators know something is wrong."""
    import logging
    mock_session.get.return_value = make_response(500)

    fetcher = Fetcher(session=mock_session, max_retries=2, backoff_base=0)
    with caplog.at_level(logging.WARNING, logger="crawler.fetcher"):
        with patch("time.sleep"):
            fetcher.fetch("https://example.com")

    warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_msgs) >= 2  # one warning per retry


def test_logs_error_when_all_retries_exhausted(mock_session, caplog):
    """When we give up entirely, log at ERROR so it's easy to spot."""
    import logging
    mock_session.get.return_value = make_response(500)

    fetcher = Fetcher(session=mock_session, max_retries=1, backoff_base=0)
    with caplog.at_level(logging.ERROR, logger="crawler.fetcher"):
        with patch("time.sleep"):
            fetcher.fetch("https://example.com")

    error_msgs = [r.message for r in caplog.records if r.levelno == logging.ERROR]
    assert any("https://example.com" in m for m in error_msgs)


# ---------------------------------------------------------------------------
# Backoff — wait times grow exponentially between retries
# ---------------------------------------------------------------------------

def test_backoff_doubles_each_retry(mock_session):
    """Wait times should be: base, base*2, base*4 — doubling each time."""
    mock_session.get.return_value = make_response(500)

    fetcher = Fetcher(session=mock_session, max_retries=3, backoff_base=1.0)

    sleep_calls = []
    with patch("time.sleep", side_effect=lambda t: sleep_calls.append(t)):
        fetcher.fetch("https://example.com")

    # Each wait should be >= the previous (exponential growth)
    # We check relative ordering rather than exact values because of jitter
    assert len(sleep_calls) == 3
    assert sleep_calls[1] > sleep_calls[0]
    assert sleep_calls[2] > sleep_calls[1]
