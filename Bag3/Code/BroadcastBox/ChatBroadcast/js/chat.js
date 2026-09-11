import { renderMarkdown } from './markdown.js';

/* The knowledge base is core plus one file per device kind in play. The
   model is told about the hardware the game actually uses and nothing else,
   so a wand-only game is never offered station verbs. */
const CORE_KNOWLEDGE = "knowledge/core.py";
const DEVICE_KNOWLEDGE = {
    wand: "knowledge/wand.py",
    icon_station: "knowledge/icon_station.py",
};

/** Device kinds a game can be written for. */
export const KNOWN_HUBTYPES = Object.keys(DEVICE_KNOWLEDGE);

let knowledgeText = "";
let loadedFiles = [];

/**
 * Load core plus the device files for the given hubtypes.
 *
 * @param {string[]} hubtypes device kinds in play, e.g. ["wand", "icon_station"]
 * @returns {Promise<string>} the concatenated knowledge text
 */
export async function loadKnowledgeBase(hubtypes = ["wand"]) {
    const files = [CORE_KNOWLEDGE];
    for (const hub of hubtypes) {
        const path = DEVICE_KNOWLEDGE[hub];
        if (path && !files.includes(path)) files.push(path);
    }
    knowledgeText = "";
    loadedFiles = [];
    for (const filepath of files) {
        const resp = await fetch(filepath);
        if (!resp.ok) {
            throw new Error(`knowledge file ${filepath} failed to load (${resp.status})`);
        }
        knowledgeText += `\n\n--- FILE: ${filepath} ---\n${await resp.text()}`;
        loadedFiles.push(filepath);
        console.log("Loaded knowledge: " + filepath);
    }
    return knowledgeText;
}

export function getKnowledgeText() { return knowledgeText; }
export function getKnowledgeFileCount() { return loadedFiles.length; }

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

const PY_FENCES = ["python", "py", "micropython", ""];

/** A fence's language tag, lowercased, or "" for an untagged fence. */
function fenceLang(block) {
    const first = block.split("\n")[0].trim().toLowerCase();
    return /^[a-z0-9+#_-]{1,12}$/.test(first) ? first : "";
}

/** A fenced block's body, with its language line removed. */
function fenceBody(block) {
    return fenceLang(block) ? block.split("\n").slice(1).join("\n").trim() : block.trim();
}

/**
 * Every python block in a reply, with the role marker that precedes it.
 *
 * A game is one file per device, so a reply carries one block per role,
 * each headed by [ROLE: <role> <hubtype>]. A block with no marker before
 * it is taken as the wand's, which is what a single-device reply looks
 * like.
 *
 * @param {string} text the model's reply
 * @returns {{role: string, hubtype: string, code: string}[]}
 */
export function extractCodeBlocks(text) {
    if (!text || !text.includes("```")) return [];
    const parts = text.split("```");
    const out = [];
    for (let i = 1; i < parts.length; i += 2) {
        // A reply also carries [ICON:] json blocks; only python is code.
        if (!PY_FENCES.includes(fenceLang(parts[i]))) continue;
        const code = fenceBody(parts[i]);
        if (!code) continue;
        // The marker sits in the prose immediately before the fence; the last
        // one there is this block's, not an earlier block's.
        const markers = [...parts[i - 1].matchAll(/\[ROLE:\s*([a-z][a-z0-9_]*)\s+([a-z][a-z0-9_]*)\s*\]/gi)];
        const m = markers[markers.length - 1];
        out.push({
            role: m ? m[1].toLowerCase() : "wand",
            hubtype: m ? m[2].toLowerCase() : "wand",
            code,
        });
    }
    return out;
}

/**
 * Icons shipped with a game: [ICON: name] followed by a json block of
 * {w, h, px} where px is w*h [r,g,b] triples, row-major from top-left.
 *
 * @param {string} text the model's reply
 * @returns {{name: string, w: number, h: number, px: number[][]}[]}
 */
export function extractIcons(text) {
    if (!text || !text.includes("[ICON:")) return [];
    const parts = text.split("```");
    const out = [];
    for (let i = 1; i < parts.length; i += 2) {
        const markers = [...parts[i - 1].matchAll(/\[ICON:\s*([a-z][a-z0-9_]*)\s*\]/gi)];
        const m = markers[markers.length - 1];
        if (!m) continue;
        const body = fenceBody(parts[i]);
        // A malformed icon is worth a loud failure: the game names it and
        // will raise on the station if it never arrives.
        const obj = JSON.parse(body);
        const px = obj.px || obj.pixels;
        if (!Array.isArray(px)) throw new Error(`icon ${m[1]}: no px array`);
        const w = obj.w || 16;
        const h = obj.h || 16;
        if (px.length !== w * h) {
            throw new Error(`icon ${m[1]}: ${px.length} pixels, expected ${w * h}`);
        }
        out.push({ name: m[1].toLowerCase(), w, h, px });
    }
    return out;
}

/** Strip the role and icon markers from prose shown to the teacher. */
export function stripBlockMarkers(text) {
    return text.replace(/\[(?:ROLE|ICON):[^\]]*\]/gi, "").trim();
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

export function trimForHistory(text) {
    if (!text.includes("```")) return text;
    return text.split("```").map((part, i) => {
        if (i % 2 === 0) return part;
        const lineCount = part.trim().split("\n").length - 1;
        return `\n[code: ${lineCount} lines, sent to editor]\n`;
    }).join("").trim();
}
