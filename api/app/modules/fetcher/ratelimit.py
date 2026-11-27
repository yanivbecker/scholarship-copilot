"""At most one request per second to any one site (FR-D2), or slower if the
site's robots.txt asks for a Crawl-delay."""

import time
from collections.abc import Callable

MIN_INTERVAL_SECONDS = 1.0


class DomainRateLimiter:
    """Waits before each request so requests to one host are spaced out.

    `clock` and `sleep` are injectable so tests run instantly.
    """

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._clock = clock
        self._sleep = sleep
        self._last: dict[str, float] = {}

    def wait(self, host: str, interval: float = MIN_INTERVAL_SECONDS) -> None:
        interval = max(interval, MIN_INTERVAL_SECONDS)
        last = self._last.get(host)
        if last is not None:
            remaining = interval - (self._clock() - last)
            if remaining > 0:
                self._sleep(remaining)
        self._last[host] = self._clock()
