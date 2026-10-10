from __future__ import annotations

import json
import re
from collections.abc import Iterable

from app.core.config import get_settings
from app.recon.base import AssetType, ReconAssetResult, ReconTool
from app.recon.runner import CommandRunner, SubprocessRunner

HOST_RE = re.compile(r"^[a-z0-9_*]([a-z0-9_.-]*[a-z0-9_])?$")


def _parse_line(line: str) -> str | None:
    line = line.strip()
    if not line:
        return None
    if line.startswith("{"):
        try:
            line = str(json.loads(line).get("host", ""))
        except (json.JSONDecodeError, AttributeError):
            return None
    host = line.strip().lower().rstrip(".")
    return host if HOST_RE.match(host) else None


class SubfinderTool(ReconTool):
    """Passive subdomain enumeration via ProjectDiscovery subfinder."""

    name = "subfinder"

    def __init__(self, runner: CommandRunner | None = None, binary: str | None = None):
        settings = get_settings()
        self.runner = runner or SubprocessRunner(settings.recon_tool_timeout)
        self.binary = binary or settings.subfinder_bin

    def run(self, targets: Iterable[str]) -> list[ReconAssetResult]:
        results: dict[str, ReconAssetResult] = {}
        for target in targets:
            out = self.runner.run([self.binary, "-silent", "-d", target])
            for line in out.splitlines():
                host = _parse_line(line)
                if host and host not in results:
                    results[host] = ReconAssetResult(
                        AssetType.SUBDOMAIN, host, self.name, {"input": target}
                    )
        return list(results.values())
