"""_apply_robot_config() tests (virtual_plc/main.py) -- the piece that
actually builds + connects a new Robot Interface and swaps it in, per a
Config Processor event. build_robot_interface() is monkeypatched so these
run without pymycobot or any real network I/O."""

from __future__ import annotations

from virtual_plc.main import _apply_robot_config
from virtual_plc.plc.config_processor import ConfigApplyEvent
from virtual_plc.plc.memory import PLCMemory


class FakeRobot:
    def __init__(self, succeed: bool) -> None:
        self.succeed = succeed
        self.connect_called = False

    def connect(self) -> bool:
        self.connect_called = True
        return self.succeed


async def test_apply_switches_robot_on_successful_connect(monkeypatch):
    memory = PLCMemory()
    old_robot = FakeRobot(succeed=True)
    new_robot = FakeRobot(succeed=True)
    monkeypatch.setattr(
        "virtual_plc.main.build_robot_interface", lambda mode, host, port, max_speed: new_robot
    )

    event = ConfigApplyEvent(mode="virtual", host="", port=9000, max_speed=30)
    result = await _apply_robot_config(old_robot, memory, event)

    assert result is new_robot
    assert new_robot.connect_called is True
    assert memory.config.active_mode == "virtual"
    assert memory.config.connection_ok is True
    assert memory.config.error_message == ""


async def test_apply_keeps_old_robot_on_connect_failure(monkeypatch):
    memory = PLCMemory()
    old_robot = FakeRobot(succeed=True)
    failing_robot = FakeRobot(succeed=False)
    monkeypatch.setattr(
        "virtual_plc.main.build_robot_interface", lambda mode, host, port, max_speed: failing_robot
    )

    event = ConfigApplyEvent(mode="real", host="10.0.0.5", port=9000, max_speed=20)
    result = await _apply_robot_config(old_robot, memory, event)

    assert result is old_robot
    assert memory.config.connection_ok is False
    assert "connect" in memory.config.error_message.lower()


async def test_apply_keeps_old_robot_when_build_raises(monkeypatch):
    memory = PLCMemory()
    old_robot = FakeRobot(succeed=True)

    def raise_error(mode, host, port, max_speed):
        raise RuntimeError("mode='real' requires a host")

    monkeypatch.setattr("virtual_plc.main.build_robot_interface", raise_error)

    event = ConfigApplyEvent(mode="real", host="", port=9000, max_speed=20)
    result = await _apply_robot_config(old_robot, memory, event)

    assert result is old_robot
    assert memory.config.connection_ok is False
    assert "host" in memory.config.error_message
