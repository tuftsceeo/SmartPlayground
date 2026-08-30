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

export function setConnectionBadge(connected, running, atRepl, wrongDevice) {
    const el = document.getElementById("connection-badge");
    if (!el) return;
    el.classList.remove("connected", "repl", "wrong");
    if (wrongDevice) {
        el.textContent = "● wrong device";
        el.classList.add("wrong");
    } else if (atRepl) {
        el.textContent = "● at REPL";
        el.classList.add("repl");
    } else if (connected && running) {
        el.textContent = "● connected";
        el.classList.add("connected");
    } else if (connected) {
        el.textContent = "● connecting…";
    } else {
        el.textContent = "● not connected";
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
