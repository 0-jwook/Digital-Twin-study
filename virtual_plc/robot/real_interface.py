"""Real myCobot 280 Pi implementation of RobotInterface, over the TCP socket
API (`pymycobot.MyCobot280Socket`) -- not a local serial connection.

The Pi's own onboard Raspberry Pi runs Elephant Robotics' `Server_280.py`,
which owns the physical serial link to the arm's controller
(`/dev/ttyAMA0`, 1,000,000 baud) and exposes it over TCP (default port
9000). That means this process does NOT need to run on the Pi itself --
`virtual_plc` keeps running wherever it already does and just connects to
the Pi's `Server_280.py` over the network, exactly like `VirtualRobotInterface`
is just swapped for this one.

Verified against Elephant Robotics' official docs/GitHub, not against real
hardware (none was available while writing this) -- see docs/architecture.md
section 4 for the exact sources. Treat the first real run as the real test.
"""

from __future__ import annotations

from .interface import JOINTS


class RealMycobotInterface:
    def __init__(self, host: str, port: int = 9000, max_speed: int = 30) -> None:
        self._host = host
        self._port = port
        self._max_speed = max_speed  # safety cap: a Sequence can never command faster than this
        self._mc = None
        self._connected = False
        self._last_target: dict[str, float] | None = None
        self._last_known_pose = {j: 0.0 for j in JOINTS}

    def connect(self) -> bool:
        try:
            # Imported here (not at module level) so "virtual" mode never
            # needs pymycobot installed -- and inside the try, not before
            # it, since a missing pymycobot install must degrade to
            # is_connected()=False like any other comms failure, not crash
            # the whole scan loop.
            from pymycobot import MyCobot280Socket

            self._mc = MyCobot280Socket(self._host, self._port)
            self._mc.get_angles()  # one round trip to confirm Server_280.py is actually reachable
            self._connected = True
        except Exception:
            self._connected = False
        return self._connected

    def is_connected(self) -> bool:
        return self._connected

    def move_to(self, joint_targets: dict[str, float], speed: float) -> None:
        clamped_speed = min(speed, self._max_speed)
        angles = [joint_targets.get(j, self._last_known_pose[j]) for j in JOINTS]
        try:
            self._mc.send_angles(angles, int(clamped_speed))
            self._last_target = dict(joint_targets)
            self._connected = True
        except Exception:
            self._connected = False

    def get_current_position(self) -> dict[str, float]:
        try:
            angles = self._mc.get_angles()
            self._last_known_pose = dict(zip(JOINTS, angles))
            self._connected = True
        except Exception:
            self._connected = False
        return dict(self._last_known_pose)

    def is_at_target(self) -> bool:
        if self._last_target is None:
            return True
        try:
            # is_in_position() checks real position feedback against a target
            # (flag 0 = angles), unlike is_moving() -- which pymycobot has a
            # known reliability issue with (always returns "moving").
            target = [self._last_target[j] for j in JOINTS]
            at_target = bool(self._mc.is_in_position(target, 0))
            self._connected = True
            return at_target
        except Exception:
            self._connected = False
            return False  # can't confirm arrival -- treat as "not yet", not "done"

    def stop(self) -> None:
        try:
            self._mc.stop()
        except Exception:
            pass
