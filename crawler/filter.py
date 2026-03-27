"""Decides if a URL is allowed to be crawled."""

from urllib.parse import urlparse
from typing import Set, Optional


class URLFilter:
    """Filters URLs based on rules."""

    def __init__(
        self,
        allowed_domains: Optional[Set[str]] = None,
        excluded_extensions: Optional[Set[str]] = None,
        max_depth: int = 3,
    ):
        """Initialize the URL filter.

        Args:
            allowed_domains: Set of domains to allow. If None, allow all.
            excluded_extensions: Set of file extensions to exclude (e.g., {'.pdf', '.zip'})
            max_depth: Maximum URL path depth to crawl
        """
        self.allowed_domains = allowed_domains
        self.excluded_extensions = excluded_extensions or {
            ".pdf",
            ".zip",
            ".exe",
            ".jpg",
            ".png",
            ".gif",
        }
        self.max_depth = max_depth
        self.visited_urls: Set[str] = set()

    def is_allowed(self, url: str) -> bool:
        """Check if a URL is allowed to be crawled.

        Args:
            url: The URL to check

        Returns:
            True if the URL should be crawled, False otherwise
        """
        # Check if already visited
        if url in self.visited_urls:
            return False

        try:
            parsed = urlparse(url)

            # Check domain restriction
            if self.allowed_domains and parsed.netloc not in self.allowed_domains:
                return False

            # Check file extension
            path = parsed.path.lower()
            for ext in self.excluded_extensions:
                if path.endswith(ext):
                    return False

            # Check depth
            path_parts = [p for p in parsed.path.split("/") if p]
            if len(path_parts) > self.max_depth:
                return False

            return True
        except Exception:
            return False

    def mark_visited(self, url: str) -> None:
        """Mark a URL as visited.

        Args:
            url: The URL that was visited
        """
        self.visited_urls.add(url)

    def get_visited_count(self) -> int:
        """Get the count of visited URLs.

        Returns:
            Number of visited URLs
        """
        return len(self.visited_urls)
