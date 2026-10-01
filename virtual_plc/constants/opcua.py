"""OPC UA protocol-level constants for the Virtual PLC's own server. Not
shared with backend/ -- see docs/architecture.md section 1 on why Backend
and Virtual PLC never share a Python package. Backend keeps its own
independent copy of NAMESPACE_URI in backend/constants/opcua.py.
"""

from __future__ import annotations

NAMESPACE_URI = "urn:digitaltwin:mycobot:plc"
DEFAULT_ENDPOINT = "opc.tcp://0.0.0.0:4840/digitaltwin/plc/"
