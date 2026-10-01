"""Loads Backend's deployment configuration. YAML (backend.yaml, next to
this file) is the readable source of truth; the matching environment
variable, when set, overrides a single field.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from ..constants.opcua import DEFAULT_OPCUA_ENDPOINT
from ..models.config import BackendConfig

_CONFIGS_DIR = Path(__file__).parent


def load_backend_config() -> BackendConfig:
    data = yaml.safe_load((_CONFIGS_DIR / "backend.yaml").read_text()) or {}
    return BackendConfig(
        opcua_endpoint=os.environ.get(
            "OPCUA_ENDPOINT", str(data.get("opcua_endpoint", DEFAULT_OPCUA_ENDPOINT))
        ),
        host=os.environ.get("BACKEND_HOST", str(data.get("host", "0.0.0.0"))),
        port=int(os.environ.get("BACKEND_PORT", data.get("port", 8000))),
    )
