"""Entry point for the web crawler.

Usage:
    python main.py <start_url>

Example:
    python main.py https://crawlme.monzo.com/
"""

import sys
from crawler.crawler import Crawler


def main(start_url: str) -> None:
    crawler = Crawler(start_url)
    results = crawler.crawl()

    for result in results:
        print(f"\n{result.url}")
        if not result.ok:
            print(f"  [error] {result.error}")
        else:
            for link in result.links:
                print(f"  -> {link}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <url>")
        sys.exit(1)

    main(sys.argv[1])
