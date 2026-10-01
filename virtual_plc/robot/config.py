"""Virtual<->Real Robot Interface switch -- explicit configuration only,
never automatic (safety requirement agreed with the user). Defaults to the
virtual robot; switching to the real myCobot 280 Pi requires BOTH
ROBOT_MODE=real and MYCOBOT_HOST to be set, or it fails loudly instead of
silently falling back.
"""

from __future__ import annotations

import os

from .interface import RobotInterface, VirtualRobotInterface

DEFAULT_PORT = 9000
DEFAULT_MAX_SPEED = 30  # conservative cap on real hardware; raise only after real-world testing


def create_robot_interface() -> RobotInterface:
    mode = os.environ.get("ROBOT_MODE", "virtual").strip().lower()

    if mode == "virtual":
        return VirtualRobotInterface()

    if mode == "real":
        host = os.environ.get("MYCOBOT_HOST")
        if not host:
            raise RuntimeError("ROBOT_MODE=real requires MYCOBOT_HOST to be set (e.g. the Pi's IP address)")
        port = int(os.environ.get("MYCOBOT_PORT", str(DEFAULT_PORT)))
        max_speed = int(os.environ.get("MYCOBOT_MAX_SPEED", str(DEFAULT_MAX_SPEED)))

        from .real_interface import RealMycobotInterface

        return RealMycobotInterface(host, port, max_speed)

    raise RuntimeError(f"Unknown ROBOT_MODE: {mode!r} (expected 'virtual' or 'real')")
