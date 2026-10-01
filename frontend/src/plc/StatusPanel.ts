import { connectionStore } from "../network/ConnectionStore";
import type { JointAngles } from "../network/PositionBuffer";
import { plcStateStore } from "./PlcStateStore";
import { sequenceStateStore } from "./SequenceStateStore";

export interface StatusPanelHandle {
  updateJoints(angles: JointAngles): void;
}

export function mountStatusPanel(container: HTMLElement): StatusPanelHandle {
  container.innerHTML = `
    <div class="panel-head"><span class="panel-title">System Status</span></div>
    <div class="status-row"><span class="label">Connection</span><span id="sp-conn" class="value"></span></div>
    <div class="status-row"><span class="label">PLC State</span><span id="sp-status" class="value"></span></div>
    <div class="status-row"><span class="label">Step</span><span id="sp-step" class="value">-</span></div>
    <div class="joint-grid" id="sp-joints"></div>
    <div id="sp-error" class="error"></div>
  `;

  const connEl = container.querySelector<HTMLElement>("#sp-conn")!;
  const statusEl = container.querySelector<HTMLElement>("#sp-status")!;
  const stepEl = container.querySelector<HTMLElement>("#sp-step")!;
  const jointsEl = container.querySelector<HTMLElement>("#sp-joints")!;
  const errorEl = container.querySelector<HTMLElement>("#sp-error")!;

  connectionStore.subscribe((state) => {
    connEl.textContent = state.connected ? "CONNECTED" : "DISCONNECTED";
    connEl.className = `value ${state.connected ? "ok" : "bad"}`;
  });

  plcStateStore.subscribe((state) => {
    statusEl.textContent = state.status;
    statusEl.className = `value status-${state.status.toLowerCase()}`;
    errorEl.textContent = state.errorCode ? `E${state.errorCode}: ${state.errorMessage ?? ""}` : "";
  });

  sequenceStateStore.subscribe((state) => {
    stepEl.textContent = state.sequenceId >= 0 ? `${state.currentStep + 1} / ${state.totalSteps}` : "-";
  });

  return {
    updateJoints(angles: JointAngles): void {
      jointsEl.innerHTML = (Object.keys(angles) as (keyof JointAngles)[])
        .map((key) => `<div>${key.toUpperCase()} <b>${angles[key].toFixed(1)}&deg;</b></div>`)
        .join("");
    },
  };
}
