/**
 * Single source of truth for Joint Offset / Direction / Unit conversion
 * (docs/architecture.md section 6). PLC joint angles (degrees, J1-J6) map
 * to this URDF's actual revolute joint names, which are named by the link
 * pair they connect rather than "J1..J6" (community URDF convention) --
 * see frontend/public/robot/mycobot/ATTRIBUTION.md for the source model.
 *
 * offsetDeg/sign default to identity (0 / 1) -- calibrate visually against
 * a known pose (e.g. all-zero "home") once the model renders, and adjust
 * only this file, never the code that calls setJointAngles().
 */

export type JointKey = "j1" | "j2" | "j3" | "j4" | "j5" | "j6";

export interface JointMapEntry {
  urdfJointName: string;
  offsetDeg: number;
  sign: 1 | -1;
}

export const JOINT_MAP: Record<JointKey, JointMapEntry> = {
  j1: { urdfJointName: "joint2_to_joint1", offsetDeg: 0, sign: 1 },
  j2: { urdfJointName: "joint3_to_joint2", offsetDeg: 0, sign: 1 },
  j3: { urdfJointName: "joint4_to_joint3", offsetDeg: 0, sign: 1 },
  j4: { urdfJointName: "joint5_to_joint4", offsetDeg: 0, sign: 1 },
  j5: { urdfJointName: "joint6_to_joint5", offsetDeg: 0, sign: 1 },
  j6: { urdfJointName: "joint6output_to_joint6", offsetDeg: 0, sign: 1 },
};

export function degToRad(deg: number): number {
  return (deg * Math.PI) / 180;
}
