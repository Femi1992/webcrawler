"""Handles HTTP requests for the crawler."""

from typing import Optional, Tuple
import requests


class Fetcher:
    """Fetches web pages over HTTP.

    Accepts an optional requests.Session for dependency injection, which
    makes it straightforward to test without hitting the network.
    """

    DEFAULT_TIMEOUT = 10

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._timeout = timeout
        if session is not None:
            self._session = session
        else:
            self._session = requests.Session()
            self._session.headers["User-Agent"] = "monzo-crawler/1.0"

    def fetch(self, url: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
        """Fetch a URL and return (html, status_code, error).

        On success: (html, status_code, None)
        On failure: (None, status_code_or_None, error_message)
        """
        try:
            response = self._session.get(url, timeout=self._timeout)
            if not response.ok:
                return None, response.status_code, f"HTTP {response.status_code}"
            return response.text, response.status_code, None
        except requests.RequestException as e:
            return None, None, str(e)
