"""ConnectionSupervisor tests: reconnect-after-failure + resync, using a
fake OPC UA client (via dependency-injected client_factory) -- no real OPC
UA server needed. Retry/health-check intervals are patched down so the
tests run in milliseconds instead of real seconds."""

from __future__ import annotations

import asyncio

import pytest

from backend.opcua import supervisor as supervisor_module
from backend.opcua.supervisor import ConnectionSupervisor
from backend.state.connection_state import ConnectionStateModel
from backend.state.robot_state import RobotStateModel
from backend.state.sequence_state import SequenceStateModel
from backend.websocket.manager import WebSocketManager

DEFAULT_VALUES = {
    "Robot.State.Status": 0,
    "Robot.State.ErrorCode": 0,
    "Robot.State.ErrorMessage": "",
    "Robot.State.RobotConnected": True,
    "Robot.Position.J1": 0.0,
    "Robot.Position.J2": 0.0,
    "Robot.Position.J3": 0.0,
    "Robot.Position.J4": 0.0,
    "Robot.Position.J5": 0.0,
    "Robot.Position.J6": 0.0,
    "Robot.Sequence.CurrentSequenceId": -1,
    "Robot.Sequence.CurrentStep": 0,
    "Robot.Sequence.TotalSteps": 0,
    "Robot.Sequence.Running": False,
    "Robot.Sequence.Done": False,
}


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def accept(self) -> None:
        pass

    async def send_json(self, message: dict) -> None:
        self.sent.append(message)


class FakeSupervisedClient:
    def __init__(self, endpoint: str, registry: dict) -> None:
        self.endpoint = endpoint
        self._registry = registry
        registry["instances"].append(self)

    async def connect(self) -> None:
        if self._registry["fail_connect"]:
            raise ConnectionError("connect failed")

    async def subscribe(self, on_change, period_ms: int = 100) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def read(self, path: str):
        if self._registry["fail_read_remaining"] > 0:
            self._registry["fail_read_remaining"] -= 1
            raise ConnectionError("read failed")
        return self._registry["values"][path]


@pytest.fixture(autouse=True)
def fast_intervals(monkeypatch):
    monkeypatch.setattr(supervisor_module, "HEALTH_CHECK_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(supervisor_module, "RECONNECT_RETRY_INTERVAL_SECONDS", 0.01)


@pytest.fixture
async def setup():
    robot_state = RobotStateModel()
    sequence_state = SequenceStateModel()
    connection_state = ConnectionStateModel()
    ws_manager = WebSocketManager()
    ws = FakeWebSocket()
    await ws_manager.connect(ws)

    registry = {
        "fail_connect": False,
        "fail_read_remaining": 0,
        "values": dict(DEFAULT_VALUES),
        "instances": [],
    }

    async def on_change(path, value):
        pass

    supervisor = ConnectionSupervisor(
        "opc.tcp://fake/",
        robot_state,
        sequence_state,
        connection_state,
        ws_manager,
        on_change,
        client_factory=lambda endpoint: FakeSupervisedClient(endpoint, registry),
    )
    return {
        "supervisor": supervisor,
        "registry": registry,
        "robot_state": robot_state,
        "sequence_state": sequence_state,
        "connection_state": connection_state,
        "ws": ws,
    }


async def test_start_connects_and_marks_connected(setup):
    supervisor = setup["supervisor"]
    await supervisor.start()
    try:
        assert setup["connection_state"].connected is True
        assert len(setup["registry"]["instances"]) == 1
    finally:
        await supervisor.stop()


async def test_reconnect_loop_recovers_after_transient_failures_and_resyncs(setup):
    supervisor = setup["supervisor"]
    registry = setup["registry"]
    connection_state = setup["connection_state"]
    robot_state = setup["robot_state"]
    sequence_state = setup["sequence_state"]
    ws = setup["ws"]

    await supervisor.start()
    ws.sent.clear()  # drop the startup full_status the /ws handler would normally send

    attempts = {"count": 0}

    def flaky_factory(endpoint):
        attempts["count"] += 1
        registry["fail_connect"] = attempts["count"] < 3  # fails twice, succeeds on the 3rd try
        return FakeSupervisedClient(endpoint, registry)

    supervisor._client_factory = flaky_factory

    # Simulate the PLC having kept running while "disconnected" -- resync
    # must pick up these new values, not the stale ones from start().
    registry["values"]["Robot.State.Status"] = 1  # RUNNING
    registry["values"]["Robot.Sequence.CurrentSequenceId"] = 1
    registry["values"]["Robot.Sequence.Running"] = True

    await asyncio.wait_for(supervisor._reconnect_loop(), timeout=2.0)

    assert attempts["count"] == 3
    assert connection_state.connected is True
    assert robot_state.status == 1
    assert sequence_state.sequence_id == 1
    assert sequence_state.running is True

    message_types = [m["type"] for m in ws.sent]
    assert message_types[0] == "connection_status"
    assert ws.sent[0]["connected"] is False
    assert "full_status" in message_types
    assert message_types[-1] == "connection_status"
    assert ws.sent[-1]["connected"] is True

    await supervisor.stop()


async def test_supervise_detects_health_check_failure(setup):
    supervisor = setup["supervisor"]
    registry = setup["registry"]
    connection_state = setup["connection_state"]

    await supervisor.start()
    assert len(registry["instances"]) == 1
    registry["fail_read_remaining"] = 1  # exactly the next health-check read fails
    registry["fail_connect"] = False  # reconnect (and its resync reads) succeed right after

    for _ in range(50):  # poll briefly for the background task to notice and recover
        if len(registry["instances"]) >= 2:  # a second client = a reconnect actually happened
            break
        await asyncio.sleep(0.01)

    assert len(registry["instances"]) >= 2
    assert connection_state.connected is True
    await supervisor.stop()
