"""Data structures for the crawler."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PageResult:
    """The result of crawling a single page."""

    url: str
    links: List[str]
    status_code: Optional[int] = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        """True if the page was fetched successfully."""
        return self.error is None
