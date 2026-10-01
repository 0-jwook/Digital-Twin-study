"""RealMycobotInterface tests. pymycobot isn't installed in this test
environment (it's deliberately not in virtual_plc/requirements.txt -- see
requirements-real.txt), so `pymycobot.MyCobot280Socket` is faked via
sys.modules rather than skipped: these tests check our own wrapper logic
(speed clamp, joint-order conversion, is_in_position delegation, and
exception-to-disconnected handling), not pymycobot itself -- that part can
only really be verified against real hardware."""

from __future__ import annotations

import sys
import types

import pytest

from virtual_plc.robot.real_interface import RealMycobotInterface


class FakeMyCobot280Socket:
    instances: list["FakeMyCobot280Socket"] = []
    fail_on_init = False

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.sent: list[tuple[list[float], int]] = []
        self.angles = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.fail = FakeMyCobot280Socket.fail_on_init
        self.in_position = True
        self.closed = False
        FakeMyCobot280Socket.instances.append(self)

    def get_angles(self):
        if self.fail:
            raise ConnectionError("comm failure")
        return list(self.angles)

    def send_angles(self, angles, speed):
        if self.fail:
            raise ConnectionError("comm failure")
        self.sent.append((list(angles), speed))
        self.angles = list(angles)

    def is_in_position(self, data, flag):
        if self.fail:
            raise ConnectionError("comm failure")
        return 1 if self.in_position else 0

    def stop(self):
        if self.fail:
            raise ConnectionError("comm failure")

    def close(self):
        self.closed = True
        if self.fail:
            raise ConnectionError("comm failure")


@pytest.fixture(autouse=True)
def fake_pymycobot(monkeypatch):
    FakeMyCobot280Socket.instances.clear()
    FakeMyCobot280Socket.fail_on_init = False
    fake_module = types.ModuleType("pymycobot")
    fake_module.MyCobot280Socket = FakeMyCobot280Socket
    monkeypatch.setitem(sys.modules, "pymycobot", fake_module)
    yield


def test_connect_success():
    robot = RealMycobotInterface("10.0.0.5", 9000, max_speed=30)
    assert robot.connect() is True
    assert robot.is_connected() is True
    assert FakeMyCobot280Socket.instances[0].host == "10.0.0.5"


def test_connect_failure_marks_disconnected():
    FakeMyCobot280Socket.fail_on_init = True
    robot = RealMycobotInterface("10.0.0.5")
    assert robot.connect() is False
    assert robot.is_connected() is False


def test_connect_does_not_raise_when_pymycobot_is_not_installed(monkeypatch):
    """Regression test: pymycobot is deliberately not in virtual_plc's
    default requirements.txt (see requirements-real.txt). Remove this test
    file's autouse fake and `import pymycobot` genuinely raises
    ModuleNotFoundError, same as it would in a real "virtual-only" install.
    connect() must degrade to is_connected()=False like any other comms
    failure, not crash the whole scan loop -- this exact bug once took down
    a live virtual_plc process when real mode was selected without
    pymycobot installed."""
    monkeypatch.delitem(sys.modules, "pymycobot", raising=False)

    robot = RealMycobotInterface("10.0.0.5")
    assert robot.connect() is False  # must not raise
    assert robot.is_connected() is False


def test_move_to_clamps_speed_and_converts_dict_to_ordered_list():
    robot = RealMycobotInterface("10.0.0.5", max_speed=30)
    robot.connect()

    robot.move_to({"j1": 10, "j2": 20, "j3": 30, "j4": 40, "j5": 50, "j6": 60}, speed=80)

    fake = FakeMyCobot280Socket.instances[-1]
    assert fake.sent == [([10, 20, 30, 40, 50, 60], 30)]  # 80 clamped down to max_speed=30


def test_move_to_does_not_clamp_below_max_speed():
    robot = RealMycobotInterface("10.0.0.5", max_speed=30)
    robot.connect()

    robot.move_to({"j1": 0, "j2": 0, "j3": 0, "j4": 0, "j5": 0, "j6": 0}, speed=15)

    fake = FakeMyCobot280Socket.instances[-1]
    assert fake.sent[-1][1] == 15


def test_get_current_position_returns_dict_in_joint_order():
    robot = RealMycobotInterface("10.0.0.5")
    robot.connect()
    FakeMyCobot280Socket.instances[-1].angles = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]

    pos = robot.get_current_position()

    assert pos == {"j1": 1.0, "j2": 2.0, "j3": 3.0, "j4": 4.0, "j5": 5.0, "j6": 6.0}


def test_is_at_target_true_before_any_move_commanded():
    robot = RealMycobotInterface("10.0.0.5")
    robot.connect()
    assert robot.is_at_target() is True


def test_is_at_target_delegates_to_is_in_position():
    robot = RealMycobotInterface("10.0.0.5")
    robot.connect()
    robot.move_to({"j1": 1, "j2": 2, "j3": 3, "j4": 4, "j5": 5, "j6": 6}, 20)
    fake = FakeMyCobot280Socket.instances[-1]

    fake.in_position = False
    assert robot.is_at_target() is False

    fake.in_position = True
    assert robot.is_at_target() is True


def test_communication_failure_marks_disconnected_without_raising():
    robot = RealMycobotInterface("10.0.0.5")
    robot.connect()
    fake = FakeMyCobot280Socket.instances[-1]
    fake.fail = True

    robot.move_to({"j1": 1, "j2": 0, "j3": 0, "j4": 0, "j5": 0, "j6": 0}, 20)  # must not raise
    assert robot.is_connected() is False

    pos = robot.get_current_position()  # must not raise; degrades to last known pose
    assert isinstance(pos, dict) and set(pos) == {"j1", "j2", "j3", "j4", "j5", "j6"}
    assert robot.is_connected() is False

    robot._connected = True  # re-arm so is_at_target's own failure is what we're isolating
    robot._last_target = {"j1": 0, "j2": 0, "j3": 0, "j4": 0, "j5": 0, "j6": 0}
    assert robot.is_at_target() is False  # can't confirm arrival -> treated as "not yet"
    assert robot.is_connected() is False


def test_disconnect_closes_the_socket():
    robot = RealMycobotInterface("10.0.0.5")
    robot.connect()
    fake = FakeMyCobot280Socket.instances[-1]

    robot.disconnect()

    assert fake.closed is True
    assert robot.is_connected() is False


def test_disconnect_before_connect_does_not_raise():
    robot = RealMycobotInterface("10.0.0.5")
    robot.disconnect()  # never connected -- self._mc is still None
    assert robot.is_connected() is False


def test_disconnect_swallows_close_failure():
    robot = RealMycobotInterface("10.0.0.5")
    robot.connect()
    FakeMyCobot280Socket.instances[-1].fail = True

    robot.disconnect()  # must not raise even if close() itself fails

    assert robot.is_connected() is False

    robot.stop()  # must not raise either
