"""Tests for the HTML parser — written before implementation (TDD RED phase)."""

import pytest
from crawler.parser import Parser


@pytest.fixture
def parser():
    return Parser()


BASE_URL = "https://example.com"


def test_extracts_http_links(parser):
    html = """
    <html><body>
        <a href="https://example.com/about">About</a>
        <a href="https://example.com/contact">Contact</a>
    </body></html>
    """
    links = parser.extract_links(html, BASE_URL)
    assert "https://example.com/about" in links
    assert "https://example.com/contact" in links


def test_resolves_relative_links_to_absolute(parser):
    html = '<html><body><a href="/about">About</a><a href="page.html">Page</a></body></html>'
    links = parser.extract_links(html, BASE_URL)
    assert "https://example.com/about" in links
    assert "https://example.com/page.html" in links


def test_strips_url_fragments(parser):
    html = '<html><body><a href="/about#section">About</a></body></html>'
    links = parser.extract_links(html, BASE_URL)
    assert "https://example.com/about" in links
    assert not any("#" in link for link in links)


def test_skips_mailto_links(parser):
    html = '<html><body><a href="mailto:hello@example.com">Email</a></body></html>'
    links = parser.extract_links(html, BASE_URL)
    assert links == []


def test_skips_tel_links(parser):
    html = '<html><body><a href="tel:+441234567890">Call</a></body></html>'
    links = parser.extract_links(html, BASE_URL)
    assert links == []


def test_deduplicates_links(parser):
    html = """
    <html><body>
        <a href="/about">About</a>
        <a href="/about">About again</a>
        <a href="/about#section">About with fragment</a>
    </body></html>
    """
    links = parser.extract_links(html, BASE_URL)
    assert links.count("https://example.com/about") == 1


def test_returns_empty_list_when_no_anchor_tags(parser):
    html = "<html><body><p>No links here</p></body></html>"
    links = parser.extract_links(html, BASE_URL)
    assert links == []


def test_handles_empty_html(parser):
    links = parser.extract_links("", BASE_URL)
    assert links == []


def test_skips_anchors_with_empty_href(parser):
    html = '<html><body><a href="">Empty</a><a href="  ">Whitespace</a></body></html>'
    links = parser.extract_links(html, BASE_URL)
    assert links == []
