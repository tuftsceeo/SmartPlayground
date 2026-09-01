/**
 * Wand simulation DOM — sprite compositing + live Python-driven LED painting.
 */

const ASSETS = {
    up: "assets/wand/WAND_notPRESSED.png",
    down: "assets/wand/WAND_PRESSED.png",
    upOff: "assets/wand/WAND_notPRESSED_off.png",
    downOff: "assets/wand/WAND_PRESSED_off.png",
};

import { dbg } from "../debug.js";
import {
    setButtonPressed,
    pulseShake as bridgePulseShake,
    setTiltActive,
    isButtonPressed,
} from "./pyodide/inputBridge.js";

const COL_CENTERS = [55.006, 61.025, 67.104, 73.302, 79.201];
const ROW_CENTERS = [32.909, 38.97, 45.091, 51.091, 57.152];
const BLACK_CELL_COLOR = "#000000";

let pressed = false;
let shakePulseUntil = 0;
let lastCaps = null;
let cellsBuilt = false;
let tickHandler = null;
let audioCtx = null;
let liveMode = false;

function ensureLedCells() {
    if (cellsBuilt) return;
    const layer = document.getElementById("sim-led-layer");
    if (!layer) return;
    layer.innerHTML = "";
    for (let row = 0; row < 5; row++) {
        for (let col = 0; col < 5; col++) {
            const cell = document.createElement("div");
            cell.className = "sim-led-cell";
            cell.dataset.index = String(row * 5 + col + 1);
            cell.style.left = `${COL_CENTERS[col] - 4.529 / 2}%`;
            cell.style.top = `${ROW_CENTERS[row] - 4.364 / 2}%`;
            layer.appendChild(cell);
        }
    }
    cellsBuilt = true;
}

function paintLedCells(ledPixels, idle) {
    ensureLedCells();
    const cells = document.querySelectorAll("#sim-led-layer .sim-led-cell");
    cells.forEach((cell, i) => {
        if (idle) {
            cell.style.background = BLACK_CELL_COLOR;
        } else {
            cell.style.background = (ledPixels && ledPixels[i]) || BLACK_CELL_COLOR;
        }
    });
}

/** Paint LED matrix directly from Pyodide runtime (list of rgb() CSS strings). */
export function paintLiveFrame(pixels) {
    liveMode = true;
    ensureLedCells();
    const cells = document.querySelectorAll("#sim-led-layer .sim-led-cell");
    cells.forEach((cell, i) => {
        cell.style.background = (pixels && pixels[i]) || BLACK_CELL_COLOR;
    });
    updateSpriteAndOverlays();
}

export function setSimSpritePressed(isPressed) {
    pressed = !!isPressed;
    updateSpriteAndOverlays();
}

function updateSpriteAndOverlays() {
    const img = document.getElementById("wand-sprite");
    const speaker = document.getElementById("sim-speaker");
    const tilt = document.getElementById("sim-tilt");
    const shake = document.getElementById("sim-shake");
    const nfc = document.getElementById("sim-nfc");
    if (!img) return;

    const btnDown = isButtonPressed();
    img.src = btnDown ? ASSETS.down : ASSETS.up;

    if (lastCaps) {
        speaker?.classList.toggle("glow", !!lastCaps.usesBuzzer);
        const shaking = Date.now() < shakePulseUntil;
        const showAccel = !!lastCaps.usesAccel || shaking;
        tilt?.classList.toggle("pulse", showAccel);
        shake?.classList.toggle("pulse", showAccel);
        nfc?.classList.toggle("active", !!lastCaps.usesNfc);
    }
}

export function playBuzzerTone(freq, ms) {
    try {
        if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = "square";
        osc.frequency.value = Math.max(80, Number(freq) || 440);
        gain.gain.value = 0.08;
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        const dur = Math.min(800, Math.max(20, Number(ms) || 100));
        setTimeout(() => {
            try { osc.stop(); } catch (_) { /* already stopped */ }
        }, dur);
        speakerGlowBrief();
    } catch (e) {
        dbg("pySim", "buzzer failed", e);
    }
}

function speakerGlowBrief() {
    const speaker = document.getElementById("sim-speaker");
    if (!speaker) return;
    speaker.classList.add("glow");
    setTimeout(() => speaker.classList.remove("glow"), 200);
}

export function setTickHandler(fn) {
    tickHandler = fn;
}

function requestTick() {
    if (tickHandler) tickHandler();
}

export function renderSim(capabilities, opts = {}) {
    const idle = opts.idle != null ? opts.idle : !(capabilities && capabilities.hasCode);
    if (opts.pressed != null) pressed = !!opts.pressed;

    lastCaps = capabilities || lastCaps || {
        ledFrames: { idle: [], pressed: [], pressDetected: false },
        usesLeds: false,
        usesBuzzer: false,
        usesAccel: false,
        usesButton: false,
        usesNfc: false,
        hasCode: false,
    };

    if (idle) {
        liveMode = false;
        setSimSpritePressed(false);
        paintLedCells(null, true);
        document.getElementById("sim-speaker")?.classList.remove("glow");
        document.getElementById("sim-tilt")?.classList.remove("pulse");
        document.getElementById("sim-shake")?.classList.remove("pulse");
        document.getElementById("sim-nfc")?.classList.remove("active");
        return;
    }

    if (!liveMode && lastCaps.ledFrames) {
        const frames = lastCaps.ledFrames;
        const activeFrame = pressed ? frames.pressed : frames.idle;
        paintLedCells(activeFrame, false);
    }
    updateSpriteAndOverlays();
}

export function setPressed(next) {
    pressed = !!next;
    setButtonPressed(next);
    setSimSpritePressed(next);
    requestTick();
}

export function pulseShake(ms = 600) {
    shakePulseUntil = Date.now() + ms;
    bridgePulseShake();
    updateSpriteAndOverlays();
    requestTick();
    setTimeout(() => updateSpriteAndOverlays(), ms + 20);
}

export function bindSimControls() {
    ensureLedCells();

    const pressBtn = document.getElementById("btn-sim-press");
    const shakeBtn = document.getElementById("btn-sim-shake");
    const tiltBtn = document.getElementById("btn-sim-tilt");

    if (pressBtn) {
        pressBtn.addEventListener("mousedown", () => setPressed(true));
        pressBtn.addEventListener("mouseup", () => setPressed(false));
        pressBtn.addEventListener("mouseleave", () => setPressed(false));
        pressBtn.addEventListener("touchstart", (e) => {
            e.preventDefault();
            setPressed(true);
        }, { passive: false });
        pressBtn.addEventListener("touchend", () => setPressed(false));
    }
    if (shakeBtn) {
        shakeBtn.addEventListener("click", () => pulseShake(700));
    }
    if (tiltBtn) {
        tiltBtn.addEventListener("mousedown", () => {
            setTiltActive(true);
            updateSpriteAndOverlays();
            requestTick();
        });
        tiltBtn.addEventListener("mouseup", () => {
            setTiltActive(false);
            updateSpriteAndOverlays();
            requestTick();
        });
        tiltBtn.addEventListener("mouseleave", () => {
            setTiltActive(false);
            updateSpriteAndOverlays();
        });
    }
}
