"""HTTP fetch with a timeout and a short retry with backoff."""

import time

import requests

USER_AGENT = "dc-bikeshare-lakehouse/0.1 (portfolio data pipeline)"


class NotFoundError(Exception):
    """The resource does not exist (HTTP 404); retrying will not help."""


def download(url: str, *, timeout: float = 60, attempts: int = 3) -> tuple[bytes, str | None]:
    """Return (body, ETag header); raise NotFoundError on 404, retry other failures."""
    for attempt in range(attempts):
        try:
            response = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
            if response.status_code == 404:
                raise NotFoundError(url)
            response.raise_for_status()
            etag = response.headers.get("ETag")
            return response.content, etag.strip('"') if etag else None
        except NotFoundError:
            raise
        except requests.RequestException:
            if attempt == attempts - 1:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def fetch(url: str, *, timeout: float = 20, attempts: int = 3) -> bytes:
    """Return the response body only."""
    body, _ = download(url, timeout=timeout, attempts=attempts)
    return body
