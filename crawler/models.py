"""Data structures for the crawler."""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class ErrorType(Enum):
    """Why a page failed.

    Think of this like a doctor's diagnosis — instead of just saying
    "the patient is unwell", we say exactly what's wrong so we can
    treat it differently.
    """
    NOT_FOUND = "not_found"                    # 404 — page doesn't exist
    FORBIDDEN = "forbidden"                    # 403 — we're not allowed in
    SERVER_ERROR = "server_error"              # 500-504 — their server broke
    RATE_LIMITED = "rate_limited"              # 429 — server told us to slow down, we gave up
    TIMEOUT = "timeout"                        # request took too long
    CONNECTION = "connection"                  # couldn't reach the server at all
    REDIRECT_OFF_DOMAIN = "redirect_off_domain"  # page redirected us to a different domain


@dataclass
class PageResult:
    """The result of crawling a single page."""

    url: str
    links: List[str]
    status_code: Optional[int] = None
    error: Optional[str] = None
    error_type: Optional[ErrorType] = None

    @property
    def ok(self) -> bool:
        """True if the page was fetched successfully."""
        return self.error is None
