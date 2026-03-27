"""Tests for the HTTP fetcher — written before implementation (TDD RED phase)."""

import pytest
import requests
from unittest.mock import MagicMock
from crawler.fetcher import Fetcher


@pytest.fixture
def mock_session():
    return MagicMock(spec=requests.Session)


def test_returns_html_and_status_on_success(mock_session):
    response = MagicMock()
    response.status_code = 200
    response.text = "<html><body>Hello</body></html>"
    mock_session.get.return_value = response

    fetcher = Fetcher(session=mock_session)
    html, status_code, error = fetcher.fetch("https://example.com")

    assert html == "<html><body>Hello</body></html>"
    assert status_code == 200
    assert error is None


def test_returns_error_tuple_on_non_200(mock_session):
    response = MagicMock()
    response.status_code = 404
    response.ok = False
    response.text = "Not found"
    mock_session.get.return_value = response

    fetcher = Fetcher(session=mock_session)
    html, status_code, error = fetcher.fetch("https://example.com/missing")

    assert html is None
    assert status_code == 404
    assert error is not None


def test_returns_error_tuple_on_connection_error(mock_session):
    mock_session.get.side_effect = requests.ConnectionError("Connection refused")

    fetcher = Fetcher(session=mock_session)
    html, status_code, error = fetcher.fetch("https://unreachable.example.com")

    assert html is None
    assert status_code is None
    assert "Connection refused" in error


def test_accepts_injected_session(mock_session):
    """Fetcher must use the provided session, enabling test isolation."""
    response = MagicMock()
    response.status_code = 200
    response.text = "<html/>"
    mock_session.get.return_value = response

    fetcher = Fetcher(session=mock_session)
    fetcher.fetch("https://example.com")

    mock_session.get.assert_called_once_with("https://example.com", timeout=10)
