import { SceneManager } from "./scene/SceneManager";
import { RobotModel } from "./robot/RobotModel";
import { PositionBuffer } from "./network/PositionBuffer";
import { WebSocketClient } from "./network/WebSocketClient";
import { RestClient } from "./network/RestClient";
import { connectionStore } from "./network/ConnectionStore";
import { plcStateStore } from "./plc/PlcStateStore";
import { sequenceStateStore } from "./plc/SequenceStateStore";
import { mountStatusPanel } from "./plc/StatusPanel";
import { mountSequencePanel } from "./sequence/SequencePanel";

const appContainer = document.getElementById("app")!;
const statusContainer = document.getElementById("status-panel")!;
const sequenceContainer = document.getElementById("sequence-panel")!;

const sceneManager = new SceneManager(appContainer);
const robotModel = new RobotModel();
const positionBuffer = new PositionBuffer();

const statusPanel = mountStatusPanel(statusContainer);
void mountSequencePanel(sequenceContainer);

robotModel.load(sceneManager.scene, () => {
  console.log("myCobot 280 Pi model loaded");
});

const wsClient = new WebSocketClient(positionBuffer);
wsClient.connect();

// One-shot REST snapshot so the HUD isn't blank before the first WebSocket
// full_status arrives (e.g. on a page refresh mid-session).
RestClient.getStatus()
  .then((status) => {
    plcStateStore.set(status.plc);
    sequenceStateStore.set(status.sequence);
    connectionStore.set(status.connection);
    positionBuffer.push(status.position);
  })
  .catch(() => {
    // The WebSocket's full_status message will arrive shortly regardless.
  });

function animate(): void {
  requestAnimationFrame(animate);
  const angles = positionBuffer.getInterpolated();
  robotModel.setJointAngles(angles);
  statusPanel.updateJoints(angles);
  sceneManager.render();
}
animate();
