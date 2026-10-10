from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable
from urllib.parse import urljoin

from app.recon.base import AssetType, Fetcher, ReconAssetResult, ReconTool
from app.recon.js_crawler import SCRIPT_SRC_RE
from app.recon.scope import ScopeValidator

RULES: dict[str, re.Pattern[str]] = {
    "aws_access_key_id": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "slack_token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    "stripe_secret_key": re.compile(r"\bsk_live_[0-9a-zA-Z]{24,}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
}
# key = "value" assignments for generic high-entropy secrets
ASSIGN_RE = re.compile(
    r"""(?i)\b([\w.-]*(?:secret|token|passw(?:or)?d|api[_-]?key|auth)[\w.-]*)\b["']?\s*[:=]\s*["']?([A-Za-z0-9/+_\-=.]{16,})["']?"""
)
ENTROPY_THRESHOLD = 3.5

# Common exposed config paths probed on in-scope hosts.
PROBE_PATHS = ("/.env", "/config.json", "/.git/config", "/config.js", "/appsettings.json")
ENV_LINE_RE = re.compile(r"(?m)^[A-Z][A-Z0-9_]{2,}\s*=\s*\S+")


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in (s.count(ch) for ch in set(s)))


def redact(value: str) -> str:
    return value[:4] + "…" + "*" * 4 if len(value) > 8 else "****"


class SecretScanner(ReconTool):
    """Regex + entropy secret scanner over page/JS bodies and exposed config files.

    Raw secret values are never stored in metadata or logs: only a redacted preview
    and a sha256 fingerprint.
    """

    name = "secret_scanner"

    def __init__(self, scope: ScopeValidator, fetcher: Fetcher, max_scripts: int = 50):
        self.scope = scope
        self.fetcher = fetcher
        self.max_scripts = max_scripts

    def scan_text(self, text: str, source: str) -> list[ReconAssetResult]:
        out: list[ReconAssetResult] = []
        seen: set[str] = set()

        def emit(rule: str, raw: str, **extra: object) -> None:
            fp = hashlib.sha256(raw.encode()).hexdigest()
            if fp in seen:
                return
            seen.add(fp)
            out.append(
                ReconAssetResult(
                    AssetType.SECRET,
                    redact(raw),
                    source,
                    {"rule": rule, "fingerprint": fp, **extra},
                )
            )

        for rule, pat in RULES.items():
            for m in pat.finditer(text):
                emit(rule, m.group(0))
        for m in ASSIGN_RE.finditer(text):
            val = m.group(2)
            ent = shannon_entropy(val)
            if ent >= ENTROPY_THRESHOLD:
                emit("high_entropy_assignment", val, key=m.group(1), entropy=round(ent, 2))
        return out

    def run(self, targets: Iterable[str]) -> list[ReconAssetResult]:
        results: list[ReconAssetResult] = []
        for target in targets:
            if not self.scope.is_in_scope(target):
                continue  # never fetched
            base = target if "://" in target else f"https://{target}"
            html = self.fetcher(base)
            bodies: list[tuple[str, str]] = []
            if html:
                bodies.append((base, html))
                for src in SCRIPT_SRC_RE.findall(html)[: self.max_scripts]:
                    js_url = urljoin(base, src)
                    if self.scope.is_in_scope(js_url) and (body := self.fetcher(js_url)):
                        bodies.append((js_url, body))
            for path in PROBE_PATHS:
                url = urljoin(base, path)
                body = self.fetcher(url)
                if not body or body.lstrip().lower().startswith(("<!doctype", "<html")):
                    continue  # SPA fallback page, not a real file
                if path == "/.env" and not ENV_LINE_RE.search(body):
                    continue
                results.append(
                    ReconAssetResult(
                        AssetType.SECRET, path, url, {"rule": "exposed_config", "exposed": True}
                    )
                )
                bodies.append((url, body))
            for src_url, body in bodies:
                results.extend(self.scan_text(body, src_url))
        return results
