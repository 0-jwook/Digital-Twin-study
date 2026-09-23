"""REST endpoints, matching docs/protocol.md section 1 exactly. State/client
access goes through FastAPI dependencies (not `request.app.state` directly
in the handlers) so tests can override them with fakes -- no real OPC UA
connection needed to test this layer.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from ..models.dto import (
    AcceptedResponse,
    ConnectionDto,
    PlcStatusDto,
    PositionDto,
    SequenceDetail,
    SequenceStateDto,
    SequenceStepDto,
    SequenceSummary,
    StartSequenceRequest,
    StatusResponse,
)
from ..opcua.client import CommandInFlightError, CommandTimeoutError, PlcOpcuaClient
from ..state.connection_state import ConnectionStateModel
from ..state.robot_state import RobotStateModel
from ..state.sequence_catalog import SequenceCatalog
from ..state.sequence_state import SequenceStateModel

router = APIRouter(prefix="/api")


def get_robot_state(request: Request) -> RobotStateModel:
    return request.app.state.robot_state


def get_sequence_state(request: Request) -> SequenceStateModel:
    return request.app.state.sequence_state


def get_connection_state(request: Request) -> ConnectionStateModel:
    return request.app.state.connection_state


def get_opcua_client(request: Request) -> PlcOpcuaClient:
    return request.app.state.opcua_client


def get_sequence_catalog(request: Request) -> SequenceCatalog:
    return request.app.state.sequence_catalog


async def _write_command_or_raise(
    client: PlcOpcuaClient, trigger_path: str, sequence_id: int | None = None
) -> None:
    try:
        await client.write_command(trigger_path, sequence_id=sequence_id)
    except CommandInFlightError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CommandTimeoutError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/sequences", response_model=list[SequenceSummary])
async def list_sequences(catalog: SequenceCatalog = Depends(get_sequence_catalog)):
    sequences = await catalog.get_all()
    return [
        SequenceSummary(sequenceId=seq["sequenceId"], name=seq["name"], stepCount=len(seq["steps"]))
        for seq in sequences
    ]


@router.get("/sequences/{sequence_id}", response_model=SequenceDetail)
async def get_sequence(sequence_id: int, catalog: SequenceCatalog = Depends(get_sequence_catalog)):
    seq = await catalog.get(sequence_id)
    if seq is None:
        raise HTTPException(status_code=404, detail=f"Unknown sequenceId {sequence_id}")
    return SequenceDetail(
        sequenceId=seq["sequenceId"],
        name=seq["name"],
        steps=[SequenceStepDto(**step) for step in seq["steps"]],
    )


@router.post("/sequence/start", response_model=AcceptedResponse, status_code=202)
async def start_sequence(
    body: StartSequenceRequest,
    robot_state: RobotStateModel = Depends(get_robot_state),
    catalog: SequenceCatalog = Depends(get_sequence_catalog),
    client: PlcOpcuaClient = Depends(get_opcua_client),
):
    if await catalog.get(body.sequenceId) is None:
        raise HTTPException(status_code=404, detail=f"Unknown sequenceId {body.sequenceId}")
    if robot_state.status_name != "IDLE":
        raise HTTPException(status_code=409, detail=f"PLC is not IDLE (current: {robot_state.status_name})")

    await _write_command_or_raise(client, "Robot.Command.Execute", sequence_id=body.sequenceId)
    return AcceptedResponse()


@router.post("/sequence/stop", response_model=AcceptedResponse, status_code=202)
async def stop_sequence(
    robot_state: RobotStateModel = Depends(get_robot_state),
    client: PlcOpcuaClient = Depends(get_opcua_client),
):
    if robot_state.status_name != "RUNNING":
        raise HTTPException(status_code=409, detail=f"No sequence running (current: {robot_state.status_name})")

    await _write_command_or_raise(client, "Robot.Command.Stop")
    return AcceptedResponse()


@router.post("/sequence/reset", response_model=AcceptedResponse, status_code=202)
async def reset_sequence(
    robot_state: RobotStateModel = Depends(get_robot_state),
    client: PlcOpcuaClient = Depends(get_opcua_client),
):
    if robot_state.status_name not in ("STOPPED", "ERROR"):
        raise HTTPException(
            status_code=409, detail=f"PLC is not STOPPED/ERROR (current: {robot_state.status_name})"
        )

    await _write_command_or_raise(client, "Robot.Command.Reset")
    return AcceptedResponse()


@router.get("/status", response_model=StatusResponse)
async def get_status(
    robot_state: RobotStateModel = Depends(get_robot_state),
    sequence_state: SequenceStateModel = Depends(get_sequence_state),
    connection_state: ConnectionStateModel = Depends(get_connection_state),
):
    return StatusResponse(
        plc=PlcStatusDto(
            status=robot_state.status_name,
            errorCode=robot_state.error_code,
            errorMessage=robot_state.error_message or None,
            robotConnected=robot_state.robot_connected,
        ),
        sequence=SequenceStateDto(
            sequenceId=sequence_state.sequence_id,
            currentStep=sequence_state.current_step,
            totalSteps=sequence_state.total_steps,
            running=sequence_state.running,
            done=sequence_state.done,
        ),
        position=PositionDto(**robot_state.position),
        connection=ConnectionDto(
            connected=connection_state.connected,
            lastSeen=connection_state.last_seen.isoformat() if connection_state.last_seen else None,
        ),
    )
