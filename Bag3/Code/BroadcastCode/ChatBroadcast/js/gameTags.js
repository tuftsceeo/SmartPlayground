/**
 * gameTags.js — read the tag set a wand game declares, from its source.
 *
 * A game names the cards it reads in a module-level `COMMANDS` set. That set
 * is what NfcReader matches a scanned card against, so it is the only honest
 * answer to "which cards does this game need?" — and it is what the Box's
 * write menu and the send checklist both have to agree on.
 *
 * Pure functions; no DOM. `tools/check_tags.mjs` asserts the output against
 * every game source in the tree.
 */

/**
 * Names that appear in a COMMANDS expression but never denote card names.
 * `_EXIT_TAGS` is the wand's "any other game tag, or stop" set — those cards
 * are not specific to this game, so they are never listed here (the Box
 * offers "stop" from its permanent utility group instead).
 */
const NOT_A_TAG_SOURCE = new Set([
    "_EXIT_TAGS", "EXIT_TAGS", "GAME_TAGS", "CONTROL_TAGS", "HIDDEN_TAGS",
    "exit_tags_excluding",
    "set", "frozenset", "list", "tuple", "dict", "keys", "values", "union",
]);

/** Every single- or double-quoted string in `src`, in order of appearance. */
function stringLiterals(src) {
    const out = [];
    const re = /(['"])((?:\\.|(?!\1).)*)\1/g;
    let m;
    while ((m = re.exec(src)) !== null) out.push(m[2]);
    return out;
}

/** Quoted strings used as dict keys, i.e. followed by a colon. */
function dictKeys(src) {
    const out = [];
    const re = /(['"])((?:\\.|(?!\1).)*)\1\s*:/g;
    let m;
    while ((m = re.exec(src)) !== null) out.push(m[2]);
    return out;
}

/**
 * The right-hand side of a top-level `name = ...` assignment, following
 * brackets across lines so multi-line dict/set literals come back whole.
 * Returns null when there is no such assignment.
 */
function topLevelAssignment(src, name) {
    const start = new RegExp("^" + name + "\\s*=\\s*", "m").exec(src);
    if (!start) return null;
    let i = start.index + start[0].length;
    let depth = 0;
    let quote = null;
    let out = "";
    for (; i < src.length; i++) {
        const c = src[i];
        out += c;
        if (quote) {
            if (c === "\\") { out += src[++i] || ""; continue; }
            if (c === quote) quote = null;
            continue;
        }
        if (c === "'" || c === '"') { quote = c; continue; }
        if (c === "(" || c === "[" || c === "{") { depth++; continue; }
        if (c === ")" || c === "]" || c === "}") { depth--; continue; }
        if (c === "\n" && depth <= 0) {
            // A trailing operator or backslash means the expression continues.
            if (/[|+\\,]\s*$/.test(out.slice(0, -1))) continue;
            break;
        }
    }
    return out.trim();
}

/**
 * Tags a game declares, read from its `COMMANDS` (or `GAME_COMMANDS`) set.
 *
 * Mirrors what the simulator derives with a real interpreter in
 * Simulator/py/runtime.py get_capabilities(): everything the expression names
 * as a literal, plus the contents of any one-level name it unions in —
 * `set(NOTE_TAGS.keys())` and `set(RECIPE)` both appear in the shipped
 * example payloads, so a literals-only read misses every note and ingredient.
 *
 * @param {string} code Python source of the game.
 * @returns {{declared: boolean, tags: string[], unresolved: string[]}}
 *   `declared` is false when the source has no COMMANDS assignment at all.
 *   `unresolved` names terms that could not be reduced to literals — the
 *   caller must surface these rather than shipping a short list silently.
 */
export function extractGameTags(code) {
    const src = code || "";
    const expr =
        topLevelAssignment(src, "COMMANDS") ??
        topLevelAssignment(src, "GAME_COMMANDS");
    if (expr === null) return { declared: false, tags: [], unresolved: [] };

    const tags = [];
    const unresolved = [];
    const push = (t) => { if (t && !tags.includes(t)) tags.push(t); };

    stringLiterals(expr).forEach(push);

    // Bare names unioned into the expression, e.g. `| set(RECIPE)`.
    const names = new Set();
    const idRe = /[A-Za-z_][A-Za-z0-9_]*/g;
    let m;
    const exprNoStrings = expr.replace(/(['"])(?:\\.|(?!\1).)*\1/g, '""');
    while ((m = idRe.exec(exprNoStrings)) !== null) {
        if (!NOT_A_TAG_SOURCE.has(m[0])) names.add(m[0]);
    }

    for (const name of names) {
        const body = topLevelAssignment(src, name);
        if (body === null) { unresolved.push(name); continue; }
        const keys = dictKeys(body);
        const found = keys.length ? keys : stringLiterals(body);
        if (!found.length) { unresolved.push(name); continue; }
        found.forEach(push);
    }

    return { declared: true, tags, unresolved };
}
