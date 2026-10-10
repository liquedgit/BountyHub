from __future__ import annotations

import subprocess
from collections.abc import Sequence
from typing import Protocol


class ToolError(Exception):
    """An external recon tool could not be run or failed."""


class CommandRunner(Protocol):
    def run(self, argv: Sequence[str], stdin: str | None = None) -> str:
        """Run argv and return stdout; raise ToolError on any failure."""


class SubprocessRunner:
    """Runs an argv list directly (never through a shell)."""

    def __init__(self, timeout: float = 300):
        self.timeout = timeout

    def run(self, argv: Sequence[str], stdin: str | None = None) -> str:
        try:
            proc = subprocess.run(
                list(argv),
                input=stdin,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                shell=False,
                check=False,
            )
        except FileNotFoundError as exc:
            raise ToolError(f"tool not found: {argv[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ToolError(f"{argv[0]} timed out after {self.timeout}s") from exc
        except OSError as exc:
            raise ToolError(f"failed to execute {argv[0]}: {exc}") from exc
        if proc.returncode != 0:
            detail = (proc.stderr or "").strip()[:500]
            raise ToolError(f"{argv[0]} exited with code {proc.returncode}: {detail}")
        return proc.stdout
