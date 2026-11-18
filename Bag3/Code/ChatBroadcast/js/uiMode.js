/** Simple / advanced UI mode — persisted in localStorage. */

const KEY = "wandcoder.uiMode";

export function loadUiMode() {
    try {
        const stored = localStorage.getItem(KEY);
        if (stored === "advanced" || stored === "simple") return stored;
    } catch (_) {}
    return "simple";
}

export function getUiMode() {
    return loadUiMode();
}

export function setUiMode(next) {
    if (next !== "simple" && next !== "advanced") return loadUiMode();
    try {
        localStorage.setItem(KEY, next);
    } catch (_) {}
    document.dispatchEvent(new CustomEvent("uimode:change", { detail: { mode: next } }));
    return next;
}

export function toggleUiMode() {
    const next = loadUiMode() === "simple" ? "advanced" : "simple";
    return setUiMode(next);
}
