"""Detects Backend<->Virtual PLC OPC UA disconnection and recovers
automatically (docs/architecture.md section 3): a background health check
reads a cheap node periodically; on failure it marks the connection down,
broadcasts that immediately, then retries reconnecting with a fixed delay
until it succeeds, at which point it does a full one-shot resync of
State/Sequence/Position and re-announces `full_status`.

Virtual PLC itself needs no change for this -- it already keeps scanning
and driving the robot regardless of whether Backend is connected.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from .client import PlcOpcuaClient
from ..state.connection_state import ConnectionStateModel
from ..state.robot_state import RobotStateModel
from ..state.sequence_catalog import SequenceCatalog
from ..state.sequence_state import SequenceStateModel
from ..websocket.manager import WebSocketManager
from ..websocket.messages import connection_status_message, full_status_message

log = logging.getLogger("backend.opcua.supervisor")

HEALTH_CHECK_INTERVAL_SECONDS = 2.0
RECONNECT_RETRY_INTERVAL_SECONDS = 2.0

OnChange = Callable[[str, object], Awaitable[None]]


class ConnectionSupervisor:
    def __init__(
        self,
        endpoint: str,
        robot_state: RobotStateModel,
        sequence_state: SequenceStateModel,
        connection_state: ConnectionStateModel,
        ws_manager: WebSocketManager,
        on_change: OnChange,
        client_factory: Callable[[str], PlcOpcuaClient] = PlcOpcuaClient,
    ) -> None:
        self._endpoint = endpoint
        self._robot_state = robot_state
        self._sequence_state = sequence_state
        self._connection_state = connection_state
        self._ws_manager = ws_manager
        self._on_change = on_change
        self._client_factory = client_factory
        self.client: PlcOpcuaClient | None = None
        self.sequence_catalog: SequenceCatalog | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self.client = self._client_factory(self._endpoint)
        await self.client.connect()
        await self.client.subscribe(self._on_change, period_ms=50)
        self.sequence_catalog = SequenceCatalog(self.client)
        self._connection_state.mark_seen()
        self._task = asyncio.create_task(self._supervise())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
        if self.client is not None:
            try:
                await self.client.disconnect()
            except Exception:
                pass

    async def _supervise(self) -> None:
        while True:
            await asyncio.sleep(HEALTH_CHECK_INTERVAL_SECONDS)
            try:
                await self.client.read("Robot.State.Status")
            except Exception:
                await self._reconnect_loop()

    async def _reconnect_loop(self) -> None:
        log.warning("OPC UA connection to Virtual PLC lost -- entering reconnect loop")
        self._connection_state.mark_disconnected()
        await self._ws_manager.broadcast(connection_status_message(self._connection_state))

        try:
            await self.client.disconnect()
        except Exception:
            pass

        while True:
            await asyncio.sleep(RECONNECT_RETRY_INTERVAL_SECONDS)
            try:
                new_client = self._client_factory(self._endpoint)
                await new_client.connect()
                await new_client.subscribe(self._on_change, period_ms=50)
                self.client = new_client
                self.sequence_catalog = SequenceCatalog(new_client)
                await self._resync()
            except Exception:
                continue

            self._connection_state.mark_seen()
            await self._ws_manager.broadcast(
                full_status_message(self._robot_state, self._sequence_state, self._connection_state)
            )
            await self._ws_manager.broadcast(connection_status_message(self._connection_state))
            log.info("Reconnected to Virtual PLC OPC UA server")
            return

    async def _resync(self) -> None:
        """One-shot re-read of everything -- the robot may have kept moving
        or finished a sequence while Backend was disconnected."""
        client = self.client
        self._robot_state.status = await client.read("Robot.State.Status")
        self._robot_state.error_code = await client.read("Robot.State.ErrorCode")
        self._robot_state.error_message = await client.read("Robot.State.ErrorMessage")
        self._robot_state.robot_connected = await client.read("Robot.State.RobotConnected")
        for joint in ("j1", "j2", "j3", "j4", "j5", "j6"):
            self._robot_state.position[joint] = await client.read(f"Robot.Position.{joint.upper()}")

        self._sequence_state.sequence_id = await client.read("Robot.Sequence.CurrentSequenceId")
        self._sequence_state.current_step = await client.read("Robot.Sequence.CurrentStep")
        self._sequence_state.total_steps = await client.read("Robot.Sequence.TotalSteps")
        self._sequence_state.running = await client.read("Robot.Sequence.Running")
        self._sequence_state.done = await client.read("Robot.Sequence.Done")
