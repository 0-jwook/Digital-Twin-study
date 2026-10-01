"""PLC scan-cycle constants -- fallback used only if configs/plc.yaml is
missing the key (see configs/config.py:load_plc_config())."""

from __future__ import annotations

DEFAULT_SCAN_PERIOD_SECONDS = 0.05  # 50ms / 20Hz
