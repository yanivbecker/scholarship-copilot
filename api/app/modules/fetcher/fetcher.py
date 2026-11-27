"""The polite, safe page fetcher (FR-D2, FR-D3, FR-D4, FR-D7, NFR-4).

Every request, including every redirect hop and every robots.txt request,
goes through the same gate:

  1. url_safety: http(s) only, no credentials, no aggregators, no IP literals
     that are private.
  2. robots.txt: is this path allowed for us? (cached per site per run)
  3. Rate limit: >= 1 s since the last request to this host (or Crawl-delay).
  4. DNS: resolve the name ourselves; every address must be public.
  5. Connect to *that* address (TLS is still checked against the real name).

Limits: GET only, no cookies kept, timeouts, max 5 redirects, max 5 MB body.
Responses that look like a login page are reported, never crawled (FR-D4).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx2

from app.modules.fetcher.network import (
    BlockedAddressError,
    Resolver,
    resolve_public_address,
    system_resolver,
)
from app.modules.fetcher.ratelimit import DomainRateLimiter
from app.modules.fetcher.robots import RobotsRules, rules_from_response
from app.modules.fetcher.text import (
    UnreadableContentError,
    content_hash,
    html_to_text,
    pdf_to_text,
)
from app.modules.sources.url_safety import UnsafeURLError, normalize_source_url

# Generic on purpose: no name, email or account in requests to other sites.
USER_AGENT = (
    "ScholarshipCopilot/0.1 (personal scholarship research tool; respects robots.txt)"
)
MAX_BODY_BYTES = 5 * 1024 * 1024
MAX_ROBOTS_BYTES = 500 * 1024
MAX_REDIRECTS = 5
MAX_CRAWL_DELAY_SECONDS = 60.0
TIMEOUT = httpx2.Timeout(20.0, connect=10.0)
ACCEPT = "text/html,application/xhtml+xml,application/pdf;q=0.9,text/plain;q=0.8"

HTML_TYPES = {"text/html", "application/xhtml+xml"}
TEXT_TYPES = {"text/plain"}
PDF_TYPES = {"application/pdf"}

LOGIN_PATH = re.compile(
    r"/(log-?in|sign-?in|sso|auth|oauth|cas|account/login|users/sign_in)\b",
    re.IGNORECASE,
)
PASSWORD_FIELD = re.compile(rb"<input[^>]+type\s*=\s*[\"']?password", re.IGNORECASE)


class FetchStatus(StrEnum):
    """The outcome of one fetch. Stored on the source (see sources.models)."""

    OK = "ok"
    NOT_MODIFIED = "not_modified"  # 304: unchanged since the last fetch
    ROBOTS_DISALLOWED = "robots_disallowed"
    LOGIN_REQUIRED = "login_required"  # FR-D4: never crawled; paste instead
    BLOCKED_URL = "blocked_url"  # unsafe address or aggregator (incl. redirects)
    HTTP_ERROR = "http_error"
    NETWORK_ERROR = "network_error"
    UNSUPPORTED_CONTENT = "unsupported_content"
    TOO_LARGE = "too_large"


@dataclass(frozen=True)
class FetchResult:  # pylint: disable=too-many-instance-attributes
    """What one fetch produced. `text` and `content_hash` are set when OK."""

    status: FetchStatus
    url: str  # final URL after redirects
    message: str = ""
    http_status: int | None = None
    content_type: str | None = None
    text: str | None = None
    content_hash: str | None = None
    etag: str | None = None
    last_modified: str | None = None


@dataclass
class _Response:
    status: int
    headers: httpx2.Headers
    body: bytes
    too_large: bool = False


class _Stop(Exception):
    """Internal: end the fetch early with this result."""

    def __init__(self, result: FetchResult):
        super().__init__(result.message)
        self.result = result


@dataclass
class PoliteFetcher:
    """Fetch pages safely. One instance per job run (it caches robots.txt).

    `transport`, `resolver` and `rate_limiter` are injectable so tests can run
    without a network and without waiting.
    """

    resolver: Resolver = system_resolver
    rate_limiter: DomainRateLimiter = field(default_factory=DomainRateLimiter)
    transport: httpx2.BaseTransport | None = None
    _robots: dict[str, RobotsRules] = field(default_factory=dict, init=False)
    _client: httpx2.Client | None = field(default=None, init=False)

    # --- public ---------------------------------------------------------

    def fetch(
        self, url: str, *, etag: str | None = None, last_modified: str | None = None
    ) -> FetchResult:
        """Fetch one page. Never raises for network/site problems."""
        try:
            return self._fetch(url, etag=etag, last_modified=last_modified)
        except _Stop as stop:
            return stop.result

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    # --- the pipeline ---------------------------------------------------

    def _fetch(
        self, url: str, *, etag: str | None, last_modified: str | None
    ) -> FetchResult:
        current = self._check_url(url, original=url)
        conditional: dict[str, str] = {}
        if etag:
            conditional["If-None-Match"] = etag
        if last_modified:
            conditional["If-Modified-Since"] = last_modified

        for _hop in range(MAX_REDIRECTS + 1):
            # Vet the address first, so a host that points at a private
            # network is reported as blocked (not as a robots.txt problem).
            self._pinned_url(current)
            self._check_robots(current)
            if LOGIN_PATH.search(urlsplit(current).path):
                raise _Stop(_login(current))
            response = self._get(current, conditional, max_bytes=MAX_BODY_BYTES)

            if response.status in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                if not location:
                    raise _Stop(_http_error(current, response.status))
                # Each hop is checked like a brand-new URL (scheme, address,
                # aggregator, robots, login).
                current = self._check_url(urljoin(current, location), original=url)
                conditional = {}  # validators belong to the original URL
                continue
            return self._finish(current, response)

        raise _Stop(FetchResult(FetchStatus.HTTP_ERROR, current, "Too many redirects."))

    # One return per HTTP outcome reads more clearly than a lookup table here.
    def _finish(  # pylint: disable=too-many-return-statements
        self, url: str, response: _Response
    ) -> FetchResult:
        status = response.status
        if status == 304:
            return FetchResult(FetchStatus.NOT_MODIFIED, url, http_status=304)
        if status == 401:
            return _login(url)
        if status == 403:
            return FetchResult(
                FetchStatus.HTTP_ERROR,
                url,
                "The site refused access (403).",
                http_status=403,
            )
        if status != 200:
            return _http_error(url, status)
        if response.too_large:
            return FetchResult(
                FetchStatus.TOO_LARGE, url, "The page is larger than 5 MB.", 200
            )

        content_type = (
            response.headers.get("content-type", "").split(";")[0].strip().lower()
        )
        if content_type in HTML_TYPES and PASSWORD_FIELD.search(response.body):
            return _login(url)
        try:
            text = self._to_text(content_type, response.body, response.headers)
        except UnreadableContentError as exc:
            return FetchResult(
                FetchStatus.UNSUPPORTED_CONTENT, url, str(exc), 200, content_type
            )
        return FetchResult(
            FetchStatus.OK,
            url,
            http_status=200,
            content_type=content_type,
            text=text,
            content_hash=content_hash(text),
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
        )

    @staticmethod
    def _to_text(content_type: str, body: bytes, headers: httpx2.Headers) -> str:
        if content_type in HTML_TYPES:
            return html_to_text(body)
        if content_type in PDF_TYPES:
            return pdf_to_text(body)
        if content_type in TEXT_TYPES:
            return body.decode(_charset(headers), errors="replace")[:200_000]
        raise UnreadableContentError(
            f"Pages of type {content_type or 'unknown'} aren't supported."
        )

    # --- the gate -------------------------------------------------------

    @staticmethod
    def _check_url(url: str, *, original: str) -> str:
        try:
            return normalize_source_url(url)
        except UnsafeURLError as exc:
            where = "" if url == original else f" (redirected to {url})"
            raise _Stop(
                FetchResult(FetchStatus.BLOCKED_URL, url, f"{exc}{where}")
            ) from None

    def _check_robots(self, url: str) -> None:
        rules = self._robots_for(url)
        if not rules.allows(url):
            message = (
                f"Not read, because {rules.unavailable_reason}; "
                "we only read pages when the robots.txt rules are known."
                if rules.unavailable_reason
                else "The site's robots.txt asks automated tools not to read this page."
            )
            raise _Stop(FetchResult(FetchStatus.ROBOTS_DISALLOWED, url, message))
        delay = rules.crawl_delay()
        if delay is not None and delay > MAX_CRAWL_DELAY_SECONDS:
            raise _Stop(
                FetchResult(
                    FetchStatus.ROBOTS_DISALLOWED,
                    url,
                    f"The site asks for {delay:g} s between requests; skipped.",
                )
            )

    def _robots_for(self, url: str) -> RobotsRules:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            robots_url = urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
            status, body, error = self._fetch_robots(robots_url)
            self._robots[origin] = rules_from_response(status, body, error)
        return self._robots[origin]

    def _fetch_robots(self, robots_url: str) -> tuple[int | None, str, str | None]:
        """GET robots.txt, following up to 5 safe redirects (as Google does).

        Returns (status, body, error). A failure gives status None, which
        means "don't fetch for now", plus the reason.
        """
        url = robots_url
        try:
            for _hop in range(MAX_REDIRECTS + 1):
                response = self._get(url, {}, max_bytes=MAX_ROBOTS_BYTES)
                location = response.headers.get("location")
                if response.status in (301, 302, 303, 307, 308) and location:
                    url = self._check_url(urljoin(url, location), original=robots_url)
                    continue
                body = response.body.decode("utf-8", errors="replace")
                return response.status, body, None
        except _Stop as stop:
            # Unsafe redirect or unreachable: be cautious, but say why.
            reason = stop.result.message.rstrip(".")
            return None, "", f"its robots.txt couldn't be read: {reason}"
        return None, "", "its robots.txt redirected too many times"

    # --- one HTTP request -----------------------------------------------

    def _get(
        self, url: str, extra_headers: dict[str, str], *, max_bytes: int
    ) -> _Response:
        """One GET: wait for the rate limit, vet the IP, connect to that IP."""
        parts = urlsplit(url)
        rules = self._robots.get(f"{parts.scheme}://{parts.netloc}")
        crawl_delay = rules.crawl_delay() if rules is not None else None
        self.rate_limiter.wait(parts.hostname or "", crawl_delay or 0.0)
        pinned = self._pinned_url(url)
        client = self._get_client()
        client.cookies.clear()  # no sessions, no tracking between requests
        try:
            with client.stream(
                "GET",
                pinned,
                headers={
                    "Host": parts.netloc,
                    "User-Agent": USER_AGENT,
                    "Accept": ACCEPT,
                    **extra_headers,
                },
                # TLS certificate is checked against the real name, not the IP.
                extensions={"sni_hostname": parts.hostname or ""},
            ) as response:
                body, too_large = _read_limited(response, max_bytes)
                return _Response(
                    response.status_code, response.headers, body, too_large
                )
        except httpx2.HTTPError as exc:
            raise _Stop(
                FetchResult(FetchStatus.NETWORK_ERROR, url, _network_message(exc))
            ) from None

    def _pinned_url(self, url: str) -> str:
        """The same URL, with the host replaced by its vetted public IP."""
        parts = urlsplit(url)
        host = parts.hostname or ""
        port = parts.port or (443 if parts.scheme == "https" else 80)
        try:
            ip = resolve_public_address(host, port, self.resolver)
        except BlockedAddressError as exc:
            raise _Stop(FetchResult(FetchStatus.BLOCKED_URL, url, str(exc))) from None
        ip_host = f"[{ip}]" if ":" in ip else ip
        netloc = f"{ip_host}:{parts.port}" if parts.port else ip_host
        return urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, ""))

    def _get_client(self) -> httpx2.Client:
        if self._client is None:
            self._client = httpx2.Client(
                transport=self.transport,
                timeout=TIMEOUT,
                follow_redirects=False,  # we follow them ourselves, safely
                trust_env=False,  # ignore proxy env vars
            )
        return self._client


def _read_limited(response: httpx2.Response, max_bytes: int) -> tuple[bytes, bool]:
    """Read the body, stopping as soon as it passes `max_bytes`."""
    body = bytearray()
    for chunk in response.iter_bytes():
        body.extend(chunk)
        if len(body) > max_bytes:
            return bytes(body), True
    return bytes(body), False


def _network_message(exc: httpx2.HTTPError) -> str:
    """A plain-language reason for a failed connection."""
    detail = str(exc)
    if "CERTIFICATE_VERIFY_FAILED" in detail or "certificate" in detail.lower():
        return "The site's security certificate isn't valid, so it wasn't read."
    if "SSL" in detail or "TLS" in detail:
        return "A secure (HTTPS) connection to the site couldn't be made."
    if isinstance(exc, httpx2.TimeoutException):
        return "The site took too long to answer (Timeout)."
    return f"Couldn't reach the site ({type(exc).__name__})."


def _charset(headers: httpx2.Headers) -> str:
    """The charset from Content-Type ("text/plain; charset=latin-1"), or utf-8."""
    for param in headers.get("content-type", "").split(";")[1:]:
        name, _, value = param.partition("=")
        if name.strip().lower() == "charset" and value.strip():
            charset = value.strip().strip("\"'")
            try:
                "".encode(charset)  # is it a codec Python knows?
            except LookupError:
                break
            return charset
    return "utf-8"


def _login(url: str) -> FetchResult:
    return FetchResult(
        FetchStatus.LOGIN_REQUIRED,
        url,
        "This page needs a login, so it isn't read automatically. You can paste "
        "the listing text instead.",
    )


def _http_error(url: str, status: int) -> FetchResult:
    return FetchResult(
        FetchStatus.HTTP_ERROR, url, f"The site answered with error {status}.", status
    )


FetcherFactory = Callable[[], PoliteFetcher]
