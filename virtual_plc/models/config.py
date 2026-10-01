"""Deployment configuration data -- what configs/config.py loads from YAML
(configs/robot.yaml, configs/plc.yaml), with environment variables as
optional overrides."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RobotConfig:
    mode: str
    host: str
    port: int
    max_speed: int


@dataclass
class PlcConfig:
    scan_period_seconds: float
    opcua_endpoint: str
