from __future__ import annotations

import fnmatch
import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ScopeRule:
    pattern: str
    kind: str = "domain"  # domain | wildcard | ip | url
    is_in_scope: bool = True


def extract_host(target: str) -> str:
    target = target.strip()
    parts = urlsplit(target if "://" in target else f"//{target}")
    return (parts.hostname or "").lower()


class ScopeValidator:
    """Gates every target: must match an in-scope rule and no out-of-scope rule."""

    def __init__(self, rules: list[ScopeRule]):
        self._in = [r for r in rules if r.is_in_scope]
        self._out = [r for r in rules if not r.is_in_scope]

    @staticmethod
    def _matches(rule: ScopeRule, target: str, host: str) -> bool:
        pat = rule.pattern.strip().lower()
        if rule.kind == "url":
            return target.strip().lower().startswith(pat)
        if rule.kind == "ip":
            try:
                if "/" in pat:
                    return ipaddress.ip_address(host) in ipaddress.ip_network(pat, strict=False)
                return host == pat
            except ValueError:
                return False
        if rule.kind == "wildcard" or "*" in pat:
            base = pat.lstrip("*.")
            return host == base or fnmatch.fnmatch(host, pat if "*" in pat else f"*.{pat}")
        return host == pat

    def is_in_scope(self, target: str) -> bool:
        host = extract_host(target)
        if not host:
            return False
        if any(self._matches(r, target, host) for r in self._out):
            return False
        return any(self._matches(r, target, host) for r in self._in)
