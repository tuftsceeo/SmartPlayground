/**
 * Tag checklist modal (screen 6) — Box writes cards; app only lists what's needed.
 * Also derives which cards a game needs, from the tag set the game declares.
 */

import { slugify } from "./gameName.js";

export function showTagChecklist({ title, subtitle, tags, writtenCount = 0, warning = null }) {
    return new Promise((resolve) => {
        const overlay = document.getElementById("tag-checklist-overlay");
        const list = document.getElementById("tag-checklist-list");
        const bars = document.getElementById("tag-checklist-bars");
        const titleEl = document.getElementById("tag-checklist-title");
        const subEl = document.getElementById("tag-checklist-subtitle");

        titleEl.textContent = title;
        subEl.textContent = subtitle;
        list.innerHTML = "";
        bars.innerHTML = "";

        // An incomplete tag list means the teacher writes the wrong cards, so
        // say so on the screen rather than only in the console.
        if (warning) {
            const warn = document.createElement("div");
            warn.className = "tag-warning";
            warn.textContent = "\u26a0 " + warning;
            list.appendChild(warn);
        }

        tags.forEach((tag, i) => {
            const bar = document.createElement("div");
            bar.className = "tag-bar" + (i < writtenCount ? " done" : i === writtenCount ? " next" : "");
            bars.appendChild(bar);

            const row = document.createElement("div");
            row.className = "tag-row" + (i < writtenCount ? " done" : i === writtenCount ? " next" : "");
            const status = i < writtenCount ? "✓" : i === writtenCount ? "→ next" : "not yet";
            row.innerHTML =
                `<span class="tag-name">${escapeHtml(tag)}</span>` +
                `<span class="tag-status">${status}</span>`;
            list.appendChild(row);
        });

        overlay.classList.remove("hidden");

        function cleanup() {
            document.getElementById("tag-checklist-continue").removeEventListener("click", onContinue);
            document.getElementById("tag-checklist-back").removeEventListener("click", onBack);
        }
        function onContinue() {
            cleanup();
            overlay.classList.add("hidden");
            resolve({ action: "continue" });
        }
        function onBack() {
            cleanup();
            overlay.classList.add("hidden");
            resolve({ action: "back" });
        }

        document.getElementById("tag-checklist-continue").addEventListener("click", onContinue);
        document.getElementById("tag-checklist-back").addEventListener("click", onBack);
    });
}

function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

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

/**
 * Cards a game needs, in the order the Box should offer them:
 * `getcode:<slug>` (pull the game), `<slug>` (play the local copy), then the
 * game's own tags. Exit tags such as "stop" are deliberately absent — the Box
 * offers those from its permanent utility group.
 *
 * @param {string[]|null} nfcCards Cards named by the chat [NFC_CARDS:] marker.
 * @param {string} code Python source of the game.
 * @param {string} gameName Pretty name; slugified for the pickup tags.
 * @returns {{tags: string[], unresolved: string[]}}
 */
export function deriveRequiredTagsDetailed(nfcCards, code, gameName) {
    const slug = slugify(gameName || "");
    let tags;
    let unresolved = [];

    if (nfcCards && nfcCards.length > 0) {
        tags = [...nfcCards];
    } else {
        const declared = extractGameTags(code);
        if (declared.declared) {
            tags = declared.tags;
            unresolved = declared.unresolved;
        } else {
            tags = legacyHeuristicTags(code, slug);
        }
    }

    const out = [];
    if (slug) out.push("getcode:" + slug, slug);
    tags.forEach((t) => { if (t && !out.includes(t)) out.push(t); });
    return { tags: out, unresolved };
}

/** Back-compatible wrapper: the tag list alone. */
export function deriveRequiredTags(nfcCards, code, gameName) {
    return deriveRequiredTagsDetailed(nfcCards, code, gameName).tags;
}

/**
 * Last resort for freshly generated code that declares no COMMANDS set.
 * Kept from the original heuristic derivation so such games do not regress
 * to an empty list.
 */
function legacyHeuristicTags(code, slug) {
    const src = code || "";
    const notes = src.match(/note_[a-g](?:_high)?/gi);
    if (notes && notes.length > 1) {
        return [...new Set(notes.map((t) => t.toLowerCase()))];
    }
    const recipe = ["flour", "egg", "milk", "butter", "sugar"].filter((t) =>
        new RegExp('"' + t + '"').test(src) || new RegExp("'" + t + "'").test(src)
    );
    if (recipe.length > 1) return recipe;
    return slug ? [] : ["jumpin"];
}

export function tagCountLabel(n) {
    if (n <= 1) return null;
    return `needs ${n} NFC tags`;
}
