/** Parses the type-discriminated messages from docs/protocol.md section 2
 * and dispatches them to PositionBuffer / PlcStateStore / SequenceStateStore
 * / ConnectionStore. Reconnects with a fixed delay if the socket drops --
 * the "freeze last pose + banner" UX for a dropped connection is Phase 7. */

import { connectionStore } from "./ConnectionStore";
import { PositionBuffer } from "./PositionBuffer";
import { plcStateStore } from "../plc/PlcStateStore";
import { sequenceStateStore } from "../plc/SequenceStateStore";

const RECONNECT_DELAY_MS = 2000;

type ServerMessage =
  | { type: "position"; j1: number; j2: number; j3: number; j4: number; j5: number; j6: number; t: number }
  | { type: "plc_state"; status: string; errorCode: number; errorMessage: string | null; robotConnected: boolean }
  | {
      type: "sequence_state";
      sequenceId: number;
      currentStep: number;
      totalSteps: number;
      running: boolean;
      done: boolean;
    }
  | { type: "connection_status"; connected: boolean; lastSeen: string | null }
  | {
      type: "full_status";
      plc: { status: string; errorCode: number; errorMessage: string | null; robotConnected: boolean };
      sequence: { sequenceId: number; currentStep: number; totalSteps: number; running: boolean; done: boolean };
      position: { j1: number; j2: number; j3: number; j4: number; j5: number; j6: number };
      connection: { connected: boolean; lastSeen: string | null };
    };

export class WebSocketClient {
  private ws: WebSocket | null = null;

  constructor(readonly positionBuffer: PositionBuffer) {}

  connect(): void {
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    this.ws = new WebSocket(`${protocol}://${location.host}/ws`);

    this.ws.onmessage = (event: MessageEvent<string>) => {
      let message: ServerMessage;
      try {
        message = JSON.parse(event.data) as ServerMessage;
      } catch {
        return; // ignore malformed frame
      }
      this.dispatch(message);
    };

    this.ws.onclose = () => {
      connectionStore.update({ connected: false });
      setTimeout(() => this.connect(), RECONNECT_DELAY_MS);
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  private dispatch(message: ServerMessage): void {
    switch (message.type) {
      case "position":
        this.positionBuffer.push({
          j1: message.j1,
          j2: message.j2,
          j3: message.j3,
          j4: message.j4,
          j5: message.j5,
          j6: message.j6,
        });
        break;
      case "plc_state":
        plcStateStore.set({
          status: message.status,
          errorCode: message.errorCode,
          errorMessage: message.errorMessage,
          robotConnected: message.robotConnected,
        });
        break;
      case "sequence_state":
        sequenceStateStore.set({
          sequenceId: message.sequenceId,
          currentStep: message.currentStep,
          totalSteps: message.totalSteps,
          running: message.running,
          done: message.done,
        });
        break;
      case "connection_status":
        connectionStore.set({ connected: message.connected, lastSeen: message.lastSeen });
        break;
      case "full_status":
        plcStateStore.set(message.plc);
        sequenceStateStore.set(message.sequence);
        connectionStore.set(message.connection);
        this.positionBuffer.push(message.position);
        break;
    }
  }
}
