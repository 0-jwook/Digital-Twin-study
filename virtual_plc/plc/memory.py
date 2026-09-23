"""Scan-cycle blackboard. Every PLC module reads/writes these plain
dataclasses -- never OPC UA nodes directly (docs/architecture.md section 4).
Mirrors docs/opcua-nodes.md 1:1, plus a couple of internal-only working
fields not exposed over OPC UA (noted below).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CommandMemory:
    sequence_id: int = -1
    execute: bool = False
    stop: bool = False
    reset: bool = False
    prev_execute: bool = False
    prev_stop: bool = False
    prev_reset: bool = False
    ack: bool = False
    busy: bool = False


@dataclass
class StateMemory:
    status: int = 0  # Status.IDLE
    error_code: int = 0
    error_message: str = ""
    robot_connected: bool = True


@dataclass
class SequenceMemory:
    current_sequence_id: int = -1
    current_step: int = 0
    total_steps: int = 0
    running: bool = False
    done: bool = False
    stop_requested: bool = False  # internal-only; not exposed over OPC UA


@dataclass
class PositionMemory:
    j1: float = 0.0
    j2: float = 0.0
    j3: float = 0.0
    j4: float = 0.0
    j5: float = 0.0
    j6: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {"j1": self.j1, "j2": self.j2, "j3": self.j3, "j4": self.j4, "j5": self.j5, "j6": self.j6}


@dataclass
class PLCMemory:
    command: CommandMemory = field(default_factory=CommandMemory)
    state: StateMemory = field(default_factory=StateMemory)
    sequence: SequenceMemory = field(default_factory=SequenceMemory)
    position: PositionMemory = field(default_factory=PositionMemory)
