"""Sequence data model -- owned entirely by the PLC. Content (joint targets,
speed) never leaves it -- see docs/opcua-nodes.md CatalogJson.
"""

from __future__ import annotations

from dataclasses import dataclass


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
