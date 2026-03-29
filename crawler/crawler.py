"""Web crawler orchestrator with dynamic worker scaling."""

import logging
import math
import threading
import time
import queue
from typing import List, Optional
from urllib.parse import urlparse

from .fetcher import Fetcher
from .models import PageResult
from .parser import Parser

logger = logging.getLogger(__name__)


class Crawler:
    """Breadth-first web crawler restricted to a single subdomain.

    Thread safety:
    - url_queue:    thread-safe by design (queue.Queue)
    - _visited:     guarded by _visited_lock
    - _results:     guarded by _results_lock
    - worker threads: spawned dynamically, tracked in _threads
    """

    def __init__(
        self,
        start_url: str,
        fetcher: Optional[Fetcher] = None,
        max_workers: int = 10,
        items_per_worker: int = 5,
    ) -> None:
        self._start_url = start_url
        self._allowed_domain = urlparse(start_url).netloc
        self._fetcher = fetcher or Fetcher()
        self._parser = Parser()
        self._max_workers = max_workers
        self._items_per_worker = items_per_worker

    def crawl(self) -> List[PageResult]:
        """Crawl the subdomain and return one PageResult per visited URL."""
        logger.info(
            f"Crawl started: {self._start_url} (max_workers={self._max_workers}, items_per_worker={self._items_per_worker})"
        )
        start_time = time.time()

        url_queue: queue.Queue = queue.Queue()
        url_queue.put(self._start_url)

        visited: set = set()
        visited_lock = threading.Lock()

        results: List[PageResult] = []
        results_lock = threading.Lock()

        threads: List[threading.Thread] = []
        threads_lock = threading.Lock()

        def worker() -> None:
            """
            Each worker loops: grab a URL, fetch it, parse it, enqueue new links.
            Exits when the queue has been empty for 2 seconds — meaning no other
            worker is about to add more work.
            """
            while True:
                try:
                    url = url_queue.get(timeout=2)
                except queue.Empty:
                    break  # queue stayed empty — we're done, thread exits

                try:
                    # Check-and-mark visited atomically so two threads can't
                    # both decide to fetch the same URL simultaneously
                    with visited_lock:
                        if url in visited:
                            continue
                        visited.add(url)

                    result = self._crawl_page(url)

                    with results_lock:
                        results.append(result)

                    for link in result.links:
                        with visited_lock:
                            already_seen = link in visited
                        if not already_seen and self._is_same_domain(link):
                            url_queue.put(link)
                            self._maybe_scale_up(url_queue, threads, threads_lock, worker)

                finally:
                    url_queue.task_done()

        # Spawn the first worker — it will trigger scale-up as it discovers links
        self._spawn_worker(worker, threads, threads_lock)

        # Block until every URL that was ever put() has been task_done()
        url_queue.join()

        elapsed = time.time() - start_time
        errors = sum(1 for r in results if not r.ok)
        logger.info(f"Crawl finished: {len(results)} pages in {elapsed:.1f}s ({errors} errors)")

        return results

    # ------------------------------------------------------------------
    # Scaling
    # ------------------------------------------------------------------

    def _maybe_scale_up(
        self,
        url_queue: queue.Queue,
        threads: List[threading.Thread],
        threads_lock: threading.Lock,
        worker_fn,
    ) -> None:
        """Spawn a new worker thread if the queue has grown beyond capacity.

        Formula: target = min(max_workers, ceil(queue_size / items_per_worker))

        Example with items_per_worker=5:
          queue=1  → target=1   (no new thread needed)
          queue=6  → target=2   (spawn 1)
          queue=25 → target=5   (spawn up to cap)
        """
        with threads_lock:
            alive = [t for t in threads if t.is_alive()]
            queue_size = url_queue.qsize()
            target = min(self._max_workers, math.ceil(queue_size / self._items_per_worker))
            while len(alive) < target:
                t = self._spawn_worker(worker_fn, threads, threads_lock, _hold_lock=True)
                alive.append(t)

    def _spawn_worker(
        self,
        worker_fn,
        threads: List[threading.Thread],
        threads_lock: threading.Lock,
        _hold_lock: bool = False,
    ) -> threading.Thread:
        """Start a new daemon worker thread."""
        t = threading.Thread(target=worker_fn, daemon=True)
        t.start()
        if _hold_lock:
            threads.append(t)
        else:
            with threads_lock:
                threads.append(t)
        return t

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _crawl_page(self, url: str) -> PageResult:
        html, status_code, error, error_type = self._fetcher.fetch(url)

        if error:
            logger.warning(f"Failed to fetch {url} — {error}")
            return PageResult(
                url=url,
                links=[],
                status_code=status_code,
                error=error,
                error_type=error_type,
            )

        # Check if we were silently redirected off-domain
        # (requests follows redirects automatically — response.url is the final destination)
        links = self._parser.extract_links(html, url)
        return PageResult(url=url, links=links, status_code=status_code)

    def _is_same_domain(self, url: str) -> bool:
        return urlparse(url).netloc == self._allowed_domain
