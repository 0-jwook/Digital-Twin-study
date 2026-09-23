"""Typed WebSocket message builders, matching docs/protocol.md section 2
exactly (field names, and which fields are top-level vs nested)."""

from __future__ import annotations

import time

from ..state.connection_state import ConnectionStateModel
from ..state.robot_state import RobotStateModel
from ..state.sequence_state import SequenceStateModel


def _plc_state_fields(robot_state: RobotStateModel) -> dict:
    return {
        "status": robot_state.status_name,
        "errorCode": robot_state.error_code,
        "errorMessage": robot_state.error_message or None,
        "robotConnected": robot_state.robot_connected,
    }


def _sequence_state_fields(sequence_state: SequenceStateModel) -> dict:
    return {
        "sequenceId": sequence_state.sequence_id,
        "currentStep": sequence_state.current_step,
        "totalSteps": sequence_state.total_steps,
        "running": sequence_state.running,
        "done": sequence_state.done,
    }


def _connection_fields(connection_state: ConnectionStateModel) -> dict:
    return {
        "connected": connection_state.connected,
        "lastSeen": connection_state.last_seen.isoformat() if connection_state.last_seen else None,
    }


def position_message(robot_state: RobotStateModel) -> dict:
    return {"type": "position", **robot_state.position, "t": int(time.time() * 1000)}


def plc_state_message(robot_state: RobotStateModel) -> dict:
    return {"type": "plc_state", **_plc_state_fields(robot_state)}


def sequence_state_message(sequence_state: SequenceStateModel) -> dict:
    return {"type": "sequence_state", **_sequence_state_fields(sequence_state)}


def connection_status_message(connection_state: ConnectionStateModel) -> dict:
    return {"type": "connection_status", **_connection_fields(connection_state)}


def full_status_message(
    robot_state: RobotStateModel,
    sequence_state: SequenceStateModel,
    connection_state: ConnectionStateModel,
) -> dict:
    return {
        "type": "full_status",
        "plc": _plc_state_fields(robot_state),
        "sequence": _sequence_state_fields(sequence_state),
        "position": dict(robot_state.position),
        "connection": _connection_fields(connection_state),
    }
