"""Tests for the crawler orchestrator — written before implementation (TDD RED phase)."""

import pytest
from unittest.mock import MagicMock
from crawler.crawler import Crawler
from crawler.fetcher import Fetcher


def make_fetcher(pages: dict) -> Fetcher:
    """
    Build a mock Fetcher where pages maps url -> html string.
    Any URL not in pages returns a connection error.
    """
    fetcher = MagicMock(spec=Fetcher)

    def side_effect(url):
        if url in pages:
            return pages[url], 200, None
        return None, None, f"No mock for {url}"

    fetcher.fetch.side_effect = side_effect
    return fetcher


HOME_HTML = """
<html><body>
    <a href="/about">About</a>
    <a href="https://external.com/page">External</a>
</body></html>
"""

ABOUT_HTML = """
<html><body>
    <a href="/">Home</a>
</body></html>
"""


def test_crawls_start_url():
    fetcher = make_fetcher({"https://example.com/": HOME_HTML})
    crawler = Crawler("https://example.com/", fetcher=fetcher)
    results = crawler.crawl()

    assert any(r.url == "https://example.com/" for r in results)


def test_result_has_correct_status_code():
    fetcher = make_fetcher({"https://example.com/": HOME_HTML})
    crawler = Crawler("https://example.com/", fetcher=fetcher)
    results = crawler.crawl()

    home = next(r for r in results if r.url == "https://example.com/")
    assert home.status_code == 200


def test_does_not_follow_external_links():
    fetcher = make_fetcher({"https://example.com/": HOME_HTML})
    crawler = Crawler("https://example.com/", fetcher=fetcher)
    results = crawler.crawl()

    visited = {r.url for r in results}
    assert "https://external.com/page" not in visited


def test_does_not_follow_different_subdomain():
    html = """
    <html><body>
        <a href="https://other.example.com/page">Other subdomain</a>
    </body></html>
    """
    fetcher = make_fetcher({"https://example.com/": html})
    crawler = Crawler("https://example.com/", fetcher=fetcher)
    results = crawler.crawl()

    visited = {r.url for r in results}
    assert "https://other.example.com/page" not in visited


def test_does_not_revisit_urls():
    # Home links to /about, /about links back to home — should only visit each once
    fetcher = make_fetcher({
        "https://example.com/": HOME_HTML,
        "https://example.com/about": ABOUT_HTML,
    })
    crawler = Crawler("https://example.com/", fetcher=fetcher)
    results = crawler.crawl()

    visited_urls = [r.url for r in results]
    assert len(visited_urls) == len(set(visited_urls))


def test_follows_same_subdomain_links():
    fetcher = make_fetcher({
        "https://example.com/": HOME_HTML,
        "https://example.com/about": ABOUT_HTML,
    })
    crawler = Crawler("https://example.com/", fetcher=fetcher)
    results = crawler.crawl()

    visited = {r.url for r in results}
    assert "https://example.com/about" in visited


def test_handles_fetch_error_gracefully():
    fetcher = make_fetcher({})  # everything fails
    crawler = Crawler("https://example.com/", fetcher=fetcher)
    results = crawler.crawl()

    assert len(results) == 1
    assert results[0].ok is False
    assert results[0].error is not None


def test_result_includes_all_links_not_just_same_domain():
    """Links in PageResult should include external links (we report all, enqueue only same-domain)."""
    fetcher = make_fetcher({"https://example.com/": HOME_HTML})
    crawler = Crawler("https://example.com/", fetcher=fetcher)
    results = crawler.crawl()

    home = next(r for r in results if r.url == "https://example.com/")
    assert any("external.com" in link for link in home.links)


def test_result_ok_is_false_on_error():
    fetcher = make_fetcher({})
    crawler = Crawler("https://example.com/", fetcher=fetcher)
    results = crawler.crawl()

    assert results[0].ok is False
