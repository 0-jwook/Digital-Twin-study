"""Loads Virtual PLC's deployment configuration. YAML (robot.yaml, plc.yaml,
next to this file) is the readable source of truth; the matching
environment variable, when set, overrides a single field -- useful for
Docker/deployment without editing the checked-in YAML. Values themselves
live only in the YAML files + models/config.py's types, never hardcoded
here.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from ..constants.opcua import DEFAULT_ENDPOINT
from ..constants.plc import DEFAULT_SCAN_PERIOD_SECONDS
from ..constants.robot import DEFAULT_MAX_SPEED, DEFAULT_PORT
from ..models.config import PlcConfig, RobotConfig

_CONFIGS_DIR = Path(__file__).parent


def _load_yaml(filename: str) -> dict:
    return yaml.safe_load((_CONFIGS_DIR / filename).read_text()) or {}


def load_robot_config() -> RobotConfig:
    data = _load_yaml("robot.yaml")
    return RobotConfig(
        mode=os.environ.get("ROBOT_MODE", str(data.get("mode", "virtual"))).strip().lower(),
        host=os.environ.get("MYCOBOT_HOST", str(data.get("host", ""))),
        port=int(os.environ.get("MYCOBOT_PORT", data.get("port", DEFAULT_PORT))),
        max_speed=int(os.environ.get("MYCOBOT_MAX_SPEED", data.get("max_speed", DEFAULT_MAX_SPEED))),
    )


def load_plc_config() -> PlcConfig:
    data = _load_yaml("plc.yaml")
    return PlcConfig(
        scan_period_seconds=float(
            os.environ.get("SCAN_PERIOD_SECONDS", data.get("scan_period_seconds", DEFAULT_SCAN_PERIOD_SECONDS))
        ),
        opcua_endpoint=os.environ.get("OPCUA_ENDPOINT", str(data.get("opcua_endpoint", DEFAULT_ENDPOINT))),
    )
