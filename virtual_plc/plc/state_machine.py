"""PLC state machine: implements the transition table in docs/architecture.md
section 3. Pure function, no OPC UA/robot dependencies -- independently unit
testable.
"""

from __future__ import annotations

from dataclasses import dataclass

from .command_processor import CommandEvent, CommandKind
from .status import ErrorCode, Status


@dataclass
class SideEffects:
    load_sequence_id: int | None = None
    clear_sequence: bool = False
    set_done: bool = False
    set_busy: bool | None = None
    error: tuple[ErrorCode, str] | None = None


@dataclass
class TickEvents:
    """Signals produced by the Sequence Manager's *previous* tick, consumed
    by this tick's transition() call. The scan cycle runs the State Machine
    before the Sequence Manager each tick, so these are always one tick
    (50ms) delayed -- imperceptible for this MVP."""

    sequence_unknown: bool = False
    sequence_finished: bool = False
    stop_boundary_reached: bool = False
    fault: tuple[ErrorCode, str] | None = None


def transition(
    current: Status,
    command_event: CommandEvent | None,
    tick_events: TickEvents,
) -> tuple[Status, SideEffects]:
    effects = SideEffects()

    if tick_events.fault is not None and current in (Status.RUNNING, Status.STOPPING):
        effects.error = tick_events.fault
        effects.set_busy = False
        return Status.ERROR, effects

    if command_event is not None:
        if command_event.kind is CommandKind.EXECUTE and current is Status.IDLE:
            if tick_events.sequence_unknown:
                effects.error = (
                    ErrorCode.UNKNOWN_SEQUENCE,
                    f"Unknown sequenceId {command_event.sequence_id}",
                )
                effects.set_busy = False
                return Status.ERROR, effects
            effects.load_sequence_id = command_event.sequence_id
            effects.set_busy = True
            return Status.RUNNING, effects

        if command_event.kind is CommandKind.STOP and current is Status.RUNNING:
            return Status.STOPPING, effects

        if command_event.kind is CommandKind.RESET and current in (Status.STOPPED, Status.ERROR):
            effects.clear_sequence = True
            effects.set_busy = False
            return Status.IDLE, effects

        # Precondition not met for the current status -- already Acked by
        # the Command Processor, no state change. Covers, explicitly:
        # Execute while RUNNING/STOPPING/STOPPED/ERROR, Stop while not
        # RUNNING, Reset while IDLE/RUNNING/STOPPING.
        return current, effects

    if current is Status.STOPPING and tick_events.stop_boundary_reached:
        effects.set_busy = False
        return Status.STOPPED, effects

    if current is Status.RUNNING and tick_events.sequence_finished:
        effects.set_done = True
        effects.set_busy = False
        return Status.IDLE, effects

    return current, effects
