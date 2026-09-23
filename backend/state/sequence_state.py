"""Sequence State: Sequence progress, mirrored from OPC UA subscription
notifications. Kept separate from Robot/Connection state
(docs/architecture.md section 1)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SequenceStateModel:
    sequence_id: int = -1
    current_step: int = 0
    total_steps: int = 0
    running: bool = False
    done: bool = False
