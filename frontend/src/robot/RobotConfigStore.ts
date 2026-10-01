import { Store } from "../network/store";

export interface RobotConfigState {
  mode: string;
  host: string;
  port: number;
  maxSpeed: number;
  activeMode: string;
  connectionOk: boolean;
  errorMessage: string | null;
}

export const robotConfigStore = new Store<RobotConfigState>({
  mode: "virtual",
  host: "",
  port: 9000,
  maxSpeed: 30,
  activeMode: "virtual",
  connectionOk: true,
  errorMessage: null,
});
