"""Virtual<->Real Robot Interface switch -- explicit configuration only,
never automatic (safety requirement agreed with the user). Defaults to the
virtual robot; switching to the real myCobot 280 Pi requires BOTH a "real"
mode and a host to be set, or it fails loudly instead of silently falling
back.

Two ways to reach that configuration:
- At process startup: from environment variables (`read_env_config` /
  `create_robot_interface`), same as before.
- At runtime, from the Web (Phase 8): `build_robot_interface` is the same
  construction logic, called by `plc/config_processor.py`'s Apply handshake
  with whatever Robot.Config.* values Backend wrote over OPC UA.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .interface import RobotInterface, VirtualRobotInterface

DEFAULT_PORT = 9000
DEFAULT_MAX_SPEED = 30  # conservative cap on real hardware; raise only after real-world testing


@dataclass
class RobotConfig:
    mode: str
    host: str
    port: int
    max_speed: int


def read_env_config() -> RobotConfig:
    return RobotConfig(
        mode=os.environ.get("ROBOT_MODE", "virtual").strip().lower(),
        host=os.environ.get("MYCOBOT_HOST", ""),
        port=int(os.environ.get("MYCOBOT_PORT", str(DEFAULT_PORT))),
        max_speed=int(os.environ.get("MYCOBOT_MAX_SPEED", str(DEFAULT_MAX_SPEED))),
    )


def build_robot_interface(mode: str, host: str, port: int, max_speed: int) -> RobotInterface:
    mode = mode.strip().lower()

    if mode == "virtual":
        return VirtualRobotInterface()

    if mode == "real":
        if not host:
            raise RuntimeError("mode='real' requires a host (e.g. the Pi's IP address)")

        from .real_interface import RealMycobotInterface

        return RealMycobotInterface(host, port, max_speed)

    raise RuntimeError(f"Unknown robot mode: {mode!r} (expected 'virtual' or 'real')")


def create_robot_interface() -> RobotInterface:
    cfg = read_env_config()
    if cfg.mode == "real" and not cfg.host:
        raise RuntimeError("ROBOT_MODE=real requires MYCOBOT_HOST to be set (e.g. the Pi's IP address)")
    try:
        return build_robot_interface(cfg.mode, cfg.host, cfg.port, cfg.max_speed)
    except RuntimeError as exc:
        if cfg.mode not in ("virtual", "real"):
            raise RuntimeError(f"Unknown ROBOT_MODE: {cfg.mode!r} (expected 'virtual' or 'real')") from exc
        raise
