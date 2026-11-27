"""Checks that a source URL is allowed before it is ever stored.

Rules (CLAUDE.md, FR-D3, NFR-4):
  * http or https only; no usernames/passwords in the URL.
  * Never an aggregator site (they repackage listings; we go to sponsors).
  * Never a private, loopback, link-local, or otherwise non-public IP address.

Limits of this check: a public-looking *hostname* can still resolve to a
private IP (or change what it resolves to later: "DNS rebinding"). So this is
the first gate only. The Phase 5 fetcher must re-check the resolved IP on
every request, right before connecting.
"""

import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit

MAX_URL_LENGTH = 2000

# Known scholarship aggregators and search sites (FR-D3). Subdomains included.
BLOCKED_AGGREGATORS = frozenset(
    {
        "fastweb.com",
        "scholarships.com",
        "bold.org",
        "niche.com",
        "scholarshipowl.com",
        "unigo.com",
        "cappex.com",
        "chegg.com",
        "scholarships360.org",
        "goingmerry.com",
        "raise.me",
        "bigfuture.collegeboard.org",
    }
)

_BLOCKED_HOSTNAMES = frozenset({"localhost", "localhost.localdomain"})
_BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home.arpa")

# A label like "1", "017" or "0x7f". Real top-level domains are never numeric,
# so a host ending in one is an IP address in some unusual spelling
# ("127.1", "0x7f.0.0.1", "2130706433") that browsers still accept.
_NUMERIC_LABEL = re.compile(r"(0x[0-9a-f]*|[0-9]+)")


class UnsafeURLError(ValueError):
    """The URL may not be used as a source. The message is user-facing."""


def normalize_source_url(raw: str) -> str:
    """Validate `raw` and return a canonical form, or raise UnsafeURLError.

    Canonical: lowercase scheme and host, no fragment, no default port,
    path at least "/". Two spellings of the same page compare equal.
    """
    text = raw.strip()
    if not text:
        raise UnsafeURLError("Enter a web address.")
    if len(text) > MAX_URL_LENGTH:
        raise UnsafeURLError("That web address is too long.")
    if any(ch.isspace() for ch in text):
        raise UnsafeURLError("Web addresses can't contain spaces.")

    try:
        parts = urlsplit(text)
        port = parts.port  # raises ValueError for a non-numeric port
    except ValueError:
        raise UnsafeURLError("That doesn't look like a valid web address.") from None

    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"}:
        raise UnsafeURLError("Only http:// and https:// addresses are allowed.")
    if parts.username is not None or parts.password is not None:
        raise UnsafeURLError(
            "Web addresses with a username or password aren't allowed."
        )

    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise UnsafeURLError("The web address needs a site name.")
    _check_host(host)

    default_port = {"http": 80, "https": 443}[scheme]
    netloc = f"[{host}]" if ":" in host else host  # bracket IPv6 literals
    if port is not None and port != default_port:
        netloc = f"{netloc}:{port}"
    return urlunsplit((scheme, netloc, parts.path or "/", parts.query, ""))


def _check_host(host: str) -> None:
    ip = _as_ip(host)
    if ip is not None:
        if not ip.is_global:
            raise UnsafeURLError(
                "Private, local, or reserved network addresses aren't allowed."
            )
        return
    if _NUMERIC_LABEL.fullmatch(host.rsplit(".", 1)[-1]):
        raise UnsafeURLError(
            "Private, local, or reserved network addresses aren't allowed."
        )
    if host in _BLOCKED_HOSTNAMES or host.endswith(_BLOCKED_SUFFIXES):
        raise UnsafeURLError("Local network addresses aren't allowed.")
    if "." not in host:
        raise UnsafeURLError("Use a full site name, like example.org.")
    if is_aggregator(host):
        raise UnsafeURLError(
            "Aggregator sites aren't used as sources. Add the sponsor's own "
            "page instead (for example, the foundation or college website)."
        )


def _as_ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return None
    # "::ffff:10.0.0.1" is an IPv4 address in IPv6 clothing: judge the IPv4.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def is_aggregator(host: str) -> bool:
    """True for a blocked domain or any of its subdomains."""
    host = host.lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in BLOCKED_AGGREGATORS)
