"""Guards against SSRF: is a host safe for this app to connect to.

Two policies, not one:

* `ensure_public_host` refuses loopback, link-local (which includes cloud
  instance-metadata endpoints at 169.254.169.254), and RFC1918 private
  ranges. For a fetch where the caller supplies a URL that is supposed to
  point at a public resource — "learn a schema from this sample file" —
  there is no legitimate reason to land on an internal address, so the
  whole private space is refused. This is the one that matters most: it's
  reachable by anyone who can sign up for an account, not just an existing
  project member.

* `ensure_not_internal_service` refuses only loopback and link-local, not
  RFC1918. Used where reaching a private-network host is the entire point
  of the feature — a database connection, an object storage endpoint, a
  webhook target — and blocking RFC1918 would break the ordinary case of
  "my Postgres is at 10.x.x.x". The addresses it still refuses could never
  legitimately be "my database": the cloud metadata endpoint, and the
  backend's own loopback interface (which would mean using this feature to
  reach the backend's other, unauthenticated-by-design internal surfaces).

Both resolve the hostname once via `socket.getaddrinfo` and check every
returned address. That leaves a DNS-rebinding gap — a name that resolves
here to a public IP but is repointed at a private one before the actual
connection happens a moment later — which would need connection-level IP
pinning to close completely. Not attempted here: every caller either
connects immediately after checking (`ingest.fetch_url`) or checks
configuration supplied by an already-authenticated project member
(everything else), which is a materially smaller window and a much
higher-trust caller than the unauthenticated-signup case this exists to
stop.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeHostError(ValueError):
    pass


def _resolved_ips(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except OSError as exc:
        raise UnsafeHostError(f"Could not resolve host '{hostname}': {exc}") from exc

    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for _family, _type, _proto, _canonname, sockaddr in infos:
        try:
            ips.append(ipaddress.ip_address(sockaddr[0]))
        except ValueError:
            continue
    if not ips:
        raise UnsafeHostError(f"Could not resolve host '{hostname}'")
    return ips


def _is_disallowed(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address, *, allow_private: bool
) -> bool:
    if ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_reserved or ip.is_multicast:
        return True
    return not allow_private and ip.is_private


def _check(hostname: str, *, allow_private: bool) -> None:
    for ip in _resolved_ips(hostname):
        if _is_disallowed(ip, allow_private=allow_private):
            raise UnsafeHostError(f"'{hostname}' resolves to {ip}, which can't be used here")


def ensure_public_host(hostname: str) -> None:
    _check(hostname, allow_private=False)


def ensure_not_internal_service(hostname: str) -> None:
    _check(hostname, allow_private=True)


def ensure_public_url(url: str, *, allowed_schemes: tuple[str, ...] = ("http", "https")) -> None:
    """Scheme plus host check together, for the common case of validating
    a whole user-supplied URL in one call."""
    parsed = urlparse(url)
    if parsed.scheme not in allowed_schemes:
        raise UnsafeHostError(
            f"Only {' and '.join(allowed_schemes)} URLs are supported, not '{parsed.scheme}'"
        )
    if not parsed.hostname:
        raise UnsafeHostError("That URL has no host")
    ensure_public_host(parsed.hostname)
