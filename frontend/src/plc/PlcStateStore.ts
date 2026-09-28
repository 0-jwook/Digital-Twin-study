import { Store } from "../network/store";

export interface PlcState {
  status: string;
  errorCode: number;
  errorMessage: string | null;
  robotConnected: boolean;
}

export const plcStateStore = new Store<PlcState>({
  status: "IDLE",
  errorCode: 0,
  errorMessage: null,
  robotConnected: true,
});
