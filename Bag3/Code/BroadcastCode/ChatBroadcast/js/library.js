/** localStorage library for saved chat/code sessions. */

const KEY = "wandcoder.savedGames";

export function loadSavedGames() {
    try {
        const raw = localStorage.getItem(KEY);
        if (!raw) return [];
        const list = JSON.parse(raw);
        return Array.isArray(list) ? list : [];
    } catch (_) {
        return [];
    }
}

function writeAll(list) {
    localStorage.setItem(KEY, JSON.stringify(list));
}

/**
 * Store one game. `code` is the wand file; `iconCode` is the icon display's,
 * empty for a single-device game. Entries saved before the display existed
 * have no iconCode and load as wand-only.
 */
export function saveGame({ name, desc, code, iconCode, requiredTags, hardware, chatHistory }) {
    const list = loadSavedGames();
    const id =
        typeof crypto !== "undefined" && crypto.randomUUID
            ? crypto.randomUUID()
            : String(Date.now());
    const entry = {
        id,
        name: name || "Untitled game",
        desc: desc || "",
        code: code || "",
        iconCode: iconCode || "",
        requiredTags: requiredTags || [],
        hardware: hardware || null,
        chatHistory: chatHistory || [],
        updatedAt: Date.now(),
    };
    list.unshift(entry);
    writeAll(list);
    return entry;
}

export function renameSavedGame(id, name) {
    const list = loadSavedGames();
    const entry = list.find((g) => g.id === id);
    if (!entry) return null;
    entry.name = (name || "").trim() || entry.name;
    entry.updatedAt = Date.now();
    writeAll(list);
    return entry;
}

export function deleteSavedGame(id) {
    const list = loadSavedGames().filter((g) => g.id !== id);
    writeAll(list);
    return list;
}

export function findSavedGame(id) {
    return loadSavedGames().find((g) => g.id === id) || null;
}
