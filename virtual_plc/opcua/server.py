"""OPC UA Server exposing the address space defined in docs/opcua-nodes.md.

Pure protocol layer: creates and holds the node tree, and offers two generic
read/write entry points (`read_command_memory` / `write_state_nodes`) for the
PLC scan loop to use. Contains no PLC logic of its own.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncua import Server, ua

NAMESPACE_URI = "urn:digitaltwin:mycobot:plc"
DEFAULT_ENDPOINT = "opc.tcp://0.0.0.0:4840/digitaltwin/plc/"

JOINTS = ("j1", "j2", "j3", "j4", "j5", "j6")


@dataclass
class CommandSnapshot:
    sequence_id: int
    execute: bool
    stop: bool
    reset: bool


@dataclass
class StateSnapshot:
    status: int
    error_code: int
    error_message: str
    robot_connected: bool
    current_sequence_id: int
    current_step: int
    total_steps: int
    running: bool
    done: bool
    position: dict[str, float]
    ack: bool
    busy: bool


class PlcOpcuaServer:
    def __init__(self, endpoint: str = DEFAULT_ENDPOINT) -> None:
        self.endpoint = endpoint
        self.server = Server()
        self.nsidx: int | None = None
        self.nodes: dict[str, "ua.uaprotocol_auto.Node"] = {}

    def _nid(self, path: str) -> ua.NodeId:
        return ua.NodeId(path, self.nsidx)

    async def init(self) -> None:
        await self.server.init()
        self.server.set_endpoint(self.endpoint)
        self.nsidx = await self.server.register_namespace(NAMESPACE_URI)

        objects = self.server.nodes.objects
        robot = await objects.add_object(self._nid("Robot"), "Robot")
        command = await robot.add_object(self._nid("Robot.Command"), "Command")
        sequence = await robot.add_object(self._nid("Robot.Sequence"), "Sequence")
        position = await robot.add_object(self._nid("Robot.Position"), "Position")
        state = await robot.add_object(self._nid("Robot.State"), "State")

        # Command (Backend -> PLC, writable)
        self.nodes["command.sequence_id"] = await command.add_variable(
            self._nid("Robot.Command.SequenceId"), "SequenceId", -1, ua.VariantType.Int32
        )
        self.nodes["command.execute"] = await command.add_variable(
            self._nid("Robot.Command.Execute"), "Execute", False
        )
        self.nodes["command.stop"] = await command.add_variable(
            self._nid("Robot.Command.Stop"), "Stop", False
        )
        self.nodes["command.reset"] = await command.add_variable(
            self._nid("Robot.Command.Reset"), "Reset", False
        )
        for key in ("command.sequence_id", "command.execute", "command.stop", "command.reset"):
            await self.nodes[key].set_writable()

        # Command handshake (PLC -> Backend, read-only from Backend's side)
        self.nodes["command.ack"] = await command.add_variable(
            self._nid("Robot.Command.Ack"), "Ack", False
        )
        self.nodes["command.busy"] = await command.add_variable(
            self._nid("Robot.Command.Busy"), "Busy", False
        )

        # Sequence
        self.nodes["sequence.current_sequence_id"] = await sequence.add_variable(
            self._nid("Robot.Sequence.CurrentSequenceId"), "CurrentSequenceId", -1, ua.VariantType.Int32
        )
        self.nodes["sequence.current_step"] = await sequence.add_variable(
            self._nid("Robot.Sequence.CurrentStep"), "CurrentStep", 0, ua.VariantType.Int32
        )
        self.nodes["sequence.total_steps"] = await sequence.add_variable(
            self._nid("Robot.Sequence.TotalSteps"), "TotalSteps", 0, ua.VariantType.Int32
        )
        self.nodes["sequence.running"] = await sequence.add_variable(
            self._nid("Robot.Sequence.Running"), "Running", False
        )
        self.nodes["sequence.done"] = await sequence.add_variable(
            self._nid("Robot.Sequence.Done"), "Done", False
        )
        # Poll-only diagnostic: static after boot, not a subscription target.
        self.nodes["sequence.catalog_json"] = await sequence.add_variable(
            self._nid("Robot.Sequence.CatalogJson"), "CatalogJson", "[]"
        )

        # Position (degrees)
        for j in JOINTS:
            self.nodes[f"position.{j}"] = await position.add_variable(
                self._nid(f"Robot.Position.{j.upper()}"), j.upper(), 0.0, ua.VariantType.Double
            )

        # State
        self.nodes["state.status"] = await state.add_variable(
            self._nid("Robot.State.Status"), "Status", 0, ua.VariantType.Int32
        )
        self.nodes["state.error_code"] = await state.add_variable(
            self._nid("Robot.State.ErrorCode"), "ErrorCode", 0, ua.VariantType.Int32
        )
        self.nodes["state.error_message"] = await state.add_variable(
            self._nid("Robot.State.ErrorMessage"), "ErrorMessage", ""
        )
        self.nodes["state.robot_connected"] = await state.add_variable(
            self._nid("Robot.State.RobotConnected"), "RobotConnected", True
        )

    async def write_catalog_json(self, catalog_json: str) -> None:
        await self.nodes["sequence.catalog_json"].write_value(catalog_json)

    async def start(self) -> None:
        await self.server.start()

    async def stop(self) -> None:
        await self.server.stop()

    async def __aenter__(self) -> "PlcOpcuaServer":
        await self.init()
        await self.start()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.stop()

    async def read_command_memory(self) -> CommandSnapshot:
        return CommandSnapshot(
            sequence_id=await self.nodes["command.sequence_id"].read_value(),
            execute=await self.nodes["command.execute"].read_value(),
            stop=await self.nodes["command.stop"].read_value(),
            reset=await self.nodes["command.reset"].read_value(),
        )

    async def write_state_nodes(self, snapshot: StateSnapshot) -> None:
        await self.nodes["state.status"].write_value(snapshot.status, ua.VariantType.Int32)
        await self.nodes["state.error_code"].write_value(snapshot.error_code, ua.VariantType.Int32)
        await self.nodes["state.error_message"].write_value(snapshot.error_message)
        await self.nodes["state.robot_connected"].write_value(snapshot.robot_connected)

        await self.nodes["sequence.current_sequence_id"].write_value(
            snapshot.current_sequence_id, ua.VariantType.Int32
        )
        await self.nodes["sequence.current_step"].write_value(snapshot.current_step, ua.VariantType.Int32)
        await self.nodes["sequence.total_steps"].write_value(snapshot.total_steps, ua.VariantType.Int32)
        await self.nodes["sequence.running"].write_value(snapshot.running)
        await self.nodes["sequence.done"].write_value(snapshot.done)

        for j in JOINTS:
            await self.nodes[f"position.{j}"].write_value(snapshot.position[j], ua.VariantType.Double)

        await self.nodes["command.ack"].write_value(snapshot.ack)
        await self.nodes["command.busy"].write_value(snapshot.busy)
