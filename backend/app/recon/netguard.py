"""Network guard: refuses recon targets that are not on a public network (spec §9.3).

This answers "is this address public?", not "is it in scope?" - scope matching stays in
``ScopeValidator``. The guard cannot be switched off by scope rules, only by the
``recon_allow_private_targets`` setting.
"""

from __future__ import annotations

import ipaddress
import socket
import string
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

BLOCKED_REASON = "blocked: private or internal address"

_BLOCKED_SUFFIXES = (".local", ".internal", ".localhost", ".lan", ".home.arpa")
_IPV4_LIKE = set(string.hexdigits + "xX.")
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_SIXTOFOUR = ipaddress.ip_network("2002::/16")


class Resolver(Protocol):
    def resolve(self, host: str) -> list[str]:
        """Return every address of ``host``; an empty list or an exception means unresolved."""
        ...


class SystemResolver:
    """``socket.getaddrinfo`` with a wall-clock timeout."""

    def __init__(self, timeout: float = 3.0):
        self.timeout = timeout

    def resolve(self, host: str) -> list[str]:
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            infos = pool.submit(socket.getaddrinfo, host, None, 0, socket.SOCK_STREAM).result(
                timeout=self.timeout
            )
        except (OSError, FutureTimeout):
            return []
        finally:
            pool.shutdown(wait=False)
        return list(dict.fromkeys(str(info[4][0]) for info in infos))


@dataclass(frozen=True)
class GuardDecision:
    value: str
    allowed: bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.allowed


def blocked_entry(value: str) -> str:
    """The string recorded in ``rejected_targets`` for a blocked target."""
    return f"{BLOCKED_REASON}: {value}"


def _host_of(value: str) -> str:
    s = (value or "").strip().lower()
    if s.count(":") > 1 and "[" not in s and "/" not in s:
        return s  # bare IPv6 literal
    if "://" not in s:
        s = "//" + s
    try:
        host = urlsplit(s).hostname or ""
    except ValueError:
        return ""
    return host.rstrip(".")


def _parse_ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        pass
    # Legacy IPv4 spellings that getaddrinfo accepts: 2130706433, 0x7f.1, 127.1, 0177.0.0.1
    if host and host[0].isdigit() and set(host) <= _IPV4_LIKE:
        try:
            return ipaddress.IPv4Address(socket.inet_aton(host))
        except OSError:
            return None
    return None


def _is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return _is_public(ip.ipv4_mapped)
        if ip in _NAT64 or ip in _SIXTOFOUR:
            embedded = (
                ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
                if ip in _NAT64
                else ipaddress.IPv4Address((int(ip) >> 80) & 0xFFFFFFFF)
            )
            return _is_public(embedded)
    if (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or ip.is_private
    ):
        return False
    return ip.is_global


class NetworkGuard:
    def __init__(self, resolver: Resolver, allow_private: bool = False):
        self._resolver = resolver
        self._allow_private = allow_private

    @property
    def allow_private(self) -> bool:
        return self._allow_private

    def check_target(self, value: str) -> GuardDecision:
        """Static check: IP literals and internal-looking names. Does no DNS."""
        if self._allow_private:
            return GuardDecision(value, True)
        host = _host_of(value)
        if not host:
            return GuardDecision(value, True)  # not ours to judge; scope handles it
        ip = _parse_ip(host)
        if ip is not None:
            if _is_public(ip):
                return GuardDecision(value, True)
            return GuardDecision(value, False, f"{BLOCKED_REASON} ({ip})")
        if host == "localhost" or "." not in host or host.endswith(_BLOCKED_SUFFIXES):
            return GuardDecision(value, False, f"{BLOCKED_REASON} ({host})")
        return GuardDecision(value, True)

    def check_resolved(self, host: str) -> GuardDecision:
        """Resolve a hostname; blocked if ANY address is not public. Unresolved passes."""
        if self._allow_private:
            return GuardDecision(host, True)
        name = _host_of(host)
        if not name or _parse_ip(name) is not None:
            return GuardDecision(host, True)
        try:
            addresses = self._resolver.resolve(name)
        except Exception:  # noqa: BLE001 - a failing resolver means "unresolved"
            return GuardDecision(host, True)
        for addr in addresses:
            ip = _parse_ip(str(addr))
            if ip is None or not _is_public(ip):
                return GuardDecision(
                    host, False, f"{BLOCKED_REASON} ({name} resolves to {addr})"
                )
        return GuardDecision(host, True)

    def check(self, value: str) -> GuardDecision:
        """Full check for a target or URL: literals and names first, then resolution."""
        decision = self.check_target(value)
        if not decision:
            return decision
        return self.check_resolved(value)

    def partition(self, values: list[str]) -> tuple[list[str], list[str]]:
        """Split into (allowed values, blocked entries for ``rejected_targets``)."""
        allowed: list[str] = []
        blocked: list[str] = []
        for v in values:
            if self.check(v):
                allowed.append(v)
            else:
                blocked.append(blocked_entry(v))
        return allowed, blocked


def default_guard() -> NetworkGuard:
    from app.core.config import get_settings

    return NetworkGuard(SystemResolver(), get_settings().recon_allow_private_targets)
