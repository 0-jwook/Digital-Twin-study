"""Virtual PLC entrypoint. Run from the repo root as:

    virtual_plc/.venv/Scripts/python.exe -m virtual_plc.main

(module form, not `python main.py`, so this package's relative imports
resolve correctly).
"""

from __future__ import annotations

import asyncio
import logging

from .opcua.server import PlcOpcuaServer, StateSnapshot
from .plc.memory import PLCMemory
from .plc.scan import run_scan_tick
from .plc.state_machine import TickEvents
from .robot.interface import RobotInterface, VirtualRobotInterface
from .robot.state import RobotState
from .sequence.manager import build_catalog_json

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("virtual_plc")

SCAN_PERIOD_SECONDS = 0.05  # 50ms / 20Hz


async def scan_loop(
    server: PlcOpcuaServer,
    memory: PLCMemory,
    robot: RobotInterface,
    robot_state: RobotState,
) -> None:
    tick_events = TickEvents()
    while True:
        command = await server.read_command_memory()
        memory.command.sequence_id = command.sequence_id
        memory.command.execute = command.execute
        memory.command.stop = command.stop
        memory.command.reset = command.reset

        tick_events = run_scan_tick(memory, robot, robot_state, tick_events)

        await server.write_state_nodes(
            StateSnapshot(
                status=memory.state.status,
                error_code=memory.state.error_code,
                error_message=memory.state.error_message,
                robot_connected=memory.state.robot_connected,
                current_sequence_id=memory.sequence.current_sequence_id,
                current_step=memory.sequence.current_step,
                total_steps=memory.sequence.total_steps,
                running=memory.sequence.running,
                done=memory.sequence.done,
                position=memory.position.as_dict(),
                ack=memory.command.ack,
                busy=memory.command.busy,
            )
        )

        await asyncio.sleep(SCAN_PERIOD_SECONDS)


async def main() -> None:
    log.info("Virtual PLC starting...")
    async with PlcOpcuaServer() as server:
        log.info("OPC UA Server listening on %s", server.endpoint)
        await server.write_catalog_json(build_catalog_json())

        memory = PLCMemory()
        robot = VirtualRobotInterface()
        robot.connect()
        robot_state = RobotState()

        try:
            await scan_loop(server, memory, robot, robot_state)
        except asyncio.CancelledError:
            log.info("Virtual PLC stopping...")


if __name__ == "__main__":
    asyncio.run(main())
