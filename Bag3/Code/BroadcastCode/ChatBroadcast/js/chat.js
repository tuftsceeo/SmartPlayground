import { renderMarkdown } from './markdown.js';
import { ROLES as ROLE_TABLE, DEFAULT_ROLE } from './roles.js';
import { knowledgePaths } from './prompt/buildRequest.js';

// path -> text for every knowledge file (knowledgePaths()); empty until
// loadKnowledgeBase() succeeds.
let knowledgeFiles = {};

/**
 * Fetch every knowledge file. All of them are required: a chat without its
 * knowledge base answers from general memory, which is how it ends up
 * inventing device behavior. Throws naming every file that failed.
 * @returns {Promise<Object<string,string>>} path -> text
 */
export async function loadKnowledgeBase() {
    knowledgeFiles = {};
    const paths = knowledgePaths();
    const failed = [];
    const loaded = {};
    await Promise.all(paths.map(async (path) => {
        try {
            const resp = await fetch(path, { cache: "no-cache" });
            if (!resp.ok) { failed.push(`${path} (HTTP ${resp.status})`); return; }
            loaded[path] = await resp.text();
        } catch (e) {
            failed.push(`${path} (${e.message})`);
        }
    }));
    if (failed.length) throw new Error(`Could not load knowledge files: ${failed.join(", ")}`);
    knowledgeFiles = loaded;
    return knowledgeFiles;
}

export function getKnowledgeFiles() { return knowledgeFiles; }
export function getKnowledgeFileCount() { return Object.keys(knowledgeFiles).length; }

export function addMsg(text, cls = "bot") {
    const box = document.getElementById("chat-box");
    const div = document.createElement("div");
    div.classList.add("msg", cls);
    if (cls === "bot") {
        renderMarkdown(div, text);
    } else {
        div.textContent = text;
    }
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
    return div;
}

export function addThinkingMsg() {
    const box = document.getElementById("chat-box");
    const div = document.createElement("div");
    div.classList.add("msg", "system");
    div.innerHTML = '<span class="thinking-dots"><span></span><span></span><span></span></span>Thinking…';
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
    return div;
}

export function removeTyping() {
    const box = document.getElementById("chat-box");
    box.querySelectorAll(".msg.system").forEach(m => {
        if (m.textContent.startsWith("Thinking")) box.removeChild(m);
    });
}

/** Device roles a reply may carry code for, in tab order (roles.js). */
export const ROLES = ROLE_TABLE.map(r => r.key);

const LANG_LINES = ["python", "py", "micropython", ""];

/**
 * Strip a fenced block's language line and trim it.
 * @param {string} block  the text between two ``` fences
 */
function blockCode(block) {
    const lines = block.split("\n");
    if (lines[0] && LANG_LINES.includes(lines[0].trim().toLowerCase())) {
        return lines.slice(1).join("\n").trim();
    }
    return block.trim();
}

/**
 * The role a fenced block belongs to, from the [DEVICE: ...] marker most
 * recently seen before it. Defaults to "wand" so a single-block reply --
 * every reply before this marker existed -- still lands somewhere.
 */
function roleBefore(prose) {
    const matches = [...prose.matchAll(/\[DEVICE:\s*([a-z_]+)\s*\]/gi)];
    if (!matches.length) return null;
    return matches[matches.length - 1][1].toLowerCase();
}

/**
 * Every fenced code block in a reply, tagged with its device role.
 *
 * A multi-device game is several files -- one per device type -- so a reply
 * can carry more than one block. Each is preceded by a [DEVICE: wand] or
 * [DEVICE: icon] marker; blocks with no marker before them are wand code.
 * A block under a marker naming no current role (e.g. the retired `splat`)
 * is left out, so it never lands in another role's editor.
 *
 * @returns {{role: string, code: string}[]} in the order they appeared
 */
export function extractCodeBlocks(text) {
    if (!text || !text.includes("```")) return [];
    const parts = text.split("```");
    const out = [];
    let role = DEFAULT_ROLE;
    for (let i = 0; i < parts.length; i++) {
        if (i % 2 === 0) {
            // Prose. A marker here names the role of the block that follows.
            const named = roleBefore(parts[i]);
            if (named) role = named;
            continue;
        }
        const code = blockCode(parts[i]);
        if (code && ROLES.includes(role)) out.push({ role, code });
    }
    return out;
}

/**
 * The first block's code, or null.
 * Single-role callers that do not care which device a reply was for.
 */
export function extractCode(text) {
    const blocks = extractCodeBlocks(text);
    return blocks.length ? blocks[0].code : null;
}

export function stripDeviceMarkers(text) {
    return text.replace(/\[DEVICE:\s*[a-z_]+\s*\]/gi, "").trim();
}

export function parseNfcCards(text) {
    const match = text.match(/\[NFC_CARDS:\s*([^\]]+)\]/);
    if (!match) return null;
    return match[1].split(",").map(s => s.trim().replace(/^["']|["']$/g, "")).filter(Boolean);
}

export function stripNfcMarker(text) {
    return text.replace(/\[NFC_CARDS:[^\]]+\]/g, "").trim();
}

export function parseGameName(text) {
    const match = text.match(/\[GAME_NAME:\s*([^\]]+)\]/);
    if (!match) return null;
    return match[1].trim().replace(/^["']|["']$/g, "") || null;
}

export function stripGameNameMarker(text) {
    return text.replace(/\[GAME_NAME:[^\]]+\]/g, "").trim();
}

/** Follow-up options from a [CHOICES: "a", "b"] marker, or null. */
export function parseChoices(text) {
    const match = text.match(/\[CHOICES:\s*([^\]]+)\]/);
    if (!match) return null;
    const quoted = [...match[1].matchAll(/["“]([^"”]+)["”]/g)].map(m => m[1].trim());
    const list = quoted.length ? quoted : match[1].split(",").map(s => s.trim());
    return list.filter(Boolean).slice(0, 4);
}

export function stripChoicesMarker(text) {
    return text.replace(/\[CHOICES:[^\]]+\]/g, "").trim();
}

/** Design brief between [GAME_BRIEF] and [/GAME_BRIEF] lines, or null. */
export function parseGameBrief(text) {
    const match = text.match(/\[GAME_BRIEF\]([\s\S]*?)\[\/GAME_BRIEF\]/);
    if (!match) return null;
    return match[1].trim() || null;
}

/** The reply with its brief block removed, for showing the text around it. */
export function stripGameBrief(text) {
    return text.replace(/\[GAME_BRIEF\][\s\S]*?(\[\/GAME_BRIEF\]|$)/g, "").trim();
}

/** Splats per wand the simulator can show, and how many wands it can hold a game for. */
const SETTINGS_LIMITS = { wand_splats: [0, 2], wands: [1, 4] };

/**
 * Simulator settings from a [GAME_SETTINGS: {...}] marker, or null.
 *
 * The game code does not carry these; only the practice window reads them.
 * `wand_splats` is how many Splats each wand starts with paired (0..2);
 * `wands` is how many wands the game is meant for (1..4). A field that is
 * missing, not a whole number or out of range is left out, and a marker
 * whose JSON does not parse gives null.
 */
export function parseGameSettings(text) {
    const match = text.match(/\[GAME_SETTINGS:\s*(\{[\s\S]*?\})\s*\]/);
    if (!match) return null;
    let raw;
    try {
        raw = JSON.parse(match[1]);
    } catch {
        return null;
    }
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
    const out = {};
    for (const [key, [lo, hi]] of Object.entries(SETTINGS_LIMITS)) {
        const n = raw[key];
        if (Number.isInteger(n) && n >= lo && n <= hi) out[key] = n;
    }
    return Object.keys(out).length ? out : null;
}

export function stripGameSettingsMarker(text) {
    // The line as well as the JSON: a reply still streaming has no closing
    // bracket yet.
    return text.replace(/\[GAME_SETTINGS:\s*\{[\s\S]*?\}\s*\]/g, "")
        .replace(/\[GAME_SETTINGS:[^\n]*/g, "").trim();
}

/** Every marker line removed, for showing a reply (complete or partial). */
export function stripAllMarkers(text) {
    return stripDeviceMarkers(stripChoicesMarker(stripGameNameMarker(stripNfcMarker(stripGameSettingsMarker(text)))));
}

export function trimForHistory(text) {
    if (!text.includes("```")) return text;
    return text.split("```").map((part, i) => {
        if (i % 2 === 0) return part;
        const lineCount = part.trim().split("\n").length - 1;
        return `\n[code: ${lineCount} lines, sent to editor]\n`;
    }).join("").trim();
}
