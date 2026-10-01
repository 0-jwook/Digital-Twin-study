import { connectionStore } from "../network/ConnectionStore";
import { RestClient, SequenceSummary } from "../network/RestClient";
import { plcStateStore } from "../plc/PlcStateStore";

export async function mountSequencePanel(container: HTMLElement): Promise<void> {
  container.innerHTML = `
    <select id="seq-select"></select>
    <button id="seq-start" class="btn btn-start"><span class="btn-icon">▶</span>Start</button>
    <button id="seq-stop" class="btn btn-stop"><span class="btn-icon">■</span>Stop</button>
    <button id="seq-reset" class="btn btn-reset"><span class="btn-icon">↺</span>Reset</button>
    <span id="seq-error" class="error"></span>
  `;

  const select = container.querySelector<HTMLSelectElement>("#seq-select")!;
  const startBtn = container.querySelector<HTMLButtonElement>("#seq-start")!;
  const stopBtn = container.querySelector<HTMLButtonElement>("#seq-stop")!;
  const resetBtn = container.querySelector<HTMLButtonElement>("#seq-reset")!;
  const errorEl = container.querySelector<HTMLElement>("#seq-error")!;

  try {
    const sequences = await RestClient.listSequences();
    select.innerHTML = sequences
      .map((seq: SequenceSummary) => `<option value="${seq.sequenceId}">${seq.name} (${seq.stepCount} steps)</option>`)
      .join("");
  } catch (err) {
    errorEl.textContent = `Sequence 목록 조회 실패: ${(err as Error).message}`;
  }

  function updateButtons(): void {
    const plc = plcStateStore.get();
    const conn = connectionStore.get();
    const offline = !conn.connected;
    startBtn.disabled = offline || plc.status !== "IDLE";
    stopBtn.disabled = offline || plc.status !== "RUNNING";
    resetBtn.disabled = offline || !(plc.status === "STOPPED" || plc.status === "ERROR");
    select.disabled = offline || plc.status !== "IDLE";
  }

  plcStateStore.subscribe(updateButtons);
  connectionStore.subscribe(updateButtons);

  async function handle(action: () => Promise<unknown>): Promise<void> {
    errorEl.textContent = "";
    try {
      await action();
    } catch (err) {
      errorEl.textContent = (err as Error).message;
    }
  }

  startBtn.addEventListener("click", () => handle(() => RestClient.startSequence(Number(select.value))));
  stopBtn.addEventListener("click", () => handle(() => RestClient.stopSequence()));
  resetBtn.addEventListener("click", () => handle(() => RestClient.resetSequence()));
}
