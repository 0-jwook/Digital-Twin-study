declare module "urdf-loader" {
  import { LoadingManager, Material, Object3D } from "three";

  export class URDFJoint extends Object3D {
    jointType: string;
    setJointValue(...values: number[]): boolean;
  }

  export class URDFRobot extends Object3D {
    joints: Record<string, URDFJoint>;
    setJointValue(jointName: string, ...angle: number[]): boolean;
    setJointValues(values: Record<string, number>): boolean;
  }

  export default class URDFLoader {
    constructor(manager?: LoadingManager);
    packages: string | Record<string, string>;
    loadMeshCb: (
      path: string,
      manager: LoadingManager,
      material: Material,
      onComplete: (mesh: Object3D | null, err?: Error) => void,
    ) => void;
    load(
      urdfPath: string,
      onComplete: (robot: URDFRobot) => void,
      onProgress?: (event: ProgressEvent) => void,
      onError?: (err: Error) => void,
    ): void;
  }
}
