import { EditorView, basicSetup } from 'https://esm.sh/codemirror@6.0.1';
import { python } from 'https://esm.sh/@codemirror/lang-python@6.1.6';
import { HighlightStyle, syntaxHighlighting } from 'https://esm.sh/@codemirror/language@6';
import { tags } from 'https://esm.sh/@lezer/highlight@1';

let editorView = null;

/* A game is one file per device role, and the editor shows one role at a
   time. Each role keeps its own document and its own version history, so
   switching tabs does not lose the other role's edits. */
const roles = new Map();   // role -> { hubtype, code, versions: [], index }
let currentRole = "wand";

const EMPTY_DOC = "# AI-generated code will appear here\n";

function roleState(role) {
    if (!roles.has(role)) {
        roles.set(role, { hubtype: role === "wand" ? "wand" : null, code: EMPTY_DOC, versions: [], index: -1 });
    }
    return roles.get(role);
}

/* Same "GitHub Light" palette as the chat code blocks (see app.css --code-*
   variables) — referenced by var() here so there is one source of truth and
   the two never drift apart again. */
const lightHighlightStyle = HighlightStyle.define([
    { tag: tags.keyword, color: 'var(--code-keyword)' },
    { tag: tags.operator, color: 'var(--code-keyword)' },
    { tag: [tags.string, tags.special(tags.string)], color: 'var(--code-string)' },
    { tag: tags.comment, color: 'var(--code-comment)', fontStyle: 'italic' },
    { tag: tags.number, color: 'var(--code-number)' },
    { tag: [tags.function(tags.variableName), tags.function(tags.propertyName)], color: 'var(--code-function)' },
    { tag: [tags.bool, tags.null, tags.atom, tags.self, tags.className], color: 'var(--code-literal)' },
    { tag: tags.propertyName, color: 'var(--code-number)' },
    { tag: tags.definition(tags.variableName), color: 'var(--code-literal)' },
]);

const lightEditorTheme = EditorView.theme({
    '&': {
        height: '100%',
        maxHeight: '100%',
        backgroundColor: 'var(--code-bg)',
        color: 'var(--code-text)',
    },
    '.cm-scroller': { overflow: 'auto' },
    '.cm-content': { caretColor: 'var(--code-text)' },
    '.cm-gutters': { backgroundColor: 'var(--code-bg)', color: 'var(--muted)', border: 'none' },
    '.cm-activeLine': { backgroundColor: 'rgba(9,105,218,0.06)' },
    '.cm-activeLineGutter': { backgroundColor: 'rgba(9,105,218,0.06)' },
    '.cm-selectionBackground, ::selection': { backgroundColor: 'rgba(84,174,255,0.35) !important' },
}, { dark: false });

export function initEditor() {
    editorView = new EditorView({
        doc: EMPTY_DOC,
        extensions: [basicSetup, python(), syntaxHighlighting(lightHighlightStyle), lightEditorTheme],
        parent: document.getElementById('code-editor'),
    });
}

/** The role the editor is currently showing. */
export function getRole() { return currentRole; }

/**
 * Show a different role's file, keeping the current one's edits.
 *
 * @param {string} role role name, e.g. "wand" or "icon"
 */
export function setRole(role) {
    if (role === currentRole) return;
    roleState(currentRole).code = getCode();
    currentRole = role;
    writeDoc(roleState(role).code);
    updateVersionUI();
}

/** Roles that have code, in the order they were first written. */
export function getRoles() {
    return [...roles.keys()].filter((r) => roles.get(r).versions.length > 0);
}

/** What device kind a role runs on, or null if never declared. */
export function getHubtype(role) { return roleState(role).hubtype; }

/** One role's current source, whether or not it is the role on screen. */
export function getCodeFor(role) {
    return role === currentRole ? getCode() : roleState(role).code;
}

/** Forget every role's code and history. */
export function resetRoles(role = "wand") {
    roles.clear();
    currentRole = role;
    writeDoc(EMPTY_DOC);
    updateVersionUI();
}

function writeDoc(code) {
    if (!editorView) return;
    editorView.dispatch({
        changes: { from: 0, to: editorView.state.doc.length, insert: code },
    });
}

export function getCode() {
    return editorView ? editorView.state.doc.toString() : "";
}

export function setCode(code) {
    roleState(currentRole).code = code;
    writeDoc(code);
}

/**
 * Push a new version of one role's file.
 *
 * @param {string} code     the file's source
 * @param {string} label    what produced it, shown when stepping versions
 * @param {object} [opts]
 * @param {string} [opts.role]     defaults to the role on screen
 * @param {string} [opts.hubtype]  device kind the role runs on
 */
export function saveVersion(code, label = "AI generated", { role = currentRole, hubtype } = {}) {
    const st = roleState(role);
    if (hubtype) st.hubtype = hubtype;
    st.versions.push({ code, label });
    st.index = st.versions.length - 1;
    st.code = code;
    if (role === currentRole) writeDoc(code);
    updateVersionUI();
}

export function getVersionCount() { return roleState(currentRole).versions.length; }
export function getVersionIndex() { return roleState(currentRole).index; }

export function updateVersionUI() {
    const labelEl = document.getElementById("version-label");
    const prevBtn = document.getElementById("btn-prev");
    const nextBtn = document.getElementById("btn-next");
    if (!labelEl || !prevBtn || !nextBtn) return;
    const st = roleState(currentRole);
    const total = st.versions.length;
    if (total === 0) {
        labelEl.textContent = "v0/0";
        prevBtn.disabled = true;
        nextBtn.disabled = true;
    } else {
        labelEl.textContent = `v${st.index + 1}/${total}`;
        prevBtn.disabled = st.index <= 0;
        nextBtn.disabled = st.index >= total - 1;
    }
}

function stepVersion(delta, addMsg) {
    const st = roleState(currentRole);
    const next = st.index + delta;
    if (next < 0 || next >= st.versions.length) return;
    st.index = next;
    const v = st.versions[next];
    setCode(v.code);
    updateVersionUI();
    addMsg(`Loaded ${currentRole} v${next + 1}: ${v.label}`, "system");
}

export function onPrevVersion(addMsg) { stepVersion(-1, addMsg); }
export function onNextVersion(addMsg) { stepVersion(1, addMsg); }

export function onDownload(addMsg) {
    const code = getCode().trim();
    if (!code) { addMsg("Nothing to download.", "system"); return; }
    const blob = new Blob([code], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const st = roleState(currentRole);
    a.download = st.index >= 0 ? `${currentRole}_v${st.index + 1}.py` : `${currentRole}.py`;
    a.click();
    URL.revokeObjectURL(url);
    addMsg(`Downloaded as ${a.download}`, "system");
}

export function onClearCode() {
    setCode("# Code will appear here\n");
}
