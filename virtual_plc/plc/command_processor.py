"""Command Processor: detects Execute/Stop/Reset rising edges and drives the
4-phase Ack/Busy handshake described in docs/opcua-nodes.md. Pure function
over PLC Memory -- no OPC UA, no robot code, no knowledge of Sequences.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from .memory import PLCMemory
from .status import Status


class CommandKind(Enum):
    EXECUTE = auto()
    STOP = auto()
    RESET = auto()


@dataclass
class CommandEvent:
    kind: CommandKind
    sequence_id: int | None = None


def process(memory: PLCMemory, current_status: Status) -> CommandEvent | None:
    cmd = memory.command
    event: CommandEvent | None = None

    if not cmd.ack:
        if cmd.execute and not cmd.prev_execute:
            cmd.ack = True
            if current_status is Status.IDLE:
                event = CommandEvent(CommandKind.EXECUTE, sequence_id=cmd.sequence_id)
        elif cmd.stop and not cmd.prev_stop:
            cmd.ack = True
            if current_status is Status.RUNNING:
                event = CommandEvent(CommandKind.STOP)
        elif cmd.reset and not cmd.prev_reset:
            cmd.ack = True
            if current_status in (Status.STOPPED, Status.ERROR):
                event = CommandEvent(CommandKind.RESET)
    elif not (cmd.execute or cmd.stop or cmd.reset):
        # Backend observed Ack and cleared its trigger -- release Ack.
        # Only one trigger is ever held at a time (the 3 channels share this
        # one Ack/Busy pair), so "all three false" is equivalent to "the
        # pending trigger was cleared".
        cmd.ack = False

    cmd.prev_execute = cmd.execute
    cmd.prev_stop = cmd.stop
    cmd.prev_reset = cmd.reset

    return event
