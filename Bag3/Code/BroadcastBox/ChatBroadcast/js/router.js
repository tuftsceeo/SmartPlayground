import { dbg, dbgWarn } from "./debug.js";
import { iconSvg } from "./icons.js";
import { deviceShortName, deviceProductName } from "./device/bboxDeviceLink.js";

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
    syncNavTabs(name);
}

/** Highlight Home / Saved / Examples from the visible view. */
export function syncNavTabs(viewName) {
    let tab = "home";
    if (viewName === "gallery") {
        tab = document.body.dataset.galleryMode === "saved" ? "saved" : "examples";
    } else if (viewName === "detail") {
        tab = "examples";
    } else if (viewName === "workspace") {
        tab = "home";
    } else if (viewName === "splash") {
        tab = null;
    }
    document.querySelectorAll(".app-tab").forEach((btn) => {
        const nav = btn.dataset.nav;
        btn.classList.toggle("active", tab != null && nav === tab);
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

function all(sel) {
    return Array.from(document.querySelectorAll(sel));
}

export function setConnectionBadge(link) {
    const state = typeof link === "object" && link !== null ? link.state : null;
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

    const mode = link?.boxMode;
    const name = link?.detail?.activeName || link?.detail?.active || null;
    const ssid = link?.detail?.ssid || null;
    const isLive = state === "live";
    const isServing = isLive && mode === "SERVE";
    const isWriting = isLive && mode === "WRITE";
    // `link.kind` (set by app.js's paintLink() from the active device link)
    // is known the instant "Wand" is picked on the connect overlay, before
    // its own `identity` has arrived -- deviceShortName() alone would still
    // default to "Box" at that point. Box vs. Dial share one link class and
    // are told apart only by deviceInfo, once it arrives.
    const short = link?.kind === "wand" ? "Wand" : deviceShortName(link?.deviceInfo);
    const product = link?.kind === "wand" ? "Wand" : deviceProductName(link?.deviceInfo);

    // SSID chip — only while serving
    all(".ssid-chip").forEach((chip) => {
        if (isServing && ssid) {
            chip.classList.remove("hidden");
            chip.innerHTML = `${iconSvg("wifi", { size: 14 })} ${escapeHtml(ssid)}`;
        } else {
            chip.classList.add("hidden");
            chip.textContent = "";
        }
    });

    // Mode pill -- opens the Box library/stats overlay, which is Box/Dial-
    // only (games.list/stats.get/etc. have no wand equivalent: a wand has no
    // command channel at all, see wandDeviceLink.js). Stays muted and
    // disabled for a wand connection even while live, same shape as "not
    // live yet" for the Box, so the click handler (app.js's .mode-pill
    // listener, which just calls openBoxLibrary()) never fires for one.
    const isWandLink = link?.kind === "wand";
    all(".mode-pill").forEach((pill) => {
        const label = pill.querySelector(".mode-pill-label");
        pill.classList.remove("write", "muted");
        if (!isLive || isWandLink) {
            pill.classList.add("muted");
            pill.disabled = true;
            if (label) label.textContent = short;
            pill.title = isWandLink ? "No game library on a wand" : `Connect to the ${short} first`;
        } else {
            pill.disabled = false;
            if (isServing) {
                if (label) label.textContent = "Code Server";
                pill.title = `Handing out code to wands. Switch modes with the controls on the ${short}.`;
            } else if (isWriting) {
                pill.classList.add("write");
                if (label) label.textContent = "Tag Writing";
                pill.title = `Ready to write pickup tags. Switch modes with the controls on the ${short}.`;
            } else {
                if (label) label.textContent = `${short} ready`;
                pill.title = `Games, health & battery on the ${short}`;
            }
        }
    });

    // Connect button
    let btnLabel = "Connect";
    let btnTitle = `Connect to the ${short}`;
    let btnDisabled = false;
    let connectedClass = false;
    let connectIcon = "cable";

    switch (state) {
        case "opening":
            btnLabel = "Connect";
            btnDisabled = true;
            break;
        case "waiting":
            btnLabel = "Cancel";
            btnTitle = "Cancel connecting";
            break;
        case "live":
            btnLabel = "Connected";
            btnTitle = "Connected — click to disconnect";
            connectedClass = true;
            connectIcon = "unplug";
            break;
        case "sending":
            btnLabel = "Connected";
            connectedClass = true;
            btnDisabled = true;
            connectIcon = "unplug";
            break;
        case "rebooting":
            btnLabel = "Connected";
            connectedClass = true;
            btnDisabled = true;
            connectIcon = "unplug";
            break;
        case "lost":
            btnLabel = "Connect";
            break;
        case "wrong":
            btnLabel = "Disconnect";
            connectedClass = true;
            connectIcon = "unplug";
            break;
        case "stuck":
        case "no-answer":
            btnLabel = "Disconnect";
            connectedClass = true;
            connectIcon = "unplug";
            break;
        default:
            btnLabel = "Connect";
            break;
    }

    all(".btn-connect-header").forEach((btn) => {
        const labelEl = btn.querySelector(".connect-label");
        const iconHost = btn.querySelector(".connect-icon");
        if (labelEl) labelEl.textContent = btnLabel;
        else btn.textContent = btnLabel;
        if (iconHost) iconHost.innerHTML = iconSvg(connectIcon, { size: 15 });
        btn.disabled = btnDisabled;
        btn.title = btnTitle;
        btn.classList.toggle("is-connected", connectedClass);
    });

    // Compact error / recovery chip (not for idle/live happy path)
    let chipText = "";
    let chipClass = "";
    switch (state) {
        case "opening":
            chipText = "connecting…";
            chipClass = "sending";
            break;
        case "waiting":
            chipText = "waking up…";
            chipClass = "sending";
            break;
        case "sending":
            chipText = "sending…";
            chipClass = "sending";
            break;
        case "rebooting":
            chipText = "restarting…";
            chipClass = "sending";
            break;
        case "lost":
            chipText = `lost the ${short}`;
            break;
        case "wrong":
            chipText = "not a Broadcast device";
            break;
        case "stuck":
            chipText = "needs a nudge";
            chipClass = "repl";
            break;
        case "no-answer":
            chipText = "isn't answering";
            chipClass = "repl";
            break;
        default:
            chipText = "";
            break;
    }
    all(".conn-chip").forEach((el) => {
        el.classList.remove("sending", "repl");
        if (chipText) {
            el.classList.remove("hidden");
            if (chipClass) el.classList.add(chipClass);
            el.textContent = chipText;
        } else {
            el.classList.add("hidden");
            el.textContent = "";
        }
    });

    const showRestart = state === "stuck" || state === "no-answer";
    all(".btn-restart-box").forEach((btn) => {
        btn.classList.toggle("hidden", !showRestart);
        btn.disabled = !showRestart;
        btn.textContent = `Restart the ${short}`;
    });

    // Send CTA enabled only when live
    const sendBtn = document.getElementById("btn-send-box");
    if (sendBtn) {
        const canSend = state === "live";
        sendBtn.disabled = !canSend;
        sendBtn.textContent = `Send to ${short} →`;
        sendBtn.title = canSend ? `Send to ${product}` : `Connect to the ${short} first`;
    }

    // The connect overlay's h2 stays static ("Connect over USB") -- it now
    // offers a device-kind choice (Broadcast Box/Dial vs. Wand) rather than
    // naming one device, so there is no single `product` to render into it.
    all("[data-restart-box], #btn-restart-box").forEach((btn) => {
        if (!btn.classList.contains("hidden")) {
            btn.textContent = `Restart the ${short}`;
        }
    });
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

export function showConnectToast(show) {
    const el = document.getElementById("connect-toast");
    if (!el) return;
    el.classList.toggle("hidden", !show);
}

export function setSendProgress(pct, label) {
    const bar = document.getElementById("send-progress-bar");
    const txt = document.getElementById("send-progress-label");
    if (bar) bar.style.width = `${pct}%`;
    if (txt) txt.textContent = label || "";
}

function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
