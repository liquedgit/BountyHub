from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import urljoin, urlsplit

from app.recon.base import AssetType, Fetcher, ReconAssetResult, ReconTool
from app.recon.scope import ScopeValidator

SCRIPT_SRC_RE = re.compile(r"""<script[^>]+src\s*=\s*["']([^"']+)["']""", re.I)
SOURCEMAP_RE = re.compile(r"""//[#@]\s*sourceMappingURL=([^\s'"]+)""")
# Quoted strings that look like API paths or absolute URLs.
PATH_RE = re.compile(
    r"""["'`]((?:/(?:api|rest|graphql|v\d+|auth|oauth|admin|internal|user|users|account)[\w\-./{}:$]*)"""
    r"""|(?:https?://[\w.\-]+(?::\d+)?/[\w\-./{}:?=&%$]*))["'`]""",
    re.I,
)
# fetch("/x"), axios.get("/x"), $.ajax({url:"/x"}), xhr.open("GET","/x")
CALL_RE = re.compile(
    r"""(?:fetch|axios(?:\.\w+)?|\$\.(?:get|post|ajax)|\.open)\s*\(\s*(?:["'`][A-Z]+["'`]\s*,\s*)?["'`]"""
    r"""(/[\w\-./{}:$?=&%]*)["'`]""",
    re.I,
)
STATIC_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".woff", ".woff2", ".ico", ".ttf")


def extract_endpoints(js: str) -> set[str]:
    found = {m.group(1) for m in PATH_RE.finditer(js)}
    found |= {m.group(1) for m in CALL_RE.finditer(js)}
    return {f for f in found if not f.lower().endswith(STATIC_EXT) and len(f) > 1}


def extract_sourcemaps(js: str) -> set[str]:
    return {m.group(1) for m in SOURCEMAP_RE.finditer(js)}


class JSEndpointCrawler(ReconTool):
    """Extracts API routes, endpoints and source maps from a target's JS bundles."""

    name = "js_crawler"

    def __init__(self, scope: ScopeValidator, fetcher: Fetcher, max_scripts: int = 50):
        self.scope = scope
        self.fetcher = fetcher
        self.max_scripts = max_scripts

    def run(self, targets: Iterable[str]) -> list[ReconAssetResult]:
        results: list[ReconAssetResult] = []
        seen: set[tuple[str, str]] = set()

        def add(kind: str, value: str, source: str) -> None:
            if (kind, value) not in seen:
                seen.add((kind, value))
                results.append(
                    ReconAssetResult(AssetType.ENDPOINT, value, source, {"kind": kind})
                )

        for target in targets:
            if not self.scope.is_in_scope(target):
                continue  # never fetched
            base = target if "://" in target else f"https://{target}"
            js_urls: list[str] = []
            if urlsplit(base).path.endswith(".js"):
                js_urls.append(base)
            else:
                html = self.fetcher(base)
                for src in SCRIPT_SRC_RE.findall(html or ""):
                    js_urls.append(urljoin(base, src))
            for js_url in js_urls[: self.max_scripts]:
                if not self.scope.is_in_scope(js_url):
                    continue  # third-party / out-of-scope CDN
                body = self.fetcher(js_url)
                if not body:
                    continue
                for ep in sorted(extract_endpoints(body)):
                    full = urljoin(js_url, ep) if ep.startswith("/") else ep
                    add("route" if ep.startswith("/") else "url", full, js_url)
                for sm in sorted(extract_sourcemaps(body)):
                    add("sourcemap", urljoin(js_url, sm), js_url)
        return results
