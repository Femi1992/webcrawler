"""Tests for the crawler orchestrator — TDD phase."""

import threading
import time
import pytest
from unittest.mock import MagicMock, patch
from crawler.crawler import Crawler
from crawler.fetcher import Fetcher
from crawler.models import ErrorType


def make_fetcher(pages: dict) -> Fetcher:
    """
    Build a mock Fetcher where pages maps url -> html string.
    Any URL not in pages returns a connection error.
    Returns a 4-tuple: (html, status_code, error, error_type)
    """
    fetcher = MagicMock(spec=Fetcher)

    def side_effect(url):
        if url in pages:
            return pages[url], 200, None, None
        return None, None, f"No mock for {url}", ErrorType.CONNECTION

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


# ---------------------------------------------------------------------------
# Existing correctness tests (updated for 4-tuple fetch return)
# ---------------------------------------------------------------------------

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
    fetcher = make_fetcher({})
    crawler = Crawler("https://example.com/", fetcher=fetcher)
    results = crawler.crawl()

    assert len(results) == 1
    assert results[0].ok is False
    assert results[0].error is not None


def test_result_includes_all_links_not_just_same_domain():
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


# ---------------------------------------------------------------------------
# Dynamic scaling tests
# ---------------------------------------------------------------------------

def test_scales_up_workers_as_queue_grows():
    """
    When the queue has more items than items_per_worker, new threads should
    be spawned. We verify this by checking that pages are fetched concurrently
    (multiple threads active at the same time).
    """
    concurrent_count = []
    active = [0]
    lock = threading.Lock()

    # Build a large site: home links to 20 pages
    links_html = "".join(f'<a href="/page{i}">Page {i}</a>' for i in range(20))
    home_html = f"<html><body>{links_html}</body></html>"
    page_html = "<html><body><p>leaf</p></body></html>"

    pages = {"https://example.com/": home_html}
    pages.update({f"https://example.com/page{i}": page_html for i in range(20)})

    fetcher = MagicMock(spec=Fetcher)

    def slow_fetch(url):
        with lock:
            active[0] += 1
            concurrent_count.append(active[0])
        time.sleep(0.05)  # simulate network latency
        with lock:
            active[0] -= 1
        if url in pages:
            return pages[url], 200, None, None
        return None, None, "not found", ErrorType.CONNECTION

    fetcher.fetch.side_effect = slow_fetch

    crawler = Crawler(
        "https://example.com/",
        fetcher=fetcher,
        max_workers=10,
        items_per_worker=3,
    )
    crawler.crawl()

    # At some point more than 1 thread should have been active simultaneously
    assert max(concurrent_count) > 1


def test_never_exceeds_max_workers():
    """No matter how large the queue gets, we never exceed max_workers threads."""
    active_threads = []
    active = [0]
    lock = threading.Lock()

    links_html = "".join(f'<a href="/page{i}">Page {i}</a>' for i in range(50))
    home_html = f"<html><body>{links_html}</body></html>"
    page_html = "<html><body></body></html>"

    pages = {"https://example.com/": home_html}
    pages.update({f"https://example.com/page{i}": page_html for i in range(50)})

    fetcher = MagicMock(spec=Fetcher)

    def tracking_fetch(url):
        with lock:
            active[0] += 1
            active_threads.append(active[0])
        time.sleep(0.02)
        with lock:
            active[0] -= 1
        if url in pages:
            return pages[url], 200, None, None
        return None, None, "not found", ErrorType.CONNECTION

    fetcher.fetch.side_effect = tracking_fetch

    max_workers = 5
    crawler = Crawler(
        "https://example.com/",
        fetcher=fetcher,
        max_workers=max_workers,
        items_per_worker=1,
    )
    crawler.crawl()

    assert max(active_threads) <= max_workers


def test_no_url_visited_twice_under_concurrency():
    """Thread safety: even with multiple workers, no URL is fetched more than once."""
    links_html = "".join(f'<a href="/page{i}">Page {i}</a>' for i in range(30))
    home_html = f"<html><body>{links_html}</body></html>"
    page_html = "<html><body></body></html>"

    pages = {"https://example.com/": home_html}
    pages.update({f"https://example.com/page{i}": page_html for i in range(30)})

    fetcher = MagicMock(spec=Fetcher)

    def fetch(url):
        time.sleep(0.01)
        if url in pages:
            return pages[url], 200, None, None
        return None, None, "not found", ErrorType.CONNECTION

    fetcher.fetch.side_effect = fetch

    crawler = Crawler(
        "https://example.com/",
        fetcher=fetcher,
        max_workers=8,
        items_per_worker=2,
    )
    results = crawler.crawl()

    visited_urls = [r.url for r in results]
    assert len(visited_urls) == len(set(visited_urls))


# ---------------------------------------------------------------------------
# Redirect off-domain detection
# ---------------------------------------------------------------------------

def test_redirect_off_domain_is_not_crawled():
    """
    If fetching a URL results in a redirect to a different domain,
    that page should be recorded as an error, not crawled.
    """
    fetcher = MagicMock(spec=Fetcher)

    def fetch(url):
        if url == "https://example.com/":
            return HOME_HTML, 200, None, None
        if url == "https://example.com/about":
            # Redirected off-domain — fetcher signals this
            return None, 301, "Redirected off-domain", ErrorType.REDIRECT_OFF_DOMAIN
        return None, None, "not found", ErrorType.CONNECTION

    fetcher.fetch.side_effect = fetch

    crawler = Crawler("https://example.com/", fetcher=fetcher)
    results = crawler.crawl()

    redirect_result = next((r for r in results if r.url == "https://example.com/about"), None)
    assert redirect_result is not None
    assert redirect_result.ok is False
    assert redirect_result.error_type == ErrorType.REDIRECT_OFF_DOMAIN


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def test_logs_info_when_crawl_starts(caplog):
    """Crawl start should be logged at INFO so we know it kicked off."""
    import logging
    fetcher = make_fetcher({"https://example.com/": HOME_HTML})
    crawler = Crawler("https://example.com/", fetcher=fetcher)

    with caplog.at_level(logging.INFO, logger="crawler.crawler"):
        crawler.crawl()

    info_msgs = [r.message for r in caplog.records if r.levelno == logging.INFO]
    assert any("https://example.com/" in m for m in info_msgs)


def test_logs_info_when_crawl_finishes(caplog):
    """Crawl completion should be logged at INFO with a page count."""
    import logging
    fetcher = make_fetcher({
        "https://example.com/": HOME_HTML,
        "https://example.com/about": ABOUT_HTML,
    })
    crawler = Crawler("https://example.com/", fetcher=fetcher)

    with caplog.at_level(logging.INFO, logger="crawler.crawler"):
        crawler.crawl()

    info_msgs = [r.message for r in caplog.records if r.levelno == logging.INFO]
    # Should mention how many pages were crawled
    assert any(any(char.isdigit() for char in m) for m in info_msgs)


def test_logs_warning_when_page_fails(caplog):
    """A failed page fetch should produce a WARNING so it's easy to spot."""
    import logging
    fetcher = make_fetcher({})  # everything fails

    crawler = Crawler("https://example.com/", fetcher=fetcher)

    with caplog.at_level(logging.WARNING, logger="crawler.crawler"):
        crawler.crawl()

    warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("https://example.com/" in m for m in warning_msgs)


# ---------------------------------------------------------------------------
# robots.txt
# ---------------------------------------------------------------------------

def test_does_not_crawl_disallowed_url():
    """URLs blocked by robots.txt must never be fetched."""
    html_with_admin = """
    <html><body>
        <a href="/about">About</a>
        <a href="/admin/secret">Admin</a>
    </body></html>
    """
    fetcher = make_fetcher({
        "https://example.com/": html_with_admin,
        "https://example.com/about": ABOUT_HTML,
    })

    from urllib.robotparser import RobotFileParser
    robots = RobotFileParser()
    robots.parse(["User-agent: *", "Disallow: /admin/"])

    crawler = Crawler("https://example.com/", fetcher=fetcher, robots=robots)
    results = crawler.crawl()

    visited = {r.url for r in results}
    assert "https://example.com/admin/secret" not in visited


def test_crawls_allowed_urls_when_robots_permits():
    """URLs not blocked by robots.txt should still be crawled."""
    fetcher = make_fetcher({
        "https://example.com/": HOME_HTML,
        "https://example.com/about": ABOUT_HTML,
    })

    from urllib.robotparser import RobotFileParser
    robots = RobotFileParser()
    robots.parse(["User-agent: *", "Disallow: /private/"])

    crawler = Crawler("https://example.com/", fetcher=fetcher, robots=robots)
    results = crawler.crawl()

    visited = {r.url for r in results}
    assert "https://example.com/about" in visited


def test_crawls_everything_if_no_robots_txt():
    """If robots.txt is unavailable, treat all URLs as allowed."""
    fetcher = make_fetcher({
        "https://example.com/": HOME_HTML,
        "https://example.com/about": ABOUT_HTML,
    })

    # No robots param — crawler should fetch robots.txt itself and get an error,
    # then allow all URLs
    crawler = Crawler("https://example.com/", fetcher=fetcher)
    results = crawler.crawl()

    visited = {r.url for r in results}
    assert "https://example.com/about" in visited


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def test_rate_limit_sleeps_between_fetches():
    """With rate_limit set, time.sleep should be called after each fetch."""
    fetcher = make_fetcher({"https://example.com/": HOME_HTML})

    with patch("crawler.crawler.time.sleep") as mock_sleep:
        crawler = Crawler("https://example.com/", fetcher=fetcher, rate_limit=0.5)
        crawler.crawl()

    mock_sleep.assert_called_with(0.5)


def test_no_sleep_when_rate_limit_is_zero():
    """Default behaviour — no sleep between fetches."""
    fetcher = make_fetcher({"https://example.com/": HOME_HTML})

    with patch("crawler.crawler.time.sleep") as mock_sleep:
        crawler = Crawler("https://example.com/", fetcher=fetcher, rate_limit=0.0)
        crawler.crawl()

    mock_sleep.assert_not_called()
