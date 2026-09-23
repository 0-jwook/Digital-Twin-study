from fakes import FakeRobotInterface

from virtual_plc.plc.memory import PLCMemory
from virtual_plc.plc.scan import run_scan_tick
from virtual_plc.plc.state_machine import TickEvents
from virtual_plc.plc.status import Status
from virtual_plc.robot.state import RobotState


def test_execute_runs_sequence_to_completion(fake_robot):
    memory = PLCMemory()
    robot_state = RobotState()
    tick_events = TickEvents()

    memory.command.sequence_id = 2  # "home", 1 step
    memory.command.execute = True
    tick_events = run_scan_tick(memory, fake_robot, robot_state, tick_events)

    assert memory.state.status == Status.RUNNING
    assert memory.command.ack is True
    assert memory.command.busy is True

    memory.command.execute = False  # backend clears trigger after seeing Ack
    tick_events = run_scan_tick(memory, fake_robot, robot_state, tick_events)

    assert memory.state.status == Status.IDLE
    assert memory.sequence.done is True
    assert memory.command.busy is False
    assert memory.command.ack is False


def test_execute_with_unknown_sequence_goes_error(fake_robot):
    memory = PLCMemory()
    robot_state = RobotState()
    tick_events = TickEvents()

    memory.command.sequence_id = 999
    memory.command.execute = True
    run_scan_tick(memory, fake_robot, robot_state, tick_events)

    assert memory.state.status == Status.ERROR
    assert memory.state.error_code == 100


def test_stop_finishes_current_step_before_stopping():
    robot = FakeRobotInterface(ticks_to_target=2)
    memory = PLCMemory()
    robot_state = RobotState()
    tick_events = TickEvents()

    memory.command.sequence_id = 1  # pick_and_place, 7 steps
    memory.command.execute = True
    tick_events = run_scan_tick(memory, robot, robot_state, tick_events)
    memory.command.execute = False

    tick_events = run_scan_tick(memory, robot, robot_state, tick_events)  # let Ack clear
    assert memory.command.ack is False

    memory.command.stop = True
    tick_events = run_scan_tick(memory, robot, robot_state, tick_events)
    memory.command.stop = False
    assert memory.state.status == Status.STOPPING

    step_when_stop_requested = memory.sequence.current_step

    for _ in range(10):
        if memory.state.status == Status.STOPPED:
            break
        tick_events = run_scan_tick(memory, robot, robot_state, tick_events)

    assert memory.state.status == Status.STOPPED
    assert memory.sequence.current_step == step_when_stop_requested


def test_reset_from_stopped_clears_sequence_and_returns_idle(fake_robot):
    memory = PLCMemory()
    memory.state.status = int(Status.STOPPED)
    memory.sequence.current_sequence_id = 1
    memory.sequence.current_step = 3
    memory.sequence.total_steps = 7
    robot_state = RobotState()
    tick_events = TickEvents()

    memory.command.reset = True
    run_scan_tick(memory, fake_robot, robot_state, tick_events)

    assert memory.state.status == Status.IDLE
    assert memory.sequence.current_sequence_id == -1
    assert memory.sequence.current_step == 0
    assert memory.sequence.total_steps == 0
