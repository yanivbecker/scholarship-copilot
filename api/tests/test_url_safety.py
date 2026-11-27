"""Source URL checks (FR-D3, NFR-4, CLAUDE.md scraper rules)."""

import pytest

from app.modules.sources.url_safety import (
    UnsafeURLError,
    is_aggregator,
    normalize_source_url,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://example.org", "https://example.org/"),
        ("  HTTPS://Example.ORG/Awards  ", "https://example.org/Awards"),
        ("https://example.org:443/a", "https://example.org/a"),  # default port
        ("http://example.org:80/", "http://example.org/"),
        ("https://example.org:8443/a", "https://example.org:8443/a"),
        ("https://example.org/a?b=1#section", "https://example.org/a?b=1"),
        ("https://example.org./a", "https://example.org/a"),  # trailing dot
        ("https://8.8.8.8/", "https://8.8.8.8/"),  # public IP is fine
    ],
)
def test_valid_urls_are_normalized(raw: str, expected: str) -> None:
    assert normalize_source_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "example.org",  # no scheme
        "ftp://example.org/",
        "javascript:alert(1)",
        "file:///etc/passwd",
        "https://user:pass@example.org/",
        "https://user@example.org/",
        "https://exa mple.org/",
        "https://example.org:notaport/",
        "https:///path-only",
        "https://intranet/",  # single-label host
        "https://" + "a" * 2000 + ".org/",
    ],
)
def test_malformed_or_disallowed_urls_are_rejected(raw: str) -> None:
    with pytest.raises(UnsafeURLError):
        normalize_source_url(raw)


@pytest.mark.parametrize(
    "raw",
    [
        "http://127.0.0.1/",
        "http://10.0.0.5/",
        "http://172.16.0.1/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint
        "http://0.0.0.0/",
        "http://100.64.0.1/",  # carrier-grade NAT
        "http://[::1]/",
        "http://[fe80::1]/",
        "http://[fc00::1]/",
        "http://[::ffff:10.0.0.1]/",  # IPv4-mapped IPv6
        "http://localhost:8000/",
        "http://api.localhost/",
        "http://printer.local/",
        "http://router.lan/",
        "http://127.1/",  # shorthand for 127.0.0.1
        "http://0x7f.0.0.1/",  # hex
        "http://2130706433/",  # decimal 127.0.0.1
        "http://017.0.0.1/",  # octal
    ],
)
def test_private_and_local_addresses_are_blocked(raw: str) -> None:
    # NFR-4: never let a source point the fetcher at our own machine/network.
    with pytest.raises(UnsafeURLError, match="aren't allowed"):
        normalize_source_url(raw)


@pytest.mark.parametrize(
    "raw",
    [
        "https://www.fastweb.com/college-scholarships",
        "https://scholarships.com/",
        "https://bold.org/scholarships/",
        "https://BIGFUTURE.collegeboard.org/scholarships",
    ],
)
def test_aggregators_are_blocked(raw: str) -> None:
    with pytest.raises(UnsafeURLError, match="Aggregator"):
        normalize_source_url(raw)


def test_aggregator_match_is_by_domain_not_substring() -> None:
    assert is_aggregator("www.bold.org")
    assert not is_aggregator("bold.organization.example")
    assert not is_aggregator("notbold.org")
    # The College Board itself isn't blocked, only its scholarship search.
    assert not is_aggregator("collegeboard.org")
