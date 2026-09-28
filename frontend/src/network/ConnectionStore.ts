import { Store } from "./store";

export interface ConnectionState {
  connected: boolean;
  lastSeen: string | null;
}

export const connectionStore = new Store<ConnectionState>({ connected: false, lastSeen: null });
