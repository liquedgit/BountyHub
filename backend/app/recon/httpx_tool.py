import json

from app.recon.base import ReconResult, ReconTool


class HttpxTool(ReconTool):
    name = "httpx"

    def __init__(self, runner=None, binary: str = "httpx"):
        super().__init__(runner)
        self.binary = binary

    async def run(self, targets: list[str]) -> list[ReconResult]:
        if not targets:
            return []
        out = await self.runner.run(
            [self.binary, "-silent", "-json", "-status-code", "-title", "-tech-detect", "-web-server"],
            stdin="\n".join(targets) + "\n",
        )
        results: list[ReconResult] = []
        for line in out.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            url = row.get("url") or row.get("input")
            if not url:
                continue
            results.append(
                ReconResult(
                    "host",
                    url,
                    self.name,
                    {
                        "input": row.get("input"),
                        "status_code": row.get("status_code"),
                        "title": row.get("title"),
                        "tech": row.get("tech") or [],
                        "webserver": row.get("webserver"),
                    },
                )
            )
        return results
