import { Store } from "../network/store";

export interface SequenceState {
  sequenceId: number;
  currentStep: number;
  totalSteps: number;
  running: boolean;
  done: boolean;
}

export const sequenceStateStore = new Store<SequenceState>({
  sequenceId: -1,
  currentStep: 0,
  totalSteps: 0,
  running: false,
  done: false,
});
