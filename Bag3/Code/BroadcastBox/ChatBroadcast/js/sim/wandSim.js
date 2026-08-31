/**
 * Capability-driven wand simulation using assets/wand PNGs.
 * Transparent live sprites: colored overlays sit behind the image; the
 * opaque artwork masks each zone to its real cutout shape, so overlay
 * divs only need to roughly cover each zone's bounding box.
 *
 * Zone geometry measured directly against
 * assets/wand/WAND_background_labelled_zones.png (canvas 839x825):
 *   grid col centers (%): 55.006, 61.025, 67.104, 73.302, 79.201
 *   grid row centers (%): 32.909, 38.97, 45.091, 51.091, 57.152
 *   cell size (%): 4.529 x 4.364
 * LED numbering is row-major (1-5 top row, 21-25 bottom row), matching
 * the real 5x5 NeoPixel matrix addressing used in the wand games.
 */

const ASSETS = {
    up: "assets/wand/WAND_notPRESSED.png",
    down: "assets/wand/WAND_PRESSED.png",
    upOff: "assets/wand/WAND_notPRESSED_off.png",
    downOff: "assets/wand/WAND_PRESSED_off.png",
};

import { dbg } from "../debug.js";

const COL_CENTERS = [55.006, 61.025, 67.104, 73.302, 79.201];
const ROW_CENTERS = [32.909, 38.97, 45.091, 51.091, 57.152];
const BLACK_CELL_COLOR = "#000000"; // LED off — always black, on real hardware and here

let pressed = false;
let shakePulseUntil = 0;
let lastCaps = null;
let cellsBuilt = false;

function ensureLedCells() {
    if (cellsBuilt) return;
    const layer = document.getElementById("sim-led-layer");
    if (!layer) return;
    layer.innerHTML = "";
    for (let row = 0; row < 5; row++) {
        for (let col = 0; col < 5; col++) {
            const cell = document.createElement("div");
            cell.className = "sim-led-cell";
            cell.dataset.index = String(row * 5 + col + 1); // 1-25, row-major
            cell.style.left = `${COL_CENTERS[col] - 4.529 / 2}%`;
            cell.style.top = `${ROW_CENTERS[row] - 4.364 / 2}%`;
            layer.appendChild(cell);
        }
    }
    cellsBuilt = true;
}

// Individual LEDs are black when off, and their actual resolved RGB
// color when lit — mirrors real hardware behavior (see js/sim/ledShapes.js).
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

export function renderSim(capabilities, opts = {}) {
    const idle = opts.idle != null ? opts.idle : !(capabilities && capabilities.hasCode);
    if (opts.pressed != null) pressed = !!opts.pressed;

    const blankFrames = { idle: new Array(25).fill(BLACK_CELL_COLOR), pressed: new Array(25).fill(BLACK_CELL_COLOR), pressDetected: false };
    lastCaps = capabilities || lastCaps || {
        ledFrames: blankFrames,
        usesLeds: false,
        usesBuzzer: false,
        usesAccel: false,
        usesButton: false,
        usesNfc: false,
        hasCode: false,
    };

    const img = document.getElementById("wand-sprite");
    const speaker = document.getElementById("sim-speaker");
    const tilt = document.getElementById("sim-tilt");
    const shake = document.getElementById("sim-shake");
    const nfc = document.getElementById("sim-nfc");
    if (!img) return;

    if (idle) {
        img.src = pressed ? ASSETS.downOff : ASSETS.upOff;
        paintLedCells(null, true);
        speaker?.classList.remove("glow");
        tilt?.classList.remove("pulse");
        shake?.classList.remove("pulse");
        nfc?.classList.remove("active");
        return;
    }

    img.src = pressed ? ASSETS.down : ASSETS.up;
    const frames = lastCaps.ledFrames || blankFrames;
    const activeFrame = pressed ? frames.pressed : frames.idle;
    dbg("ledSim", `renderSim() — pressed=${pressed} pressDetected=${!!frames.pressDetected} -> painting ${pressed ? "pressed" : "idle"} frame`, activeFrame);
    paintLedCells(activeFrame, false);

    speaker?.classList.toggle("glow", !!lastCaps.usesBuzzer);

    const shaking = Date.now() < shakePulseUntil;
    const showAccel = !!lastCaps.usesAccel || shaking;
    tilt?.classList.toggle("pulse", showAccel);
    shake?.classList.toggle("pulse", showAccel);

    // Placeholder NFC-tap affordance pending real NFC-tap artwork
    nfc?.classList.toggle("active", !!lastCaps.usesNfc);
}

export function setPressed(next) {
    pressed = !!next;
    dbg("ledSim", `setPressed(${pressed}) — sim "Press button" control ${pressed ? "pressed" : "released"}`);
    renderSim(lastCaps, { pressed, idle: !(lastCaps && lastCaps.hasCode) });
}

export function pulseShake(ms = 600) {
    shakePulseUntil = Date.now() + ms;
    renderSim(lastCaps, { idle: !(lastCaps && lastCaps.hasCode) });
    setTimeout(() => {
        renderSim(lastCaps, { idle: !(lastCaps && lastCaps.hasCode) });
    }, ms + 20);
}

export function bindSimControls() {
    ensureLedCells();
    const pressBtn = document.getElementById("btn-sim-press");
    const shakeBtn = document.getElementById("btn-sim-shake");
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
}
