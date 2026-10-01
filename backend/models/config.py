"""Deployment configuration data -- what configs/config.py loads from YAML
(configs/backend.yaml), with environment variables as optional overrides."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BackendConfig:
    opcua_endpoint: str
    host: str
    port: int
