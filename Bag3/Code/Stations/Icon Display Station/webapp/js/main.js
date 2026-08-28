/**
 * main.js -- App shell. Persistent canvases (source/segmented/preview/grid)
 * are built once and painted imperatively; everything else rebuilds via
 * innerHTML on state changes. See plan §App architecture for the tier
 * rationale (T0-T5) and why color/priority edits get fast local paths.
 */

import { state, setState, onStateChange } from "./state/store.js";
import { doc, resetDoc, releaseSource, overlayToObject, overlayFromObject, pushUndoSnapshot, popUndo } from "./state/doc.js";

import {
  decodeToWorking,
  decodeUrlToWorking,
  loadSource,
  renderWorking,
  defaultTransform,
} from "./pipeline/decode.js";
import { histogramFills } from "./pipeline/histogram.js";
import { labelMap, computeSegmentStats, buildCoverageBySeg, buildOpaqueCoverage, autoPropose } from "./pipeline/segment.js";
import { buildDecisions, toMapObj, serializeMap } from "./pipeline/mapio.js";
import { rasterize, applyOverlay, cellsWon, effectiveColor } from "./pipeline/raster.js";
import { enforceFloor, iconText, lint } from "./pipeline/emit.js";
import { renderPreview, previewToBlob } from "./pipeline/preview.js";
import { W, H, WORK, DEFAULT_MAX_SEGMENTS, applyProfile } from "./pipeline/constants.js";
import { getProfile, setProfile, profileForHello, listProfiles } from "./pipeline/profiles.js";
import { authoredToDisplay } from "./pipeline/ledDisplay.js";
import { ledSwatchHex } from "./pipeline/ledGamut.js";

import { createTopBar } from "./components/topBar.js";
import { createSimpleTopBar } from "./components/simple/simpleTopBar.js";
import { createSegmentList } from "./components/segmentList.js";
import { createSimpleSegmentList } from "./components/simple/simpleSegmentList.js";
import { createProblemsPanel } from "./components/problemsPanel.js";
import { createDeviceBar } from "./components/deviceBar.js";
import { createSimpleDeviceBar } from "./components/simple/simpleDeviceBar.js";
import { createBrightnessControls } from "./components/previewPane.js";
import { createImportControls } from "./components/sourcePane.js";
import { createToolRow } from "./components/toolRow.js";
import { createDocumentSwatches } from "./components/documentSwatches.js";
import { CropModal } from "./components/cropModal.js";
import { PalettePicker } from "./components/palettePicker.js";
import { showToast } from "./components/toast.js";
import { OFF_DUTY } from "./pipeline/ledGamut.js";
import { advancedLayoutHtml } from "./layouts/advancedLayout.js";
import { simpleLayoutHtml } from "./layouts/simpleLayout.js";

import { DeviceLink } from "./device/deviceLink.js";
import { FrameThrottle, suggestSafeIntensity } from "./device/frameThrottle.js";
import { SerialMonitor } from "./components/serialMonitor.js";
import { logInfo, logError } from "./device/serialLog.js";

const FIXTURES = ["apple", "cherries", "grapes", "lemon", "orange", "watermelon"];
const GRID_BACKING = 640;

function downloadText(filename, text, mime) {
  downloadBlob(filename, new Blob([text], { type: mime }));
}

/** Array<[r,g,b]> (256 entries) -> Uint8Array(768), row-major -- the wire frame shape. */
function flattenPixels(pixels) {
  const out = new Uint8Array(768);
  for (let i = 0; i < 256; i++) {
    const [r, g, b] = pixels[i];
    out[i * 3] = r;
    out[i * 3 + 1] = g;
    out[i * 3 + 2] = b;
  }
  return out;
}

function describeTransform(t) {
  if (!t) return "";
  if (t.crop) return `crop ${Math.round(t.crop.width)}×${Math.round(t.crop.height)}`;
  return { contain: "whole image", cover: "fill square", stretch: "stretched" }[t.mode] || t.mode;
}

function downloadBlob(filename, blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

class App {
  constructor() {
    this.root = document.getElementById("root");
    this.painting = false;
    this.device = new DeviceLink();
    this.throttle = new FrameThrottle(this.device);
    this.throttle.setProfile(getProfile());
    this._intensityInFlight = false;
    this._intensityLatest = null;
    this.crop = new CropModal();
    this.palette = new PalettePicker();
    this.monitor = new SerialMonitor({
      onProbe: () => this.probeDevice(),
      onSendRaw: (text) => this.sendRawToDevice(text),
      onRestart: () => this.restartDeviceFirmware(),
      onConnect: () => this.connectDevice(),
      onDisconnect: () => this.disconnectDevice(),
    });
    this.wireDevice();
    this.createCanvases();
    this.buildShell();
    this.applyMonitorVisibility();
    onStateChange(() => this.renderReactive());
    this.renderReactive();
    this.loadFixture("apple").catch((e) => showToast(String(e.message || e), { kind: "error" }));
  }

  // ── device wiring ───────────────────────────────────────────────────
  // Connection is event-driven, not request/reply -- see deviceLink.js's
  // docstring. connect() only opens the port; whether icon_server.py is
  // actually running is reported later, asynchronously, via 'hello'
  // (mirrors Live_Page/WebApp2's mpy/hub_serial.py + main.py "ready"
  // handshake pattern -- never block the UI on a synchronous probe that
  // can race a device reset).
  wireDevice() {
    this.device.on("hello", (info) => {
      setState({ deviceRunning: true, deviceCapabilities: this.device.capabilities });
      // The board reports its own geometry, so connecting one generally
      // selects the right profile without the user choosing.
      const match = profileForHello(info);
      if (match && match.id !== getProfile().id) {
        logInfo(`device reports ${info.w}x${info.h} -- switching profile to ${match.label}`);
        this.changeProfile(match.id);
      }
      this.refreshDeviceIcons();
    });
    this.device.on("heartbeat", (obj) => setState({ deviceMemFree: obj.mem }));
    this.device.on("fatal", (obj) => showToast(`device error: ${obj.msg}`, { kind: "error" }));
    this.device.on("bye", () =>
      setState({ deviceRunning: false, devicePushEnabled: false, deviceAtRepl: true })
    );
    // Board parked at the MicroPython prompt: firmware isn't running, so it
    // will only echo commands. deviceLink attempts one automatic restart;
    // the UI shows a manual button either way.
    this.device.on("repl", () => setState({ deviceRunning: false, devicePushEnabled: false, deviceAtRepl: true }));
    this.device.on("hello", () => setState({ deviceAtRepl: false }));
    this.device.on("error", (obj) => {
      if (obj.code) showToast(`device: ${obj.code}`, { kind: "error" });
    });
  }

  async connectDevice() {
    try {
      await this.device.connect();
      // deviceRunning stays false until 'hello' actually arrives (wireDevice
      // above) -- could be near-instant (device reset on connect) or take a
      // few seconds (already running, answering the proactive probe).
      setState({ deviceConnected: true, deviceRunning: false });
    } catch (e) {
      showToast(String(e.message || e), { kind: "error" });
    }
  }

  async installDeviceFirmware() {
    setState({ deviceInstalling: true, deviceInstallProgress: null });
    try {
      await this.device.installFirmware((progress) => setState({ deviceInstallProgress: progress }));
      // deviceRunning flips via the 'hello' listener once the freshly
      // rebooted firmware announces itself -- just clear the progress UI here.
      setState({ deviceInstalling: false, deviceInstallProgress: null });
      showToast("Firmware installed", { kind: "success" });
    } catch (e) {
      setState({ deviceInstalling: false, deviceInstallProgress: null });
      showToast(String(e.message || e), { kind: "error" });
    }
  }

  async restartDeviceFirmware() {
    if (!this.device.isConnected()) {
      logError("Restart: not connected -- click 'Connect device' first.");
      return;
    }
    setState({ deviceRestarting: true });
    try {
      const ok = await this.device.restartFirmware();
      setState({ deviceRestarting: false });
      showToast(ok ? "Firmware restarted" : "No response after restart -- see Serial Monitor", {
        kind: ok ? "success" : "error",
      });
    } catch (e) {
      setState({ deviceRestarting: false });
      showToast(String(e.message || e), { kind: "error" });
    }
  }

  /**
   * Switch target hardware. Geometry constants are live bindings, but
   * nothing recomputes on its own: the persistent canvases are sized in
   * WORK/grid units and the pipeline has to re-run from the decoded source.
   */
  changeProfile(id) {
    const p = setProfile(id);
    applyProfile(p);
    this.throttle.setProfile(p);
    this.palette.invalidate();

    // Persistent canvases were sized for the old profile.
    for (const c of [this.sourceCanvas, this.segmentedCanvas]) {
      c.width = WORK;
      c.height = WORK;
    }
    this.resizeGridCanvas();

    setState({ profileId: p.id, maxSegments: p.maxSegments });

    if (doc.source) {
      doc.transform = doc.transform || defaultTransform(doc.source);
      const { imageData } = renderWorking(doc.source, doc.transform);
      this.applyLoad(imageData, null, p.maxSegments, state.iconName, state.sourcePath);
    } else {
      this.loadFixture("apple").catch((e) => showToast(String(e.message || e), { kind: "error" }));
    }
  }

  async probeDevice() {
    if (!this.device.isConnected()) {
      logError("Probe: not connected -- click 'Connect device' first.");
      return;
    }
    try {
      await this.device.probe();
    } catch (e) {
      logError(`probe failed: ${e.message}`);
    }
  }

  async sendRawToDevice(text) {
    if (!this.device.isConnected()) {
      logError("Send: not connected -- click 'Connect device' first.");
      return;
    }
    try {
      await this.device.sendRaw(text);
    } catch (e) {
      logError(`send failed: ${e.message}`);
    }
  }

  async disconnectDevice() {
    await this.device.disconnect();
    setState({
      deviceConnected: false,
      deviceRunning: false,
      devicePushEnabled: false,
      deviceCapabilities: { liveFrames: false, fileOps: false },
      deviceIcons: [],
      deviceLastRefusal: null,
      deviceLastCurrentMa: null,
    });
  }

  toggleLivePush(on) {
    setState({ devicePushEnabled: on, deviceLastRefusal: null });
    if (on) this.maybePushLiveFrame(true);
  }

  toggleTwelveV(on) {
    this.throttle.setTwelveVMode(on);
    setState({ deviceTwelveV: on, deviceLastRefusal: null });
  }

  async refreshDeviceIcons() {
    try {
      const list = await this.device.listIcons();
      setState({ deviceIcons: list });
    } catch (e) {
      showToast(String(e.message || e), { kind: "error" });
    }
  }

  async loadFromDevice(name) {
    try {
      // Ask the device to draw it (so what you're editing matches what's
      // shown), then pull it in as an overlay-only "imported" document --
      // there's no source PNG for an on-device icon, only its 256 pixels.
      await this.device.showIcon(name);
      showToast(`showing ${name} on the device`, { kind: "success" });
    } catch (e) {
      showToast(String(e.message || e), { kind: "error" });
    }
  }

  async deleteFromDevice(name) {
    try {
      await this.device.deleteIcon(name);
      this.refreshDeviceIcons();
    } catch (e) {
      showToast(String(e.message || e), { kind: "error" });
    }
  }

  async saveCurrentToDevice() {
    if (!doc.pixels) return;
    try {
      const frame = flattenPixels(doc.pixels);
      await this.device.saveIcon(state.iconName || "icon", frame, { overwrite: true });
      showToast(`saved ${state.iconName} to device`, { kind: "success" });
      this.refreshDeviceIcons();
    } catch (e) {
      showToast(String(e.message || e), { kind: "error" });
    }
  }

  // ── live push ───────────────────────────────────────────────────────
  maybePushLiveFrame(force = false) {
    if (!doc.pixels) return;
    if (!state.deviceRunning || !state.devicePushEnabled) return;
    if (!this.device.capabilities.liveFrames) return;
    const authored = flattenPixels(doc.pixels);
    const scaled = authored.map((c) => Math.trunc(c * state.intensity));
    const result = this.throttle.request(authored, scaled);
    if (result.refused) {
      const now = Date.now();
      if (force || !this._lastRefusalToast || now - this._lastRefusalToast > 3000) {
        this._lastRefusalToast = now;
        setState({
          deviceLastRefusal: {
            estimatedMa: result.estimatedMa,
            ceilingMa: result.ceilingMa,
            suggestedIntensity: suggestSafeIntensity(authored, result.ceilingMa, state.intensity),
          },
        });
      }
    } else {
      setState({ deviceLastCurrentMa: result.estimatedMa, deviceLastRefusal: null });
    }
  }

  applySuggestedIntensity(v) {
    this.commitIntensity(v);
    setState({ deviceLastRefusal: null });
  }

  flashAnyway() {
    if (!doc.pixels) return;
    const authored = flattenPixels(doc.pixels);
    this.throttle.flashAnyway(authored, null);
  }

  pushIntensityToDevice(v) {
    if (!state.deviceRunning || !this.device.capabilities.liveFrames) return;
    if (this._intensityInFlight) {
      this._intensityLatest = v;
      return;
    }
    this._intensityInFlight = true;
    this.device
      .setIntensity(v)
      .catch(() => {})
      .finally(() => {
        this._intensityInFlight = false;
        if (this._intensityLatest !== null && this._intensityLatest !== v) {
          const next = this._intensityLatest;
          this._intensityLatest = null;
          this.pushIntensityToDevice(next);
        } else {
          this._intensityLatest = null;
        }
      });
  }

  // ── shell: layout rebuilds on mode switch; canvases persist ─────────────
  createCanvases() {
    this.sourceCanvas = document.createElement("canvas");
    this.sourceCanvas.id = "sourceCanvas";
    this.sourceCanvas.className = "pixelated bg-neutral-900 rounded canvas-source";
    this.sourceCanvas.width = WORK;
    this.sourceCanvas.height = WORK;

    this.segmentedCanvas = document.createElement("canvas");
    this.segmentedCanvas.id = "segmentedCanvas";
    this.segmentedCanvas.className = "pixelated bg-neutral-900 rounded canvas-source";
    this.segmentedCanvas.width = WORK;
    this.segmentedCanvas.height = WORK;

    this.previewCanvas = document.createElement("canvas");
    this.previewCanvas.id = "previewCanvas";
    this.previewCanvas.className = "pixelated rounded canvas-preview";
    this.previewCanvas.width = 384;
    this.previewCanvas.height = 384;

    this.gridCanvas = document.createElement("canvas");
    this.gridCanvas.id = "gridCanvas";
    this.gridCanvas.className = "pixelated bg-neutral-900 rounded";
    this.resizeGridCanvas();

    this.wireGridCanvas();
  }

  resizeGridCanvas() {
    this.gridCanvas.width = GRID_BACKING;
    this.gridCanvas.height = GRID_BACKING;
  }

  buildShell() {
    const html = state.uiMode === "simple" ? simpleLayoutHtml() : advancedLayoutHtml();
    this.root.innerHTML = html;

    this.topBarMount = this.root.querySelector("#topBarMount");
    this.importMount = this.root.querySelector("#importMount");
    this.segmentListMount = this.root.querySelector("#segmentListMount");
    this.brightnessMount = this.root.querySelector("#brightnessMount");
    this.gridControlsMount = this.root.querySelector("#gridControlsMount");
    this.problemsMount = this.root.querySelector("#problemsMount");
    this.deviceMount = this.root.querySelector("#deviceMount");

    this.adoptCanvases();
  }

  adoptCanvases() {
    this.root.querySelector('[data-canvas-slot="source"]').appendChild(this.sourceCanvas);
    this.root.querySelector('[data-canvas-slot="segmented"]').appendChild(this.segmentedCanvas);
    this.root.querySelector('[data-canvas-slot="preview"]').appendChild(this.previewCanvas);
    this.root.querySelector('[data-canvas-slot="grid"]').appendChild(this.gridCanvas);
  }

  setUiMode(next) {
    if (next === state.uiMode) return;
    if (this.crop.el) return;
    localStorage.setItem("iconmaker.uiMode", next);
    state.uiMode = next;
    this.palette.close();
    this.buildShell();
    this.renderReactive();
    this.applyMonitorVisibility();
    this.paintAll();
  }

  applyMonitorVisibility() {
    const hide = state.uiMode === "simple";
    this.monitor.root.classList.toggle("hidden", hide);
    if (hide) {
      document.body.style.paddingBottom = "";
    } else if (this.monitor.open) {
      requestAnimationFrame(() => {
        document.body.style.paddingBottom = `${this.monitor.root.offsetHeight}px`;
      });
    }
  }

  // ── reactive panels: rebuilt on every setState ─────────────────────────
  renderReactive() {
    const simple = state.uiMode === "simple";
    const cropOpen = !!this.crop.el;
    const brushPalette = (anchor) =>
      this.palette.open(anchor, state.brushColor, state.intensity, (duty) => setState({ brushColor: duty }));
    const segmentPalette = (i, anchor) =>
      this.palette.open(anchor, state.decisions[i]?.color, state.intensity, (duty) =>
        this.commitDecisionPatch(i, { color: duty })
      );

    this.topBarMount.innerHTML = "";
    this.topBarMount.appendChild(
      simple
        ? createSimpleTopBar(state, {
            onMaxSegmentsChange: (n) => this.changeMaxSegments(n),
            onExportIcon: () => this.exportIcon(),
            onProfileChange: (id) => this.changeProfile(id),
            onIconNameChange: (name) => setState({ iconName: name }),
            onUiModeChange: (mode) => this.setUiMode(mode),
            cropOpen,
          })
        : createTopBar(state, {
            onMaxSegmentsChange: (n) => this.changeMaxSegments(n),
            onSaveMap: () => this.exportMap(),
            onExportIcon: () => this.exportIcon(),
            onDownloadPreview: () => this.exportPreview(),
            onProfileChange: (id) => this.changeProfile(id),
            onLoadFixture: (name) => this.loadFixture(name).catch((e) => showToast(String(e.message || e), { kind: "error" })),
            onUiModeChange: (mode) => this.setUiMode(mode),
            cropOpen,
          })
    );

    this.importMount.innerHTML = "";
    this.importMount.appendChild(
      createImportControls(state, {
        onFilePicked: (file) => this.loadFile(file).catch((e) => showToast(String(e.message || e), { kind: "error" })),
        onOpenCrop: () => this.openCropTool(),
        onLoadFixture: (name) => this.loadFixture(name).catch((e) => showToast(String(e.message || e), { kind: "error" })),
      })
    );

    this.segmentListMount.innerHTML = "";
    this.segmentListMount.appendChild(
      simple
        ? createSimpleSegmentList(state, {
            onRoleChange: (i, role) => this.onRoleChange(i, role),
            onOpenPalette: segmentPalette,
          })
        : createSegmentList(state, {
            onRoleChange: (i, role) => this.onRoleChange(i, role),
            onMergeChange: (i, target) => this.commitDecisionPatch(i, { merge_into: target }),
            onOpenPalette: segmentPalette,
            onPriorityInput: (i, val) => this.livePriorityInput(i, val),
            onPriorityCommit: (i, val) => this.commitDecisionPatch(i, { priority: val }),
          })
    );

    this.brightnessMount.innerHTML = "";
    this.brightnessMount.appendChild(
      createBrightnessControls(state, {
        onIntensityInput: (v) => this.liveIntensityInput(v),
        onIntensityCommit: (v) => this.commitIntensity(v),
      })
    );

    this.gridControlsMount.innerHTML = "";
    const swatches = createDocumentSwatches(state, {
      onPick: (duty) => setState({ brushColor: duty, activeTool: "pencil" }),
    });
    const tools = createToolRow(state, {
      onToolChange: (tool) => setState({ activeTool: tool }),
      onUndo: () => this.undo(),
      onOpenBrushPalette: brushPalette,
    });
    this.gridControlsMount.appendChild(swatches);
    this.gridControlsMount.appendChild(tools);

    this.problemsMount.innerHTML = "";
    this.problemsMount.appendChild(createProblemsPanel(state));

    this.deviceMount.innerHTML = "";
    this.deviceMount.appendChild(
      simple
        ? createSimpleDeviceBar(state, {
            onConnect: () => this.connectDevice(),
            onDisconnect: () => this.disconnectDevice(),
            onToggleLivePush: (on) => this.toggleLivePush(on),
            onRefreshIcons: () => this.refreshDeviceIcons(),
            onLoadFromDevice: (name) => this.loadFromDevice(name),
            onDeleteFromDevice: (name) => this.deleteFromDevice(name),
            onSaveToDevice: () => this.saveCurrentToDevice(),
            onApplySuggestedIntensity: (v) => this.applySuggestedIntensity(v),
          })
        : createDeviceBar(state, {
            onConnect: () => this.connectDevice(),
            onInstall: () => this.installDeviceFirmware(),
            onRestart: () => this.restartDeviceFirmware(),
            onDisconnect: () => this.disconnectDevice(),
            onToggleLivePush: (on) => this.toggleLivePush(on),
            onToggleTwelveV: (on) => this.toggleTwelveV(on),
            onRefreshIcons: () => this.refreshDeviceIcons(),
            onLoadFromDevice: (name) => this.loadFromDevice(name),
            onDeleteFromDevice: (name) => this.deleteFromDevice(name),
            onSaveToDevice: () => this.saveCurrentToDevice(),
            onApplySuggestedIntensity: (v) => this.applySuggestedIntensity(v),
            onFlashAnyway: () => this.flashAnyway(),
          })
    );

    this.monitor?.setDeviceState({
      connected: state.deviceConnected,
      running: state.deviceRunning,
      atRepl: state.deviceAtRepl,
    });

    window.lucide?.createIcons?.();
  }

  // ── tiers ───────────────────────────────────────────────────────────
  runTier2(maxSegments) {
    const { fills, mode } = histogramFills(doc.imageData, { maxSegments });
    const nSegs = fills.length;
    const labels = labelMap(doc.imageData, fills);
    const stats = computeSegmentStats(labels, nSegs);
    doc.labels = labels;
    doc.coverageBySeg = buildCoverageBySeg(stats.covCounts, nSegs);
    doc.opaqueCoverage = buildOpaqueCoverage(stats.opaqueCounts);
    doc.ringMatch = stats.ringMatch;
    doc.ringTotal = stats.ringTotal;
    doc.bgMatch = stats.bgMatch;
    return { fills, mode, nSegs };
  }

  runTier4() {
    const { winner, pixels: rasterPixels } = rasterize(doc.coverageBySeg, state.decisions);
    doc.winner = winner;
    doc.rasterPixels = rasterPixels;
    const overlaid = applyOverlay(rasterPixels, doc.overlay);
    doc.pixels = enforceFloor(overlaid);
  }

  runTier5() {
    const won = cellsWon(doc.coverageBySeg, state.decisions);
    const problems = lint(doc.pixels, state.fills, state.decisions, won, state.intensity);
    return { won, problems };
  }

  /** Color-only fast path: doesn't touch winner-take-all, just re-maps winner->color. */
  rebuildPixelsFromWinner() {
    const pixels = new Array(W * H);
    for (let c = 0; c < W * H; c++) {
      const seg = doc.winner[c];
      pixels[c] = seg === -1 ? [0, 0, 0] : effectiveColor(state.decisions, seg) || [0, 0, 0];
    }
    doc.rasterPixels = pixels;
    const overlaid = applyOverlay(pixels, doc.overlay);
    doc.pixels = enforceFloor(overlaid);
  }

  // ── load / resegment ────────────────────────────────────────────────
  async loadFixture(name) {
    setState({ loading: true, statusText: `loading ${name}…` });
    releaseSource();
    const { imageData, source, transform } = await decodeUrlToWorking(`../assets/${name}.png`);
    doc.source = source;
    doc.transform = transform;
    let existingMap = null;
    try {
      const res = await fetch(`../maps/${name}.json`);
      if (res.ok) existingMap = await res.json();
    } catch {
      /* no map yet -- fine */
    }
    this.applyLoad(imageData, existingMap, existingMap?.max_segments, name, `assets/${name}.png`);
  }

  async loadFile(file) {
    setState({ loading: true, statusText: `loading ${file.name}…` });
    releaseSource();
    const source = await loadSource(file);
    doc.source = source;
    const name = file.name.replace(/\.[^.]+$/, "").replace(/[^a-z0-9_]+/gi, "_").toLowerCase();

    // A non-square import has to be framed somehow; open the crop tool right
    // away rather than silently letterboxing and letting the user discover it.
    const needsFraming = source.width !== source.height;
    const xform = defaultTransform(source);
    if (needsFraming) {
      xform.mode = "cover"; // sensible starting point the dialog can override
    }
    doc.transform = xform;
    const { imageData } = renderWorking(source, xform);
    this.applyLoad(imageData, null, DEFAULT_MAX_SEGMENTS, name, null);

    if (needsFraming) this.openCropTool();
  }

  /** Re-frame the already-decoded source; re-runs the pipeline on Apply. */
  openCropTool() {
    if (!doc.source) {
      showToast("Load an image first", { kind: "error" });
      return;
    }
    this.crop.open(doc.source, doc.transform || defaultTransform(doc.source), (xform) => {
      doc.transform = xform;
      const { imageData } = renderWorking(doc.source, xform);
      // Keep the current decisions/overlay across a re-crop where possible:
      // segment RGB keys often survive a reframing of the same artwork.
      const pseudoMap = state.mode
        ? toMapObj(state.sourcePath, state.fills, state.decisions, overlayToObject(doc.overlay), state.intensity, state.maxSegments, false)
        : null;
      this.applyLoad(imageData, pseudoMap, state.maxSegments, state.iconName, state.sourcePath);
    });
  }

  changeMaxSegments(n) {
    if (!doc.imageData) return;
    const pseudoMap = toMapObj(state.sourcePath, state.fills, state.decisions, overlayToObject(doc.overlay), state.intensity, n, false);
    this.applyLoad(doc.imageData, pseudoMap, n, state.iconName, state.sourcePath);
  }

  applyLoad(imageData, existingMap, maxSegmentsOverride, name, sourcePath) {
    resetDoc();
    doc.imageData = imageData;
    doc.existingMap = existingMap;
    const maxSegments = maxSegmentsOverride ?? existingMap?.max_segments ?? DEFAULT_MAX_SEGMENTS;

    const { fills, mode, nSegs } = this.runTier2(maxSegments);
    const proposed = autoPropose(fills, nSegs, doc.ringMatch, doc.ringTotal, doc.bgMatch);
    const { decisions, overlay, intensity } = buildDecisions(fills, proposed, existingMap);
    doc.overlay = overlayFromObject(overlay);

    state.fills = fills;
    state.decisions = decisions;
    this.runTier4();
    const { won, problems } = this.runTier5();

    setState({
      iconName: name,
      sourcePath,
      mode,
      maxSegments,
      intensity,
      fills,
      decisions,
      cellsWon: won,
      problems,
      loading: false,
      loadError: null,
      statusText: `loaded ${name}`,
      sourceInfo: doc.source ? { width: doc.source.width, height: doc.source.height } : null,
      transformLabel: describeTransform(doc.transform),
    });
    this.paintAll();
  }

  // ── decision edits ──────────────────────────────────────────────────
  onRoleChange(i, role) {
    const d = state.decisions[i];
    const patch = { role };
    if (role === "color" && !d.color) patch.color = state.fills[i].rgb.slice();
    if (role === "merge" && (d.merge_into === undefined || d.merge_into === i)) {
      patch.merge_into = i === 0 ? (state.fills.length > 1 ? 1 : 0) : 0;
    }
    this.commitDecisionPatch(i, patch);
  }

  commitDecisionPatch(i, patch) {
    state.decisions[i] = { ...state.decisions[i], ...patch };
    this.runTier4();
    const { won, problems } = this.runTier5();
    setState({ decisions: state.decisions, cellsWon: won, problems });
    this.paintAll();
  }

  liveColorInput(i, rgb) {
    state.decisions[i] = { ...state.decisions[i], color: rgb };
    this.rebuildPixelsFromWinner();
    this.refreshOutputs();
  }

  livePriorityInput(i, val) {
    state.decisions[i] = { ...state.decisions[i], priority: val };
    this.runTier4();
    this.refreshOutputs();
  }

  liveIntensityInput(v) {
    state.intensity = v;
    this.paintPreview();
    this.pushIntensityToDevice(v);
    this.maybePushLiveFrame(); // re-check the power gate at the new brightness
  }

  commitIntensity(v) {
    state.intensity = v;
    this.palette.invalidate(); // fewer colours are distinguishable when dimmer
    const { problems } = this.runTier5();
    setState({ intensity: v, problems });
    this.pushIntensityToDevice(v);
  }

  /** Repaint preview+grid and push a live frame if the device link is armed. */
  refreshOutputs() {
    this.paintPreview();
    this.paintGrid();
    this.maybePushLiveFrame();
  }

  // ── grid painting ───────────────────────────────────────────────────
  applyTool(idx) {
    const t = state.activeTool;
    if (t === "revert") doc.overlay.delete(idx);
    else if (t === "eraser") doc.overlay.set(idx, OFF_DUTY.slice());
    else doc.overlay.set(idx, state.brushColor.slice());
    this.recomputePixelsFromOverlay();
  }

  wireGridCanvas() {
    const canvas = this.gridCanvas;
    const cellAt = (e) => {
      const rect = canvas.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * W;
      const y = ((e.clientY - rect.top) / rect.height) * H;
      const col = Math.max(0, Math.min(W - 1, Math.floor(x)));
      const row = Math.max(0, Math.min(H - 1, Math.floor(y)));
      return row * W + col;
    };

    canvas.addEventListener("mousedown", (e) => {
      if (!doc.pixels) return;
      this.painting = true;
      pushUndoSnapshot();
      this.applyTool(cellAt(e));
    });
    canvas.addEventListener("mousemove", (e) => {
      if (!this.painting || !doc.pixels) return;
      this.applyTool(cellAt(e));
    });
    window.addEventListener("mouseup", () => {
      if (this.painting) {
        this.painting = false;
        const { problems } = this.runTier5();
        setState({ problems });
      }
    });
    canvas.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      if (!doc.pixels) return;
      pushUndoSnapshot();
      doc.overlay.delete(cellAt(e));
      this.recomputePixelsFromOverlay();
      const { problems } = this.runTier5();
      setState({ problems });
    });
  }

  recomputePixelsFromOverlay() {
    const overlaid = applyOverlay(doc.rasterPixels, doc.overlay);
    doc.pixels = enforceFloor(overlaid);
    this.refreshOutputs();
  }

  undo() {
    if (!popUndo()) return;
    this.recomputePixelsFromOverlay();
    const { problems } = this.runTier5();
    setState({ problems });
  }

  // ── canvas painting ─────────────────────────────────────────────────
  paintAll() {
    this.paintSource();
    this.paintSegmented();
    this.paintPreview();
    this.paintGrid();
    this.maybePushLiveFrame();
  }

  paintSource() {
    const ctx = this.sourceCanvas.getContext("2d");
    if (!doc.imageData) {
      ctx.clearRect(0, 0, WORK, WORK);
      return;
    }
    ctx.putImageData(doc.imageData, 0, 0);
  }

  paintSegmented() {
    const ctx = this.segmentedCanvas.getContext("2d");
    if (!doc.labels || !doc.imageData) {
      ctx.clearRect(0, 0, WORK, WORK);
      return;
    }
    const { data } = doc.imageData;
    const out = new Uint8ClampedArray(WORK * WORK * 4);
    // Paint each segment in its OWN source colour, not an arbitrary per-index
    // debug swatch. With many near-identical segments the swatch version gave
    // adjacent pixels wildly different colours, rendering a flat region as
    // multicoloured confetti that looked like a pipeline failure when the
    // underlying output was fine. Source colours make genuine mis-segmentation
    // visible instead of hiding it in noise.
    const segRgb = state.fills.map((f) => f.rgb);
    for (let i = 0; i < WORK * WORK; i++) {
      const lbl = doc.labels[i];
      const o = i * 4;
      if (lbl === -1) continue; // stays transparent
      const rgb = segRgb[lbl] || [255, 0, 255]; // magenta = label with no fill (a bug)
      out[o] = rgb[0];
      out[o + 1] = rgb[1];
      out[o + 2] = rgb[2];
      out[o + 3] = data[o + 3];
    }
    ctx.putImageData(new ImageData(out, WORK, WORK), 0, 0);
  }

  paintPreview() {
    if (!doc.pixels) {
      const ctx = this.previewCanvas.getContext("2d");
      ctx.clearRect(0, 0, this.previewCanvas.width, this.previewCanvas.height);
      return;
    }
    renderPreview(doc.pixels, state.intensity, this.previewCanvas);
  }

  paintGrid() {
    const ctx = this.gridCanvas.getContext("2d");
    const size = this.gridCanvas.width;
    const cell = size / W;
    if (!doc.pixels) {
      ctx.clearRect(0, 0, size, size);
      return;
    }
    for (let row = 0; row < H; row++) {
      for (let col = 0; col < W; col++) {
        ctx.fillStyle = ledSwatchHex(doc.pixels[row * W + col]);
        ctx.fillRect(col * cell, row * cell, cell, cell);
      }
    }
    ctx.strokeStyle = "rgba(255,255,255,0.08)";
    ctx.lineWidth = 1;
    for (let i = 0; i <= W; i++) {
      ctx.beginPath();
      ctx.moveTo(i * cell, 0);
      ctx.lineTo(i * cell, size);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(0, i * cell);
      ctx.lineTo(size, i * cell);
      ctx.stroke();
    }
  }

  // ── export ──────────────────────────────────────────────────────────
  exportMap() {
    if (!state.mode) return;
    const mapObj = toMapObj(state.sourcePath, state.fills, state.decisions, overlayToObject(doc.overlay), state.intensity, state.maxSegments);
    downloadText(`${state.iconName}.json`, serializeMap(mapObj), "application/json");
  }

  exportIcon() {
    if (!state.mode) return;
    const text = iconText(doc.pixels, `Generated by Icon Maker (web) from ${state.sourcePath || "an imported image"}`);
    downloadText(`${state.iconName}.py`, text, "text/x-python");
  }

  async exportPreview() {
    if (!state.mode) return;
    const blob = await previewToBlob(this.previewCanvas);
    downloadBlob(`${state.iconName}_preview.png`, blob);
  }
}

new App();
