from types import SimpleNamespace as R

import pytest

from app.models.bounty import ScopeAction, ScopeType
from app.recon.scope import ScopeValidator


def rule(action, type_, value):
    return R(action=action, type=type_, value=value)


def v(*rules):
    return ScopeValidator([rule(*r) for r in rules])


def test_no_rules_rejects_everything():
    assert not v().is_in_scope("example.com")


def test_domain_exact_only():
    sv = v(("in", "domain", "example.com"))
    assert sv.is_in_scope("example.com")
    assert sv.is_in_scope("EXAMPLE.com.")
    assert sv.is_in_scope("example.com:8443")
    assert sv.is_in_scope("https://example.com/login")
    assert not sv.is_in_scope("sub.example.com")
    assert not sv.is_in_scope("notexample.com")
    assert not sv.is_in_scope("example.com.evil.net")


def test_wildcard_covers_subdomains_not_apex():
    sv = v(("in", "wildcard", "*.example.com"))
    assert sv.is_in_scope("a.example.com")
    assert sv.is_in_scope("a.b.example.com")
    assert sv.is_in_scope("https://api.example.com/v1")
    assert not sv.is_in_scope("example.com")
    assert not sv.is_in_scope("badexample.com")
    assert not sv.is_in_scope("a.example.com.evil.net")


def test_out_overrides_in():
    sv = v(
        ("in", "wildcard", "*.example.com"),
        ("out", "domain", "admin.example.com"),
        ("out", "wildcard", "*.internal.example.com"),
    )
    assert sv.is_in_scope("www.example.com")
    d = sv.check("admin.example.com")
    assert not d.in_scope and "excluded" in d.reason
    assert not sv.is_in_scope("x.internal.example.com")
    assert sv.is_in_scope("internal.example.com")


def test_out_declared_before_in_still_wins():
    sv = v(("out", "domain", "a.example.com"), ("in", "wildcard", "*.example.com"))
    assert not sv.is_in_scope("a.example.com")


def test_ip_and_cidr():
    sv = v(("in", "ip", "203.0.113.5"), ("in", "ip", "10.0.0.0/24"), ("out", "ip", "10.0.0.7"))
    assert sv.is_in_scope("203.0.113.5")
    assert sv.is_in_scope("10.0.0.200")
    assert sv.is_in_scope("http://10.0.0.1:8080/x")
    assert not sv.is_in_scope("10.0.0.7")
    assert not sv.is_in_scope("10.0.1.1")
    assert not sv.is_in_scope("203.0.113.6")


def test_ip_rule_does_not_match_hostnames_and_vice_versa():
    sv = v(("in", "ip", "10.0.0.0/8"), ("in", "domain", "example.com"))
    assert not sv.is_in_scope("10.example.com")
    assert not v(("in", "domain", "10.0.0.1")).is_in_scope("10.0.0.1")


def test_ipv6():
    sv = v(("in", "ip", "2001:db8::/32"))
    assert sv.is_in_scope("[2001:db8::1]")
    assert sv.is_in_scope("http://[2001:db8::1]:80/")
    assert not sv.is_in_scope("2001:dead::1")
    assert not sv.is_in_scope("10.0.0.1")


def test_url_rule_path_prefix():
    sv = v(("in", "url", "https://app.example.com/api"))
    assert sv.is_in_scope("https://app.example.com/api")
    assert sv.is_in_scope("https://app.example.com/api/v1/users")
    assert not sv.is_in_scope("https://app.example.com/apiary")
    assert not sv.is_in_scope("https://app.example.com/admin")
    assert not sv.is_in_scope("http://app.example.com/api")
    assert not sv.is_in_scope("https://other.example.com/api")
    assert not sv.is_in_scope("app.example.com")  # bare host not covered by a path rule


def test_url_rule_root_covers_host():
    sv = v(("in", "url", "https://app.example.com/"))
    assert sv.is_in_scope("app.example.com")
    assert sv.is_in_scope("https://app.example.com/anything")


def test_out_url_excludes_path_within_in_scope_host():
    sv = v(("in", "wildcard", "*.example.com"), ("out", "url", "https://app.example.com/admin"))
    assert sv.is_in_scope("https://app.example.com/")
    assert sv.is_in_scope("https://app.example.com/administrator-guide")
    assert not sv.is_in_scope("https://app.example.com/admin")
    assert not sv.is_in_scope("https://app.example.com/admin/users")


@pytest.mark.parametrize(
    "bad", ["", "   ", "exa mple.com", "http://", "https://:80", "a.com:notaport"]
)
def test_invalid_targets_rejected(bad):
    sv = v(("in", "wildcard", "*.example.com"), ("in", "domain", "a.com"))
    d = sv.check(bad)
    assert not d.in_scope and d.reason == "invalid target"


def test_malformed_rules_never_match():
    sv = v(
        ("in", "wildcard", "example.com"),
        ("in", "wildcard", "*."),
        ("in", "ip", "not-an-ip"),
        ("in", "domain", ""),
        ("in", "url", ""),
    )
    for t in ["example.com", "a.example.com", "1.2.3.4", "x"]:
        assert not sv.is_in_scope(t)


def test_accepts_enum_values():
    sv = ScopeValidator(
        [
            rule(ScopeAction.IN, ScopeType.WILDCARD, "*.example.com"),
            rule(ScopeAction.OUT, ScopeType.DOMAIN, "x.example.com"),
        ]
    )
    assert sv.is_in_scope("a.example.com")
    assert not sv.is_in_scope("x.example.com")


def test_partition_and_decision_details():
    sv = v(("in", "wildcard", "*.example.com"), ("out", "domain", "x.example.com"))
    ok, bad = sv.partition(["a.example.com", "x.example.com", "evil.com"])
    assert ok == ["a.example.com"]
    assert [d.target for d in bad] == ["x.example.com", "evil.com"]
    assert sv.check("a.example.com").matched_rule.value == "*.example.com"
    assert bool(sv.check("a.example.com")) is True


def test_url_rule_rejects_lookalike_host():
    sv = v(("in", "url", "https://example.com"))
    assert sv.is_in_scope("https://example.com")
    assert sv.is_in_scope("https://example.com/path")
    assert not sv.is_in_scope("https://example.com.evil.net")
    assert not sv.is_in_scope("https://example.com.evil.net/path")
    assert not sv.is_in_scope("https://example.company")


def test_out_rule_beats_matching_wildcard():
    sv = v(("in", "wildcard", "*.example.com"), ("out", "wildcard", "*.example.com"))
    assert not sv.is_in_scope("a.example.com")


def test_wildcard_does_not_match_apex():
    assert not v(("in", "wildcard", "*.example.com")).is_in_scope("example.com")


@pytest.mark.parametrize("target", ["example.com", "https://example.com/x", "10.0.0.1", "[::1]"])
def test_empty_rule_set_rejects_everything(target):
    assert not v().is_in_scope(target)
    assert v().partition([target]) == ([], [v().check(target)])


@pytest.mark.parametrize(
    "garbage", ["", "\x00", "http://", "://", "a b", "https://[::1", "\n", "http://exa mple.com"]
)
def test_garbage_input_rejected(garbage):
    sv = v(
        ("in", "wildcard", "*.example.com"),
        ("in", "domain", "example.com"),
        ("in", "url", "https://example.com"),
    )
    assert not sv.is_in_scope(garbage)
