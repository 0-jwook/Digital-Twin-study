"""Robot Interface constants -- joint naming and connection defaults.
Previously duplicated verbatim between robot/interface.py and
opcua/server.py (JOINTS); consolidated here so both import the same tuple.
"""

from __future__ import annotations

JOINTS = ("j1", "j2", "j3", "j4", "j5", "j6")

DEFAULT_PORT = 9000
DEFAULT_MAX_SPEED = 30  # conservative cap on real hardware; raise only after real-world testing
