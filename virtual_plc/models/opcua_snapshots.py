"""Plain data snapshots passed between the OPC UA Server layer
(opcua/server.py) and the PLC scan loop -- a snapshot in, a snapshot out,
never raw OPC UA nodes beyond that boundary.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CommandSnapshot:
    sequence_id: int
    execute: bool
    stop: bool
    reset: bool


@dataclass
class StateSnapshot:
    status: int
    error_code: int
    error_message: str
    robot_connected: bool
    current_sequence_id: int
    current_step: int
    total_steps: int
    running: bool
    done: bool
    position: dict[str, float]
    ack: bool
    busy: bool
    config_ack: bool
    config_active_mode: str
    config_connection_ok: bool
    config_error_message: str


@dataclass
class ConfigCommandSnapshot:
    mode: str
    host: str
    port: int
    max_speed: int
    apply: bool
