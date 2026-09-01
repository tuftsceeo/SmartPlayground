/**
 * Maps sim UI controls to the Python-side input_state dict (sim_bootstrap.py).
 */

/** @typedef {{ button: number, accel: [number,number,number], nfcPending: [string,string]|null, espnowQueue: Array<[string, unknown, string]> }} SimInputState */

/** @type {SimInputState} */
let state = {
    button: 1,
    accel: [0, 0, 1],
    nfcPending: null,
    espnowQueue: [],
};

const REST_ACCEL = [0, 0, 1];
const SHAKE_ACCEL = [2.5, 0.5, 0.2];
const TILT_ACCEL = [0.8, 0.8, 0.3];

let onInputChange = null;

export function setInputChangeHandler(fn) {
    onInputChange = fn;
}

function notifyInput() {
    if (onInputChange) onInputChange();
}

export function getInputState() {
    return {
        button: state.button,
        accel: state.accel.slice(),
        nfc_pending: state.nfcPending,
        espnow_queue: state.espnowQueue.map((m) => m.slice()),
    };
}

export function setButtonPressed(pressed) {
    state.button = pressed ? 0 : 1;
}

export function isButtonPressed() {
    return state.button === 0;
}

export function pulseShake() {
    state.accel = SHAKE_ACCEL.slice();
    setTimeout(() => {
        if (state.accel[0] === SHAKE_ACCEL[0]) {
            state.accel = REST_ACCEL.slice();
        }
    }, 400);
}

export function setTiltActive(active) {
    state.accel = active ? TILT_ACCEL.slice() : REST_ACCEL.slice();
}

export function tapNfcTag(command, uid = "sim_uid") {
    state.nfcPending = [command, uid];
    notifyInput();
}

export function pushEspnowMessage(msgType, data = null, mac = "ff:ff:ff:ff:ff:ff") {
    state.espnowQueue.push([msgType, data, mac]);
    notifyInput();
}

export function resetInputState() {
    state = {
        button: 1,
        accel: REST_ACCEL.slice(),
        nfcPending: null,
        espnowQueue: [],
    };
}

/**
 * Build NFC tap buttons from deriveRequiredTags() output.
 * @param {string[]} tags
 */
export function renderNfcButtons(tags) {
    const row = document.getElementById("sim-nfc-buttons");
    if (!row) return;
    row.innerHTML = "";
    (tags || []).forEach((tag) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "sim-input-btn";
        btn.textContent = tag;
        btn.title = `Tap NFC card: ${tag}`;
        btn.addEventListener("click", () => tapNfcTag(tag));
        row.appendChild(btn);
    });
}

/** Standard ESP-NOW messages teachers may need to emulate. */
const ESPNOW_PRESETS = [
    ["stop", "Stop game"],
    ["start_game", "Start game"],
];

export function renderEspnowButtons() {
    const row = document.getElementById("sim-espnow-buttons");
    if (!row) return;
    row.innerHTML = "";
    ESPNOW_PRESETS.forEach(([msgType, label]) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "sim-input-btn";
        btn.textContent = label;
        btn.addEventListener("click", () => pushEspnowMessage(msgType));
        row.appendChild(btn);
    });
}
