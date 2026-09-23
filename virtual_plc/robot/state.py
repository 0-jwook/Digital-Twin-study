"""Robot State: canonical, once-per-tick-refreshed position cache. Other PLC
modules read this instead of calling the Robot Interface directly for
position, keeping Robot State one of the five distinct state models
(docs/architecture.md section 1)."""

from __future__ import annotations

from dataclasses import dataclass

from .interface import RobotInterface


@dataclass
class RobotState:
    j1: float = 0.0
    j2: float = 0.0
    j3: float = 0.0
    j4: float = 0.0
    j5: float = 0.0
    j6: float = 0.0

    def refresh(self, robot: RobotInterface) -> None:
        pos = robot.get_current_position()
        self.j1, self.j2, self.j3 = pos["j1"], pos["j2"], pos["j3"]
        self.j4, self.j5, self.j6 = pos["j4"], pos["j5"], pos["j6"]
