from __future__ import annotations

import json
from collections.abc import Iterable

from app.core.config import get_settings
from app.recon.base import AssetType, ReconAssetResult, ReconTool
from app.recon.runner import CommandRunner, SubprocessRunner


class HttpxTool(ReconTool):
    """HTTP probing via ProjectDiscovery httpx (binary `pd-httpx` by default)."""

    name = "httpx"

    def __init__(self, runner: CommandRunner | None = None, binary: str | None = None):
        settings = get_settings()
        self.runner = runner or SubprocessRunner(settings.recon_tool_timeout)
        self.binary = binary or settings.httpx_bin

    def run(self, targets: Iterable[str]) -> list[ReconAssetResult]:
        targets = list(targets)
        if not targets:
            return []
        out = self.runner.run(
            [self.binary, "-silent", "-json", "-status-code", "-title", "-tech-detect"],
            stdin="\n".join(targets) + "\n",
        )
        results: dict[str, ReconAssetResult] = {}
        for line in out.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            url = row.get("url") or row.get("input")
            if not url or url in results:
                continue
            results[url] = ReconAssetResult(
                AssetType.HOST,
                url,
                self.name,
                {
                    "input": row.get("input"),
                    "status_code": row.get("status_code"),
                    "title": row.get("title"),
                    "tech": row.get("tech") or [],
                },
            )
        return list(results.values())
