import json

from app.recon.base import ReconResult, ReconTool
from app.recon.scope import normalize_host


class SubfinderTool(ReconTool):
    name = "subfinder"

    def __init__(self, runner=None, binary: str = "subfinder"):
        super().__init__(runner)
        self.binary = binary

    async def run(self, targets: list[str]) -> list[ReconResult]:
        results: dict[str, ReconResult] = {}
        for target in targets:
            out = await self.runner.run([self.binary, "-silent", "-json", "-d", normalize_host(target)])
            for line in out.splitlines():
                host = self._parse_line(line)
                if host and host not in results:
                    results[host] = ReconResult("subdomain", host, self.name, {"input": target})
        return list(results.values())

    @staticmethod
    def _parse_line(line: str) -> str | None:
        line = line.strip()
        if not line:
            return None
        if line.startswith("{"):
            try:
                host = json.loads(line).get("host", "")
            except json.JSONDecodeError:
                return None
        else:
            host = line
        return normalize_host(host) or None
