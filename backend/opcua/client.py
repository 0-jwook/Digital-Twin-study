"""OPC UA Client wrapper for talking to the Virtual PLC's (or a real PLC's)
OPC UA Server, per docs/opcua-nodes.md. Generic connection/read/write/
subscription mechanics only -- the command handshake stepper and REST/WS
wiring are added in later phases.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from asyncua import Client, ua

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

    def datachange_notification(self, node: "ua.uaprotocol_auto.Node", val: object, data: object) -> None:
        path = self._path_by_node_id.get(node.nodeid.to_string(), str(node))
        self._on_change(path, val)


class PlcOpcuaClient:
    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint
        self.client = Client(endpoint)
        self.nsidx: int | None = None
        self._subscription = None

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
        handler = _SubscriptionHandler(path_by_node_id, on_change)
        self._subscription = await self.client.create_subscription(period_ms, handler)
        await self._subscription.subscribe_data_change(nodes)
        return self._subscription
