/** Fetch wrapper for docs/protocol.md section 1. Vite's dev server proxies
 * /api to the Backend (vite.config.ts); in production this is served from
 * the same origin as the Backend. */

export interface SequenceSummary {
  sequenceId: number;
  name: string;
  stepCount: number;
}

export interface SequenceStepDto {
  index: number;
  name: string;
}

export interface SequenceDetail {
  sequenceId: number;
  name: string;
  steps: SequenceStepDto[];
}

export interface RobotConfigResponse {
  mode: string;
  host: string;
  port: number;
  maxSpeed: number;
  activeMode: string;
  connectionOk: boolean;
  errorMessage: string | null;
}

export interface StatusResponse {
  plc: { status: string; errorCode: number; errorMessage: string | null; robotConnected: boolean };
  sequence: { sequenceId: number; currentStep: number; totalSteps: number; running: boolean; done: boolean };
  position: Record<"j1" | "j2" | "j3" | "j4" | "j5" | "j6", number>;
  connection: { connected: boolean; lastSeen: string | null };
  robotConfig: RobotConfigResponse;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}) as { detail?: string });
    throw new ApiError(body.detail ?? `HTTP ${res.status}`, res.status);
  }
  return (await res.json()) as T;
}

export const RestClient = {
  listSequences: () => request<SequenceSummary[]>("/sequences"),
  getSequence: (sequenceId: number) => request<SequenceDetail>(`/sequences/${sequenceId}`),
  startSequence: (sequenceId: number) =>
    request<{ accepted: boolean }>("/sequence/start", {
      method: "POST",
      body: JSON.stringify({ sequenceId }),
    }),
  stopSequence: () => request<{ accepted: boolean }>("/sequence/stop", { method: "POST" }),
  resetSequence: () => request<{ accepted: boolean }>("/sequence/reset", { method: "POST" }),
  getStatus: () => request<StatusResponse>("/status"),
  getRobotConfig: () => request<RobotConfigResponse>("/robot-config"),
  applyRobotConfig: (config: { mode: string; host: string; port: number; maxSpeed: number }) =>
    request<{ accepted: boolean }>("/robot-config", {
      method: "POST",
      body: JSON.stringify(config),
    }),
};
