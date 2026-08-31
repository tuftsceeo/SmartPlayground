/**
 * Pyodide runtime — executes generated wand game code with hardware stubs.
 */

import { dbg, dbgWarn, dbgError } from "../../debug.js";
import { getInputState, isButtonPressed } from "./inputBridge.js";
import { paintLiveFrame, playBuzzerTone, setSimSpritePressed } from "../wandSim.js";

const PYODIDE_VERSION = "0.26.4";
const PYODIDE_CDN = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

const STUB_FILES = [
    "machine.py",
    "neopixel.py",
    "brightness.py",
    "hubtype.py",
    "buzzer.py",
    "pn532.py",
    "nfc_reader.py",
    "lis2dw12.py",
    "espnow_manager.py",
    "sim_bootstrap.py",
];

const VENDOR_FILES = ["leds.py", "game_tags.py"];

let pyodidePromise = null;
let lastCode = "";
let tickTimer = null;
let simStatus = "idle"; // idle | loading | running | error
let lastError = null;
let onStatusChange = null;

function baseUrl() {
    return new URL(".", import.meta.url).href;
}

async function fetchText(relativePath) {
    const res = await fetch(new URL(relativePath, baseUrl()));
    if (!res.ok) throw new Error(`Failed to load ${relativePath}: ${res.status}`);
    return res.text();
}

function loadPyodideScript() {
    return new Promise((resolve, reject) => {
        if (globalThis.loadPyodide) {
            resolve();
            return;
        }
        const script = document.createElement("script");
        script.src = `${PYODIDE_CDN}pyodide.js`;
        script.onload = () => resolve();
        script.onerror = () => reject(new Error("Failed to load Pyodide from CDN"));
        document.head.appendChild(script);
    });
}

async function initPyodide() {
    if (pyodidePromise) return pyodidePromise;

    pyodidePromise = (async () => {
        dbg("pySim", "loading Pyodide…");
        setSimStatus("loading");
        await loadPyodideScript();
        const pyodide = await globalThis.loadPyodide({ indexURL: PYODIDE_CDN });
        dbg("pySim", "Pyodide loaded, writing virtual FS…");

        pyodide.FS.mkdir("/sim");
        pyodide.FS.mkdir("/sim/vendor");

        for (const name of STUB_FILES) {
            const text = await fetchText(`hwStubs/${name}`);
            pyodide.FS.writeFile(`/sim/${name}`, text);
        }
        for (const name of VENDOR_FILES) {
            const text = await fetchText(`vendor/${name}`);
            pyodide.FS.writeFile(`/sim/vendor/${name}`, text);
        }

        pyodide.globals.set("_js_paint_leds", (pixels) => {
            paintLiveFrame(pixels.toJs());
        });
        pyodide.globals.set("_js_beep", (freq, ms) => {
            playBuzzerTone(freq, ms);
        });

        pyodide.runPython(`
import sys
sys.path.insert(0, '/sim/vendor')
sys.path.insert(0, '/sim')
`);

        dbg("pySim", "virtual FS ready");
        setSimStatus("running");
        return pyodide;
    })().catch((err) => {
        pyodidePromise = null;
        setSimStatus("error", err.message);
        throw err;
    });

    return pyodidePromise;
}

function setSimStatus(status, errorMsg = null) {
    simStatus = status;
    lastError = errorMsg;
    const el = document.getElementById("sim-status");
    const banner = document.getElementById("sim-error-banner");
    if (el) {
        const labels = {
            idle: "Quick preview",
            loading: "Loading Python simulator…",
            running: "Simulating with Python",
            error: "Could not be simulated",
        };
        el.textContent = labels[status] || status;
        el.className = `sim-status sim-status-${status}`;
    }
    if (banner) {
        if (status === "error" && errorMsg) {
            banner.textContent = errorMsg;
            banner.classList.remove("hidden");
        } else {
            banner.classList.add("hidden");
        }
    }
    if (onStatusChange) onStatusChange(status, errorMsg);
}

function isPlaceholderCode(code) {
    const t = (code || "").trim();
    return !t || t.startsWith("# AI-generated");
}

function hasPlayContract(code) {
    return /def\s+play\s*\(/.test(code || "");
}

/**
 * Run one bounded simulation burst with current input state.
 * @param {string} code
 * @returns {Promise<{ ok: boolean, pixels?: string[], error?: string }>}
 */
export async function runTick(code) {
    if (isPlaceholderCode(code)) {
        setSimStatus("idle");
        return { ok: false, error: "no code" };
    }
    if (!hasPlayContract(code)) {
        setSimStatus("error", "Generated code must define play(nfc, leds, buz, accel, i2c, enow).");
        return { ok: false, error: "missing play()" };
    }

    try {
        const pyodide = await initPyodide();
        const inp = getInputState();
        setSimSpritePressed(isButtonPressed());

        pyodide.globals.set("_user_code", code);
        pyodide.globals.set("_input_state", inp);

        const result = pyodide.runPython(`
import json
from sim_bootstrap import input_state, run_sim_tick, SimError
import sim_bootstrap as sb

# Sync JS input dict into Python
_in = _input_state.to_py()
input_state.clear()
input_state.update(_in)

from pn532 import PN532
from leds import Leds
from buzzer import Buzzer
from lis2dw12 import LIS2DW12
from espnow_manager import ESPNowManager

nfc = PN532(None)
leds = Leds(pin=20, num=25)
buz = Buzzer(19)
accel = LIS2DW12(None)
i2c = None
enow = ESPNowManager()
enow.init()

try:
    pixels = run_sim_tick(_user_code, nfc, leds, buz, accel, i2c, enow)
    json.dumps({"ok": True, "pixels": pixels})
except SimError as e:
    json.dumps({"ok": False, "error": str(e)})
except Exception as e:
    json.dumps({"ok": False, "error": str(e)})
`);

        const parsed = JSON.parse(result);
        if (parsed.ok) {
            setSimStatus("running");
            if (parsed.pixels) paintLiveFrame(parsed.pixels);
            dbg("pySim", `tick OK — ${parsed.pixels.filter((p) => p !== "rgb(0,0,0)").length} lit LEDs`);
            return parsed;
        }
        setSimStatus("error", parsed.error || "Simulation failed");
        dbgWarn("pySim", "tick failed", parsed.error);
        return parsed;
    } catch (err) {
        const msg = err.message || String(err);
        setSimStatus("error", msg);
        dbgError("pySim", "runTick exception", err);
        return { ok: false, error: msg };
    }
}

/**
 * Start or restart the ambient tick loop for the current code string.
 * @param {string} code
 * @param {{ intervalMs?: number }} opts
 */
export function startSimLoop(code, opts = {}) {
    stopSimLoop();
    lastCode = code || "";
    if (isPlaceholderCode(lastCode)) return;

    const intervalMs = opts.intervalMs ?? 150;

    const tick = () => {
        runTick(lastCode);
    };

    tick();
    tickTimer = setInterval(tick, intervalMs);
    dbg("pySim", `sim loop started (${intervalMs}ms)`);
}

export function stopSimLoop() {
    if (tickTimer) {
        clearInterval(tickTimer);
        tickTimer = null;
    }
}

/** Re-run one tick immediately (e.g. on button press). */
export function triggerTick(code) {
    const c = code || lastCode;
    if (!isPlaceholderCode(c)) runTick(c);
}

export function setStatusCallback(fn) {
    onStatusChange = fn;
}

export function getSimStatus() {
    return { status: simStatus, error: lastError };
}

export async function preloadPyodide() {
    try {
        await initPyodide();
    } catch (e) {
        dbgWarn("pySim", "preload failed", e);
    }
}
