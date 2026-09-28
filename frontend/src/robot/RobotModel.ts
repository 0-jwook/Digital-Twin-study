import * as THREE from "three";
import URDFLoader, { URDFRobot } from "urdf-loader";

import { JOINT_MAP, JointKey, degToRad } from "./jointMap.config";

const URDF_PATH = "/robot/mycobot/mycobot_280_jn.urdf";

export class RobotModel {
  private robot: URDFRobot | null = null;

  load(scene: THREE.Scene, onLoaded: (robot: URDFRobot) => void): void {
    const manager = new THREE.LoadingManager();
    // urdf-loader already routes .dae meshes through three's ColladaLoader
    // internally (URDFLoader.js's defaultMeshLoader) -- no custom
    // loadMeshCb needed, and its callback signature is
    // (path, manager, material, onComplete), not (path, manager, onComplete).
    const loader = new URDFLoader(manager);

    loader.load(URDF_PATH, (robot) => {
      // URDF is Z-up, three.js is Y-up.
      robot.rotation.x = -Math.PI / 2;
      this.robot = robot;
      scene.add(robot);
      onLoaded(robot);
    });
  }

  setJointAngles(anglesDeg: Partial<Record<JointKey, number>>): void {
    if (!this.robot) return;
    const values: Record<string, number> = {};
    for (const key of Object.keys(anglesDeg) as JointKey[]) {
      const deg = anglesDeg[key];
      if (deg === undefined) continue;
      const map = JOINT_MAP[key];
      values[map.urdfJointName] = degToRad(deg * map.sign + map.offsetDeg);
    }
    this.robot.setJointValues(values);
  }
}
