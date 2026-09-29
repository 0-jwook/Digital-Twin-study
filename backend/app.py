"""Backend entrypoint. Run from the repo root as:

    backend/.venv/Scripts/python.exe -m backend.app

(module form, so this package's relative imports resolve correctly), or via
`uvicorn backend.app:app` from the repo root for auto-reload during dev.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .api.routes import router
from .opcua.supervisor import ConnectionSupervisor
from .state.connection_state import ConnectionStateModel
from .state.robot_state import RobotStateModel
from .state.sequence_state import SequenceStateModel
from .websocket.manager import WebSocketManager
from .websocket.messages import (
    connection_status_message,
    full_status_message,
    plc_state_message,
    position_message,
    sequence_state_message,
)

OPCUA_ENDPOINT = "opc.tcp://127.0.0.1:4840/digitaltwin/plc/"


def _make_on_change(
    robot_state: RobotStateModel,
    sequence_state: SequenceStateModel,
    connection_state: ConnectionStateModel,
    ws_manager: WebSocketManager,
):
    async def on_change(path: str, value: object) -> None:
        if path == "Robot.State.Status":
            robot_state.status = value
            await ws_manager.broadcast(plc_state_message(robot_state))
        elif path == "Robot.State.ErrorCode":
            robot_state.error_code = value
            await ws_manager.broadcast(plc_state_message(robot_state))
        elif path == "Robot.State.ErrorMessage":
            robot_state.error_message = value
            await ws_manager.broadcast(plc_state_message(robot_state))
        elif path == "Robot.State.RobotConnected":
            robot_state.robot_connected = value
            await ws_manager.broadcast(plc_state_message(robot_state))
        elif path.startswith("Robot.Position."):
            joint = path.rsplit(".", 1)[-1].lower()
            robot_state.position[joint] = value
            await ws_manager.broadcast(position_message(robot_state))
        elif path == "Robot.Sequence.CurrentSequenceId":
            sequence_state.sequence_id = value
            await ws_manager.broadcast(sequence_state_message(sequence_state))
        elif path == "Robot.Sequence.CurrentStep":
            sequence_state.current_step = value
            await ws_manager.broadcast(sequence_state_message(sequence_state))
        elif path == "Robot.Sequence.TotalSteps":
            sequence_state.total_steps = value
            await ws_manager.broadcast(sequence_state_message(sequence_state))
        elif path == "Robot.Sequence.Running":
            sequence_state.running = value
            await ws_manager.broadcast(sequence_state_message(sequence_state))
        elif path == "Robot.Sequence.Done":
            sequence_state.done = value
            await ws_manager.broadcast(sequence_state_message(sequence_state))
        # Command.Ack / Command.Busy are handled internally by PlcOpcuaClient.
        connection_state.mark_seen()

    return on_change


@asynccontextmanager
async def lifespan(app: FastAPI):
    robot_state = RobotStateModel()
    sequence_state = SequenceStateModel()
    connection_state = ConnectionStateModel()
    ws_manager = WebSocketManager()

    # Subscription publish interval must be at or below the PLC's own scan
    # period (50ms/20Hz, docs/architecture.md section 8) so the OPC UA layer
    # is never the bottleneck ahead of the WebSocket's 25Hz position cap.
    # The supervisor owns the OPC UA client/catalog and transparently swaps
    # them for fresh ones if the connection drops and comes back
    # (docs/architecture.md section 3).
    supervisor = ConnectionSupervisor(
        OPCUA_ENDPOINT,
        robot_state,
        sequence_state,
        connection_state,
        ws_manager,
        _make_on_change(robot_state, sequence_state, connection_state, ws_manager),
    )
    await supervisor.start()

    app.state.robot_state = robot_state
    app.state.sequence_state = sequence_state
    app.state.connection_state = connection_state
    app.state.ws_manager = ws_manager
    app.state.supervisor = supervisor

    yield

    await supervisor.stop()


app = FastAPI(title="digital-twin-backend", lifespan=lifespan)
app.include_router(router)


@app.get("/")
def health() -> dict:
    return {"service": "backend", "status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    ws_manager: WebSocketManager = websocket.app.state.ws_manager
    robot_state: RobotStateModel = websocket.app.state.robot_state
    sequence_state: SequenceStateModel = websocket.app.state.sequence_state
    connection_state: ConnectionStateModel = websocket.app.state.connection_state

    await ws_manager.connect(websocket)
    await ws_manager.send_to(websocket, full_status_message(robot_state, sequence_state, connection_state))

    try:
        while True:
            await websocket.receive_text()  # Web never sends anything meaningful; just detects disconnect
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
