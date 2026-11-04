const KNOWLEDGE_FILES = ["knowledge/knowledge.py"];
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
    div.textContent = text;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
    return div;
}

export function removeTyping() {
    const box = document.getElementById("chat-box");
    box.querySelectorAll(".msg.system").forEach(m => {
        if (m.textContent === "Thinking...") box.removeChild(m);
    });
}

export function extractCode(text) {
    if (!text.includes("```")) return null;
    const blocks = text.split("```");
    for (let i = 1; i < blocks.length; i += 2) {
        let code = blocks[i];
        const lines = code.split("\n");
        if (lines[0] && ["python", "py", "micropython", ""].includes(lines[0].trim().toLowerCase())) {
            code = lines.slice(1).join("\n");
        }
        return code.trim();
    }
    return null;
}

export function parseNfcCards(text) {
    const match = text.match(/\[NFC_CARDS:\s*([^\]]+)\]/);
    if (!match) return null;
    return match[1].split(",").map(s => s.trim().replace(/^["']|["']$/g, "")).filter(Boolean);
}

export function stripNfcMarker(text) {
    return text.replace(/\[NFC_CARDS:[^\]]+\]/g, "").trim();
}

export function trimForHistory(text) {
    if (!text.includes("```")) return text;
    return text.split("```").map((part, i) => {
        if (i % 2 === 0) return part;
        const lineCount = part.trim().split("\n").length - 1;
        return `\n[code: ${lineCount} lines, sent to editor]\n`;
    }).join("").trim();
}
