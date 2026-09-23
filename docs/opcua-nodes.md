# OPC UA Information Model — myCobot 280 Pi 디지털 트윈

Virtual PLC(OPC UA Server)가 노출하고 Backend(OPC UA Client)가 소비하는 전체
주소 공간을 정의한다. 이 문서가 Backend와 Virtual PLC 사이의 **유일한 공유
계약**이다 — 두 프로세스는 이 문서 외에는 어떤 Python 타입도 공유하지 않는다
([`architecture.md`](./architecture.md) 1장 참고).

## 네임스페이스 / NodeId 규약

- 커스텀 네임스페이스 URI: `urn:digitaltwin:mycobot:plc` — Virtual PLC의
  `asyncua.Server`가 시작 시 등록한다.
- **Backend는 네임스페이스 인덱스를 하드코딩하지 않는다.** 연결 직후
  `get_namespace_index(uri)`로 조회해서 사용한다. 실PLC로 교체되면 인덱스가
  달라질 수 있기 때문이다.
- NodeId 식별자 타입: **String**. Browse Path를 그대로 반영하는 점(dot) 구분
  계층 규약을 사용한다. 예: `ns=<resolved>;s=Robot.Command.Execute`. 이는
  Beckhoff/Siemens 등 실제 산업용 OPC UA 서버에서 흔한 심볼릭(태그) 주소 지정
  방식과 유사해 주소 공간 자체가 자기 설명적이다.
- 모든 노드는 `Objects/Robot` 아래, `Command` / `Sequence` / `Position` /
  `State` 4개 폴더로 구성한다.

## Command 노드 — `Objects/Robot/Command` (Backend → PLC, write)

| 노드 | NodeId (`s=`) | DataType | 접근 권한 | 역할 |
|---|---|---|---|---|
| SequenceId | `Robot.Command.SequenceId` | Int32 | RW | Execute 전에 Backend가 실행할 Sequence를 지정 |
| Execute | `Robot.Command.Execute` | Boolean | RW | 커맨드 트리거. Ack 관찰 전까지 True로 유지 |
| Stop | `Robot.Command.Stop` | Boolean | RW | 커맨드 트리거. Ack 관찰 전까지 True로 유지 |
| Reset | `Robot.Command.Reset` | Boolean | RW | 커맨드 트리거. Ack 관찰 전까지 True로 유지 |

## Command 핸드셰이크 노드 — `Objects/Robot/Command` (PLC → Backend, Subscription 대상)

| 노드 | NodeId | DataType | 접근 권한 | 역할 |
|---|---|---|---|---|
| Ack | `Robot.Command.Ack` | Boolean | RO(Backend 관점) | Subscription 대상. PLC가 보류 중인 트리거를 래치해 핸드셰이크 중일 때 True |
| Busy | `Robot.Command.Busy` | Boolean | RO(Backend 관점) | Subscription 대상. Command Processor/Sequence Manager가 실제로 동작 중일 때 True (Execute의 경우 Sequence 종료까지 유지되어 `Ack`보다 수명이 김, Stop/Reset은 짧은 펄스) |

`Busy`와 `Sequence.Running`은 다른 개념이다. `Busy`는 "Command Processor가
지금 어떤 커맨드 처리로 점유되어 있는가"(Execute/Stop/Reset 모두 해당)를
답하고, `Sequence.Running`은 "Sequence Manager가 지금 Step을 진행 중인가"를
답한다. 이 둘을 하나로 합치면 "커맨드 처리 중"과 "Sequence 실행 중"이라는
서로 다른 의미가 뒤섞이므로 분리한다.

## 4단계 커맨드 핸드셰이크 프로토콜

Execute / Stop / Reset 3개 트리거가 **하나의 Ack/Busy 쌍을 공유**하는 레벨 기반
4단계 핸드셰이크다.

1. Backend가 (Execute라면 `SequenceId`를 먼저 쓴 뒤) 해당 트리거(`Execute` /
   `Stop` / `Reset`)를 **True로 쓰고, 그대로 유지**한다.
2. PLC 스캔 사이클의 Command Processor가 매 틱 커맨드 노드를 읽는다.
   **`Ack == False`일 때만** 이전 값과 비교한 rising edge로 트리거를
   감지한다(OPC UA Subscription은 "edge"가 아니라 "level"만 알려주므로, PLC
   내부에서 `prev_execute`/`prev_stop`/`prev_reset` 래치 값과 비교해 직접
   edge를 판정한다). 전제조건을 통과하면 `Ack = True`로 설정하고(실제 동작이
   뒤따르는 Execute/Stop이면 `Busy = True`도 설정), 검증된 `CommandEvent`를
   상태 머신에 전달한다.
3. Backend의 OPC UA Subscription이 `Ack → True`를 감지한다. **이때 Backend가
   트리거를 False로 되돌려 쓴다.** — "누가 트리거를 리셋하는가"에 대한 규칙:
   **Backend가, Ack를 관찰한 후에** 리셋한다.
4. PLC는 매 스캔 틱마다 트리거가 False로 돌아왔는지 확인하고, 확인되면
   `Ack = False`로 되돌린다. **PLC가, 트리거가 False로 돌아온 것을 확인한
   후에만** Ack를 내린다. `Busy`는 실제 동작(Execute의 경우 Sequence 완료 또는
   정지, Stop/Reset의 경우 처리 완료)까지 True로 유지된 뒤 False가 된다.

이 설계가 막는 문제:

- **트리거 씹힘(missed trigger)**: 트리거가 펄스가 아니라 레벨로 유지되므로,
  Subscription 지연으로 PLC 스캔이 늦게 반응해도 트리거가 사라지지 않는다 —
  Ack가 관찰될 때까지 계속 True로 남아 있다.
- **중복 트리거(double trigger)**: Command Processor는 `Ack == False`일 때만
  새 rising edge를 인정한다. 3개 트리거 채널이 하나의 Ack/Busy 쌍으로
  직렬화되므로, Execute 핸드셰이크가 진행 중일 때 들어온 Stop 쓰기는 Ack가
  풀릴 때까지 무시된다.
- **Backend의 조기 재전송**: Backend 내부 `CommandStateModel`
  (`NONE/SENDING/AWAITING_ACK/CLEARING/COMPLETE`)은 이전 커맨드의 Ack
  상승→하강 전체 사이클을 관찰하기 전까지 새 트리거 쓰기를 허용하지 않는다.

전제조건이 맞지 않는 트리거(예: RUNNING 중 Execute, RUNNING 중 Reset)도
**Ack는 되어 Backend의 트리거를 정상적으로 해제**시키지만, 상태 전이는
일으키지 않는다. 이런 no-op은 ERROR로 취급하지 않는다 — ERROR는 실제 실행
결함 전용이다.

## Sequence 상태 — `Objects/Robot/Sequence` (PLC → Backend)

| 노드 | NodeId | DataType | 접근 권한 | 역할 |
|---|---|---|---|---|
| CurrentSequenceId | `Robot.Sequence.CurrentSequenceId` | Int32 | RO | Subscription 대상. `-1` = 로드된 Sequence 없음 |
| CurrentStep | `Robot.Sequence.CurrentStep` | Int32 | RO | Subscription 대상. 0-based Step 인덱스 |
| TotalSteps | `Robot.Sequence.TotalSteps` | Int32 | RO | Subscription 대상 |
| Running | `Robot.Sequence.Running` | Boolean | RO | Subscription 대상. Sequence Manager가 Step을 진행 중 |
| Done | `Robot.Sequence.Done` | Boolean | RO | Subscription 대상. 정상 완료 시에만 True(Stop으로 멈춘 경우는 False) |
| CatalogJson | `Robot.Sequence.CatalogJson` | String | RO | **Poll-only(구독 대상 아님)** — PLC 부팅 시 1회 고정되는 정적 값. Backend가 시작/재연결 시 1회만 읽는다 |

`CatalogJson` 예시 내용(PLC 부팅 시 내부 `SEQUENCE_TABLE`로부터 생성):

```json
[
  {
    "sequenceId": 1,
    "name": "pick_and_place",
    "steps": [
      { "index": 0, "name": "approach" },
      { "index": 1, "name": "descend" },
      { "index": 2, "name": "grip" },
      { "index": 3, "name": "lift" },
      { "index": 4, "name": "move_to_place" },
      { "index": 5, "name": "release" },
      { "index": 6, "name": "retract" }
    ]
  },
  {
    "sequenceId": 2,
    "name": "home",
    "steps": [{ "index": 0, "name": "go_home" }]
  }
]
```

의도적으로 이 하나의 문자열 노드로만 노출한다(OPC UA 배열/구조체 노드 여러
개로 쪼개지 않음). 이유: JSON 문자열은 원자적으로 읽히므로 여러 배열 노드를
따로 읽을 때 생길 수 있는 부분 읽기(torn read) 문제가 없고, `asyncua`에서
다루기 간단하며, `name`/`index`만 노출해 순수하게 서술적 정보로 남는다 —
`joint_targets`나 `speed` 같은 실제 동작 데이터는 이 노드에도, 다른 어떤
OPC UA 노드에도 절대 나가지 않는다(Sequence는 PLC가 ID로만 참조되도록 소유한다는
원칙 유지). Backend/Web이 Sequence 내용을 업로드하거나 수정할 수 있는 경로도
존재하지 않는다.

## Position — `Objects/Robot/Position` (PLC → Backend, Subscription 대상)

| 노드 | NodeId | DataType | 접근 권한 | 단위 |
|---|---|---|---|---|
| J1 ~ J6 | `Robot.Position.J1` … `Robot.Position.J6` | Double | RO | **도(degree)**. `pymycobot`의 `send_angles`/`get_angles` 규약과 동일해 실로봇 전환 시 단위 변환 버그를 없앤다. 매 스캔 틱 `RobotInterface.get_current_position()`에서 갱신 |

## State — `Objects/Robot/State` (PLC → Backend, Subscription 대상)

| 노드 | NodeId | DataType | 접근 권한 | 역할 |
|---|---|---|---|---|
| Status | `Robot.State.Status` | Int32 (enum) | RO | Subscription 대상. `0=IDLE, 1=RUNNING, 2=STOPPING, 3=STOPPED, 4=ERROR` |
| ErrorCode | `Robot.State.ErrorCode` | Int32 | RO | Subscription 대상. 아래 코드표 참고 |
| ErrorMessage | `Robot.State.ErrorMessage` | String | RO | Subscription 대상. ErrorCode와 짝을 이루는 사람이 읽을 수 있는 설명 |
| RobotConnected | `Robot.State.RobotConnected` | Boolean | RO | Subscription 대상. **Robot Interface ↔ 로봇** 사이의 연결(가상 로봇은 항상 True, 실로봇은 시리얼 링크 상태 반영). Backend ↔ PLC 사이의 OPC UA 세션 상태와는 다른 개념이며, 후자는 Backend가 자신의 세션/구독 상태로부터 스스로 판단한다(PLC가 자신에게 연결이 끊겼음을 노드로 알릴 수는 없으므로) |

### ErrorCode 표 (MVP 범위)

| 코드 | 의미 |
|---|---|
| 0 | 에러 없음 |
| E100 | Execute 요청에 알 수 없는/유효하지 않은 SequenceId |
| E200 | 모션 중 Robot Interface가 연결 끊김을 보고 |
| E201 | Sequence Step에 범위를 벗어난 관절 목표값 포함(로드 시 검증) |
| E900 | 미분류 내부 결함(catch-all) |

## State vs Command 구분 원칙

Backend가 **쓰는** 노드는 `Command.SequenceId`, `Command.Execute`,
`Command.Stop`, `Command.Reset` 뿐이다. 그 외 모든 노드(`Command.Ack`,
`Command.Busy`, `Sequence.*` 전체, `Position.*` 전체, `State.*` 전체)는
Backend 관점에서 읽기 전용 상태이며, `CatalogJson`만 poll-only이고 나머지는
전부 Subscription 대상이다. Command와 State를 어디에서도 뒤섞지 않는다.
