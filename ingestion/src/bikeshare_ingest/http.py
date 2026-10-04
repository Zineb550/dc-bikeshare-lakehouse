"""HTTP fetch with a timeout and a short retry with backoff."""

import time

import requests

USER_AGENT = "dc-bikeshare-lakehouse/0.1 (portfolio data pipeline)"


def fetch(url: str, *, timeout: float = 20, attempts: int = 3) -> bytes:
    """Return the response body; raise after `attempts` failures."""
    for attempt in range(attempts):
        try:
            response = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            return response.content
        except requests.RequestException:
            if attempt == attempts - 1:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")
