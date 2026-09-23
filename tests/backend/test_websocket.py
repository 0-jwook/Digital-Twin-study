"""WebSocketManager tests: throttling policy and broadcast/disconnect
behavior, per docs/protocol.md section 2. Uses a fake WebSocket -- no real
network, no FastAPI app needed."""

from __future__ import annotations

import asyncio

from backend.state.connection_state import ConnectionStateModel
from backend.state.robot_state import RobotStateModel
from backend.state.sequence_state import SequenceStateModel
from backend.websocket.manager import POSITION_MIN_INTERVAL_SECONDS, WebSocketManager
from backend.websocket.messages import full_status_message


class FakeWebSocket:
    def __init__(self, fail: bool = False) -> None:
        self.accepted = False
        self.sent: list[dict] = []
        self.fail = fail

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        if self.fail:
            raise RuntimeError("send failed")
        self.sent.append(message)


async def test_connect_accepts_and_registers():
    manager = WebSocketManager()
    ws = FakeWebSocket()

    await manager.connect(ws)

    assert ws.accepted is True
    assert ws in manager._connections


async def test_broadcast_sends_to_all_connections():
    manager = WebSocketManager()
    ws1, ws2 = FakeWebSocket(), FakeWebSocket()
    await manager.connect(ws1)
    await manager.connect(ws2)

    await manager.broadcast({"type": "plc_state", "status": "IDLE"})

    assert ws1.sent == [{"type": "plc_state", "status": "IDLE"}]
    assert ws2.sent == [{"type": "plc_state", "status": "IDLE"}]


async def test_non_position_messages_are_never_throttled():
    manager = WebSocketManager()
    ws = FakeWebSocket()
    await manager.connect(ws)

    for i in range(5):
        await manager.broadcast({"type": "sequence_state", "currentStep": i})

    assert len(ws.sent) == 5


async def test_position_messages_are_throttled_to_25hz():
    manager = WebSocketManager()
    ws = FakeWebSocket()
    await manager.connect(ws)

    await manager.broadcast({"type": "position", "j1": 1.0})
    await manager.broadcast({"type": "position", "j1": 2.0})  # arrives too soon -- dropped

    assert len(ws.sent) == 1
    assert ws.sent[0]["j1"] == 1.0

    await asyncio.sleep(POSITION_MIN_INTERVAL_SECONDS + 0.01)
    await manager.broadcast({"type": "position", "j1": 3.0})

    assert len(ws.sent) == 2
    assert ws.sent[1]["j1"] == 3.0


async def test_disconnect_removes_failed_connection_on_broadcast():
    manager = WebSocketManager()
    good = FakeWebSocket()
    bad = FakeWebSocket(fail=True)
    await manager.connect(good)
    await manager.connect(bad)

    await manager.broadcast({"type": "plc_state", "status": "ERROR"})

    assert bad not in manager._connections
    assert good in manager._connections
    assert good.sent == [{"type": "plc_state", "status": "ERROR"}]


def test_full_status_message_shape():
    robot_state = RobotStateModel(status=1, error_code=0, error_message="", robot_connected=True)
    robot_state.position["j1"] = 12.5
    sequence_state = SequenceStateModel(sequence_id=1, current_step=2, total_steps=7, running=True, done=False)
    connection_state = ConnectionStateModel()
    connection_state.mark_seen()

    message = full_status_message(robot_state, sequence_state, connection_state)

    assert message["type"] == "full_status"
    assert message["plc"]["status"] == "RUNNING"
    assert message["sequence"]["currentStep"] == 2
    assert message["position"]["j1"] == 12.5
    assert message["connection"]["connected"] is True
