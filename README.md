# Web Crawler

A concurrent web crawler that, given a starting URL, visits every reachable page on the same subdomain. It prints each visited URL and the links found on it, and stays strictly within the starting subdomain — external links and different subdomains are never followed.

## Requirements

- Python 3.8+
- pip

## Setup

```bash
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate       # macOS / Linux
venv\Scripts\activate          # Windows

# Install dependencies
pip install -r requirements.txt
```

## Running

```bash
python main.py <start_url>
```

Example:

```bash
python main.py https://crawlme.monzo.com/
```

Output format:

```
https://crawlme.monzo.com/
  -> https://crawlme.monzo.com/about.html
  -> https://crawlme.monzo.com/contact.html
  -> https://facebook.com               ← external links are listed but not followed

https://crawlme.monzo.com/about.html
  -> https://crawlme.monzo.com/index.html
  ...
```

## Running the tests

```bash
# All tests
pytest tests/ -v

# With coverage report
pytest tests/ -v --cov=crawler --cov-report=term-missing

# A specific test file
pytest tests/test_crawler.py -v

# Only logging tests
pytest tests/ -v -k "log"
```

## Architecture

```
crawler/
├── models.py    — PageResult dataclass and ErrorType enum
├── parser.py    — extracts and resolves links from raw HTML
├── fetcher.py   — HTTP client with retry and exponential backoff
├── crawler.py   — BFS orchestrator with dynamic worker scaling
├── logger.py    — logging configuration
tests/
├── test_parser.py
├── test_fetcher.py
└── test_crawler.py
main.py          — CLI entry point
```

### Key design decisions

**Subdomain restriction** — domain filtering uses `urlparse(url).netloc`, so `crawlme.monzo.com`, `monzo.com`, and `community.monzo.com` are treated as distinct domains. Only pages whose netloc exactly matches the start URL are crawled.

**Concurrent fetching** — workers scale dynamically based on queue depth:

```
target_workers = min(max_workers, ceil(queue_size / items_per_worker))
```

As more links are discovered, more workers are spawned up to `max_workers`. Workers exit naturally when the queue is empty. Thread safety is maintained with locks on the visited set and results list.

**Retry with exponential backoff** — transient failures (500, 502, 503, 504, connection errors, timeouts) are retried up to `max_retries` times with exponentially increasing wait times and jitter. Permanent failures (404, 403) are not retried. `429 Too Many Requests` honours the `Retry-After` header if present.

**Error types** — failures are categorised via `ErrorType` enum (`NOT_FOUND`, `SERVER_ERROR`, `RATE_LIMITED`, `TIMEOUT`, `CONNECTION`, `REDIRECT_OFF_DOMAIN`) so callers can handle them differently.

**Logging** — the `crawler` package logger is silent by default. `main.py` enables it at `INFO` level. Set to `DEBUG` for per-request tracing.

## Configuration

`Crawler` accepts optional parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_workers` | `10` | Maximum concurrent worker threads |
| `items_per_worker` | `5` | Queue items per worker before scaling up |
| `rate_limit` | `0.0` | Seconds to sleep between fetches per worker (0 = off) |
| `robots` | `None` | Pre-parsed `RobotFileParser`; if `None`, fetched automatically |

`Fetcher` accepts optional parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `timeout` | `10` | Request timeout in seconds |
| `max_retries` | `3` | Maximum retry attempts for transient failures |
| `backoff_base` | `1.0` | Base wait time in seconds (doubles each retry) |
