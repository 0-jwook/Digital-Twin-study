"""Per-tick PLC scan orchestration: wires Command Processor, State Machine,
Sequence Manager and Robot Interface together, per docs/architecture.md
section 4 (Virtual PLC scan cycle). Pure w.r.t. OPC UA -- takes/returns plain
objects, so it is unit-testable without a running OPC UA server.
"""

from __future__ import annotations

from .command_processor import CommandKind, process as process_command
from .memory import PLCMemory
from .state_machine import TickEvents, transition
from .status import Status
from ..robot.interface import RobotInterface
from ..robot.state import RobotState
from ..sequence import manager as sequence_manager


def run_scan_tick(
    memory: PLCMemory,
    robot: RobotInterface,
    robot_state: RobotState,
    tick_events: TickEvents,
) -> TickEvents:
    current_status = Status(memory.state.status)

    event = process_command(memory, current_status)

    if event is not None and event.kind is CommandKind.EXECUTE:
        tick_events.sequence_unknown = not sequence_manager.exists(event.sequence_id)

    new_status, effects = transition(current_status, event, tick_events)

    if effects.load_sequence_id is not None:
        sequence_manager.start(memory, effects.load_sequence_id, robot)
    if effects.clear_sequence:
        memory.sequence.current_sequence_id = -1
        memory.sequence.current_step = 0
        memory.sequence.total_steps = 0
        memory.sequence.stop_requested = False
        memory.state.error_code = 0
        memory.state.error_message = ""
    if effects.set_done:
        memory.sequence.done = True
    if effects.set_busy is not None:
        memory.command.busy = effects.set_busy
    if effects.error is not None:
        code, message = effects.error
        memory.state.error_code = int(code)
        memory.state.error_message = message
    if new_status is Status.STOPPING and current_status is Status.RUNNING:
        memory.sequence.stop_requested = True

    memory.state.status = int(new_status)
    memory.sequence.running = new_status in (Status.RUNNING, Status.STOPPING)

    if new_status in (Status.RUNNING, Status.STOPPING):
        next_tick_events = sequence_manager.tick(memory, robot)
    else:
        next_tick_events = TickEvents()

    robot_state.refresh(robot)
    memory.position.j1 = robot_state.j1
    memory.position.j2 = robot_state.j2
    memory.position.j3 = robot_state.j3
    memory.position.j4 = robot_state.j4
    memory.position.j5 = robot_state.j5
    memory.position.j6 = robot_state.j6
    memory.state.robot_connected = robot.is_connected()

    return next_tick_events
