"""Resolve a hostname and refuse anything that isn't a public address (NFR-4).

url_safety only sees the *name* in a URL. A public-looking name can resolve to
127.0.0.1 or 10.x, or switch to one between our check and the connection
("DNS rebinding"). So the fetcher resolves the name itself, checks every
address it gets back, and then connects to that exact address. There is no
second lookup an attacker could change.
"""

import ipaddress
import socket
from collections.abc import Callable

type IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
type Resolver = Callable[[str, int], list[str]]


class BlockedAddressError(ValueError):
    """The host resolves to a private/local/reserved address, or not at all."""


def system_resolver(host: str, port: int) -> list[str]:
    """All addresses the OS resolver returns for host:port."""
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(str(info[4][0]) for info in infos))


def _parse(address: str) -> IPAddress:
    ip = ipaddress.ip_address(address.split("%", 1)[0])  # drop IPv6 zone id
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def resolve_public_address(host: str, port: int, resolver: Resolver) -> str:
    """Return one public IP for host, or raise BlockedAddressError.

    If *any* address is non-public we refuse the whole host: a name that mixes
    public and private answers is either misconfigured or an attack.
    """
    try:
        addresses = resolver(host, port)
    except (OSError, UnicodeError):
        raise BlockedAddressError(f"Couldn't find the site {host!r}.") from None
    if not addresses:
        raise BlockedAddressError(f"Couldn't find the site {host!r}.")
    parsed = [_parse(a) for a in addresses]
    if not all(ip.is_global for ip in parsed):
        raise BlockedAddressError(
            f"{host!r} points to a private or local network address."
        )
    # Prefer IPv4: it works on more home networks.
    parsed.sort(key=lambda ip: ip.version)
    return str(parsed[0])
