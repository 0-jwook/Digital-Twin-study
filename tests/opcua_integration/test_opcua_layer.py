"""Integration tests for the OPC UA layer (Phase 2).

Spins up a real asyncua Server (virtual_plc.opcua.server.PlcOpcuaServer) and
connects a real asyncua Client (backend.opcua.client.PlcOpcuaClient) against
it, over an ephemeral local port. Verifies connection, the node tree, raw
Command Read/Write, and Subscription data-change delivery.

No PLC logic (Command Processor / State Machine / Sequence Manager) is
involved yet -- that's Phase 3. State-node changes here are triggered
directly via `PlcOpcuaServer.write_state_nodes()`, standing in for what the
PLC scan loop will call in Phase 3.
"""

import asyncio

import pytest
from asyncua import ua

from backend.opcua.client import PlcOpcuaClient
from virtual_plc.opcua.server import PlcOpcuaServer, StateSnapshot

TEST_ENDPOINT = "opc.tcp://127.0.0.1:48401/digitaltwin/plc/"


@pytest.fixture
async def server():
    srv = PlcOpcuaServer(endpoint=TEST_ENDPOINT)
    await srv.init()
    await srv.start()
    yield srv
    await srv.stop()


@pytest.fixture
async def client(server):
    cli = PlcOpcuaClient(TEST_ENDPOINT)
    await cli.connect()
    yield cli
    await cli.disconnect()


async def test_connect_resolves_namespace(client):
    assert client.nsidx is not None
    assert client.nsidx != 0  # not the default namespace


async def test_default_values_match_spec(client):
    assert await client.read("Robot.State.Status") == 0  # IDLE
    assert await client.read("Robot.Sequence.CurrentSequenceId") == -1
    assert await client.read("Robot.Position.J1") == 0.0
    assert await client.read("Robot.Command.Ack") is False
    assert await client.read("Robot.Sequence.CatalogJson") == "[]"


async def test_command_node_write_and_read_back(client):
    await client.write("Robot.Command.SequenceId", 1, ua.VariantType.Int32)
    await client.write("Robot.Command.Execute", True)

    assert await client.read("Robot.Command.SequenceId") == 1
    assert await client.read("Robot.Command.Execute") is True


async def test_subscription_receives_state_change(server, client):
    received: list[tuple[str, object]] = []

    def on_change(path: str, value: object) -> None:
        received.append((path, value))

    await client.subscribe(on_change, period_ms=50)

    snapshot = StateSnapshot(
        status=1,  # RUNNING
        error_code=0,
        error_message="",
        robot_connected=True,
        current_sequence_id=1,
        current_step=0,
        total_steps=7,
        running=True,
        done=False,
        position={"j1": 10.0, "j2": 0.0, "j3": 0.0, "j4": 0.0, "j5": 0.0, "j6": 0.0},
        ack=True,
        busy=True,
    )
    await server.write_state_nodes(snapshot)

    # Subscription notifications arrive asynchronously; poll briefly.
    for _ in range(20):
        if any(path == "Robot.State.Status" for path, _ in received):
            break
        await asyncio.sleep(0.1)

    paths_seen = {path for path, _ in received}
    assert "Robot.State.Status" in paths_seen
    assert "Robot.Position.J1" in paths_seen
    assert "Robot.Command.Ack" in paths_seen

    status_updates = [value for path, value in received if path == "Robot.State.Status"]
    assert 1 in status_updates
