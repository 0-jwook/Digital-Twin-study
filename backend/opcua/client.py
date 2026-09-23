"""OPC UA Client wrapper for talking to the Virtual PLC's (or a real PLC's)
OPC UA Server, per docs/opcua-nodes.md. Connection/read/write/subscription
mechanics, plus the 4-phase command handshake stepper Backend REST handlers
use to drive Execute/Stop/Reset.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Awaitable, Callable

from asyncua import Client, ua


class CommandInFlightError(RuntimeError):
    """Raised when a new command is requested while a previous command's
    Ack/Busy handshake has not fully completed yet."""


class CommandTimeoutError(RuntimeError):
    """Raised when the PLC does not Ack (or clear Ack) within the timeout."""

NAMESPACE_URI = "urn:digitaltwin:mycobot:plc"

# Nodes the Backend subscribes to (everything under State/Sequence/Position
# plus the command handshake pair, excluding the poll-only CatalogJson).
SUBSCRIBED_PATHS = (
    "Robot.State.Status",
    "Robot.State.ErrorCode",
    "Robot.State.ErrorMessage",
    "Robot.State.RobotConnected",
    "Robot.Sequence.CurrentSequenceId",
    "Robot.Sequence.CurrentStep",
    "Robot.Sequence.TotalSteps",
    "Robot.Sequence.Running",
    "Robot.Sequence.Done",
    "Robot.Position.J1",
    "Robot.Position.J2",
    "Robot.Position.J3",
    "Robot.Position.J4",
    "Robot.Position.J5",
    "Robot.Position.J6",
    "Robot.Command.Ack",
    "Robot.Command.Busy",
)

DataChangeHandler = Callable[[str, object], Awaitable[None] | None]


class _SubscriptionHandler:
    def __init__(self, path_by_node_id: dict[str, str], on_change: DataChangeHandler) -> None:
        self._path_by_node_id = path_by_node_id
        self._on_change = on_change

    async def datachange_notification(self, node: "ua.uaprotocol_auto.Node", val: object, data: object) -> None:
        path = self._path_by_node_id.get(node.nodeid.to_string(), str(node))
        await self._on_change(path, val)


class PlcOpcuaClient:
    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint
        self.client = Client(endpoint)
        self.nsidx: int | None = None
        self._subscription = None
        self._command_lock = asyncio.Lock()
        self._ack_event = asyncio.Event()
        self._last_ack = False

    async def connect(self) -> None:
        await self.client.connect()
        self.nsidx = await self.client.get_namespace_index(NAMESPACE_URI)

    async def disconnect(self) -> None:
        if self._subscription is not None:
            await self._subscription.delete()
            self._subscription = None
        await self.client.disconnect()

    def _node(self, path: str) -> "ua.uaprotocol_auto.Node":
        return self.client.get_node(ua.NodeId(path, self.nsidx))

    async def read(self, path: str):
        return await self._node(path).read_value()

    async def write(self, path: str, value: object, variant_type: ua.VariantType | None = None) -> None:
        node = self._node(path)
        if variant_type is not None:
            await node.write_value(ua.DataValue(ua.Variant(value, variant_type)))
        else:
            await node.write_value(value)

    async def subscribe(self, on_change: DataChangeHandler, period_ms: int = 100):
        nodes = [self._node(path) for path in SUBSCRIBED_PATHS]
        path_by_node_id = {
            node.nodeid.to_string(): path for node, path in zip(nodes, SUBSCRIBED_PATHS)
        }

        async def _dispatch(path: str, value: object) -> None:
            if path == "Robot.Command.Ack":
                self._last_ack = bool(value)
                self._ack_event.set()
            result = on_change(path, value)
            if inspect.isawaitable(result):
                await result

        handler = _SubscriptionHandler(path_by_node_id, _dispatch)
        self._subscription = await self.client.create_subscription(period_ms, handler)
        await self._subscription.subscribe_data_change(nodes)
        return self._subscription

    async def write_command(
        self, trigger_path: str, sequence_id: int | None = None, timeout: float = 2.0
    ) -> None:
        """Drive the 4-phase Ack handshake (docs/opcua-nodes.md) for one of
        Robot.Command.{Execute,Stop,Reset}. Only one handshake may be in
        flight at a time -- the PLC serializes all three through one shared
        Ack/Busy pair, so Backend must too."""
        if self._command_lock.locked():
            raise CommandInFlightError("Another command handshake is already in progress")
        async with self._command_lock:
            if sequence_id is not None:
                await self.write("Robot.Command.SequenceId", sequence_id, ua.VariantType.Int32)
            self._ack_event.clear()
            await self.write(trigger_path, True)
            await self._wait_for_ack(True, timeout)
            await self.write(trigger_path, False)
            await self._wait_for_ack(False, timeout)

    async def _wait_for_ack(self, expected: bool, timeout: float) -> None:
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while self._last_ack != expected:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise CommandTimeoutError(f"Timed out waiting for Command.Ack == {expected}")
            self._ack_event.clear()
            try:
                await asyncio.wait_for(self._ack_event.wait(), timeout=remaining)
            except asyncio.TimeoutError as exc:
                raise CommandTimeoutError(f"Timed out waiting for Command.Ack == {expected}") from exc
