"""Deterministic test doubles for Virtual PLC unit tests."""

from __future__ import annotations

JOINTS = ("j1", "j2", "j3", "j4", "j5", "j6")


class FakeRobotInterface:
    """`is_at_target()` returns False `ticks_to_target` times, then True and
    snaps to the commanded target -- lets tests control exactly how many
    scan ticks a move takes."""

    def __init__(self, ticks_to_target: int = 0) -> None:
        self.ticks_to_target = ticks_to_target
        self._remaining = 0
        self.position = {j: 0.0 for j in JOINTS}
        self.target = dict(self.position)
        self.connected = True
        self.move_calls: list[tuple[dict[str, float], float]] = []

    def connect(self) -> bool:
        self.connected = True
        return True

    def is_connected(self) -> bool:
        return self.connected

    def move_to(self, joint_targets: dict[str, float], speed: float) -> None:
        self.move_calls.append((dict(joint_targets), speed))
        self.target = {**self.position, **joint_targets}
        self._remaining = self.ticks_to_target

    def get_current_position(self) -> dict[str, float]:
        return dict(self.position)

    def is_at_target(self) -> bool:
        if self._remaining > 0:
            self._remaining -= 1
            return False
        self.position = dict(self.target)
        return True

    def stop(self) -> None:
        pass
