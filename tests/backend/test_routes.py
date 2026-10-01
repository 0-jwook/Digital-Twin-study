"""REST API tests. Builds a bare FastAPI app around just the router (no
lifespan, no real OPC UA connection) and overrides every dependency with a
fake -- matches docs/architecture.md's Backend test strategy: "OPC UA
client is swapped for a fake implementing the same interface"."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import routes
from backend.opcua.client import CommandInFlightError, CommandTimeoutError, ConfigInFlightError, ConfigTimeoutError
from backend.state.connection_state import ConnectionStateModel
from backend.state.robot_config_state import RobotConfigState
from backend.state.robot_state import RobotStateModel
from backend.state.sequence_state import SequenceStateModel

SAMPLE_CATALOG = [
    {"sequenceId": 1, "name": "pick_and_place", "steps": [{"index": 0, "name": "approach"}]},
    {"sequenceId": 2, "name": "home", "steps": [{"index": 0, "name": "go_home"}]},
]


class FakeCatalog:
    def __init__(self, sequences: list[dict]) -> None:
        self._sequences = sequences

    async def get_all(self) -> list[dict]:
        return self._sequences

    async def get(self, sequence_id: int) -> dict | None:
        for seq in self._sequences:
            if seq["sequenceId"] == sequence_id:
                return seq
        return None


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int | None]] = []
        self.raise_error: Exception | None = None
        self.config_calls: list[tuple[str, str, int, int]] = []
        self.raise_config_error: Exception | None = None

    async def write_command(self, trigger_path: str, sequence_id: int | None = None, timeout: float = 2.0) -> None:
        self.calls.append((trigger_path, sequence_id))
        if self.raise_error is not None:
            raise self.raise_error

    async def write_config_apply(
        self, mode: str, host: str, port: int, max_speed: int, timeout: float = 10.0
    ) -> None:
        self.config_calls.append((mode, host, port, max_speed))
        if self.raise_config_error is not None:
            raise self.raise_config_error


@pytest.fixture
def env():
    robot_state = RobotStateModel()
    sequence_state = SequenceStateModel()
    connection_state = ConnectionStateModel()
    connection_state.mark_seen()  # tests default to "connected" -- disconnect is tested explicitly
    catalog = FakeCatalog(SAMPLE_CATALOG)
    client = FakeClient()
    robot_config_state = RobotConfigState()

    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_robot_state] = lambda: robot_state
    app.dependency_overrides[routes.get_sequence_state] = lambda: sequence_state
    app.dependency_overrides[routes.get_connection_state] = lambda: connection_state
    app.dependency_overrides[routes.get_sequence_catalog] = lambda: catalog
    app.dependency_overrides[routes.get_opcua_client] = lambda: client
    app.dependency_overrides[routes.get_robot_config_state] = lambda: robot_config_state

    return {
        "client": TestClient(app),
        "robot_state": robot_state,
        "sequence_state": sequence_state,
        "connection_state": connection_state,
        "opcua_client": client,
        "robot_config_state": robot_config_state,
    }


def test_list_sequences(env):
    resp = env["client"].get("/api/sequences")
    assert resp.status_code == 200
    assert resp.json() == [
        {"sequenceId": 1, "name": "pick_and_place", "stepCount": 1},
        {"sequenceId": 2, "name": "home", "stepCount": 1},
    ]


def test_get_sequence_detail(env):
    resp = env["client"].get("/api/sequences/1")
    assert resp.status_code == 200
    assert resp.json()["name"] == "pick_and_place"


def test_get_sequence_detail_404(env):
    resp = env["client"].get("/api/sequences/999")
    assert resp.status_code == 404


def test_start_sequence_success(env):
    env["robot_state"].status = 0  # IDLE
    resp = env["client"].post("/api/sequence/start", json={"sequenceId": 1})
    assert resp.status_code == 202
    assert resp.json() == {"accepted": True}
    assert env["opcua_client"].calls == [("Robot.Command.Execute", 1)]


def test_start_sequence_unknown_id_404(env):
    env["robot_state"].status = 0
    resp = env["client"].post("/api/sequence/start", json={"sequenceId": 999})
    assert resp.status_code == 404
    assert env["opcua_client"].calls == []


def test_start_sequence_not_idle_409(env):
    env["robot_state"].status = 1  # RUNNING
    resp = env["client"].post("/api/sequence/start", json={"sequenceId": 1})
    assert resp.status_code == 409
    assert env["opcua_client"].calls == []


def test_start_sequence_command_in_flight_409(env):
    env["robot_state"].status = 0
    env["opcua_client"].raise_error = CommandInFlightError("busy")
    resp = env["client"].post("/api/sequence/start", json={"sequenceId": 1})
    assert resp.status_code == 409


def test_start_sequence_timeout_503(env):
    env["robot_state"].status = 0
    env["opcua_client"].raise_error = CommandTimeoutError("timeout")
    resp = env["client"].post("/api/sequence/start", json={"sequenceId": 1})
    assert resp.status_code == 503


def test_start_sequence_disconnected_503(env):
    env["robot_state"].status = 0
    env["connection_state"].mark_disconnected()
    resp = env["client"].post("/api/sequence/start", json={"sequenceId": 1})
    assert resp.status_code == 503
    assert env["opcua_client"].calls == []  # never even attempted the write


def test_stop_sequence_success(env):
    env["robot_state"].status = 1  # RUNNING
    resp = env["client"].post("/api/sequence/stop")
    assert resp.status_code == 202
    assert env["opcua_client"].calls == [("Robot.Command.Stop", None)]


def test_stop_sequence_not_running_409(env):
    env["robot_state"].status = 0  # IDLE
    resp = env["client"].post("/api/sequence/stop")
    assert resp.status_code == 409


def test_reset_sequence_success(env):
    env["robot_state"].status = 3  # STOPPED
    resp = env["client"].post("/api/sequence/reset")
    assert resp.status_code == 202
    assert env["opcua_client"].calls == [("Robot.Command.Reset", None)]


def test_reset_sequence_invalid_state_409(env):
    env["robot_state"].status = 1  # RUNNING
    resp = env["client"].post("/api/sequence/reset")
    assert resp.status_code == 409


def test_get_status(env):
    env["robot_state"].status = 1  # RUNNING
    env["robot_state"].position["j1"] = 12.5
    env["sequence_state"].sequence_id = 1
    env["sequence_state"].current_step = 2
    env["sequence_state"].total_steps = 7
    env["sequence_state"].running = True
    env["connection_state"].mark_seen()

    resp = env["client"].get("/api/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["plc"]["status"] == "RUNNING"
    assert body["position"]["j1"] == 12.5
    assert body["sequence"]["currentStep"] == 2
    assert body["connection"]["connected"] is True


def test_get_robot_config(env):
    cfg = env["robot_config_state"]
    cfg.mode = "real"
    cfg.host = "172.20.10.14"
    cfg.active_mode = "virtual"
    cfg.connection_ok = False
    cfg.error_message = "connect() failed"

    resp = env["client"].get("/api/robot-config")

    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "real"
    assert body["host"] == "172.20.10.14"
    assert body["activeMode"] == "virtual"
    assert body["connectionOk"] is False
    assert body["errorMessage"] == "connect() failed"


def test_apply_robot_config_success(env):
    env["robot_state"].status = 0  # IDLE
    resp = env["client"].post(
        "/api/robot-config", json={"mode": "real", "host": "172.20.10.14", "port": 9000, "maxSpeed": 20}
    )
    assert resp.status_code == 202
    assert env["opcua_client"].config_calls == [("real", "172.20.10.14", 9000, 20)]


def test_apply_robot_config_not_idle_409(env):
    env["robot_state"].status = 1  # RUNNING
    resp = env["client"].post("/api/robot-config", json={"mode": "virtual"})
    assert resp.status_code == 409
    assert env["opcua_client"].config_calls == []


def test_apply_robot_config_real_without_host_400(env):
    env["robot_state"].status = 0  # IDLE
    resp = env["client"].post("/api/robot-config", json={"mode": "real", "host": ""})
    assert resp.status_code == 400
    assert env["opcua_client"].config_calls == []


def test_apply_robot_config_disconnected_503(env):
    env["robot_state"].status = 0
    env["connection_state"].mark_disconnected()
    resp = env["client"].post("/api/robot-config", json={"mode": "virtual"})
    assert resp.status_code == 503
    assert env["opcua_client"].config_calls == []


def test_apply_robot_config_in_flight_409(env):
    env["robot_state"].status = 0
    env["opcua_client"].raise_config_error = ConfigInFlightError("busy")
    resp = env["client"].post("/api/robot-config", json={"mode": "virtual"})
    assert resp.status_code == 409


def test_apply_robot_config_timeout_503(env):
    env["robot_state"].status = 0
    env["opcua_client"].raise_config_error = ConfigTimeoutError("timeout")
    resp = env["client"].post("/api/robot-config", json={"mode": "virtual"})
    assert resp.status_code == 503
