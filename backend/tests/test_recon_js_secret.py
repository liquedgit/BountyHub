from app.recon.base import AssetType
from app.recon.js_crawler import JSEndpointCrawler
from app.recon.scope import ScopeRule, ScopeValidator
from app.recon.secret_scanner import SecretScanner, shannon_entropy

HTML = '<html><script src="/static/app.js"></script><script src="https://cdn.other.com/x.js"></script></html>'
JS = """
fetch("/api/v1/users"); axios.get('/graphql');
const u = "https://api.example.com/v2/orders/{id}";
const logo = "/api/logo.png";
//# sourceMappingURL=app.js.map
"""
AWS = "AKIAIOSFODNN7EXAMPLE"
SECRET_JS = f'var k="{AWS}"; var apiKey = "q8Zr3Xv9LmP2wT7yB4nK6sD1";'
ENV = "DB_PASSWORD=hunter2hunter2\nSTRIPE_KEY=abc\n"


class FakeFetcher:
    def __init__(self, files):
        self.files = files
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        return self.files.get(url)


def scope():
    return ScopeValidator(
        [
            ScopeRule("example.com", "wildcard"),
            ScopeRule("admin.example.com", "domain", is_in_scope=False),
        ]
    )


def test_js_crawler_extracts_endpoints_and_sourcemaps():
    f = FakeFetcher({"https://app.example.com": HTML, "https://app.example.com/static/app.js": JS})
    res = JSEndpointCrawler(scope(), f).run(["app.example.com"])
    vals = {r.value for r in res}
    assert all(r.type == AssetType.ENDPOINT for r in res)
    assert "https://app.example.com/api/v1/users" in vals
    assert "https://app.example.com/graphql" in vals
    assert "https://api.example.com/v2/orders/{id}" in vals
    maps = [r for r in res if r.metadata["kind"] == "sourcemap"]
    assert [m.value for m in maps] == ["https://app.example.com/static/app.js.map"]
    assert not any("logo.png" in v for v in vals)
    assert "https://cdn.other.com/x.js" not in f.calls  # out-of-scope CDN never fetched


def test_js_crawler_never_fetches_out_of_scope():
    f = FakeFetcher({})
    res = JSEndpointCrawler(scope(), f).run(["evil.com", "admin.example.com"])
    assert res == [] and f.calls == []


def test_secret_scanner_finds_secrets_and_redacts():
    f = FakeFetcher(
        {
            "https://app.example.com": HTML,
            "https://app.example.com/static/app.js": SECRET_JS,
            "https://app.example.com/.env": ENV,
            "https://app.example.com/config.json": "<!doctype html><html></html>",
        }
    )
    res = SecretScanner(scope(), f).run(["app.example.com"])
    assert all(r.type == AssetType.SECRET for r in res)
    rules = {r.metadata["rule"] for r in res}
    assert {"aws_access_key_id", "high_entropy_assignment", "exposed_config"} <= rules
    assert not any(AWS in r.value or AWS in str(r.metadata) for r in res)
    exposed = [r for r in res if r.metadata["rule"] == "exposed_config"]
    assert [r.value for r in exposed] == ["/.env"]
    assert "https://cdn.other.com/x.js" not in f.calls


def test_secret_scanner_never_fetches_out_of_scope():
    f = FakeFetcher({})
    assert SecretScanner(scope(), f).run(["evil.com", "https://admin.example.com/"]) == []
    assert f.calls == []


def test_entropy_and_low_entropy_ignored():
    assert shannon_entropy("aaaa") == 0
    s = SecretScanner(scope(), FakeFetcher({}))
    assert s.scan_text('password = "aaaaaaaaaaaaaaaaaaaa"', "x") == []
