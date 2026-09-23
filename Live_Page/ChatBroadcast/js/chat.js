import { renderMarkdown } from './markdown.js';

// One file per device type. Each documents that device's own play()
// signature and hardware; there is no shared game API to document.
const KNOWLEDGE_FILES = [
    "knowledge/knowledge.py",          // wand
    "knowledge/icon_display.py",       // icon display
];
let knowledgeText = "";

export async function loadKnowledgeBase() {
    knowledgeText = "";
    for (const filepath of KNOWLEDGE_FILES) {
        try {
            const resp = await fetch(filepath);
            if (resp.ok) {
                const text = await resp.text();
                knowledgeText += `\n\n--- FILE: ${filepath} ---\n${text}`;
                console.log("Loaded knowledge: " + filepath);
            }
        } catch (e) {
            console.log("Could not load " + filepath + ": " + e);
        }
    }
    return knowledgeText;
}

export function getKnowledgeText() { return knowledgeText; }
export function getKnowledgeFileCount() { return KNOWLEDGE_FILES.length; }

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

/** Device roles a reply may carry code for, in tab order. */
export const ROLES = ["wand", "icon"];

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
    let role = "wand";
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

export function trimForHistory(text) {
    if (!text.includes("```")) return text;
    return text.split("```").map((part, i) => {
        if (i % 2 === 0) return part;
        const lineCount = part.trim().split("\n").length - 1;
        return `\n[code: ${lineCount} lines, sent to editor]\n`;
    }).join("").trim();
}
