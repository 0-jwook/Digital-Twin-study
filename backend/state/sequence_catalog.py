"""Read-through cache over Robot.Sequence.CatalogJson (docs/architecture.md
section 5). The PLC remains the sole authority for sequence content -- this
is a performance shim only (~5s TTL to avoid re-parsing on rapid UI
refreshes)."""

from __future__ import annotations

import json
import time
from typing import Any, Protocol


class _CatalogReader(Protocol):
    async def read(self, path: str) -> Any: ...


class SequenceCatalog:
    def __init__(self, client: _CatalogReader, ttl_seconds: float = 5.0) -> None:
        self._client = client
        self._ttl = ttl_seconds
        self._cached_at = 0.0
        self._sequences: list[dict] = []

    async def get_all(self) -> list[dict]:
        now = time.monotonic()
        if now - self._cached_at > self._ttl:
            raw = await self._client.read("Robot.Sequence.CatalogJson")
            self._sequences = json.loads(raw)
            self._cached_at = now
        return self._sequences

    async def get(self, sequence_id: int) -> dict | None:
        for seq in await self.get_all():
            if seq["sequenceId"] == sequence_id:
                return seq
        return None

    def invalidate(self) -> None:
        self._cached_at = 0.0
