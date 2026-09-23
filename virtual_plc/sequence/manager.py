"""Sequence Manager: owns the PLC's pre-defined sequence table and drives
per-step progress during RUNNING/STOPPING. Sequence content (joint targets,
speed) never leaves the PLC -- see docs/opcua-nodes.md CatalogJson.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from ..plc.memory import PLCMemory
from ..plc.state_machine import TickEvents
from ..plc.status import ErrorCode
from ..robot.interface import RobotInterface


@dataclass
class SequenceStep:
    name: str
    joint_targets: dict[str, float]
    speed: float


@dataclass
class Sequence:
    sequence_id: int
    name: str
    steps: list[SequenceStep]


def _pose(**overrides: float) -> dict[str, float]:
    base = {"j1": 0.0, "j2": 0.0, "j3": 0.0, "j4": 0.0, "j5": 0.0, "j6": 0.0}
    base.update(overrides)
    return base


SEQUENCE_TABLE: dict[int, Sequence] = {
    1: Sequence(
        sequence_id=1,
        name="pick_and_place",
        steps=[
            SequenceStep("approach", _pose(j1=0, j2=-20, j3=20), 40),
            SequenceStep("descend", _pose(j1=0, j2=-40, j3=45), 20),
            SequenceStep("grip", _pose(j1=0, j2=-40, j3=45), 15),
            SequenceStep("lift", _pose(j1=0, j2=-20, j3=20), 30),
            SequenceStep("move_to_place", _pose(j1=45, j2=-20, j3=20), 40),
            SequenceStep("release", _pose(j1=45, j2=-40, j3=45), 15),
            SequenceStep("retract", _pose(j1=45, j2=-20, j3=20), 30),
        ],
    ),
    2: Sequence(
        sequence_id=2,
        name="home",
        steps=[SequenceStep("go_home", _pose(), 30)],
    ),
}


def exists(sequence_id: int) -> bool:
    return sequence_id in SEQUENCE_TABLE


def build_catalog_json() -> str:
    return json.dumps(
        [
            {
                "sequenceId": seq.sequence_id,
                "name": seq.name,
                "steps": [{"index": i, "name": step.name} for i, step in enumerate(seq.steps)],
            }
            for seq in SEQUENCE_TABLE.values()
        ]
    )


def start(memory: PLCMemory, sequence_id: int, robot: RobotInterface) -> None:
    seq = SEQUENCE_TABLE[sequence_id]
    memory.sequence.current_sequence_id = sequence_id
    memory.sequence.current_step = 0
    memory.sequence.total_steps = len(seq.steps)
    memory.sequence.done = False
    memory.sequence.stop_requested = False
    robot.move_to(seq.steps[0].joint_targets, seq.steps[0].speed)


def tick(memory: PLCMemory, robot: RobotInterface) -> TickEvents:
    seq = SEQUENCE_TABLE[memory.sequence.current_sequence_id]

    if not robot.is_at_target():
        return TickEvents()

    if memory.sequence.stop_requested:
        memory.sequence.stop_requested = False
        return TickEvents(stop_boundary_reached=True)

    if not robot.is_connected():
        return TickEvents(fault=(ErrorCode.ROBOT_DISCONNECTED, "Robot Interface disconnected during motion"))

    next_index = memory.sequence.current_step + 1
    if next_index >= len(seq.steps):
        return TickEvents(sequence_finished=True)

    memory.sequence.current_step = next_index
    step = seq.steps[next_index]
    robot.move_to(step.joint_targets, step.speed)
    return TickEvents()
