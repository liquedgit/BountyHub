import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ReconResult:
    asset_type: str  # subdomain | host | endpoint | secret
    value: str
    source: str
    meta: dict = field(default_factory=dict)


class ToolError(Exception):
    pass


class CommandRunner(Protocol):
    async def run(
        self, argv: list[str], stdin: str | None = None, timeout: float = 600
    ) -> str: ...


class SubprocessRunner:
    """The only place subprocesses are spawned (argv list, never a shell)."""

    async def run(self, argv: list[str], stdin: str | None = None, timeout: float = 600) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await asyncio.wait_for(
                proc.communicate(stdin.encode() if stdin is not None else None), timeout
            )
        except FileNotFoundError as exc:
            raise ToolError(f"{argv[0]} is not installed") from exc
        except asyncio.TimeoutError as exc:
            proc.kill()
            raise ToolError(f"{argv[0]} timed out after {timeout}s") from exc
        if proc.returncode != 0:
            raise ToolError(f"{argv[0]} exited {proc.returncode}: {err.decode(errors='replace')[:500]}")
        return out.decode(errors="replace")


class ReconTool(ABC):
    """Common adapter interface. Callers must pass only scope-validated targets."""

    name: str

    def __init__(self, runner: CommandRunner | None = None):
        self.runner: CommandRunner = runner or SubprocessRunner()

    @abstractmethod
    async def run(self, targets: list[str]) -> list[ReconResult]: ...
