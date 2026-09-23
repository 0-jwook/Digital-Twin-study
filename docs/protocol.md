# REST / WebSocket 프로토콜 — myCobot 280 Pi 디지털 트윈

Backend가 Web(Frontend)에 노출하는 HTTP REST API와 WebSocket 메시지 계약,
그리고 Sequence 데이터 구조를 정의한다. OPC UA 쪽 계약은
[`opcua-nodes.md`](./opcua-nodes.md), 상위 아키텍처는
[`architecture.md`](./architecture.md)를 참고한다.

## 1. REST API

| Method | Path | Body | 응답 | 상태 코드 |
|---|---|---|---|---|
| GET | `/api/sequences` | — | `[{ "sequenceId": 1, "name": "pick_and_place", "stepCount": 7 }]` | 200 |
| GET | `/api/sequences/{sequenceId}` | — | `{ "sequenceId": 1, "name": "pick_and_place", "steps": [{ "index": 0, "name": "approach" }, ...] }` | 200, 404(미지의 id) |
| POST | `/api/sequence/start` | `{ "sequenceId": 1 }` | `{ "accepted": true }` | 202, 404(미지의 id — 캐시된 카탈로그로 사전 확인), 409(PLC가 IDLE이 아니거나 다른 커맨드 핸드셰이크 진행 중) |
| POST | `/api/sequence/stop` | — | `{ "accepted": true }` | 202, 409(실행 중인 Sequence 없음) |
| POST | `/api/sequence/reset` | — | `{ "accepted": true }` | 202, 409(PLC가 STOPPED/ERROR가 아님) |
| GET | `/api/status` | — | 아래 참고 | 200 |

### `GET /api/status` 응답

초기 페이지 로드 및 WebSocket 재연결 시 폴백 조회에 사용한다. Backend 내부의
4개 분리된 상태 모델을 **응답 경계에서만** 하나의 JSON으로 투영한 것이며, 이는
직렬화 편의이지 내부 모델을 병합하는 것이 아니다([`architecture.md`](./architecture.md)
1장 참고).

```json
{
  "plc": {
    "status": "RUNNING",
    "errorCode": 0,
    "errorMessage": null,
    "robotConnected": true
  },
  "sequence": {
    "sequenceId": 1,
    "currentStep": 2,
    "totalSteps": 7,
    "running": true,
    "done": false
  },
  "position": { "j1": 0.0, "j2": -45.0, "j3": 30.0, "j4": 0.0, "j5": 60.0, "j6": 0.0 },
  "connection": { "connected": true, "lastSeen": "2026-09-23T10:15:30Z" }
}
```

409 응답은 Backend 측의 UX 가드일 뿐이다. 실제 권한은 여전히 Virtual PLC의
Command Processor/State Machine에 있으며, 부적절한 요청이 OPC UA까지
전달되더라도 PLC가 no-op으로 처리하고 Ack만 돌려준다
([`opcua-nodes.md`](./opcua-nodes.md) "4단계 커맨드 핸드셰이크" 참고).

## 2. WebSocket 프로토콜

엔드포인트: `/ws`. `type` 판별 필드를 가진 **개별 타입 메시지**로 나눈다 —
Position은 빈번/연속적으로 바뀌지만 State/Sequence/Error/Connection은 드물게,
이산적으로 바뀌므로, 하나의 메시지에 모두 합치면 상태가 안 변해도 20~25Hz로
전체를 재전송하게 되어 낭비다.

```json
{ "type": "position", "j1": 0.0, "j2": -45.0, "j3": 30.0, "j4": 0.0, "j5": 60.0, "j6": 0.0, "t": 1758619200123 }
```
```json
{ "type": "plc_state", "status": "RUNNING", "errorCode": 0, "errorMessage": null, "robotConnected": true }
```
```json
{ "type": "sequence_state", "sequenceId": 1, "currentStep": 2, "totalSteps": 7, "running": true, "done": false }
```
```json
{ "type": "connection_status", "connected": false, "lastSeen": "2026-09-23T10:15:30Z" }
```
```json
{ "type": "full_status", "plc": { ... }, "sequence": { ... }, "position": { ... }, "connection": { ... } }
```

`full_status`는 WebSocket 연결 직후 **1회만** 전송한다(`GET /api/status`와
동일한 내용). 이후의 모든 갱신은 위의 개별 타입 메시지로만 전달한다.

### 전송 주기 정책

- `position`: `WebSocketManager`가 마지막 전송 시각을 기준으로 **25Hz(40ms)
  상한**을 둔다. 40ms 창 안에 여러 OPC UA data-change 알림이 도착하면 가장 최근
  값만 전송한다(coalesce — 큐에 쌓아 나중에 다 보내는 방식이 아니다).
- `plc_state` / `sequence_state` / `connection_status`: **무제한, 변경 시 즉시**
  전송한다. 이산적인 이벤트는 대역폭보다 지연이 더 중요하기 때문이다.

주기 근거와 전체 흐름(PLC 20Hz → OPC UA 구독 → WebSocket ≤25Hz → 60fps 렌더링)은
[`architecture.md`](./architecture.md) 8장 참고.

## 3. Sequence 데이터 구조

### 단위

- **관절 위치: 도(degree)** — `pymycobot`의 `send_angles()`/`get_angles()`
  규약과 동일. Virtual PLC와 향후 실로봇 인터페이스가 같은 단위를 쓰게 되어
  전환 시 단위 변환 버그가 생기지 않는다.
- **속도: 백분율(0~100)** — `pymycobot`의 각도 이동 API의 `speed` 파라미터와
  동일. 실로봇 전환 시 `SequenceStep.speed` 값을 그대로 전달할 수 있다.

### 내부 구조 (Virtual PLC 내부, 영속화 계층 없음)

```text
SequenceStep:
    name: str
    joint_targets: dict[str, float]   # 키: "j1".."j6", 단위: 도
    speed: float                      # 0-100

Sequence:
    sequence_id: int
    name: str
    steps: list[SequenceStep]

SEQUENCE_TABLE: dict[int, Sequence] = {
    1: Sequence(1, "pick_and_place", [
        SequenceStep("approach",      {...}, 40),
        SequenceStep("descend",       {...}, 20),
        SequenceStep("grip",          {...}, 15),
        SequenceStep("lift",          {...}, 30),
        SequenceStep("move_to_place", {...}, 40),
        SequenceStep("release",       {...}, 15),
        SequenceStep("retract",       {...}, 30),
    ]),
    2: Sequence(2, "home", [
        SequenceStep("go_home", {...}, 30),
    ]),
}
```

`SEQUENCE_TABLE`은 Virtual PLC 프로세스 시작 시 모듈 레벨 상수로 로드되는
사전 정의 테이블이다(데이터베이스 없음 — "MVP 범위에서는 PLC 메모리 이상의
영속화를 두지 않는다"는 제약에 따름). 구체적인 관절 목표값(`joint_targets`)은
실제 myCobot 280 Pi 워크스페이스 좌표에 맞춰 구현 단계에서 확정한다.

### OPC UA로의 노출 방식

PLC 부팅 시 `Robot.Sequence.CatalogJson`을
`json.dumps([{sequenceId, name, steps:[{index, name} for step in steps]} for seq in SEQUENCE_TABLE.values()])`로
생성한다. `name`/`index`만 노출하고 `joint_targets`/`speed`는 절대 내보내지
않는다 — 이것이 "Sequence는 PLC가 소유하고 ID로만 참조한다"는 원칙을 OPC UA
계층에서 지키는 방법이다. Backend는 이 JSON을 1회성 read로 가져와
`GET /api/sequences`, `GET /api/sequences/{id}` 응답을 구성한다
([`architecture.md`](./architecture.md) 5장 "Sequence 목록/메타데이터 제공
방식" 참고).
