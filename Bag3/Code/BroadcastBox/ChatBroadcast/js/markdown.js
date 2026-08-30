/**
 * markdown.js — lightweight chat markdown renderer, ported from the EDL
 * GoPiGo chat tool's renderMd/highlightPython. No external dependencies:
 * fenced code blocks (with Copy + Send to editor buttons and a small
 * Python highlighter), tables, headings, lists, and inline bold/italic/code.
 */

import { dbg } from './debug.js';

let workspaceHandler = null;

/** Wired once from app.js so a code block's "Send to editor" button can
 *  push straight into the CodeMirror editor. */
export function setWorkspaceHandler(fn) {
    workspaceHandler = fn;
}

export function renderMarkdown(el, text) {
    el.innerHTML = "";
    const CODE_FENCE = /```(\w*)\n([\s\S]*?)```/g;
    const parts = [];
    let last = 0, m;
    while ((m = CODE_FENCE.exec(text)) !== null) {
        if (m.index > last) parts.push({ type: "text", val: text.slice(last, m.index) });
        parts.push({ type: "code", lang: m[1] || "python", val: m[2] });
        last = m.index + m[0].length;
    }
    if (last < text.length) parts.push({ type: "text", val: text.slice(last) });

    for (const part of parts) {
        el.appendChild(part.type === "code" ? buildCodeBlock(part.lang, part.val) : buildTextBlock(part.val));
    }
}

function buildCodeBlock(lang, code) {
    const wrap = document.createElement("div");
    wrap.className = "code-block-wrap";
    const trimmed = code.replace(/\n$/, "");
    const isPy = /^(py|python|micropython)?$/i.test((lang || "").trim());

    const bar = document.createElement("div");
    bar.className = "code-block-bar";
    const langLabel = document.createElement("span");
    langLabel.textContent = lang || "python";
    bar.appendChild(langLabel);

    const actions = document.createElement("div");
    actions.className = "code-block-actions";

    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "code-action-btn";
    copyBtn.textContent = "Copy";
    copyBtn.addEventListener("click", () => copyCode(trimmed, copyBtn));
    actions.appendChild(copyBtn);

    if (workspaceHandler) {
        const sendBtn = document.createElement("button");
        sendBtn.type = "button";
        sendBtn.className = "code-action-btn";
        sendBtn.textContent = "Send to editor";
        sendBtn.addEventListener("click", () => {
            dbg("markdown", `"Send to editor" clicked (${trimmed.length} chars)`);
            workspaceHandler(trimmed);
        });
        actions.appendChild(sendBtn);
    }

    bar.appendChild(actions);
    wrap.appendChild(bar);

    const pre = document.createElement("pre");
    const codeEl = document.createElement("code");
    codeEl.innerHTML = isPy ? highlightPython(trimmed) : escHtml(trimmed);
    pre.appendChild(codeEl);
    wrap.appendChild(pre);

    wrap.dataset.code = trimmed;
    return wrap;
}

function isTableRow(line) { return /^\s*\|.*\|\s*$/.test(line.trim()); }
function isSepRow(line) { return /^\s*\|?(\s*:?-{2,}:?\s*\|)+\s*:?-{2,}:?\s*\|?\s*$/.test(line.trim()); }
function splitRow(line) {
    let t = line.trim();
    if (t.startsWith("|")) t = t.slice(1);
    if (t.endsWith("|")) t = t.slice(0, -1);
    return t.split("|").map((c) => c.trim());
}

function buildTextBlock(text) {
    const frag = document.createDocumentFragment();
    const lines = text.split("\n");
    let i = 0;
    while (i < lines.length) {
        const line = lines[i];
        if (!line.trim()) { i++; continue; }

        const hm = line.match(/^(#{1,3})\s+(.+)/);
        if (hm) {
            const h = document.createElement("h" + Math.min(hm[1].length + 3, 6));
            h.innerHTML = inlineMd(hm[2]);
            frag.appendChild(h);
            i++; continue;
        }

        if (isTableRow(line) && i + 1 < lines.length && isSepRow(lines[i + 1])) {
            const headCells = splitRow(line);
            const table = document.createElement("table");
            const thead = document.createElement("thead");
            const htr = document.createElement("tr");
            headCells.forEach((c) => { const th = document.createElement("th"); th.innerHTML = inlineMd(c); htr.appendChild(th); });
            thead.appendChild(htr); table.appendChild(thead);
            const tbody = document.createElement("tbody");
            i += 2;
            while (i < lines.length && isTableRow(lines[i])) {
                const cells = splitRow(lines[i]);
                const tr = document.createElement("tr");
                cells.forEach((c) => { const td = document.createElement("td"); td.innerHTML = inlineMd(c); tr.appendChild(td); });
                tbody.appendChild(tr);
                i++;
            }
            table.appendChild(tbody);
            frag.appendChild(table);
            continue;
        }

        if (/^[-*]\s/.test(line)) {
            const ul = document.createElement("ul");
            while (i < lines.length && /^[-*]\s/.test(lines[i])) {
                const li = document.createElement("li");
                li.innerHTML = inlineMd(lines[i].replace(/^[-*]\s/, ""));
                ul.appendChild(li); i++;
            }
            frag.appendChild(ul); continue;
        }

        if (/^\d+\.\s/.test(line)) {
            const ol = document.createElement("ol");
            while (i < lines.length && /^\d+\.\s/.test(lines[i])) {
                const li = document.createElement("li");
                li.innerHTML = inlineMd(lines[i].replace(/^\d+\.\s/, ""));
                ol.appendChild(li); i++;
            }
            frag.appendChild(ol); continue;
        }

        const p = document.createElement("p");
        p.innerHTML = inlineMd(line);
        frag.appendChild(p);
        i++;
    }
    return frag;
}

function inlineMd(text) {
    return escHtml(text)
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.+?)\*/g, "<em>$1</em>")
        .replace(/`([^`]+)`/g, "<code>$1</code>");
}

function escHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/** Small dependency-free Python highlighter — mirrors the markdown parser's approach. */
function highlightPython(code) {
    const TOKEN = /(#[^\n]*)|("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')|\b(def|class|return|if|elif|else|for|while|in|is|not|and|or|import|from|as|with|try|except|finally|raise|pass|break|continue|lambda|yield|global|nonlocal|assert|del|async|await)\b|\b(None|True|False|self)\b|\b(\d+\.\d+|\.\d+|\d+)\b|\b([A-Za-z_]\w*)(?=\s*\()/g;
    let out = "", last = 0, m;
    while ((m = TOKEN.exec(code)) !== null) {
        if (m.index > last) out += escHtml(code.slice(last, m.index));
        const [, comment, str, kw, lit, num, fn] = m;
        if (comment != null) out += `<span class="tok-com">${escHtml(comment)}</span>`;
        else if (str != null) out += `<span class="tok-str">${escHtml(str)}</span>`;
        else if (kw != null) out += `<span class="tok-kw">${escHtml(kw)}</span>`;
        else if (lit != null) out += `<span class="tok-lit">${escHtml(lit)}</span>`;
        else if (num != null) out += `<span class="tok-num">${escHtml(num)}</span>`;
        else if (fn != null) out += `<span class="tok-fn">${escHtml(fn)}</span>`;
        last = TOKEN.lastIndex;
    }
    out += escHtml(code.slice(last));
    return out;
}

async function copyCode(text, btn) {
    const orig = btn.textContent;
    try {
        await navigator.clipboard.writeText(text);
        btn.textContent = "Copied";
    } catch {
        btn.textContent = "Couldn't copy";
    }
    setTimeout(() => { btn.textContent = orig; }, 1500);
}
