"""Shared retry wrapper for the data pullers' HTTP fetches."""
from __future__ import annotations

import time
from json import JSONDecodeError
from urllib.error import HTTPError, URLError

RETRYABLE = (HTTPError, URLError, TimeoutError, JSONDecodeError)


def retrying(fn, attempts: int = 3, base_sleep_s: float = 1.0):
    """Wrap an HTTP fetch: retry transient failures with exponential backoff
    (1s, 2s, ...). Re-raises the final error unchanged so callers' existing
    except blocks keep working."""
    def wrapped(*args, **kwargs):
        for attempt in range(attempts):
            try:
                return fn(*args, **kwargs)
            except RETRYABLE:
                if attempt == attempts - 1:
                    raise
                time.sleep(base_sleep_s * (2 ** attempt))
    wrapped.__wrapped__ = fn
    return wrapped
