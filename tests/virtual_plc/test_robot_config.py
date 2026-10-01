"""create_robot_interface() tests: the virtual<->real switch must be
explicit-config-only, per the safety requirement agreed with the user --
never silently falls back to real, never silently falls back to virtual
once real is requested."""

from __future__ import annotations

import pytest

from virtual_plc.robot.config import create_robot_interface
from virtual_plc.robot.interface import VirtualRobotInterface
from virtual_plc.robot.real_interface import RealMycobotInterface


def test_defaults_to_virtual_with_no_env(monkeypatch):
    monkeypatch.delenv("ROBOT_MODE", raising=False)
    assert isinstance(create_robot_interface(), VirtualRobotInterface)


def test_explicit_virtual(monkeypatch):
    monkeypatch.setenv("ROBOT_MODE", "virtual")
    assert isinstance(create_robot_interface(), VirtualRobotInterface)


def test_real_without_host_raises(monkeypatch):
    monkeypatch.setenv("ROBOT_MODE", "real")
    monkeypatch.delenv("MYCOBOT_HOST", raising=False)
    with pytest.raises(RuntimeError, match="MYCOBOT_HOST"):
        create_robot_interface()


def test_real_with_host_returns_real_interface_with_configured_values(monkeypatch):
    monkeypatch.setenv("ROBOT_MODE", "real")
    monkeypatch.setenv("MYCOBOT_HOST", "172.20.10.14")
    monkeypatch.setenv("MYCOBOT_PORT", "9001")
    monkeypatch.setenv("MYCOBOT_MAX_SPEED", "15")

    robot = create_robot_interface()

    assert isinstance(robot, RealMycobotInterface)
    assert robot._host == "172.20.10.14"
    assert robot._port == 9001
    assert robot._max_speed == 15


def test_real_with_host_uses_safe_defaults_for_port_and_speed(monkeypatch):
    monkeypatch.setenv("ROBOT_MODE", "real")
    monkeypatch.setenv("MYCOBOT_HOST", "172.20.10.14")
    monkeypatch.delenv("MYCOBOT_PORT", raising=False)
    monkeypatch.delenv("MYCOBOT_MAX_SPEED", raising=False)

    robot = create_robot_interface()

    assert robot._port == 9000
    assert robot._max_speed == 30


def test_unknown_mode_raises(monkeypatch):
    monkeypatch.setenv("ROBOT_MODE", "bogus")
    with pytest.raises(RuntimeError, match="Unknown ROBOT_MODE"):
        create_robot_interface()
