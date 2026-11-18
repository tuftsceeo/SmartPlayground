/** The simulator for the runner: sim-room.js from ../Simulator. */
import { makeSimRoomSimulator } from './sim-core.js';

export const simRoomSimulator = makeSimRoomSimulator(() => import('../Simulator/sim-room.js'));
