from virtual_plc.plc.command_processor import CommandKind, process
from virtual_plc.plc.memory import PLCMemory
from virtual_plc.plc.status import Status


def test_execute_rising_edge_from_idle_produces_event_and_ack():
    memory = PLCMemory()
    memory.command.sequence_id = 1
    memory.command.execute = True

    event = process(memory, Status.IDLE)

    assert event is not None
    assert event.kind is CommandKind.EXECUTE
    assert event.sequence_id == 1
    assert memory.command.ack is True


def test_execute_while_running_is_acked_but_no_event():
    memory = PLCMemory()
    memory.command.execute = True

    event = process(memory, Status.RUNNING)

    assert event is None
    assert memory.command.ack is True


def test_no_new_event_while_ack_still_pending():
    memory = PLCMemory()
    memory.command.execute = True
    process(memory, Status.IDLE)  # ack goes True, event fires

    memory.command.stop = True  # a different trigger arrives before ack clears
    event = process(memory, Status.RUNNING)

    assert event is None  # guarded: ack is still True from the Execute handshake


def test_backend_clearing_trigger_releases_ack():
    memory = PLCMemory()
    memory.command.execute = True
    process(memory, Status.IDLE)
    assert memory.command.ack is True

    memory.command.execute = False  # backend observed Ack and cleared its trigger
    process(memory, Status.RUNNING)

    assert memory.command.ack is False


def test_reset_invalid_from_running_is_acked_with_no_event():
    memory = PLCMemory()
    memory.command.reset = True

    event = process(memory, Status.RUNNING)

    assert event is None
    assert memory.command.ack is True


def test_reset_valid_from_stopped():
    memory = PLCMemory()
    memory.command.reset = True

    event = process(memory, Status.STOPPED)

    assert event is not None
    assert event.kind is CommandKind.RESET


def test_stop_valid_from_running():
    memory = PLCMemory()
    memory.command.stop = True

    event = process(memory, Status.RUNNING)

    assert event is not None
    assert event.kind is CommandKind.STOP
