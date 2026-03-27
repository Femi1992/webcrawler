"""Web crawler orchestrator."""

from collections import deque
from typing import List, Optional
from urllib.parse import urlparse

from .fetcher import Fetcher
from .models import PageResult
from .parser import Parser


class Crawler:
    """Breadth-first web crawler restricted to a single subdomain.

    Given a starting URL the crawler visits every reachable page whose
    netloc exactly matches the start URL's netloc (e.g. crawlme.monzo.com).
    External links are recorded in the page result but never enqueued.
    """

    def __init__(self, start_url: str, fetcher: Optional[Fetcher] = None) -> None:
        self._start_url = start_url
        self._allowed_domain = urlparse(start_url).netloc
        self._fetcher = fetcher or Fetcher()
        self._parser = Parser()

    def crawl(self) -> List[PageResult]:
        """Crawl the subdomain and return one PageResult per visited URL."""
        results: List[PageResult] = []
        visited: set = set()
        queue: deque = deque([self._start_url])

        while queue:
            url = queue.popleft()

            if url in visited:
                continue
            visited.add(url)

            result = self._crawl_page(url)
            results.append(result)

            for link in result.links:
                if link not in visited and self._is_same_domain(link):
                    queue.append(link)

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _crawl_page(self, url: str) -> PageResult:
        html, status_code, error = self._fetcher.fetch(url)

        if error:
            return PageResult(url=url, links=[], status_code=status_code, error=error)

        links = self._parser.extract_links(html, url)
        return PageResult(url=url, links=links, status_code=status_code)

    def _is_same_domain(self, url: str) -> bool:
        return urlparse(url).netloc == self._allowed_domain
