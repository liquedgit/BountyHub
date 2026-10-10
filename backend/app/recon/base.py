from __future__ import annotations

import abc
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class AssetType(StrEnum):
    SUBDOMAIN = "subdomain"
    HOST = "host"
    ENDPOINT = "endpoint"
    SECRET = "secret"


@dataclass(frozen=True)
class ReconAssetResult:
    """Typed result destined for the `recon_assets` table."""

    type: AssetType
    value: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)


# Fetches a URL and returns its text body, or None if unavailable.
Fetcher = Callable[[str], "str | None"]


class OutOfScopeError(Exception):
    def __init__(self, target: str):
        super().__init__(f"target out of scope: {target}")
        self.target = target


class ReconTool(abc.ABC):
    name: str

    @abc.abstractmethod
    def run(self, targets: Iterable[str]) -> list[ReconAssetResult]:
        """Run the tool against targets; out-of-scope targets are never touched."""
