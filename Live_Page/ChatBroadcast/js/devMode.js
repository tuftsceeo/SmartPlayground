/** Developer mode — a sub-option of advanced mode, persisted in localStorage.
 *  On together with advanced mode, it shows the log footer. */

const KEY = "wandcoder.devMode";

export function loadDevMode() {
    try {
        return localStorage.getItem(KEY) === "on";
    } catch (_) {}
    return false;
}

export function toggleDevMode() {
    const next = !loadDevMode();
    try {
        localStorage.setItem(KEY, next ? "on" : "off");
    } catch (_) {}
    document.dispatchEvent(new CustomEvent("devmode:change", { detail: { on: next } }));
    return next;
}
