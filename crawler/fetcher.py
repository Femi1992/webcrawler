"""Handles HTTP requests for the crawler."""

import logging
import random
import time
from typing import Dict, Optional, Tuple
import requests

from .models import ErrorType

logger = logging.getLogger(__name__)


# Status codes where retrying will never help — give up immediately
_PERMANENT_STATUSES = {400, 403, 404}

_STATUS_TO_ERROR_TYPE = {
    400: ErrorType.CONNECTION,
    403: ErrorType.FORBIDDEN,
    404: ErrorType.NOT_FOUND,
    429: ErrorType.RATE_LIMITED,
    500: ErrorType.SERVER_ERROR,
    502: ErrorType.SERVER_ERROR,
    503: ErrorType.SERVER_ERROR,
    504: ErrorType.SERVER_ERROR,
}


class Fetcher:
    """Fetches web pages over HTTP with retry and exponential backoff.

    Think of this like a delivery driver:
    - If nobody answers the door (network error), knock again after a short wait
    - If the building is temporarily closed (500), come back later — wait longer each time
    - If the address doesn't exist (404), don't bother knocking again
    - If they say "come back in 2 hours" (429 Retry-After), respect that exactly

    Accepts an optional requests.Session for dependency injection (easy testing).
    """

    DEFAULT_TIMEOUT = 10

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        session: Optional[requests.Session] = None,
        max_retries: int = 3,
        backoff_base: float = 1.0,
    ) -> None:
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff_base = backoff_base

        if session is not None:
            self._session = session
        else:
            self._session = requests.Session()
            self._session.headers["User-Agent"] = "monzo-crawler/1.0"

    def fetch(
        self, url: str
    ) -> Tuple[Optional[str], Optional[int], Optional[str], Optional[ErrorType]]:
        """Fetch a URL and return (html, status_code, error, error_type).

        On success:  (html, status_code, None, None)
        On failure:  (None, status_code_or_None, error_message, ErrorType)
        """
        last_error: Optional[str] = None
        last_error_type: Optional[ErrorType] = None
        last_status: Optional[int] = None
        last_headers: Dict[str, str] = {}

        for attempt in range(self._max_retries + 1):

            if attempt > 0:
                wait = self._backoff_seconds(attempt, last_status, last_headers)
                logger.warning(
                    f"Retrying {url} (attempt {attempt}/{self._max_retries}) after {wait:.1f}s — {last_error}"
                )
                time.sleep(wait)

            logger.debug(f"Fetching {url} (attempt {attempt + 1})")

            try:
                response = self._session.get(url, timeout=self._timeout)

                if response.ok:
                    return response.text, response.status_code, None, None

                status = response.status_code
                last_status = status
                last_headers = dict(response.headers)
                last_error = f"HTTP {status}"
                last_error_type = _STATUS_TO_ERROR_TYPE.get(status, ErrorType.SERVER_ERROR)

                if status in _PERMANENT_STATUSES:
                    logger.debug(f"Non-retryable status {status} for {url}")
                    return None, status, last_error, last_error_type

            except requests.Timeout:
                last_error = "Request timed out"
                last_error_type = ErrorType.TIMEOUT
                last_status = None

            except requests.ConnectionError as e:
                last_error = str(e)
                last_error_type = ErrorType.CONNECTION
                last_status = None

            except requests.RequestException as e:
                last_error = str(e)
                last_error_type = ErrorType.CONNECTION
                last_status = None

        logger.error(f"Giving up on {url} after {self._max_retries} retries — {last_error}")
        return None, last_status, last_error, last_error_type

    def _backoff_seconds(
        self, attempt: int, status: Optional[int], headers: Dict[str, str]
    ) -> float:
        """How long to wait before retry attempt N.

        - If the server sent a Retry-After header (429), use that exact value
        - Otherwise: base * 2^(attempt-1) + small random jitter
          attempt 1 → ~1s, attempt 2 → ~2s, attempt 3 → ~4s
        """
        if status == 429 and "Retry-After" in headers:
            try:
                return float(headers["Retry-After"])
            except ValueError:
                pass  # malformed header — fall through to exponential backoff

        exponential = self._backoff_base * (2 ** (attempt - 1))
        jitter = random.uniform(0, self._backoff_base * 0.5)
        return exponential + jitter
