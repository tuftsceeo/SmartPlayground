import { VERSIONS, REPO, DEVICES, getDeviceByHubType } from "./devices.js";
import { fetchManifestFiles, listBranchesAndTags } from "./github.js";
import { loadManifest } from "./manifest.js";
import { SerialEngine } from "./serial.js";
import {
  parseDeviceType,
  applyHubMainPyPatches,
  showAntennaOption,
} from "./hubConfig.js";

// ─── State ───────────────────────────────────────────────────────────────────
let selectedRef = VERSIONS.find((v) => v.recommended)?.ref ?? VERSIONS[0].ref;
let useAdvancedRef = false;
let selectedDeviceId = null;
let detectedHubType = null;
let deviceHubName = null;
let boardType = null;
let boardInfoRaw = null;
let fetchedFiles = {};

const serial = new SerialEngine({ log });

// ─── UI helpers ──────────────────────────────────────────────────────────────
const STATUS_CLASSES = {
  info: "text-gray-600",
  success: "text-green-700",
  error: "text-red-700",
  warn: "text-amber-700",
};

function setStatus(id, msg, kind = "info") {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = msg;
  el.className = `text-sm ${STATUS_CLASSES[kind] || STATUS_CLASSES.info}`;
}

function log(msg, cls = "") {
  document.getElementById("log-wrap").classList.remove("hidden");
  const box = document.getElementById("serial-log");
  const line = document.createElement("div");
  const colors = {
    err: "text-red-400",
    dim: "text-gray-500",
    warn: "text-amber-400",
    info: "text-blue-300",
  };
  line.className = colors[cls] || "text-gray-300";
  line.textContent = msg;
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
}

function setProgress(pct) {
  const wrap = document.getElementById("progress-wrap");
  const bar = document.getElementById("progress-bar");
  if (pct === null) {
    wrap.classList.add("hidden");
    bar.style.width = "0%";
    return;
  }
  wrap.classList.remove("hidden");
  bar.style.width = pct + "%";
}

function getSelectedDevice() {
  return DEVICES.find((d) => d.id === selectedDeviceId) ?? null;
}

function getActiveRef() {
  if (useAdvancedRef) {
    const v = document.getElementById("advanced-version-input").value.trim();
    return v || selectedRef;
  }
  return selectedRef;
}

function updateUploadButton() {
  const device = getSelectedDevice();
  const ref = getActiveRef();
  const ready = serial.isConnected() && device && ref;
  document.getElementById("btn-upload").disabled = !ready;
}

function refreshFileList() {
  const keys = Object.keys(fetchedFiles);
  const wrap = document.getElementById("file-list-wrap");
  const container = document.getElementById("file-list");
  if (!keys.length) {
    wrap.classList.add("hidden");
    return;
  }
  wrap.classList.remove("hidden");
  container.innerHTML = keys
    .map(
      (f) =>
        `<div class="flex justify-between gap-2 py-0.5"><span>${f}</span><span class="text-gray-400">${fetchedFiles[f].length.toLocaleString()} B</span></div>`
    )
    .join("");
}

function updateHubAntennaPanel() {
  const device = getSelectedDevice();
  const panel = document.getElementById("hub-antenna-panel");
  if (device?.hubConfig && boardType && showAntennaOption(boardType)) {
    panel.classList.remove("hidden");
  } else {
    panel.classList.add("hidden");
  }
}

function updateDetectionUI() {
  const device = getSelectedDevice();
  const detectWarn = document.getElementById("detect-warn");
  const provisionNote = document.getElementById("provision-note");
  detectWarn.classList.add("hidden");
  provisionNote.classList.add("hidden");

  if (detectedHubType) {
    const detected = getDeviceByHubType(detectedHubType);
    if (detected && device && detected.id !== device.id) {
      detectWarn.textContent = `Device reports hubType "${detectedHubType}" but you selected ${device.label}. Upload will use your selection.`;
      detectWarn.classList.remove("hidden");
    }
  } else if (device?.writeHubType) {
    provisionNote.textContent = `No hubType.txt found — "${device.hubTypeValue}" will be written during upload.`;
    provisionNote.classList.remove("hidden");
  }

  document.querySelectorAll("[data-device-id]").forEach((card) => {
    const id = card.dataset.deviceId;
    const badge = card.querySelector(".detected-badge");
    const isDetected =
      detectedHubType && getDeviceByHubType(detectedHubType)?.id === id;
    if (isDetected) {
      badge?.classList.remove("hidden");
      if (!selectedDeviceId) {
        selectDevice(id, false);
      }
    } else {
      badge?.classList.add("hidden");
    }
  });

  updateHubAntennaPanel();
  updateUploadButton();
}

// ─── Version UI ──────────────────────────────────────────────────────────────
function renderVersions() {
  const container = document.getElementById("version-buttons");
  container.innerHTML = "";
  VERSIONS.forEach((v) => {
    const btn = document.createElement("button");
    btn.type = "button";
    const active = !useAdvancedRef && selectedRef === v.ref;
    btn.className = [
      "px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors",
      active
        ? "bg-blue-600 text-white border-blue-600"
        : "bg-white text-gray-700 border-gray-300 hover:border-blue-400",
    ].join(" ");
    btn.textContent = v.label + (v.recommended ? " ★" : "");
    btn.addEventListener("click", () => {
      useAdvancedRef = false;
      selectedRef = v.ref;
      renderVersions();
      setStatus("version-status", `Selected: ${v.label} (${v.ref})`, "success");
      updateUploadButton();
    });
    container.appendChild(btn);
  });
  const v = VERSIONS.find((x) => x.ref === selectedRef);
  if (v && !useAdvancedRef) {
    setStatus("version-status", `Selected: ${v.label} (${v.ref})`, "success");
  }
}

// ─── Device UI ───────────────────────────────────────────────────────────────
function renderDevices() {
  const grid = document.getElementById("device-grid");
  grid.innerHTML = "";
  DEVICES.forEach((d) => {
    const card = document.createElement("button");
    card.type = "button";
    card.dataset.deviceId = d.id;
    const active = selectedDeviceId === d.id;
    card.className = [
      "relative text-left rounded-lg border p-4 flex flex-col gap-2 transition-colors",
      active
        ? "border-blue-500 bg-blue-50 ring-2 ring-blue-200"
        : "border-gray-200 bg-white hover:border-blue-300",
    ].join(" ");
    card.innerHTML = `
      <span class="detected-badge hidden absolute top-2 right-2 text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">detected</span>
      <i data-lucide="${d.icon}" class="w-8 h-8 text-blue-600"></i>
      <span class="font-semibold text-gray-800">${d.label}</span>
      <span class="text-xs text-gray-500">${d.blurb}</span>
    `;
    card.addEventListener("click", () => selectDevice(d.id, true));
    grid.appendChild(card);
  });
  if (window.lucide) window.lucide.createIcons();
}

function selectDevice(id, userInitiated) {
  selectedDeviceId = id;
  const device = getSelectedDevice();
  renderDevices();
  if (userInitiated && device) {
    setStatus("device-status", `Selected: ${device.label}`, "success");
  }
  updateDetectionUI();
}

// ─── Connect / disconnect ────────────────────────────────────────────────────
async function handleConnect() {
  const device = getSelectedDevice();
  if (!device) {
    setStatus("connect-status", "⚠ Select a device first.", "warn");
    return;
  }

  document.getElementById("btn-connect").disabled = true;
  setStatus("connect-status", "⏳ Connecting…", "info");

  try {
    serial.setOnDisconnect(() => {
      handleDisconnectState();
      setStatus("connect-status", "⚠ Device was unplugged.", "warn");
    });

    await serial.connect(device.baudRate);

    setStatus("connect-status", "⏳ Reading device info…", "info");
    const info = await serial.readDeviceInfo(device.devicePathRoot);
    detectedHubType = info.hubType;
    deviceHubName = info.hubName;

    document.getElementById("device-info").classList.remove("hidden");
    document.getElementById("info-type").textContent = info.hubType || "—";
    document.getElementById("info-name").textContent = info.hubName || "—";

    if (device.hubConfig) {
      setStatus("connect-status", "⏳ Detecting board type…", "info");
      try {
        boardInfoRaw = await serial.readBoardInfo();
        boardType = parseDeviceType(boardInfoRaw);
        document.getElementById("board-chip").classList.remove("hidden");
        document.getElementById("info-board").textContent = boardType;
      } catch (e) {
        boardType = null;
        boardInfoRaw = null;
        log(`  ⚠ Board detect failed: ${e.message}`, "warn");
      }
    } else {
      boardType = null;
      boardInfoRaw = null;
      document.getElementById("board-chip").classList.add("hidden");
    }

    document.getElementById("btn-connect").disabled = true;
    document.getElementById("btn-disconnect").disabled = false;

    if (info.hubType) {
      setStatus(
        "connect-status",
        `✅ Connected — ${info.hubName || "unnamed"} (${info.hubType})`,
        "success"
      );
    } else {
      setStatus("connect-status", "✅ Connected", "success");
    }

    updateDetectionUI();
  } catch (e) {
    setStatus("connect-status", `❌ ${e.message}`, "error");
    document.getElementById("btn-connect").disabled = false;
  }
}

function handleDisconnectState() {
  detectedHubType = null;
  deviceHubName = null;
  boardType = null;
  boardInfoRaw = null;
  document.getElementById("device-info").classList.add("hidden");
  document.getElementById("btn-connect").disabled = false;
  document.getElementById("btn-disconnect").disabled = true;
  document.getElementById("hub-antenna-panel").classList.add("hidden");
  updateUploadButton();
}

async function handleDisconnect() {
  await serial.disconnect();
  handleDisconnectState();
  setStatus("connect-status", "Disconnected.", "info");
}

// ─── Upload ──────────────────────────────────────────────────────────────────
async function handleUpload() {
  const device = getSelectedDevice();
  const ref = getActiveRef();
  if (!device || !ref || !serial.isConnected()) return;

  document.getElementById("btn-upload").disabled = true;
  fetchedFiles = {};
  setProgress(0);
  refreshFileList();

  try {
    setStatus("upload-status", "⏳ Loading manifest…", "info");
    const manifest = await loadManifest(device.manifest);
    log(`── Manifest ${device.manifest}: ${manifest.sources.map((s) => s.repoPath).join(" + ")} ──`);

    setStatus("upload-status", "⏳ Fetching files from GitHub…", "info");
    fetchedFiles = await fetchManifestFiles(REPO, ref, manifest, {
      log,
      onProgress: (f) => setStatus("upload-status", `⏳ Fetching ${f}…`, "info"),
    });

    if (device.hubConfig && fetchedFiles["main.py"]) {
      const hasExternalAntenna =
        document.getElementById("external-antenna").checked;
      fetchedFiles["main.py"] = applyHubMainPyPatches(
        fetchedFiles["main.py"],
        boardType || "C6",
        hasExternalAntenna
      );
      log(`  Patched main.py for board ${boardType || "C6"}`, "dim");
    }

    refreshFileList();
    log(`Fetched ${Object.keys(fetchedFiles).length} file(s).`, "dim");
    setProgress(10);

    if (device.writeHubType) {
      const needsProvision =
        !detectedHubType || detectedHubType !== device.hubTypeValue;
      if (needsProvision) {
        setStatus("upload-status", "⏳ Provisioning hubType.txt…", "info");
        await serial.writeHubType(
          device.hubTypeValue,
          deviceHubName || "",
          device.devicePathRoot
        );
        detectedHubType = device.hubTypeValue;
        document.getElementById("info-type").textContent = device.hubTypeValue;
        log(`  Wrote hubType.txt = "${device.hubTypeValue}"`, "dim");
      }
    }

    const result = await serial.uploadWithRetry(fetchedFiles, device, {
      onProgress: setProgress,
      onStatus: (msg) => setStatus("upload-status", msg, "info"),
    });

    setStatus(
      "upload-status",
      `✅ ${result.total} file(s) uploaded to ${device.label} and running!`,
      "success"
    );
    setTimeout(() => setProgress(null), 1000);
  } catch (e) {
    setStatus("upload-status", `❌ ${e.message}`, "error");
    log(`❌ ${e.message}`, "err");
    setProgress(null);
  } finally {
    updateUploadButton();
  }
}

// ─── Init ────────────────────────────────────────────────────────────────────
function init() {
  if (!("serial" in navigator)) {
    document.getElementById("browser-warn").classList.remove("hidden");
    document.getElementById("btn-connect").disabled = true;
  }

  renderVersions();
  renderDevices();

  document.getElementById("toggle-advanced-version").addEventListener("click", () => {
    const panel = document.getElementById("advanced-version-panel");
    const btn = document.getElementById("toggle-advanced-version");
    const hidden = panel.classList.toggle("hidden");
    btn.textContent = hidden
      ? "▸ Advanced: type a branch or tag"
      : "▾ Advanced: type a branch or tag";
    if (!hidden) {
      useAdvancedRef = true;
      renderVersions();
    }
  });

  document.getElementById("advanced-version-input").addEventListener("input", () => {
    useAdvancedRef = true;
    renderVersions();
    const ref = document.getElementById("advanced-version-input").value.trim();
    if (ref) setStatus("version-status", `Advanced ref: ${ref}`, "info");
    updateUploadButton();
  });

  document.getElementById("btn-load-branches").addEventListener("click", async () => {
    const sel = document.getElementById("branch-select");
    setStatus("version-status", "⏳ Loading branches…", "info");
    try {
      const names = await listBranchesAndTags(REPO);
      sel.innerHTML = '<option value="">— pick a branch/tag —</option>';
      names.forEach((n) => {
        const opt = document.createElement("option");
        opt.value = n;
        opt.textContent = n;
        sel.appendChild(opt);
      });
      sel.classList.remove("hidden");
      setStatus("version-status", `Loaded ${names.length} branches/tags.`, "success");
    } catch (e) {
      setStatus("version-status", `❌ ${e.message}`, "error");
    }
  });

  document.getElementById("branch-select").addEventListener("change", (e) => {
    if (e.target.value) {
      document.getElementById("advanced-version-input").value = e.target.value;
      useAdvancedRef = true;
      renderVersions();
      setStatus("version-status", `Advanced ref: ${e.target.value}`, "info");
      updateUploadButton();
    }
  });

  document.getElementById("btn-connect").addEventListener("click", handleConnect);
  document.getElementById("btn-disconnect").addEventListener("click", handleDisconnect);
  document.getElementById("btn-upload").addEventListener("click", handleUpload);
  document.getElementById("external-antenna").addEventListener("change", updateUploadButton);

  if (window.lucide) window.lucide.createIcons();
}

init();
