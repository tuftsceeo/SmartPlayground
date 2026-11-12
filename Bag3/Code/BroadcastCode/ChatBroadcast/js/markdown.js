/**
 * markdown.js — lightweight chat markdown renderer, ported from the EDL
 * GoPiGo chat tool's renderMd/highlightPython. No external dependencies:
 * fenced code blocks (with Hide/Show + View code buttons and a small
 * Python highlighter), tables, headings, lists, and inline bold/italic/code.
 */

import { dbg } from './debug.js';
import { getUiMode } from './uiMode.js';

let workspaceHandler = null;

/** Wired once from app.js so a code block's "View code" button opens it
 *  in the code drawer. */
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

    const simple = getUiMode() === "simple" && !!workspaceHandler;
    let seeCodeAdded = false;
    for (const part of parts) {
        if (part.type === "code" && simple) {
            // Simple mode: one "See the code" link per reply, no inline block.
            if (!seeCodeAdded) {
                el.appendChild(buildSeeCodeLink(part.val));
                seeCodeAdded = true;
            }
            continue;
        }
        el.appendChild(part.type === "code"
            ? buildCodeBlock(part.lang, part.val, { collapsed: getUiMode() === "simple" })
            : buildTextBlock(part.val));
    }
}

/** The simple-mode stand-in for a code block: a link that opens the code drawer. */
function buildSeeCodeLink(code) {
    const link = document.createElement("button");
    link.type = "button";
    link.className = "see-code";
    link.textContent = "See the code";
    link.addEventListener("click", () => {
        dbg("markdown", `"See the code" clicked (${code.length} chars)`);
        workspaceHandler(code.replace(/\n$/, ""));
    });
    return link;
}

/**
 * A fenced block with its bar. opts.collapsed starts it folded to the bar
 * (simple mode does this for every reply); opts.editor = false leaves out
 * "View code".
 */
export function buildCodeBlock(lang, code, opts = {}) {
    const wrap = document.createElement("div");
    wrap.className = "code-block-wrap";
    if (opts.collapsed) wrap.classList.add("is-collapsed");
    const trimmed = code.replace(/\n$/, "");
    const isPy = /^(py|python|micropython)?$/i.test((lang || "").trim());

    const bar = document.createElement("div");
    bar.className = "code-block-bar";
    const langLabel = document.createElement("span");
    langLabel.textContent = lang || "python";
    bar.appendChild(langLabel);

    const actions = document.createElement("div");
    actions.className = "code-block-actions";

    const foldBtn = document.createElement("button");
    foldBtn.type = "button";
    foldBtn.className = "code-action-btn";
    const foldLabel = () => {
        foldBtn.textContent = wrap.classList.contains("is-collapsed") ? "Show" : "Hide";
    };
    foldLabel();
    foldBtn.addEventListener("click", () => {
        wrap.classList.toggle("is-collapsed");
        foldLabel();
    });
    actions.appendChild(foldBtn);

    if (workspaceHandler && opts.editor !== false) {
        const sendBtn = document.createElement("button");
        sendBtn.type = "button";
        sendBtn.className = "code-action-btn";
        sendBtn.textContent = "View code";
        sendBtn.addEventListener("click", () => {
            dbg("markdown", `"View code" clicked (${trimmed.length} chars)`);
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

const LIST_ITEM = /^\s*([-*]|\d+\.)\s/;
function indentOf(line) { return line.match(/^\s*/)[0].replace(/\t/g, "    ").length; }

/** A list starting at lines[i], nesting items indented deeper than `indent`
 *  under the item above them. Returns [element, index after the list]. */
function buildList(lines, i, indent) {
    const ordered = /^\s*\d+\.\s/.test(lines[i]);
    const list = document.createElement(ordered ? "ol" : "ul");
    let li = null;
    while (i < lines.length) {
        const line = lines[i];
        if (!line.trim()) {
            const nxt = lines.slice(i + 1).find((l) => l.trim());
            if (nxt && LIST_ITEM.test(nxt) && indentOf(nxt) >= indent) { i++; continue; }
            break;
        }
        if (!LIST_ITEM.test(line)) break;
        const d = indentOf(line);
        if (d < indent) break;
        if (d > indent && li) {
            const [sub, next] = buildList(lines, i, d);
            li.appendChild(sub);
            i = next; continue;
        }
        if (/^\s*\d+\.\s/.test(line) !== ordered) break;
        li = document.createElement("li");
        li.innerHTML = inlineMd(line.replace(LIST_ITEM, ""));
        list.appendChild(li); i++;
    }
    return [list, i];
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

        if (LIST_ITEM.test(line)) {
            const [list, next] = buildList(lines, i, indentOf(line));
            frag.appendChild(list);
            i = next; continue;
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
