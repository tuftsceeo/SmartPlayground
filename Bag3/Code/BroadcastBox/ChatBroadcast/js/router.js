import { dbg, dbgWarn } from "./debug.js";

const VIEWS = ["splash", "gallery", "detail", "workspace"];

export function showView(name) {
    dbg("router", `showView("${name}")`);
    if (!VIEWS.includes(name)) {
        dbgWarn("router", `showView called with unknown view "${name}" — no-op on the view panels`);
    }
    VIEWS.forEach((v) => {
        const el = document.getElementById(`view-${v}`);
        if (el) el.classList.toggle("hidden", v !== name);
    });
    document.querySelectorAll(".overlay-view").forEach((el) => {
        if (el.dataset.persistent) {
            dbg("router", `showView("${name}") skipping persistent overlay #${el.id}`);
            return;
        }
        el.classList.add("hidden");
    });
}

export function showOverlay(id) {
    const el = document.getElementById(id);
    if (!el) {
        dbgWarn("router", `showOverlay("${id}") — element not found`);
        return;
    }
    dbg("router", `showOverlay("${id}")`);
    el.classList.remove("hidden");
}

export function hideOverlay(id) {
    const el = document.getElementById(id);
    if (!el) {
        dbgWarn("router", `hideOverlay("${id}") — element not found`);
        return;
    }
    dbg("router", `hideOverlay("${id}")`);
    el.classList.add("hidden");
}

export function setConnectionBadge(link) {
    const el = document.getElementById("connection-badge");
    const btn = document.getElementById("btn-connect-header");
    const restartBtn = document.getElementById("btn-restart-box");
    if (!el) return;

    const state = typeof link === "object" && link !== null ? link.state : null;
    // Legacy boolean call site: setConnectionBadge(connected, running, …)
    // kept only until callers are migrated — prefer the link object.
    if (state == null && arguments.length >= 1 && typeof link !== "object") {
        const connected = !!arguments[0];
        const running = !!arguments[1];
        const atRepl = !!arguments[2];
        const wrongDevice = !!arguments[3];
        return setConnectionBadge({
            state: wrongDevice ? "wrong" : atRepl ? "stuck" : connected && running ? "live" : connected ? "waiting" : "idle",
            boxMode: null,
            detail: null,
        });
    }

    el.classList.remove("connected", "repl", "wrong", "lost", "sending");
    let text = "● not connected";
    let btnLabel = "Connect";
    let btnDisabled = false;
    let showRestart = false;
    let connectedClass = false;

    switch (state) {
        case "opening":
            text = "● connecting…";
            btnLabel = "Connect";
            btnDisabled = true;
            break;
        case "waiting":
            text = "● waking up the Box…";
            btnLabel = "Cancel";
            break;
        case "live": {
            const mode = link.boxMode;
            const name = link.detail?.activeName || link.detail?.active || null;
            if (mode === "IDLE") text = "● Box ready — no games yet";
            else if (mode === "WRITE") text = "● ready to make cards";
            else if (mode === "SERVE") text = name ? `● handing out ${name}` : "● handing out a game";
            else text = "● connected";
            el.classList.add("connected");
            connectedClass = true;
            btnLabel = "Disconnect";
            break;
        }
        case "sending":
            text = "● sending your game…";
            el.classList.add("sending");
            btnLabel = "Disconnect";
            btnDisabled = true;
            break;
        case "rebooting":
            text = "● restarting the Box…";
            btnLabel = "Disconnect";
            btnDisabled = true;
            break;
        case "lost":
            text = "● lost the Box — check the cable";
            el.classList.add("lost");
            btnLabel = "Connect";
            break;
        case "wrong":
            text = "● that's not a Broadcast Box";
            el.classList.add("wrong");
            btnLabel = "Disconnect";
            break;
        case "stuck":
            text = "● the Box needs a nudge";
            el.classList.add("repl");
            btnLabel = "Disconnect";
            showRestart = true;
            break;
        // Port is open and the cable is fine, but the Box has sent nothing at
        // all. Distinct from "lost" (cable/port gone) because the remedy is
        // different: restart the Box, don't go looking for the cable.
        case "no-answer":
            text = "● the Box isn't answering";
            el.classList.add("repl");
            btnLabel = "Disconnect";
            showRestart = true;
            break;
        case "idle":
        default:
            text = "● not connected";
            btnLabel = "Connect";
            break;
    }

    el.textContent = text;
    if (btn) {
        btn.textContent = btnLabel;
        btn.disabled = btnDisabled;
        btn.classList.toggle("is-connected", connectedClass || state === "waiting" || state === "stuck" || state === "wrong" || state === "no-answer" || state === "sending" || state === "rebooting");
    }
    if (restartBtn) {
        restartBtn.classList.toggle("hidden", !showRestart);
        restartBtn.disabled = !showRestart;
    }
}

export function toast(msg, isError = false) {
    const el = document.getElementById("toast");
    if (!el) return;
    (isError ? dbgWarn : dbg)("router", `toast: ${msg}`);
    el.textContent = msg;
    el.classList.toggle("error", isError);
    el.classList.remove("hidden");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.add("hidden"), 5000);
}

export function setSendProgress(pct, label) {
    const bar = document.getElementById("send-progress-bar");
    const txt = document.getElementById("send-progress-label");
    if (bar) bar.style.width = `${pct}%`;
    if (txt) txt.textContent = label || "";
}
