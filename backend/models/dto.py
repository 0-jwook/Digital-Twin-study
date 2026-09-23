"""REST request/response DTOs, matching docs/protocol.md section 1 exactly."""

from __future__ import annotations

from pydantic import BaseModel


class SequenceSummary(BaseModel):
    sequenceId: int
    name: str
    stepCount: int


class SequenceStepDto(BaseModel):
    index: int
    name: str


class SequenceDetail(BaseModel):
    sequenceId: int
    name: str
    steps: list[SequenceStepDto]


class StartSequenceRequest(BaseModel):
    sequenceId: int


class AcceptedResponse(BaseModel):
    accepted: bool = True


class PlcStatusDto(BaseModel):
    status: str
    errorCode: int
    errorMessage: str | None
    robotConnected: bool


class SequenceStateDto(BaseModel):
    sequenceId: int
    currentStep: int
    totalSteps: int
    running: bool
    done: bool


class PositionDto(BaseModel):
    j1: float
    j2: float
    j3: float
    j4: float
    j5: float
    j6: float


class ConnectionDto(BaseModel):
    connected: bool
    lastSeen: str | None


class StatusResponse(BaseModel):
    plc: PlcStatusDto
    sequence: SequenceStateDto
    position: PositionDto
    connection: ConnectionDto
