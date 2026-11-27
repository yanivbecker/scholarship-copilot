"""A fake web for fetcher tests: canned pages, fake DNS, a fake clock.

No real network is ever used. All sites and content are fictional.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

import httpx2

from app.modules.fetcher.fetcher import PoliteFetcher
from app.modules.fetcher.ratelimit import DomainRateLimiter

PUBLIC_IP = "93.184.216.34"
HTML = (
    b"<html><body><main><h1>Test Award</h1>"
    b"<p>GPA of 3.0 or higher.</p></main></body></html>"
)

type Reply = httpx2.Response | Callable[[httpx2.Request], httpx2.Response]


@dataclass
class FakeWeb:
    """Serves canned responses by (host, path) and records every request."""

    pages: dict[tuple[str, str], Reply] = field(default_factory=dict)
    dns: dict[str, list[str]] = field(default_factory=dict)
    requests: list[httpx2.Request] = field(default_factory=list)
    now: float = 1000.0
    sleeps: list[float] = field(default_factory=list)

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        key = (request.headers["host"], request.url.path)
        reply = self.pages.get(key)
        if reply is None:
            return httpx2.Response(404)
        return reply(request) if callable(reply) else reply

    def resolve(self, host: str, _port: int) -> list[str]:
        if host not in self.dns:
            raise OSError("no such host")
        return self.dns[host]

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def fetcher(self) -> PoliteFetcher:
        return PoliteFetcher(
            resolver=self.resolve,
            rate_limiter=DomainRateLimiter(clock=lambda: self.now, sleep=self.sleep),
            transport=httpx2.MockTransport(self.handler),
        )

    def paths_requested(self) -> list[str]:
        return [f"{r.headers['host']}{r.url.path}" for r in self.requests]


def new_web() -> FakeWeb:
    """A fake web where example.org exists and allows everything."""
    web = FakeWeb()
    web.dns["example.org"] = [PUBLIC_IP]
    web.pages[("example.org", "/robots.txt")] = httpx2.Response(200, text="")
    return web


def html(body: bytes = HTML, headers: dict[str, str] | None = None) -> httpx2.Response:
    return httpx2.Response(
        200, content=body, headers={"content-type": "text/html", **(headers or {})}
    )
