"""Connection State: Backend<->Virtual PLC OPC UA session health. Kept
separate from Robot/Sequence state (docs/architecture.md section 1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class ConnectionStateModel:
    connected: bool = False
    last_seen: datetime | None = None

    def mark_seen(self) -> None:
        self.connected = True
        self.last_seen = datetime.now(timezone.utc)

    def mark_disconnected(self) -> None:
        self.connected = False
