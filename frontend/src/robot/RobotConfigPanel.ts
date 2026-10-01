import { connectionStore } from "../network/ConnectionStore";
import { RestClient } from "../network/RestClient";
import { plcStateStore } from "../plc/PlcStateStore";
import { robotConfigStore } from "./RobotConfigStore";

export async function mountRobotConfigPanel(container: HTMLElement): Promise<void> {
  container.innerHTML = `
    <div class="panel-head">
      <span class="panel-title">Robot Interface</span>
      <span id="rc-active" class="chip"></span>
    </div>
    <div class="rc-grid">
      <select id="rc-mode">
        <option value="virtual">Virtual</option>
        <option value="real">Real Hardware</option>
      </select>
      <input id="rc-host" type="text" placeholder="Host (e.g. 172.20.10.14)" />
      <input id="rc-port" type="number" placeholder="Port" />
      <input id="rc-maxspeed" type="number" placeholder="Max speed" />
      <button id="rc-apply" class="btn btn-apply">Apply</button>
    </div>
    <span id="rc-error" class="error"></span>
  `;

  const modeSelect = container.querySelector<HTMLSelectElement>("#rc-mode")!;
  const hostInput = container.querySelector<HTMLInputElement>("#rc-host")!;
  const portInput = container.querySelector<HTMLInputElement>("#rc-port")!;
  const maxSpeedInput = container.querySelector<HTMLInputElement>("#rc-maxspeed")!;
  const applyBtn = container.querySelector<HTMLButtonElement>("#rc-apply")!;
  const activeEl = container.querySelector<HTMLElement>("#rc-active")!;
  const errorEl = container.querySelector<HTMLElement>("#rc-error")!;

  try {
    const config = await RestClient.getRobotConfig();
    robotConfigStore.set(config);
  } catch (err) {
    errorEl.textContent = `설정 조회 실패: ${(err as Error).message}`;
  }

  robotConfigStore.subscribe((config) => {
    // Don't clobber what the user is currently typing -- only sync fields
    // on first load / after our own apply, by checking they're not focused.
    if (document.activeElement !== modeSelect) modeSelect.value = config.mode;
    if (document.activeElement !== hostInput) hostInput.value = config.host;
    if (document.activeElement !== portInput) portInput.value = String(config.port);
    if (document.activeElement !== maxSpeedInput) maxSpeedInput.value = String(config.maxSpeed);

    const okText = config.connectionOk ? "OK" : `FAILED${config.errorMessage ? `: ${config.errorMessage}` : ""}`;
    activeEl.textContent = `active=${config.activeMode} (${okText})`;
    activeEl.className = `chip ${config.connectionOk ? "ok" : "bad"}`;
  });

  function updateDisabled(): void {
    const plc = plcStateStore.get();
    const conn = connectionStore.get();
    const disabled = !conn.connected || plc.status !== "IDLE";
    for (const el of [modeSelect, hostInput, portInput, maxSpeedInput, applyBtn]) {
      el.disabled = disabled;
    }
  }

  plcStateStore.subscribe(updateDisabled);
  connectionStore.subscribe(updateDisabled);

  applyBtn.addEventListener("click", async () => {
    const mode = modeSelect.value;
    if (mode === "real" && !window.confirm("실제 로봇이 움직일 수 있습니다. 계속할까요?")) {
      return;
    }

    errorEl.textContent = "";
    try {
      await RestClient.applyRobotConfig({
        mode,
        host: hostInput.value.trim(),
        port: Number(portInput.value) || 9000,
        maxSpeed: Number(maxSpeedInput.value) || 30,
      });
    } catch (err) {
      errorEl.textContent = (err as Error).message;
    }
  });
}
