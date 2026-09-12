/**
 * store.js -- flat mutable state + rAF-batched subscribers. Same shape as
 * Live_Page/WebApp2/js/state/store.js. Holds only what should trigger a DOM
 * rebuild; the big typed arrays (image data, labels, coverage, pixels) live
 * in state/doc.js instead -- see plan §App architecture.
 */

function loadUiMode() {
  try {
    const stored = localStorage.getItem("iconmaker.uiMode");
    if (stored === "advanced" || stored === "simple") return stored;
  } catch (_) {}
  return "simple";
}

export const state = {
  // source / icon identity
  iconName: null,
  sourcePath: null,
  mode: null, // 'exact' | 'quantize' | null
  maxSegments: 12,
  intensity: 0.3,

  // segmentation results (small: <=12 entries, fine to keep reactive)
  fills: [],
  decisions: [],
  cellsWon: [],
  problems: [],

  profileId: "matrix16", // target hardware; see pipeline/profiles.js
  sourceInfo: null, // {width, height, name} of the decoded original
  transformLabel: "", // human-readable summary of the applied crop/fit

  // UI
  uiMode: loadUiMode(), // 'simple' | 'advanced'
  activeTool: "pencil", // 'pencil' | 'eraser' | 'revert'
  showAdjust: false, // collapsible segmentation drawer
  hwDrawerOpen: false, // collapsible hardware/serial drawer (advanced)
  devicePanelOpen: false, // device popover anchored to top-bar plug button
  loading: false,
  loadError: null,
  brushColor: [255, 0, 149], // AUTHORED linear duty, not a hex string
  customPaletteColors: [], // duties added via the brush dropper / "+" -- persists across resegment of the same doc
  selectedFillIndex: null,
  statusText: "",

  // device
  deviceSupported: typeof navigator !== "undefined" && "serial" in navigator,
  deviceConnected: false, // serial port open
  deviceRunning: false, // icon_server.py attached (hello received)
  deviceCapabilities: { liveFrames: false, fileOps: false },
  deviceStatusText: "",
  deviceAtRepl: false, // board parked at '>>>' -- firmware not running
  deviceRestarting: false,
  deviceInstalling: false,
  deviceInstallProgress: null, // {current, total, file, status}
  devicePushEnabled: false,
  deviceTwelveV: false,
  deviceLastCurrentMa: null,
  deviceLastRefusal: null, // {estimatedMa, ceilingMa, suggestedIntensity}
  deviceIcons: [], // [{name, bytes}]
  deviceMemFree: null,
};

const renderCallbacks = new Set();
let renderScheduled = false;

export function onStateChange(callback) {
  renderCallbacks.add(callback);
  return () => renderCallbacks.delete(callback);
}

export function setState(updates) {
  Object.assign(state, updates);
  if (!renderScheduled) {
    renderScheduled = true;
    requestAnimationFrame(() => {
      renderCallbacks.forEach((cb) => cb(state));
      renderScheduled = false;
    });
  }
}
