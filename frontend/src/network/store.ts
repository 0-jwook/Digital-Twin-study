/** Tiny observable used by the PLC/Sequence/Connection stores -- each stays
 * its own instance (never merged), matching docs/architecture.md's
 * never-merge-state-models rule. */
export class Store<T> {
  private listeners = new Set<(value: T) => void>();

  constructor(private value: T) {}

  get(): T {
    return this.value;
  }

  set(value: T): void {
    this.value = value;
    this.listeners.forEach((listener) => listener(value));
  }

  update(patch: Partial<T>): void {
    this.set({ ...this.value, ...patch });
  }

  subscribe(listener: (value: T) => void): () => void {
    this.listeners.add(listener);
    listener(this.value);
    return () => this.listeners.delete(listener);
  }
}
