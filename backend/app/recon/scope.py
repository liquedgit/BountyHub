import ipaddress
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class Rule:
    rule_type: str  # domain | wildcard | ip | url
    pattern: str
    in_scope: bool = True


def normalize_host(value: str) -> str:
    """Reduce a URL or host[:port] to a lowercase bare hostname."""
    value = value.strip().lower()
    if "://" in value:
        value = urlparse(value).hostname or ""
    else:
        value = value.split("/")[0]
        if value.count(":") == 1:
            value = value.split(":")[0]
    return value.rstrip(".")


class ScopeValidator:
    """Decides whether a target host is allowed. Explicit exclusions always win;
    anything not matched by an in-scope rule is out of scope (default deny)."""

    def __init__(self, rules: Iterable[Rule]):
        self._rules = list(rules)

    def is_in_scope(self, target: str) -> bool:
        host = normalize_host(target)
        if not host:
            return False
        if any(not r.in_scope and self._matches(r, host) for r in self._rules):
            return False
        return any(r.in_scope and self._matches(r, host) for r in self._rules)

    def partition(self, targets: Iterable[str]) -> tuple[list[str], list[str]]:
        allowed: list[str] = []
        rejected: list[str] = []
        for t in targets:
            (allowed if self.is_in_scope(t) else rejected).append(t)
        return allowed, rejected

    @staticmethod
    def _matches(rule: Rule, host: str) -> bool:
        pattern = rule.pattern.strip().lower()
        if rule.rule_type == "url":
            pattern = normalize_host(pattern)
            return host == pattern
        if rule.rule_type == "ip":
            try:
                host_ip = ipaddress.ip_address(host)
                if "/" in pattern:
                    return host_ip in ipaddress.ip_network(pattern, strict=False)
                return host_ip == ipaddress.ip_address(pattern)
            except ValueError:
                return False
        if rule.rule_type == "wildcard":
            base = pattern.removeprefix("*.").removeprefix(".")
            return host.endswith("." + base)
        return host == pattern.rstrip(".")  # domain: exact host only
