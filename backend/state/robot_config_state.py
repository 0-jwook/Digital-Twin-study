"""Robot Config State: the Robot Interface's virtual<->real configuration,
mirrored from OPC UA Robot.Config.* subscription notifications. Kept
separate from Robot/Sequence/Connection state -- a 5th distinct state model,
same "never merge" principle (docs/architecture.md section 1).

`mode`/`host`/`port`/`max_speed` are the last-requested values; `active_mode`/
`connection_ok`/`error_message` are what's actually running right now --
these can disagree briefly while an apply is in flight, or permanently if
the last apply failed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RobotConfigState:
    mode: str = "virtual"
    host: str = ""
    port: int = 9000
    max_speed: int = 30
    active_mode: str = "virtual"
    connection_ok: bool = True
    error_message: str = ""
