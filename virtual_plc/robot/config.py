"""Virtual<->Real Robot Interface switch -- explicit configuration only,
never automatic (safety requirement agreed with the user). Defaults to the
virtual robot; switching to the real myCobot 280 Pi requires BOTH a "real"
mode and a host to be set, or it fails loudly instead of silently falling
back.

Two ways to reach that configuration:
- At process startup: from configs/robot.yaml, env vars optionally
  overriding a field (`configs/config.py:load_robot_config()`, used by
  `create_robot_interface` below).
- At runtime, from the Web: `build_robot_interface` is the same
  construction logic, called by `plc/config_processor.py`'s Apply handshake
  with whatever Robot.Config.* values Backend wrote over OPC UA.
"""

from __future__ import annotations

from .interface import RobotInterface, VirtualRobotInterface


def build_robot_interface(mode: str, host: str, port: int, max_speed: int) -> RobotInterface:
    mode = mode.strip().lower()

    if mode == "virtual":
        return VirtualRobotInterface()

    if mode == "real":
        if not host:
            raise RuntimeError(
                "mode='real' requires a host -- set MYCOBOT_HOST or configs/robot.yaml's host"
            )

        from .real_interface import RealMycobotInterface

        return RealMycobotInterface(host, port, max_speed)

    raise RuntimeError(f"Unknown robot mode: {mode!r} (expected 'virtual' or 'real')")


def create_robot_interface() -> RobotInterface:
    from ..configs.config import load_robot_config

    cfg = load_robot_config()
    if cfg.mode == "real" and not cfg.host:
        raise RuntimeError("ROBOT_MODE=real requires MYCOBOT_HOST to be set (e.g. the Pi's IP address)")
    try:
        return build_robot_interface(cfg.mode, cfg.host, cfg.port, cfg.max_speed)
    except RuntimeError as exc:
        if cfg.mode not in ("virtual", "real"):
            raise RuntimeError(f"Unknown ROBOT_MODE: {cfg.mode!r} (expected 'virtual' or 'real')") from exc
        raise
