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
    const role = matches[matches.length - 1][1].toLowerCase();
    return ROLES.includes(role) ? role : null;
}

/**
 * Every fenced code block in a reply, tagged with its device role.
 *
 * A multi-device game is several files -- one per device type -- so a reply
 * can carry more than one block. Each is preceded by a [DEVICE: wand] or
 * [DEVICE: icon] marker; blocks with no marker before them are wand code.
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
        if (code) out.push({ role, code });
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

/** Every marker line removed, for showing a reply (complete or partial). */
export function stripAllMarkers(text) {
    return stripDeviceMarkers(stripChoicesMarker(stripGameNameMarker(stripNfcMarker(text))));
}

export function trimForHistory(text) {
    if (!text.includes("```")) return text;
    return text.split("```").map((part, i) => {
        if (i % 2 === 0) return part;
        const lineCount = part.trim().split("\n").length - 1;
        return `\n[code: ${lineCount} lines, sent to editor]\n`;
    }).join("").trim();
}
