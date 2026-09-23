"""Robot Interface: the swappable abstraction between PLC logic and the
actual robot (docs/architecture.md section 4). MVP ships only the virtual,
time-based interpolator; a real myCobot implementation (pymycobot-based) is
a future drop-in replacement -- plc/ and sequence/ never change for it.
"""

from __future__ import annotations

import time
from typing import Protocol

JOINTS = ("j1", "j2", "j3", "j4", "j5", "j6")


class RobotInterface(Protocol):
    def connect(self) -> bool: ...
    def move_to(self, joint_targets: dict[str, float], speed: float) -> None: ...
    def get_current_position(self) -> dict[str, float]: ...
    def is_at_target(self) -> bool: ...
    def is_connected(self) -> bool: ...
    def stop(self) -> None: ...


class VirtualRobotInterface:
    """Time-based joint interpolation. Degrees throughout (matches
    pymycobot's convention); speed is 0-100%, higher moves faster."""

    MAX_DEG_PER_SEC_AT_FULL_SPEED = 60.0

    def __init__(self) -> None:
        self._pose = {j: 0.0 for j in JOINTS}
        self._start_pose = dict(self._pose)
        self._target_pose = dict(self._pose)
        self._start_time = time.monotonic()
        self._duration = 0.0
        self._connected = True

    def connect(self) -> bool:
        self._connected = True
        return True

    def is_connected(self) -> bool:
        return self._connected

    def move_to(self, joint_targets: dict[str, float], speed: float) -> None:
        self._start_pose = self._interpolate()
        self._target_pose = {**self._start_pose, **joint_targets}
        max_delta = max(abs(self._target_pose[j] - self._start_pose[j]) for j in JOINTS)
        deg_per_sec = self.MAX_DEG_PER_SEC_AT_FULL_SPEED * (max(speed, 1.0) / 100.0)
        self._duration = max_delta / deg_per_sec if deg_per_sec > 0 else 0.0
        self._start_time = time.monotonic()

    def _interpolate(self) -> dict[str, float]:
        if self._duration <= 0:
            return dict(self._target_pose)
        alpha = min(max((time.monotonic() - self._start_time) / self._duration, 0.0), 1.0)
        return {
            j: self._start_pose[j] + (self._target_pose[j] - self._start_pose[j]) * alpha
            for j in JOINTS
        }

    def get_current_position(self) -> dict[str, float]:
        self._pose = self._interpolate()
        return dict(self._pose)

    def is_at_target(self) -> bool:
        if self._duration <= 0:
            return True
        return (time.monotonic() - self._start_time) >= self._duration

    def stop(self) -> None:
        pass  # reserved -- normal Stop flow lets the current move finish
