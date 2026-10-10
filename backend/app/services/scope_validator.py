"""Scope guard: decides whether a host/URL is allowed by a program's scope rules.

Semantics (fail-closed):
- Any matching ``out`` rule rejects the target, even if an ``in`` rule also matches.
- A target must match at least one ``in`` rule; with no in-rules everything is rejected.
- Unparseable targets or rules never match.

Rule types:
- ``domain``:   exact host match (``example.com`` does NOT cover ``sub.example.com``).
- ``wildcard``: ``*.example.com`` covers any subdomain depth, but not the apex.
- ``ip``:       single IP or CIDR; only matches IP-literal targets.
- ``url``:      host match plus path prefix on a segment boundary. A bare-host target
                (no path) only matches a url rule whose path is empty or ``/``.
"""

import ipaddress
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.parse import urlsplit

_IP = ipaddress.IPv4Address | ipaddress.IPv6Address


@dataclass(frozen=True)
class _Parsed:
    host: str
    path: str  # "" when the target was a bare host
    scheme: str  # "" when absent

    @property
    def ip(self) -> _IP | None:
        try:
            return ipaddress.ip_address(self.host)
        except ValueError:
            return None


@dataclass(frozen=True)
class ScopeDecision:
    target: str
    in_scope: bool
    reason: str
    matched_rule: Any = None

    def __bool__(self) -> bool:
        return self.in_scope


def _val(x: Any) -> str:
    return (x.value if isinstance(x, Enum) else str(x)).lower()


def _parse(raw: str) -> _Parsed | None:
    s = (raw or "").strip().lower()
    if not s or any(c.isspace() for c in s):
        return None
    has_scheme = "://" in s
    try:
        parts = urlsplit(s if has_scheme else "//" + s)
        host = parts.hostname
        parts.port  # noqa: B018 - validates the port
    except ValueError:
        return None
    if not host:
        return None
    host = host.rstrip(".")
    if not host:
        return None
    path = parts.path if parts.path not in ("", "/") or has_scheme else ""
    if has_scheme and path == "":
        path = "/"
    return _Parsed(host=host, path=path, scheme=parts.scheme if has_scheme else "")


class ScopeValidator:
    def __init__(self, rules: Iterable[Any]):
        """``rules``: objects exposing ``action`` (in/out), ``type`` and ``value``."""
        self._in: list[Any] = []
        self._out: list[Any] = []
        for r in rules:
            (self._out if _val(r.action) == "out" else self._in).append(r)

    # -- matching ---------------------------------------------------------
    @staticmethod
    def _matches(rule: Any, t: _Parsed) -> bool:
        rtype = _val(rule.type)
        raw = str(rule.value).strip().lower()
        if rtype == "domain":
            p = _parse(raw)
            return p is not None and t.ip is None and p.host == t.host
        if rtype == "wildcard":
            if not raw.startswith("*."):
                return False
            apex = raw[2:].rstrip(".")
            if not apex or "*" in apex or "/" in apex:
                return False
            return t.ip is None and t.host.endswith("." + apex)
        if rtype == "ip":
            ip = t.ip
            if ip is None:
                return False
            try:
                if "/" in raw:
                    net = ipaddress.ip_network(raw, strict=False)
                    return ip.version == net.version and ip in net
                return ip == ipaddress.ip_address(raw)
            except ValueError:
                return False
        if rtype == "url":
            p = _parse(raw)
            if p is None or p.host != t.host:
                return False
            if p.scheme and t.scheme and p.scheme != t.scheme:
                return False
            rule_path = p.path.rstrip("/")
            if not t.path:
                return rule_path == ""
            tpath = t.path.rstrip("/")
            return tpath == rule_path or tpath.startswith(rule_path + "/")
        return False

    # -- public API -------------------------------------------------------
    def check(self, target: str) -> ScopeDecision:
        t = _parse(target)
        if t is None:
            return ScopeDecision(target, False, "invalid target")
        for rule in self._out:
            if self._matches(rule, t):
                return ScopeDecision(target, False, f"excluded by out-of-scope rule {rule.value!r}", rule)
        for rule in self._in:
            if self._matches(rule, t):
                return ScopeDecision(target, True, f"matched in-scope rule {rule.value!r}", rule)
        return ScopeDecision(target, False, "no matching in-scope rule")

    def is_in_scope(self, target: str) -> bool:
        return self.check(target).in_scope

    def partition(self, targets: Iterable[str]) -> tuple[list[str], list[ScopeDecision]]:
        """Split targets into (accepted, rejected decisions)."""
        accepted: list[str] = []
        rejected: list[ScopeDecision] = []
        for t in targets:
            d = self.check(t)
            (accepted.append(t) if d.in_scope else rejected.append(d))
        return accepted, rejected
