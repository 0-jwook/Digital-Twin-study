from fakes import FakeRobotInterface

from virtual_plc.plc.memory import PLCMemory
from virtual_plc.plc.state_machine import TickEvents
from virtual_plc.sequence import manager as sequence_manager


def test_exists():
    assert sequence_manager.exists(1) is True
    assert sequence_manager.exists(9999) is False


def test_start_commands_first_step(fake_robot):
    memory = PLCMemory()
    sequence_manager.start(memory, 2, fake_robot)  # "home" has 1 step

    assert memory.sequence.current_sequence_id == 2
    assert memory.sequence.current_step == 0
    assert memory.sequence.total_steps == 1
    assert len(fake_robot.move_calls) == 1


def test_tick_advances_step_when_target_reached(fake_robot):
    memory = PLCMemory()
    sequence_manager.start(memory, 1, fake_robot)  # pick_and_place has 7 steps

    events = sequence_manager.tick(memory, fake_robot)  # fake robot is instantly at target

    assert memory.sequence.current_step == 1
    assert events.sequence_finished is False
    assert len(fake_robot.move_calls) == 2  # step0 (from start) + step1 (from tick)


def test_tick_reports_finished_on_last_step(fake_robot):
    memory = PLCMemory()
    sequence_manager.start(memory, 2, fake_robot)  # "home" has 1 step (index 0 = last)

    events = sequence_manager.tick(memory, fake_robot)

    assert events.sequence_finished is True


def test_tick_finishes_current_step_before_honoring_stop():
    robot = FakeRobotInterface(ticks_to_target=2)
    memory = PLCMemory()
    sequence_manager.start(memory, 1, robot)
    memory.sequence.stop_requested = True

    events = sequence_manager.tick(memory, robot)  # 1st poll: still moving
    assert events == TickEvents()
    assert memory.sequence.current_step == 0
    assert memory.sequence.stop_requested is True

    events = sequence_manager.tick(memory, robot)  # 2nd poll: still moving
    assert events == TickEvents()
    assert memory.sequence.current_step == 0

    events = sequence_manager.tick(memory, robot)  # 3rd poll: target reached
    assert events.stop_boundary_reached is True
    assert memory.sequence.current_step == 0  # did not advance to the next step
    assert memory.sequence.stop_requested is False
