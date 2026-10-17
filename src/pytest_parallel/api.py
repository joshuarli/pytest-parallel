from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Shard:
    files: tuple[Path, ...]
    nodeids: tuple[str, ...]
    weight: float
    groups: tuple[str, ...]
    ordinal: int


__all__ = ["Shard"]
