"""Virtual PLC entrypoint. Run from the repo root as:

    virtual_plc/.venv/Scripts/python.exe -m virtual_plc.main

(module form, not `python main.py`, so this package's relative imports
resolve correctly).
"""

from __future__ import annotations

import asyncio

from .configs.config import load_plc_config, load_robot_config
from .configs.logger import get_logger, setup_logging
from .models.config import PlcConfig
from .models.memory import PLCMemory
from .models.opcua_snapshots import StateSnapshot
from .opcua.server import PlcOpcuaServer
from .plc import config_processor
from .plc.config_processor import ConfigApplyEvent
from .plc.scan import run_scan_tick
from .plc.state_machine import TickEvents
from .plc.status import Status
from .robot.config import build_robot_interface, create_robot_interface
from .robot.interface import RobotInterface
from .robot.state import RobotState
from .sequence.manager import build_catalog_json

log = get_logger(__name__)


async def _apply_robot_config(
    current_robot: RobotInterface, memory: PLCMemory, event: ConfigApplyEvent
) -> RobotInterface:
    """Build + connect the requested Robot Interface and swap it in on
    success. Runs connect() in a thread so a slow/unreachable real
    connection never stalls the 50ms scan loop (docs/architecture.md
    section 4)."""
    try:
        new_robot = build_robot_interface(event.mode, event.host, event.port, event.max_speed)
    except RuntimeError as exc:
        memory.config.connection_ok = False
        memory.config.error_message = str(exc)
        log.warning("Robot Config apply rejected: %s", exc)
        return current_robot

    connected = await asyncio.to_thread(new_robot.connect)
    if not connected:
        memory.config.connection_ok = False
        memory.config.error_message = "connect() failed -- check host/port and that Server_280.py is running"
        log.warning("Robot Config apply failed to connect (mode=%s)", event.mode)
        return current_robot

    memory.config.active_mode = event.mode
    memory.config.connection_ok = True
    memory.config.error_message = ""
    log.info("Robot Interface switched to mode=%s", event.mode)
    return new_robot


async def scan_loop(
    server: PlcOpcuaServer,
    memory: PLCMemory,
    robot: RobotInterface,
    robot_state: RobotState,
    scan_period_seconds: float,
) -> None:
    tick_events = TickEvents()
    while True:
        command = await server.read_command_memory()
        memory.command.sequence_id = command.sequence_id
        memory.command.execute = command.execute
        memory.command.stop = command.stop
        memory.command.reset = command.reset

        config_command = await server.read_config_memory()
        memory.config.mode = config_command.mode
        memory.config.host = config_command.host
        memory.config.port = config_command.port
        memory.config.max_speed = config_command.max_speed
        memory.config.apply = config_command.apply

        config_event = config_processor.process(memory, Status(memory.state.status))
        if config_event is not None:
            robot = await _apply_robot_config(robot, memory, config_event)

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
                config_ack=memory.config.ack,
                config_active_mode=memory.config.active_mode,
                config_connection_ok=memory.config.connection_ok,
                config_error_message=memory.config.error_message,
            )
        )

        await asyncio.sleep(scan_period_seconds)


async def main() -> None:
    setup_logging()
    log.info("Virtual PLC starting...")

    robot_cfg = load_robot_config()
    plc_cfg: PlcConfig = load_plc_config()

    async with PlcOpcuaServer(
        endpoint=plc_cfg.opcua_endpoint,
        initial_mode=robot_cfg.mode,
        initial_host=robot_cfg.host,
        initial_port=robot_cfg.port,
        initial_max_speed=robot_cfg.max_speed,
    ) as server:
        log.info("OPC UA Server listening on %s", server.endpoint)
        await server.write_catalog_json(build_catalog_json())

        memory = PLCMemory()
        memory.config.mode = robot_cfg.mode
        memory.config.host = robot_cfg.host
        memory.config.port = robot_cfg.port
        memory.config.max_speed = robot_cfg.max_speed
        memory.config.active_mode = robot_cfg.mode

        robot = create_robot_interface()  # virtual by default; ROBOT_MODE=real + MYCOBOT_HOST switches it
        connected = robot.connect()
        memory.config.connection_ok = connected
        if not connected:
            memory.config.error_message = "Initial connect() failed -- check host/port and that Server_280.py is running"
            log.warning("Robot Interface failed to connect on startup -- continuing, will report via State.RobotConnected")
        robot_state = RobotState()

        try:
            await scan_loop(server, memory, robot, robot_state, plc_cfg.scan_period_seconds)
        except asyncio.CancelledError:
            log.info("Virtual PLC stopping...")


if __name__ == "__main__":
    asyncio.run(main())
