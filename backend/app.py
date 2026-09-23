"""Backend entrypoint. Run from the repo root as:

    backend/.venv/Scripts/python.exe -m backend.app

(module form, so this package's relative imports resolve correctly), or via
`uvicorn backend.app:app` from the repo root for auto-reload during dev.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routes import router
from .opcua.client import PlcOpcuaClient
from .state.connection_state import ConnectionStateModel
from .state.robot_state import RobotStateModel
from .state.sequence_catalog import SequenceCatalog
from .state.sequence_state import SequenceStateModel

OPCUA_ENDPOINT = "opc.tcp://127.0.0.1:4840/digitaltwin/plc/"


def _make_on_change(
    robot_state: RobotStateModel,
    sequence_state: SequenceStateModel,
    connection_state: ConnectionStateModel,
):
    def on_change(path: str, value: object) -> None:
        if path == "Robot.State.Status":
            robot_state.status = value
        elif path == "Robot.State.ErrorCode":
            robot_state.error_code = value
        elif path == "Robot.State.ErrorMessage":
            robot_state.error_message = value
        elif path == "Robot.State.RobotConnected":
            robot_state.robot_connected = value
        elif path.startswith("Robot.Position."):
            joint = path.rsplit(".", 1)[-1].lower()
            robot_state.position[joint] = value
        elif path == "Robot.Sequence.CurrentSequenceId":
            sequence_state.sequence_id = value
        elif path == "Robot.Sequence.CurrentStep":
            sequence_state.current_step = value
        elif path == "Robot.Sequence.TotalSteps":
            sequence_state.total_steps = value
        elif path == "Robot.Sequence.Running":
            sequence_state.running = value
        elif path == "Robot.Sequence.Done":
            sequence_state.done = value
        # Command.Ack / Command.Busy are handled internally by PlcOpcuaClient.
        connection_state.mark_seen()

    return on_change


@asynccontextmanager
async def lifespan(app: FastAPI):
    robot_state = RobotStateModel()
    sequence_state = SequenceStateModel()
    connection_state = ConnectionStateModel()
    client = PlcOpcuaClient(OPCUA_ENDPOINT)
    catalog = SequenceCatalog(client)

    await client.connect()
    await client.subscribe(_make_on_change(robot_state, sequence_state, connection_state))
    connection_state.mark_seen()

    app.state.robot_state = robot_state
    app.state.sequence_state = sequence_state
    app.state.connection_state = connection_state
    app.state.opcua_client = client
    app.state.sequence_catalog = catalog

    yield

    await client.disconnect()


app = FastAPI(title="digital-twin-backend", lifespan=lifespan)
app.include_router(router)


@app.get("/")
def health() -> dict:
    return {"service": "backend", "status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
