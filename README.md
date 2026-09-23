# myCobot 280 Pi — PLC 기반 디지털 트윈

myCobot 280 Pi를 대상으로 PLC 중심 아키텍처의 디지털 트윈 시스템을 구축하는
프로젝트다. **현재 단계는 설계 문서 작성까지이며, 코드는 아직 작성되지 않았다.**

## 아키텍처 개요

```text
┌──────────────────────────┐
│ WEB (Three.js + TS)      │
│ myCobot URDF / HMI       │
└────────────┬─────────────┘
             │ HTTP / WebSocket
┌────────────▼─────────────┐
│ BACKEND (Python)         │
│ FastAPI / WebSocket      │
│ OPC UA Client            │
└────────────┬─────────────┘
             │ OPC UA (Subscription 우선)
┌────────────▼─────────────┐
│ VIRTUAL PLC (Python)     │
│ OPC UA Server            │
│ PLC Logic / Sequence     │
└────────────┬─────────────┘
             │ Robot Interface (교체 가능)
┌────────────▼─────────────┐
│ myCobot 280 Pi           │
│ (MVP: 가상 로봇)          │
└──────────────────────────┘
```

Backend는 **OPC UA 노드 모델에만 의존**하고 Virtual PLC의 내부 구현을 알지
못한다 — 이는 나중에 실제 PLC(내장 OPC UA Server)로 교체 가능하게 하기 위한
핵심 제약이다.

## 문서

| 문서 | 내용 |
|---|---|
| [`docs/architecture.md`](./docs/architecture.md) | 전체 아키텍처/데이터 흐름, PLC 상태 머신, Virtual PLC/Backend/Frontend 내부 구조, 디렉터리 구조, 갱신 주기, 테스트 전략 |
| [`docs/opcua-nodes.md`](./docs/opcua-nodes.md) | OPC UA Information Model — 노드 트리, 커맨드 핸드셰이크 프로토콜, ErrorCode 표 |
| [`docs/protocol.md`](./docs/protocol.md) | REST API, WebSocket 메시지 스키마, Sequence 데이터 구조 |

## 확정된 설계 결정

| 항목 | 결정 |
|---|---|
| Command 표현 방식 | Boolean 트리거 노드 + Ack/Busy 핸드셰이크 (OPC UA Method 아님) |
| Frontend 언어 | TypeScript |
| Stop 동작 | 현재 Step 완료 후 정지 (즉시 정지 아님) |
| Sequence 소유자 | Virtual PLC가 사전 정의 보유, Backend/Web은 SequenceId로만 참조 |
| OPC UA 라이브러리 | `asyncua` (Virtual PLC=Server, Backend=Client) |

## 디렉터리 구조 (예정)

```text
digital-twin/
├── backend/        app.py, api/, opcua/, websocket/, state/, models/
├── virtual_plc/    main.py, opcua/, plc/, sequence/, robot/
├── frontend/       index.html, src/{scene,robot,plc,sequence,network}/, public/robot/mycobot/
├── docs/           architecture.md, opcua-nodes.md, protocol.md
├── tests/          virtual_plc/, opcua_integration/, backend/
└── README.md
```

`backend/`, `virtual_plc/`, `frontend/`, `tests/`는 아직 생성되지 않았다 —
Phase 1(아래)부터 만든다.

## 개발 단계

| Phase | 내용 | 검증 |
|---|---|---|
| 1 | Backend / Virtual PLC / Frontend 실행 환경 | 각 프로그램 독립 실행 |
| 2 | OPC UA 통신 | 연결, 노드 생성, Read/Write, Subscription |
| 3 | Virtual PLC 기능 | Memory, Command, Sequence, Run/Stop/Reset, Error |
| 4 | Backend REST API | 설계된 API 전체 호출 |
| 5 | WebSocket | 상태 변경이 Web에 실시간 도달 |
| 6 | Three.js + URDF | 정적 모델 표시 후 Joint State 적용 |
| 7 | End-to-End 통합 | MVP 시나리오(아래) 통과 |

### MVP 시나리오

1. Web에서 3D 모델 확인 → Sequence 선택 → START
2. Backend가 명령 수신 → OPC UA Client로 Virtual PLC에 전달
3. Virtual PLC가 Sequence 실행 → Current Step / Joint State 갱신
4. Backend가 Subscription으로 상태 감지 → WebSocket으로 전달
5. Three.js가 Joint를 갱신하여 3D 로봇이 Sequence대로 움직임
6. Sequence 완료 → Web에 완료 상태 표시

MVP의 로봇은 가상 로봇(시간 기반 관절 보간)이며, 실제 myCobot 연동은 이후
단계에서 진행한다.

## 작업 방식

각 Phase를 시작하기 전에 다음 형식으로 보고 후 승인을 받는다.

```text
[작업] [변경 파일] [구현 내용] [데이터 흐름] [검증 방법]
```

다음 변경은 Phase 도중이라도 먼저 보고하고 승인 후 진행한다: OPC UA Node 구조,
API, 데이터 모델/Sequence 구조, 계층 간 책임, 디렉터리 구조.
