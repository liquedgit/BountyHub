from types import SimpleNamespace

import httpx

from app.recon.fetcher import HttpFetcher
from app.recon.scope import ScopeValidator


def fetcher(handler, **kw):
    scope = ScopeValidator([SimpleNamespace(action="in", type="wildcard", value="*.example.com")])
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return HttpFetcher(scope, client=client, **kw)


def test_fetches_body():
    f = fetcher(lambda r: httpx.Response(200, text="hello"))
    assert f("https://app.example.com/a.js") == "hello"


def test_out_of_scope_url_not_requested():
    seen = []

    def h(r):
        seen.append(str(r.url))
        return httpx.Response(200, text="x")

    assert fetcher(h)("https://evil.com/") is None
    assert seen == []


def test_out_of_scope_redirect_not_followed():
    seen = []

    def h(r):
        seen.append(str(r.url))
        return httpx.Response(302, headers={"location": "https://evil.com/x"})

    assert fetcher(h)("https://app.example.com/") is None
    assert seen == ["https://app.example.com/"]


def test_in_scope_redirect_followed():
    def h(r):
        if r.url.path == "/":
            return httpx.Response(302, headers={"location": "/final"})
        return httpx.Response(200, text="done")

    assert fetcher(h)("https://app.example.com/") == "done"


def test_size_cap_and_errors_return_none():
    big = fetcher(lambda r: httpx.Response(200, content=b"a" * 100), max_bytes=10)
    assert big("https://a.example.com/") is None
    err = fetcher(lambda r: httpx.Response(500))
    assert err("https://a.example.com/") is None

    def boom(r):
        raise httpx.ConnectError("x")

    assert fetcher(boom)("https://a.example.com/") is None
