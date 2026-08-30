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

export function saveGame({ name, desc, code, requiredTags, chatHistory }) {
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
        requiredTags: requiredTags || [],
        chatHistory: chatHistory || [],
        updatedAt: Date.now(),
    };
    list.unshift(entry);
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
