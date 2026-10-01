"""OPC UA protocol-level constants for the Backend's own client. Not shared
with virtual_plc/ -- see docs/architecture.md section 1 on why Backend and
Virtual PLC never share a Python package. Virtual PLC keeps its own
independent copy of NAMESPACE_URI in virtual_plc/constants/opcua.py.
"""

from __future__ import annotations

NAMESPACE_URI = "urn:digitaltwin:mycobot:plc"

# Fallback only -- used by configs/config.py:load_backend_config() when
# configs/backend.yaml doesn't have the key. The actual endpoint used at
# runtime comes from that YAML (or the OPCUA_ENDPOINT env var override).
DEFAULT_OPCUA_ENDPOINT = "opc.tcp://127.0.0.1:4840/digitaltwin/plc/"

# Nodes the Backend subscribes to (everything under State/Sequence/Position
# plus the command and config handshake pairs, excluding the poll-only
# CatalogJson).
SUBSCRIBED_PATHS = (
    "Robot.State.Status",
    "Robot.State.ErrorCode",
    "Robot.State.ErrorMessage",
    "Robot.State.RobotConnected",
    "Robot.Sequence.CurrentSequenceId",
    "Robot.Sequence.CurrentStep",
    "Robot.Sequence.TotalSteps",
    "Robot.Sequence.Running",
    "Robot.Sequence.Done",
    "Robot.Position.J1",
    "Robot.Position.J2",
    "Robot.Position.J3",
    "Robot.Position.J4",
    "Robot.Position.J5",
    "Robot.Position.J6",
    "Robot.Command.Ack",
    "Robot.Command.Busy",
    "Robot.Config.Mode",
    "Robot.Config.Host",
    "Robot.Config.Port",
    "Robot.Config.MaxSpeed",
    "Robot.Config.Ack",
    "Robot.Config.ActiveMode",
    "Robot.Config.ConnectionOk",
    "Robot.Config.ErrorMessage",
)
