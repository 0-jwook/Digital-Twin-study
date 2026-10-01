"""Config Processor: detects a Robot.Config.Apply rising edge and drives its
own Ack handshake, mirroring command_processor.py's pattern -- but simpler,
since there's only one trigger instead of three. Only produces an event
(meaning: actually go reconfigure the Robot Interface) when the PLC is IDLE;
otherwise it still Acks (so Backend's trigger clears) but no-ops, exactly
like Command's precondition-rejection rows.

Pure function over PLC Memory -- no OPC UA, no robot code. The actual
reconnect (which may block on real network I/O) happens in main.py, which
owns the mutable `robot` reference this module has no business touching.
"""

from __future__ import annotations

from dataclasses import dataclass

from .memory import PLCMemory
from .status import Status


@dataclass
class ConfigApplyEvent:
    mode: str
    host: str
    port: int
    max_speed: int


def process(memory: PLCMemory, current_status: Status) -> ConfigApplyEvent | None:
    cfg = memory.config
    event: ConfigApplyEvent | None = None

    if not cfg.ack:
        if cfg.apply and not cfg.prev_apply:
            cfg.ack = True
            if current_status is Status.IDLE:
                event = ConfigApplyEvent(
                    mode=cfg.mode, host=cfg.host, port=cfg.port, max_speed=cfg.max_speed
                )
            # else: PLC busy -- Acked so Backend's trigger clears, no event (no-op)
    elif not cfg.apply:
        cfg.ack = False

    cfg.prev_apply = cfg.apply

    return event
