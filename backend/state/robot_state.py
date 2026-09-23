"""Robot State: PLC status/error/position, mirrored from OPC UA subscription
notifications. Kept separate from Sequence/Connection state
(docs/architecture.md section 1)."""

from __future__ import annotations

from dataclasses import dataclass, field

STATUS_NAMES = {0: "IDLE", 1: "RUNNING", 2: "STOPPING", 3: "STOPPED", 4: "ERROR"}


@dataclass
class RobotStateModel:
    status: int = 0
    error_code: int = 0
    error_message: str = ""
    robot_connected: bool = True
    position: dict[str, float] = field(
        default_factory=lambda: {f"j{i}": 0.0 for i in range(1, 7)}
    )

    @property
    def status_name(self) -> str:
        return STATUS_NAMES.get(self.status, "UNKNOWN")
