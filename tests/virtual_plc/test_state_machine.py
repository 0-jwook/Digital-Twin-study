import pytest

from virtual_plc.plc.command_processor import CommandEvent, CommandKind
from virtual_plc.plc.state_machine import TickEvents, transition
from virtual_plc.plc.status import ErrorCode, Status


def test_execute_from_idle_with_valid_sequence_goes_running():
    event = CommandEvent(CommandKind.EXECUTE, sequence_id=1)
    new_status, effects = transition(Status.IDLE, event, TickEvents())

    assert new_status is Status.RUNNING
    assert effects.load_sequence_id == 1
    assert effects.set_busy is True


def test_execute_from_idle_with_unknown_sequence_goes_error():
    event = CommandEvent(CommandKind.EXECUTE, sequence_id=999)
    new_status, effects = transition(Status.IDLE, event, TickEvents(sequence_unknown=True))

    assert new_status is Status.ERROR
    assert effects.error == (ErrorCode.UNKNOWN_SEQUENCE, "Unknown sequenceId 999")


@pytest.mark.parametrize("current", [Status.RUNNING, Status.STOPPING, Status.STOPPED, Status.ERROR])
def test_execute_ignored_outside_idle(current):
    event = CommandEvent(CommandKind.EXECUTE, sequence_id=1)
    new_status, effects = transition(current, event, TickEvents())

    assert new_status is current
    assert effects.load_sequence_id is None


def test_stop_from_running_goes_stopping():
    event = CommandEvent(CommandKind.STOP)
    new_status, _ = transition(Status.RUNNING, event, TickEvents())
    assert new_status is Status.STOPPING


@pytest.mark.parametrize("current", [Status.IDLE, Status.STOPPING, Status.STOPPED, Status.ERROR])
def test_stop_ignored_outside_running(current):
    event = CommandEvent(CommandKind.STOP)
    new_status, _ = transition(current, event, TickEvents())
    assert new_status is current


@pytest.mark.parametrize("current", [Status.STOPPED, Status.ERROR])
def test_reset_from_stopped_or_error_goes_idle(current):
    event = CommandEvent(CommandKind.RESET)
    new_status, effects = transition(current, event, TickEvents())
    assert new_status is Status.IDLE
    assert effects.clear_sequence is True


@pytest.mark.parametrize("current", [Status.IDLE, Status.RUNNING, Status.STOPPING])
def test_reset_ignored_outside_stopped_or_error(current):
    event = CommandEvent(CommandKind.RESET)
    new_status, _ = transition(current, event, TickEvents())
    assert new_status is current


def test_stopping_reaches_stopped_at_step_boundary():
    new_status, effects = transition(Status.STOPPING, None, TickEvents(stop_boundary_reached=True))
    assert new_status is Status.STOPPED
    assert effects.set_busy is False


def test_running_finishes_to_idle_when_sequence_done():
    new_status, effects = transition(Status.RUNNING, None, TickEvents(sequence_finished=True))
    assert new_status is Status.IDLE
    assert effects.set_done is True


@pytest.mark.parametrize("current", [Status.RUNNING, Status.STOPPING])
def test_fault_goes_to_error_from_any_active_status(current):
    fault = (ErrorCode.ROBOT_DISCONNECTED, "lost")
    new_status, effects = transition(current, None, TickEvents(fault=fault))
    assert new_status is Status.ERROR
    assert effects.error == fault


def test_no_event_and_no_tick_events_is_a_pure_no_op():
    new_status, effects = transition(Status.IDLE, None, TickEvents())
    assert new_status is Status.IDLE
    assert effects == type(effects)()
