from __future__ import annotations

from urllib.parse import urljoin

import httpx

from app.recon.base import Fetcher
from app.recon.netguard import NetworkGuard, default_guard
from app.recon.scope import ScopeValidator

MAX_REDIRECTS = 5


class HttpFetcher:
    """HTTP GET fetcher with a timeout, a response size cap and scope-checked redirects.

    Redirects are followed manually so an out-of-scope redirect target is never requested.
    With a ``guard`` the first URL and every redirect hop must also be a public address.
    Any error (network, size cap, scope) yields ``None``.
    """

    def __init__(
        self,
        scope: ScopeValidator,
        timeout: float = 10.0,
        max_bytes: int = 2_000_000,
        client: httpx.Client | None = None,
        guard: NetworkGuard | None = None,
    ):
        self.scope = scope
        self.timeout = timeout
        self.max_bytes = max_bytes
        self._client = client
        self._guard = guard

    def __call__(self, url: str) -> str | None:
        client = self._client or httpx.Client(timeout=self.timeout, follow_redirects=False)
        try:
            return self._fetch(client, url)
        except Exception:
            return None
        finally:
            if self._client is None:
                client.close()

    def _fetch(self, client: httpx.Client, url: str) -> str | None:
        for _ in range(MAX_REDIRECTS + 1):
            if not self.scope.is_in_scope(url):
                return None
            if self._guard is not None and not self._guard.check(url):
                return None
            with client.stream("GET", url, timeout=self.timeout) as resp:
                if resp.is_redirect:
                    location = resp.headers.get("location")
                    if not location:
                        return None
                    url = urljoin(url, location)
                    continue
                if resp.status_code >= 400:
                    return None
                declared = resp.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > self.max_bytes:
                    return None
                body = bytearray()
                for chunk in resp.iter_bytes():
                    body.extend(chunk)
                    if len(body) > self.max_bytes:
                        return None
                return body.decode(resp.encoding or "utf-8", errors="replace")
        return None


def make_fetcher(scope: ScopeValidator, **kwargs) -> Fetcher:
    kwargs.setdefault("guard", default_guard())
    return HttpFetcher(scope, **kwargs)
