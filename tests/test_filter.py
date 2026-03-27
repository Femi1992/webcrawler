"""Tests for the URL filter."""

import pytest
from crawler.filter import URLFilter


class TestURLFilter:
    """Test the URLFilter class."""

    def test_allowed_domain_restriction(self):
        """Test domain restriction."""
        filter = URLFilter(allowed_domains={"example.com"})
        assert filter.is_allowed("https://example.com/page")
        assert not filter.is_allowed("https://other.com/page")

    def test_excluded_extensions(self):
        """Test file extension exclusion."""
        filter = URLFilter()
        assert not filter.is_allowed("https://example.com/file.pdf")
        assert not filter.is_allowed("https://example.com/image.jpg")
        assert filter.is_allowed("https://example.com/page.html")

    def test_visited_urls(self):
        """Test visited URL tracking."""
        filter = URLFilter()
        url = "https://example.com/page"
        assert filter.is_allowed(url)
        filter.mark_visited(url)
        assert not filter.is_allowed(url)

    def test_max_depth(self):
        """Test maximum depth restriction."""
        filter = URLFilter(max_depth=2)
        assert filter.is_allowed("https://example.com/a")
        assert filter.is_allowed("https://example.com/a/b")
        assert not filter.is_allowed("https://example.com/a/b/c/d")

    def test_visited_count(self):
        """Test visited URL count."""
        filter = URLFilter()
        assert filter.get_visited_count() == 0
        filter.mark_visited("https://example.com/1")
        filter.mark_visited("https://example.com/2")
        assert filter.get_visited_count() == 2
