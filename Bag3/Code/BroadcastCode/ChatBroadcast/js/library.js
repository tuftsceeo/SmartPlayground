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
 * Store one game. `code` is the wand file; `roleCode` is every other role's
 * code keyed by role (roles.js), empty/absent for a single-device game.
 * `iconCode` is kept as a plain top-level field too -- mirroring
 * `roleCode.icon` -- since it predates `roleCode` and other code may still
 * read it directly. Entries saved before a role existed simply have no
 * entry for it and load as if that role had no code.
 */
export function saveGame({ name, desc, code, roleCode, iconCode, requiredTags, hardware, chatHistory, icons }) {
    const list = loadSavedGames();
    const id =
        typeof crypto !== "undefined" && crypto.randomUUID
            ? crypto.randomUUID()
            : String(Date.now());
    const resolvedRoleCode = { ...(roleCode || {}) };
    if (iconCode && !resolvedRoleCode.icon) resolvedRoleCode.icon = iconCode;
    const entry = {
        id,
        name: name || "Untitled game",
        desc: desc || "",
        code: code || "",
        iconCode: resolvedRoleCode.icon || "",
        roleCode: resolvedRoleCode,
        requiredTags: requiredTags || [],
        hardware: hardware || null,
        chatHistory: chatHistory || [],
        // {name: duty[768]} -- only the icons this game edited. Kept with the
        // game so reopening it draws what it was saved with, whatever later
        // games did to an icon of the same name.
        icons: icons || {},
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
