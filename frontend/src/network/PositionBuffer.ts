/** Bridges the ~20-25Hz WebSocket `position` cadence to 60fps rendering via
 * linear interpolation (docs/architecture.md section 6). */

export type JointAngles = Record<"j1" | "j2" | "j3" | "j4" | "j5" | "j6", number>;

const WINDOW_MS = 40; // matches the WS `position` throttle window

export class PositionBuffer {
  private prev: JointAngles = { j1: 0, j2: 0, j3: 0, j4: 0, j5: 0, j6: 0 };
  private target: JointAngles = { j1: 0, j2: 0, j3: 0, j4: 0, j5: 0, j6: 0 };
  private receivedAt = 0;

  push(angles: JointAngles): void {
    this.prev = this.getInterpolated();
    this.target = angles;
    this.receivedAt = performance.now();
  }

  getInterpolated(): JointAngles {
    const alpha = Math.min(Math.max((performance.now() - this.receivedAt) / WINDOW_MS, 0), 1);
    const lerp = (a: number, b: number) => a + (b - a) * alpha;
    return {
      j1: lerp(this.prev.j1, this.target.j1),
      j2: lerp(this.prev.j2, this.target.j2),
      j3: lerp(this.prev.j3, this.target.j3),
      j4: lerp(this.prev.j4, this.target.j4),
      j5: lerp(this.prev.j5, this.target.j5),
      j6: lerp(this.prev.j6, this.target.j6),
    };
  }
}
