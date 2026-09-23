import pytest

from fakes import FakeRobotInterface


@pytest.fixture
def fake_robot() -> FakeRobotInterface:
    return FakeRobotInterface()
