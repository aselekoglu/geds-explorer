from __future__ import annotations

import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class FetchStats:
    request_count: int = 0


class PoliteFetcher:
    def __init__(
        self,
        rate_limit_seconds: float = 1.0,
        retry_delays_seconds: tuple[float, ...] = (2.0, 5.0, 15.0),
        user_agent: str = "GEDS Explorer research crawler/0.1",
    ):
        self.rate_limit_seconds = rate_limit_seconds
        self.retry_delays_seconds = retry_delays_seconds
        self.user_agent = user_agent
        self.stats = FetchStats()
        self._last_request_at = 0.0

    def fetch_text(self, url: str) -> str:
        attempts = len(self.retry_delays_seconds) + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            self._wait()
            try:
                request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
                with urllib.request.urlopen(request, timeout=30) as response:
                    self.stats.request_count += 1
                    raw = response.read()
                    charset = response.headers.get_content_charset() or "utf-8"
                    return raw.decode(charset, errors="replace")
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt < len(self.retry_delays_seconds):
                    time.sleep(self.retry_delays_seconds[attempt])

        raise RuntimeError(f"failed to fetch {url}: {last_error}")

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)
        self._last_request_at = time.monotonic()
