"""Shared PLC status / error code enums -- see docs/opcua-nodes.md."""

from __future__ import annotations

from enum import IntEnum


class Status(IntEnum):
    IDLE = 0
    RUNNING = 1
    STOPPING = 2
    STOPPED = 3
    ERROR = 4


class ErrorCode(IntEnum):
    NONE = 0
    UNKNOWN_SEQUENCE = 100
    ROBOT_DISCONNECTED = 200
    JOINT_OUT_OF_RANGE = 201
    INTERNAL = 900
