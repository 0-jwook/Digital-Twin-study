from virtual_plc.plc.config_processor import process
from virtual_plc.plc.memory import PLCMemory
from virtual_plc.plc.status import Status


def test_apply_rising_edge_from_idle_produces_event_and_ack():
    memory = PLCMemory()
    memory.config.mode = "real"
    memory.config.host = "10.0.0.5"
    memory.config.port = 9000
    memory.config.max_speed = 20
    memory.config.apply = True

    event = process(memory, Status.IDLE)

    assert event is not None
    assert event.mode == "real"
    assert event.host == "10.0.0.5"
    assert event.port == 9000
    assert event.max_speed == 20
    assert memory.config.ack is True


def test_apply_while_running_is_acked_but_no_event():
    memory = PLCMemory()
    memory.config.apply = True

    event = process(memory, Status.RUNNING)

    assert event is None
    assert memory.config.ack is True


def test_no_new_event_while_ack_still_pending():
    memory = PLCMemory()
    memory.config.apply = True
    process(memory, Status.IDLE)  # ack goes True, event fires

    event = process(memory, Status.IDLE)  # apply still held True

    assert event is None  # guarded: ack is still True


def test_backend_clearing_trigger_releases_ack():
    memory = PLCMemory()
    memory.config.apply = True
    process(memory, Status.IDLE)
    assert memory.config.ack is True

    memory.config.apply = False  # backend observed Ack and cleared its trigger
    process(memory, Status.RUNNING)

    assert memory.config.ack is False
