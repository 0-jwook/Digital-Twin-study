# 아키텍처 설계 — myCobot 280 Pi PLC 기반 디지털 트윈

이 문서는 전체 아키텍처, 계층별 책임, PLC 상태 머신, Virtual PLC/Backend/Frontend
내부 구조, 디렉터리 구조, 갱신 주기, 테스트 전략을 정의한다. OPC UA 노드의 상세
스펙은 [`opcua-nodes.md`](./opcua-nodes.md), REST/WebSocket 계약은
[`protocol.md`](./protocol.md)를 참고한다.

## 1. 전체 아키텍처 / 데이터 흐름

```text
┌──────────────────────────┐
│ WEB (Three.js + TS)      │
│ myCobot URDF / HMI       │
└────────────┬─────────────┘
             │ HTTP (명령/조회) + WebSocket (상태 push)
┌────────────▼─────────────┐
│ BACKEND (Python)         │
│ FastAPI / WebSocket      │
│ OPC UA Client            │
│ State Management         │
└────────────┬─────────────┘
             │ OPC UA (Subscription 우선, Polling은 CatalogJson 등 정적 값만)
┌────────────▼─────────────┐
│ VIRTUAL PLC (Python)     │
│ OPC UA Server            │
│ PLC Logic / Sequence     │
│ Memory / State           │
└────────────┬─────────────┘
             │ Robot Interface (교체 가능)
┌────────────▼─────────────┐
│ myCobot 280 Pi           │
│ (MVP: 가상 로봇)          │
└──────────────────────────┘
```

### 계층 책임

| 계층 | 책임 |
|---|---|
| Frontend | 3D 시각화 / HMI. Backend가 준 상태만 그린다. 자체적으로 로봇/PLC 상태를 판단하지 않는다 |
| Backend | REST API / WebSocket / OPC UA Client / 데이터 중계. **OPC UA 노드 모델에만 의존**, Virtual PLC의 내부 Python 구현을 알지 못한다 |
| Virtual PLC | OPC UA Server / PLC 로직 / Sequence 실행 / 상태 관리. 실제 PLC로 교체될 수 있는 계층 |
| Robot Interface | 가상 또는 실제 로봇 제어. Virtual PLC 내부의 교체 가능한 추상화 |

### 핵심 원칙

- 계층의 역할을 섞지 않는다. Frontend가 PLC 로직을 흉내내거나, Backend가 Sequence
  내용을 자체 보관하거나, Virtual PLC가 HTTP를 직접 노출하는 식의 월경을 하지 않는다.
- **Command State / PLC State / Robot State / Sequence State / Web UI State는
  어디서도 하나의 객체로 합치지 않는다.** Backend 내부에는 `RobotStateModel`,
  `SequenceStateModel`, `CommandStateModel`, `ConnectionStateModel` 4개를 분리
  유지한다. `GET /api/status` 응답에서만 이 4개를 하나의 JSON으로 묶는데, 이는
  "응답 경계에서의 직렬화"이지 내부 모델을 병합하는 것이 아니다.
- **실제 PLC 교체를 고려한다.** Virtual PLC가 OPC UA Server를 제공하는 것은 실제
  PLC(내장 OPC UA Server)와 동일한 구조를 유지하기 위함이다. Backend는 OPC UA 노드
  모델에만 의존하고 Virtual PLC의 내부 구현(모듈 구조, 스캔 주기 등)에 의존하지
  않는다. 이 원칙에서 파생되는 구체적 규칙:
  - Backend는 OPC UA 네임스페이스 인덱스를 **런타임에 `get_namespace_index(uri)`로
    조회**하고 하드코딩하지 않는다 — 실PLC로 교체되면 인덱스가 달라질 수 있다.
  - `backend/`와 `virtual_plc/` 사이에 **공유 Python 패키지를 두지 않는다.**
    타입을 공유하면 Backend가 Virtual PLC의 내부 구현에 암묵적으로 결합되어 교체
    가능성이 깨진다. 유일하게 공유되는 진실은 `opcua-nodes.md` 문서 자체이며,
    ErrorCode 표 등 양쪽에 필요한 상수는 각자 독립적으로 정의한다.

## 2. OPC UA 라이브러리

Virtual PLC(Server)와 Backend(Client) 모두 **`asyncua`**를 사용한다. `python-opcua`의
후속으로 활발히 유지보수되며 async 기반이고, Server/Client 양쪽 역할을 모두
지원하는 사실상의 Python 표준이기 때문이다.

## 3. PLC 상태 머신

### 상태

`IDLE`, `RUNNING`, `STOPPING`, `STOPPED`, `ERROR` — 5개. `STOPPING`은 "Stop
명령이 오면 현재 Step을 끝까지 마친 뒤 정지한다"는 요구사항을 표현하기 위한
필수 전이 상태다(RUNNING과 STOPPED 어느 쪽으로도 뭉뚱그릴 수 없다).

### 전이표

| From | Trigger/Event | To | 부수 효과 |
|---|---|---|---|
| IDLE | Execute 승인, 유효한 SequenceId | RUNNING | Sequence 로드, `CurrentStep=0`, `TotalSteps=len(steps)`, `Running=True`, `Done=False`, `Busy=True` |
| IDLE | Execute 승인, 미지의 SequenceId | ERROR | `ErrorCode=E100`, `ErrorMessage` 설정, `Busy=False` |
| IDLE / RUNNING / STOPPING / STOPPED / ERROR | 이미 유효하지 않은 상태에서 Execute 승인 (예: RUNNING 중 재실행 요청, 또는 STOPPED/ERROR/STOPPING 상태에서 Execute) | *(변화 없음)* | Ack만 되어 Backend의 트리거는 해제되지만 상태 전이는 없음 |
| RUNNING | Stop 승인 | STOPPING | `stop_requested=True` 설정. **진행 중인 현재 Step의 `move_to()`는 중단하지 않는다** |
| STOPPING | 현재 Step 도달 (`is_at_target()==True`) 이고 `stop_requested` | STOPPED | `Running=False`, `Busy=False`. `CurrentStep`은 유지(어디서 멈췄는지 UI에 표시하기 위함) |
| RUNNING | 마지막 Step 도달, 정지 요청 없음 | IDLE | `Running=False`, `Done=True`, `Busy=False` |
| RUNNING / STOPPING | 실행 중 실제 결함(로봇 연결 끊김 등) | ERROR | `Running=False`, `Busy=False`, `ErrorCode`/`ErrorMessage` 설정, `CurrentStep` 유지 |
| IDLE / RUNNING / STOPPING / STOPPED / ERROR | 이미 정지 상태이거나 Stop이 의미 없는 상태에서 Stop 승인 | *(변화 없음)* | Ack만 |
| STOPPED | Reset 승인 | IDLE | `CurrentSequenceId=-1`, `CurrentStep=0`, `TotalSteps=0`, `Done=False` |
| ERROR | Reset 승인 | IDLE | `ErrorCode=0`, `ErrorMessage=""`, Sequence 메모리 초기화 |
| IDLE / RUNNING / STOPPING | Reset 승인 | *(변화 없음)* | Ack만. **Reset은 STOPPED 또는 ERROR에서만 유효** |

전제조건 불충족으로 인한 no-op은 ERROR가 아니다. ERROR는 실제 실행 결함(로봇
연결 끊김, 범위 초과 등)에만 사용한다.

### "현재 Step 완료 후 정지"의 구현 위치

`SequenceManager.tick()` 내부에서, **현재 Step의 `robot_interface.is_at_target()
== True`를 확인한 직후, 다음 Step의 `move_to()`를 호출하기 전** 분기점에서
`stop_requested` 플래그를 검사한다. 플래그가 설정되어 있으면 다음 Step으로
진행하는 대신 STOPPING → STOPPED 전이를 수행한다. 이 구조는 로봇이 항상 현재
보간 중인 Step을 끝까지 마친 뒤에만 멈춘다는 것을 코드 구조적으로 보장하며,
Stop은 오직 Step 경계에서만 평가되고 보간 도중에는 절대 평가되지 않는다.

### OPC UA 연결 끊김 시 동작 (Backend ↔ Virtual PLC)

- **Virtual PLC는 Backend 연결 여부와 무관하게 스캔을 계속하고 로봇을 계속
  구동한다.** 실제 PLC가 SCADA/HMI 연결 상태와 무관하게 스캔 사이클을 계속하는
  것과 동일하며, "Backend는 PLC 실행을 제어하지 않고 관찰만 한다"는 원칙의 직접적
  결과다.
- Backend의 `asyncua` 클라이언트가 세션/킵얼라이브 실패를 감지하면 자체
  `ConnectionStateModel.connected = False`로 전환하고, 즉시 `connection_status`
  WebSocket 메시지(마지막으로 알고 있던 스냅샷 포함)를 보낸다.
- Web UI는 "연결 끊김 — 마지막 확인 시각 T" 배너를 표시하고, 마지막 렌더링된
  포즈를 **고정(0으로 리셋하지 않음)**하며, Start/Stop/Reset 버튼을 비활성화한다.
- Backend는 backoff를 두고 재연결을 시도한다(예: 2초 간격). 재연결에 성공하면
  State/Sequence/Position 전체 노드를 **1회 전체 재조회**해 내부 모델을
  재동기화한 뒤(연결이 끊긴 동안 로봇이 계속 움직였거나 Sequence가 끝났을 수
  있으므로), `full_status` + `connection_status(connected=true)`를 보내 UI가
  고정을 풀고 최신 상태로 갱신되게 한다.

## 4. Virtual PLC 내부 구조

```text
OPC UA Server → PLC Memory → PLC Logic → Sequence Manager → Robot Interface
```

### 모듈

| 모듈 | 파일(예정) | 책임 |
|---|---|---|
| OPC UA Server | `virtual_plc/opcua/server.py` | `asyncua.Server` 래핑. 주소 공간 노출만 담당하며 PLC 로직은 전혀 갖지 않는다. `read_command_memory()`, `write_state_nodes()`만 제공 |
| PLC Memory | `virtual_plc/plc/memory.py` | 스캔 사이클의 blackboard. `CommandMemory`(execute, stop, reset, sequence_id, prev_execute, prev_stop, prev_reset, ack, busy), `StateMemory`, `SequenceMemory`, `PositionMemory` — 순수 dataclass. 다른 모든 모듈은 OPC UA가 아니라 이 Memory를 읽고 쓴다 |
| Command Processor | `virtual_plc/plc/command_processor.py` | PLC Memory에 대한 순수 함수. `prev_*` 래치 비교로 rising edge 감지, 전제조건 검증, Ack/Busy 핸드셰이크 갱신. OPC UA·로봇 코드를 모른다 |
| PLC State Machine | `virtual_plc/plc/state_machine.py` | `transition(current, event, sequence_done, fault) -> (new_status, side_effects)` 순수 함수. 위 3장 전이표를 그대로 구현. 외부 의존성이 없어 독립적으로 단위테스트 가능 |
| Sequence Manager | `virtual_plc/sequence/manager.py` | `SEQUENCE_TABLE: dict[int, Sequence]` 소유. `load_sequence(id)`, `tick(memory, robot)` — Step 진행 및 Stop 경계 체크 담당 |
| Robot State | `virtual_plc/robot/state.py` | 매 틱 `robot_interface.get_current_position()`로 갱신되는 위치 캐시. Command Processor/Sequence Manager가 로봇을 직접 호출하지 않고 이 객체를 통해서만 위치를 읽게 해 "Robot State"를 독립된 상태로 유지 |
| Robot Interface | `virtual_plc/robot/interface.py` | 교체 가능한 추상화(Protocol/ABC) |

Robot Interface 계약:

```text
connect() -> bool
move_to(joint_targets: dict[str, float], speed: float) -> None   # non-blocking, 도, 0-100%
get_current_position() -> dict[str, float]                        # 도
is_at_target() -> bool
is_connected() -> bool
stop() -> None   # 예약됨. 일반 Stop 흐름(현재 Step 완료 후 정지)에서는 사용하지 않음
```

MVP 구현은 `VirtualRobotInterface`(시간 기반 관절 보간): `move_to()` 호출 시
관절별 delta와 `speed%`·최대 delta로 duration을 계산해 시작 포즈/목표 포즈/시작
시각을 기록하고, `get_current_position()`은 경과 시간 비율로 보간, `is_at_target()`은
경과 시간이 duration 이상이면 True. 실로봇용 `RealMycobotInterface`(pymycobot
기반)는 이번 설계·구현 범위에 포함하지 않으며, 이 인터페이스를 그대로 구현해
교체하는 것으로 설계되어 있다.

### 스캔 주기

**고정 50ms(20Hz)**. 실제 PLC는 통상 10~100ms 범위에서 스캔하며, 20Hz는 WebSocket
상한(25Hz, [`protocol.md`](./protocol.md) 참고)보다 빨라 PLC가 렌더링의 병목이
되지 않으면서도, 단일 `asyncio` 루프에서 `asyncua` 서버와 함께 안정적으로 돌 수
있는 수준이다.

매 틱, 다음 순서로 고정 실행:

1. **Copy-in**: OPC UA Server에서 커맨드 노드를 읽어 `PLCMemory.CommandMemory`에 반영
2. Command Processor가 Memory를 처리 → `CommandEvent` 산출, Ack/Busy 갱신
3. PLC State Machine이 이벤트를 적용 → 새 `Status` + 부수효과(예: "Sequence 로드")
4. Sequence Manager `tick()` — RUNNING/STOPPING이면 Robot Interface 진행 상태
   확인, Stop 경계 규칙에 따라 다음 Step 진행 또는 정지, 필요 시 `move_to()` 호출
5. Robot State를 `robot_interface.get_current_position()`으로 갱신
6. **Copy-back**: PLC Memory의 Status/Error/Sequence/Position 필드 갱신
7. **Copy-out**: PLC Memory의 상태 필드를 OPC UA 노드 값으로 씀 — 이 시점에
   `asyncua` 구독 알림이 Backend로 발화됨

## 5. Backend 구조

### 디렉터리

`backend/{app.py, api/, opcua/, websocket/, state/, models/}`

- `app.py` — FastAPI 진입점
- `api/routes.py` — REST 라우트 ([`protocol.md`](./protocol.md) 참고)
- `opcua/client.py` — OPC UA Client, 구독 콜백, 4단계 커맨드 핸드셰이크
- `websocket/manager.py` — 연결 레지스트리 + 브로드캐스트
- `state/{robot_state.py, sequence_state.py, command_state.py, connection_state.py}`
- `models/` — REST/WS용 Pydantic DTO

### 내부 상태 모델 (분리 유지)

- `RobotStateModel`: status, errorCode, errorMessage, robotConnected, position(j1-j6)
- `SequenceStateModel`: sequenceId, currentStep, totalSteps, running, done
- `CommandStateModel`: 내부 전용 핸드셰이크 상태기 — `NONE / SENDING /
  AWAITING_ACK / CLEARING / COMPLETE`. 이전 커맨드의 Ack 사이클이 끝나기 전에
  Backend가 새 트리거를 또 쓰는 것을 막는 역할
- `ConnectionStateModel`: opcuaConnected(bool), lastSeen(timestamp)

### Sequence 목록/메타데이터 제공 방식

Backend는 Sequence 내용을 영속적으로 복제하지 않는다. 시작 시, 그리고 짧은
TTL(~5초, 반복 요청 시 재파싱 방지용) 캐시로 `Robot.Sequence.CatalogJson`을
**1회성 OPC UA read**(구독 아님 — 부팅 후 정적이므로)로 읽어 파싱해
`GET /api/sequences*`에 응답한다. 캐시는 Backend 재시작 및 OPC UA 재연결 시
무효화된다. 이는 순수 성능상의 캐시일 뿐이며, Sequence 내용의 유일한 권한은
여전히 Virtual PLC에 있다.

### OPC UA Client 책임

- 연결 직후 `get_namespace_index(uri)`로 네임스페이스 인덱스 조회
- `State.*`, `Sequence.*`(`CatalogJson` 제외), `Position.J1-J6`,
  `Command.Ack`, `Command.Busy`를 포괄하는 Subscription 1개 생성
- `datachange_notification` 콜백에서 해당 상태 모델 갱신 후
  `WebSocketManager.broadcast(...)` 호출 — **이것이 WS 푸시의 유일한 경로이며,
  별도 폴링 루프는 없다**
- `write_command(node, value)` — REST 핸들러가 사용. [`opcua-nodes.md`](./opcua-nodes.md)의
  4단계 핸드셰이크(트리거 True 쓰기 → 같은 구독 콜백으로 Ack 관찰 → 트리거
  False 쓰기)를 이 안에 캡슐화해 라우트 핸들러가 OPC UA 원시 쓰기를 직접 다루지
  않게 한다

### WebSocket 서버

FastAPI 네이티브 `/ws` 엔드포인트. `WebSocketManager`의 브로드캐스트는 오직
(a) OPC UA 구독 콜백, (b) `ConnectionStateModel` 전이(연결 끊김/복구)에서만
발생한다. REST 핸들러나 폴링 루프에서 직접 브로드캐스트하지 않는다.

## 6. Frontend 구조

### 디렉터리

`frontend/src/{scene, robot, plc, sequence, network}/`, `public/robot/mycobot/`
— 브리프의 제안 구조를 그대로 채택.

- `scene/` — `SceneManager`: Three.js scene/camera/lights/ground, `animate()`
  렌더 루프(`requestAnimationFrame`, 60fps)
- `robot/` — URDF 로딩(urdf-loader)으로 `public/robot/mycobot/`의 myCobot 280 Pi
  모델을 불러옴. `RobotModel.setJointAngles(anglesDeg)`가 joint map 설정을 적용해
  URDF 관절 객체를 구동
- `robot/jointMap.config.ts` — **관절 Offset / 방향 / 단위 변환을 관리하는 단일
  설정 파일** (코드에 하드코딩 금지):

  ```json
  {
    "j1": { "urdfJointName": "joint1", "offsetDeg": 0,   "sign": 1 },
    "j2": { "urdfJointName": "joint2", "offsetDeg": -90, "sign": -1 },
    "j3": { "urdfJointName": "joint3", "offsetDeg": 0,   "sign": 1 },
    "j4": { "urdfJointName": "joint4", "offsetDeg": 0,   "sign": 1 },
    "j5": { "urdfJointName": "joint5", "offsetDeg": 0,   "sign": 1 },
    "j6": { "urdfJointName": "joint6", "offsetDeg": 0,   "sign": 1 }
  }
  ```

  적용식: `urdfAngleRad = degToRad(plcAngleDeg * sign + offsetDeg)`. 실제
  myCobot과 URDF의 영점(zero-pose)이 다르면 이 파일만 고치면 된다. 값은
  실물/모델 확인 후 구현 단계에서 보정한다.
- `plc/` — `PlcStateStore`(최신 `plc_state`/`sequence_state`를 보관하는
  observable). 로봇 포즈 데이터와는 분리 유지
- `sequence/` — `SequenceListView`, `SequenceDetailView`, Start/Stop/Reset
  컨트롤(REST 엔드포인트에 연결, `PlcStateStore.status`/`ConnectionStore.connected`에
  따라 비활성화)
- `network/` — `RestClient`(fetch 래퍼), `WebSocketClient`(`type` 판별 메시지
  파싱 후 `PositionBuffer`/`PlcStateStore`/`SequenceStateStore`/`ConnectionStore`로
  분배)

### 25Hz WebSocket → 60fps 렌더링 매끄럽게 잇기

`WebSocketClient`가 각 `position` 메시지를 `PositionBuffer{prev, target,
receivedAt}`에 기록한다. 매 `requestAnimationFrame` 틱마다
`alpha = clamp((now - receivedAt) / 40ms, 0, 1)`을 계산해
`setJointAngles(lerp(prev, target, alpha))`를 호출한다. myCobot의 관절 이동은
느리고 연속적이므로 MVP에서는 단순 선형 보간으로 충분하며, 속도 기반 외삽은
필요하지 않다.

## 7. 디렉터리 구조

브리프가 제안한 구조를 그대로 채택하되, 다음 2가지만 이유를 밝히고 보완한다.

```text
digital-twin/
├── backend/        app.py, api/, opcua/, websocket/, state/, models/
├── virtual_plc/    main.py, opcua/, plc/, sequence/, robot/
├── frontend/       index.html, src/{scene,robot,plc,sequence,network}/, public/robot/mycobot/
├── docs/           architecture.md, opcua-nodes.md, protocol.md
├── tests/
│   ├── virtual_plc/        # OPC UA·네트워크 의존 없는 순수 단위테스트
│   ├── opcua_integration/  # 실제 asyncua 서버+클라이언트
│   └── backend/            # API 테스트, fake OPC UA client
└── README.md
```

1. **`tests/`를 `virtual_plc/` / `opcua_integration/` / `backend/`로 분리** —
   PLC 상태 머신/Command Processor 단위테스트는 서버·네트워크 의존이 전혀 없어야
   CI에서 빠르게 돌릴 수 있고, OPC UA 통합 테스트는 실제 서버 fixture가 필요해
   실행 시간이 다르기 때문이다.
2. **`backend/`와 `virtual_plc/` 사이에 공유 Python 패키지를 두지 않는다** —
   1장에서 설명한 대로, 공유 타입은 Backend를 Virtual PLC 내부 구현에 결합시켜
   "실PLC 교체 가능" 원칙을 깬다. 공유되는 것은 `opcua-nodes.md` 문서뿐이다.

## 8. 갱신 주기 요약

| 구간 | 주기 |
|---|---|
| PLC 스캔 사이클 | 50ms(20Hz) 고정 |
| OPC UA 구독 | State/Sequence/Command Ack·Busy는 변경 시 즉시 발화. Position은 PLC 스캔 속도(~20Hz)로 갱신 |
| Backend → Web WebSocket | `position`은 25Hz(40ms) 상한(coalesce). `plc_state`/`sequence_state`/`connection_status`는 무제한, 즉시 |
| Frontend 렌더링 | `requestAnimationFrame` 60fps, 선형 보간으로 네트워크 주기와의 간극을 메움 |

흐름: **PLC 20Hz → OPC UA 구독 ~20Hz → WebSocket ≤25Hz → 60fps 렌더링(보간)**.
25Hz 상한은 PLC의 20Hz보다 높으므로 실제로는 병목이 되지 않는다(여유 마진).

## 9. 테스트 전략

| 계층 | 방식 | 검증 대상 |
|---|---|---|
| Virtual PLC (단위) | `tests/virtual_plc/` — `state_machine.transition()`을 3장 전이표의 모든 행(no-op 포함)에 대해 파라미터화 테스트. `command_processor`의 edge 감지·Ack 가드 로직을 fake `PLCMemory`로 검증. `sequence_manager.tick()`을 스크립트 가능한 `FakeRobotInterface` 테스트 더블로 검증. **OPC UA 서버·실시간 지연 없음** | 상태 머신 정확성, 핸드셰이크 가드 로직, Step 진행/정지 경계 로직 |
| OPC UA 계층 (통합) | `tests/opcua_integration/` — 임시 포트에 실제 `asyncua.Server`를 프로세스 내에서 띄우고 실제 `asyncua.Client`로 연결. 노드 트리가 [`opcua-nodes.md`](./opcua-nodes.md)와 일치하는지 browse로 확인, 구독이 PLC Memory 변경에 실제로 발화하는지, Execute 4단계 핸드셰이크가 end-to-end로 동작하는지 확인 | 프로토콜 수준 정확성 — 단위테스트로는 숨겨지기 쉬운 버그 |
| Backend | `tests/backend/` — FastAPI `TestClient`로 REST 엔드포인트(상태 코드/응답 바디)를 검증하되, OPC UA 클라이언트는 Robot Interface와 동일한 "교체 가능 인터페이스" 패턴을 가진 fake로 대체. 일부 테스트는 OPC UA 통합 하네스를 재사용해 실제 Virtual PLC로 fake/real 드리프트를 확인 | REST 계약, 커맨드 핸드셰이크 stepper 로직, 실PLC 상호운용성 |
| Frontend | MVP는 무거운 테스트 프레임워크 없이 수동 체크리스트: WS 연결 후 `full_status`로 UI가 채워지는지, Sequence 실행 시 시각적으로 예상 동작과 일치하는지, Step 중간에 Stop을 눌러도 현재 Step을 끝까지 마친 뒤 정지하는지, Reset이 컨트롤을 다시 활성화하는지, Virtual PLC 프로세스를 강제 종료했을 때 "연결 끊김"이 표시되고 포즈가 고정되는지 | End-to-end 시각적/행동적 정확성 |

### Phase별 검증 대응 (브리프 11장)

| Phase | 범위 | 검증 |
|---|---|---|
| 1 | Backend/Virtual PLC/Frontend 실행 환경 | 각 프로그램 독립 실행 확인 |
| 2 | OPC UA 통신 | `tests/opcua_integration/` — 연결, 노드 생성, Read/Write, Subscription |
| 3 | Virtual PLC 기능(Memory, Command, Sequence, Run/Stop/Reset, Error) | `tests/virtual_plc/` 단위테스트 |
| 4 | Backend REST API | `tests/backend/` |
| 5 | WebSocket | 수동/통합 테스트로 상태 변경이 Web에 실시간 도달하는지 확인 |
| 6 | Three.js + URDF | 정적 모델 표시 → Joint State 적용, 수동 체크리스트 |
| 7 | End-to-End 통합 | 브리프 10장 MVP 시나리오 통과, 수동 체크리스트(연결 끊김 포함) |
