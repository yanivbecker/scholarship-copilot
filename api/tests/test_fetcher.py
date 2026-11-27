"""The polite fetcher (FR-D2, FR-D3, FR-D4, FR-D7, NFR-4).

No real network: a fake web (httpx2 MockTransport), fake DNS and a fake clock.
All sites and content are fictional.
"""

import httpx2
import pytest

from app.modules.fetcher.fetcher import USER_AGENT, FetchStatus
from tests.fake_web import PUBLIC_IP, FakeWeb, html
from tests.resume_files import make_pdf

# --- Happy path ---------------------------------------------------------------


def test_ok_page_gives_text_and_hash(web: FakeWeb) -> None:
    web.pages[("example.org", "/awards")] = html(headers={"etag": '"v1"'})

    result = web.fetcher().fetch("https://example.org/awards")

    assert result.status is FetchStatus.OK
    assert result.text is not None and "GPA of 3.0 or higher." in result.text
    assert result.content_hash is not None and len(result.content_hash) == 64
    assert result.etag == '"v1"'


def test_connects_to_the_vetted_ip_with_the_real_name(web: FakeWeb) -> None:
    web.pages[("example.org", "/awards")] = html()

    web.fetcher().fetch("https://example.org/awards")

    page = web.requests[-1]
    assert page.url.host == PUBLIC_IP  # no second DNS lookup to rebind
    assert page.headers["host"] == "example.org"
    assert page.extensions["sni_hostname"] == "example.org"  # TLS checks the name
    assert page.headers["user-agent"] == USER_AGENT
    assert page.method == "GET"


def test_user_agent_contains_no_personal_details() -> None:
    assert "@" not in USER_AGENT and "github" not in USER_AGENT.lower()


# --- robots.txt (FR-D2) ---------------------------------------------------------


def test_robots_disallow_means_the_page_is_never_requested(web: FakeWeb) -> None:
    web.pages[("example.org", "/robots.txt")] = httpx2.Response(
        200, text="User-agent: *\nDisallow: /private/"
    )
    web.pages[("example.org", "/private/awards")] = html()

    result = web.fetcher().fetch("https://example.org/private/awards")

    assert result.status is FetchStatus.ROBOTS_DISALLOWED
    assert web.paths_requested() == ["example.org/robots.txt"]


def test_rules_for_our_agent_are_respected(web: FakeWeb) -> None:
    web.pages[("example.org", "/robots.txt")] = httpx2.Response(
        200,
        text="User-agent: ScholarshipCopilot\nDisallow: /\n\nUser-agent: *\nAllow: /",
    )

    result = web.fetcher().fetch("https://example.org/awards")

    assert result.status is FetchStatus.ROBOTS_DISALLOWED


@pytest.mark.parametrize(
    ("robots_status", "allowed"),
    [(404, True), (410, True), (401, False), (403, False), (429, False), (500, False)],
)
def test_robots_status_codes(web: FakeWeb, robots_status: int, allowed: bool) -> None:
    web.pages[("example.org", "/robots.txt")] = httpx2.Response(robots_status)
    web.pages[("example.org", "/awards")] = html()

    result = web.fetcher().fetch("https://example.org/awards")

    assert (result.status is FetchStatus.OK) is allowed


def test_robots_redirect_is_followed(web: FakeWeb) -> None:
    web.dns["www.example.org"] = [PUBLIC_IP]
    web.pages[("example.org", "/robots.txt")] = httpx2.Response(
        301, headers={"location": "https://www.example.org/robots.txt"}
    )
    web.pages[("www.example.org", "/robots.txt")] = httpx2.Response(
        200, text="User-agent: *\nDisallow: /"
    )

    result = web.fetcher().fetch("https://example.org/awards")

    assert result.status is FetchStatus.ROBOTS_DISALLOWED


def test_robots_is_fetched_once_per_site(web: FakeWeb) -> None:
    web.pages[("example.org", "/a")] = html()
    web.pages[("example.org", "/b")] = html()
    fetcher = web.fetcher()

    fetcher.fetch("https://example.org/a")
    fetcher.fetch("https://example.org/b")

    assert web.paths_requested().count("example.org/robots.txt") == 1


def test_unreachable_robots_means_no_fetch(web: FakeWeb) -> None:
    def boom(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("down", request=request)

    web.pages[("example.org", "/robots.txt")] = boom
    web.pages[("example.org", "/awards")] = html()

    result = web.fetcher().fetch("https://example.org/awards")

    assert result.status is FetchStatus.ROBOTS_DISALLOWED


# --- Rate limits (FR-D2) ----------------------------------------------------


def test_one_request_per_second_per_site(web: FakeWeb) -> None:
    web.pages[("example.org", "/awards")] = html()

    web.fetcher().fetch("https://example.org/awards")

    # robots.txt, then the page: the second request waited a full second.
    assert web.sleeps == [pytest.approx(1.0)]


def test_crawl_delay_is_honored(web: FakeWeb) -> None:
    web.pages[("example.org", "/robots.txt")] = httpx2.Response(
        200, text="User-agent: *\nCrawl-delay: 3"
    )
    web.pages[("example.org", "/awards")] = html()

    web.fetcher().fetch("https://example.org/awards")

    assert web.sleeps == [pytest.approx(3.0)]


def test_very_long_crawl_delay_skips_the_site(web: FakeWeb) -> None:
    web.pages[("example.org", "/robots.txt")] = httpx2.Response(
        200, text="User-agent: *\nCrawl-delay: 600"
    )

    result = web.fetcher().fetch("https://example.org/awards")

    assert result.status is FetchStatus.ROBOTS_DISALLOWED
    assert "600" in result.message


# --- Address safety (NFR-4) -------------------------------------------------


@pytest.mark.parametrize(
    "addresses",
    [
        ["127.0.0.1"],
        ["10.1.2.3"],
        ["169.254.169.254"],
        ["::1"],
        [PUBLIC_IP, "192.168.0.9"],
    ],
)
def test_names_that_resolve_to_private_addresses_are_blocked(
    web: FakeWeb, addresses: list[str]
) -> None:
    web.dns["sneaky.example"] = addresses

    result = web.fetcher().fetch("https://sneaky.example/awards")

    assert result.status is FetchStatus.BLOCKED_URL
    assert not web.requests  # nothing was sent, not even robots.txt


def test_unknown_host(web: FakeWeb) -> None:
    result = web.fetcher().fetch("https://nowhere.example/")

    assert result.status is FetchStatus.BLOCKED_URL
    assert "Couldn't find" in result.message


def test_unsafe_url_is_refused_before_any_request(web: FakeWeb) -> None:
    result = web.fetcher().fetch("http://192.168.1.1/admin")

    assert result.status is FetchStatus.BLOCKED_URL
    assert not web.requests


# --- Redirects --------------------------------------------------------------


def redirect(to: str) -> httpx2.Response:
    return httpx2.Response(302, headers={"location": to})


def test_redirect_to_a_private_address_is_blocked(web: FakeWeb) -> None:
    web.dns["internal.example"] = ["10.0.0.7"]
    web.pages[("example.org", "/awards")] = redirect("https://internal.example/x")

    result = web.fetcher().fetch("https://example.org/awards")

    assert result.status is FetchStatus.BLOCKED_URL
    assert "internal.example" not in " ".join(web.paths_requested())


def test_redirect_to_an_aggregator_is_blocked(web: FakeWeb) -> None:
    web.pages[("example.org", "/awards")] = redirect("https://www.fastweb.com/x")

    result = web.fetcher().fetch("https://example.org/awards")

    assert result.status is FetchStatus.BLOCKED_URL
    assert "redirected to" in result.message


def test_redirect_to_a_login_page_stops(web: FakeWeb) -> None:
    web.pages[("example.org", "/awards")] = redirect("/users/sign_in?next=/awards")

    result = web.fetcher().fetch("https://example.org/awards")

    assert result.status is FetchStatus.LOGIN_REQUIRED
    assert "example.org/users/sign_in" not in web.paths_requested()


def test_relative_redirect_is_followed(web: FakeWeb) -> None:
    web.pages[("example.org", "/old")] = redirect("/new")
    web.pages[("example.org", "/new")] = html()

    result = web.fetcher().fetch("https://example.org/old")

    assert result.status is FetchStatus.OK
    assert result.url == "https://example.org/new"


def test_redirect_loops_end(web: FakeWeb) -> None:
    web.pages[("example.org", "/loop")] = redirect("/loop")

    result = web.fetcher().fetch("https://example.org/loop")

    assert result.status is FetchStatus.HTTP_ERROR
    assert "Too many redirects" in result.message


# --- Login walls (FR-D4) ----------------------------------------------------


def test_401_is_a_login_wall(web: FakeWeb) -> None:
    web.pages[("example.org", "/portal")] = httpx2.Response(401)

    assert web.fetcher().fetch("https://example.org/portal").status is (
        FetchStatus.LOGIN_REQUIRED
    )


def test_page_with_a_password_field_is_a_login_wall(web: FakeWeb) -> None:
    web.pages[("example.org", "/portal")] = html(
        b'<form><input name="u"><input type="password" name="p"></form>'
    )

    result = web.fetcher().fetch("https://example.org/portal")

    assert result.status is FetchStatus.LOGIN_REQUIRED
    assert result.text is None  # nothing from a login page is kept


def test_login_url_is_never_requested(web: FakeWeb) -> None:
    result = web.fetcher().fetch("https://example.org/login")

    assert result.status is FetchStatus.LOGIN_REQUIRED
    assert web.paths_requested() == ["example.org/robots.txt"]


# --- HTTP caching and limits ------------------------------------------------


def test_conditional_request_and_304(web: FakeWeb) -> None:
    web.pages[("example.org", "/awards")] = httpx2.Response(304)

    result = web.fetcher().fetch(
        "https://example.org/awards", etag='"v1"', last_modified="Mon, 01 Jan 2026"
    )

    assert result.status is FetchStatus.NOT_MODIFIED
    page = web.requests[-1]
    assert page.headers["if-none-match"] == '"v1"'
    assert page.headers["if-modified-since"] == "Mon, 01 Jan 2026"


def test_too_large_page(web: FakeWeb) -> None:
    web.pages[("example.org", "/big")] = html(b"x" * (5 * 1024 * 1024 + 10))

    assert (
        web.fetcher().fetch("https://example.org/big").status is FetchStatus.TOO_LARGE
    )


def test_403_and_500_are_http_errors(web: FakeWeb) -> None:
    web.pages[("example.org", "/a")] = httpx2.Response(403)
    web.pages[("example.org", "/b")] = httpx2.Response(500)
    fetcher = web.fetcher()

    assert fetcher.fetch("https://example.org/a").status is FetchStatus.HTTP_ERROR
    assert fetcher.fetch("https://example.org/b").http_status == 500


def test_network_error(web: FakeWeb) -> None:
    def boom(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("slow", request=request)

    web.pages[("example.org", "/slow")] = boom

    result = web.fetcher().fetch("https://example.org/slow")

    assert result.status is FetchStatus.NETWORK_ERROR
    assert "took too long" in result.message


def test_bad_certificate_is_explained(web: FakeWeb) -> None:
    def bad_cert(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError(
            "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed",
            request=request,
        )

    web.pages[("example.org", "/awards")] = bad_cert

    result = web.fetcher().fetch("https://example.org/awards")

    assert result.status is FetchStatus.NETWORK_ERROR
    assert "security certificate isn't valid" in result.message


def test_cookies_are_not_kept_between_requests(web: FakeWeb) -> None:
    web.pages[("example.org", "/a")] = html(
        headers={"set-cookie": "session=abc; Path=/"}
    )
    web.pages[("example.org", "/b")] = html()
    fetcher = web.fetcher()

    fetcher.fetch("https://example.org/a")
    fetcher.fetch("https://example.org/b")

    assert "cookie" not in web.requests[-1].headers


# --- Content types ----------------------------------------------------------


def test_pdf_pages_are_read(web: FakeWeb) -> None:
    web.pages[("example.org", "/rules.pdf")] = httpx2.Response(
        200,
        content=make_pdf(["Eligibility: GPA 3.0 or higher"]),
        headers={"content-type": "application/pdf"},
    )

    result = web.fetcher().fetch("https://example.org/rules.pdf")

    assert result.status is FetchStatus.OK
    assert result.text is not None and "GPA 3.0 or higher" in result.text


def test_plain_text_uses_the_declared_charset(web: FakeWeb) -> None:
    web.pages[("example.org", "/notes.txt")] = httpx2.Response(
        200,
        content="Bourse d'études: 500 €".encode("cp1252"),
        headers={"content-type": "text/plain; charset=cp1252"},
    )

    result = web.fetcher().fetch("https://example.org/notes.txt")

    assert result.text == "Bourse d'études: 500 €"


def test_unsupported_content(web: FakeWeb) -> None:
    web.pages[("example.org", "/logo.png")] = httpx2.Response(
        200, content=b"\x89PNG", headers={"content-type": "image/png"}
    )

    result = web.fetcher().fetch("https://example.org/logo.png")

    assert result.status is FetchStatus.UNSUPPORTED_CONTENT


def test_same_text_same_hash_regardless_of_spacing(web: FakeWeb) -> None:
    web.pages[("example.org", "/a")] = html(b"<p>GPA   3.0\n required</p>")
    web.pages[("example.org", "/b")] = html(b"<p>GPA 3.0 required</p>")
    fetcher = web.fetcher()

    assert (
        fetcher.fetch("https://example.org/a").content_hash
        == fetcher.fetch("https://example.org/b").content_hash
    )
