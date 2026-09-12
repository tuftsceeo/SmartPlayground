import { EditorView, basicSetup } from 'https://esm.sh/codemirror@6.0.1';
import { python } from 'https://esm.sh/@codemirror/lang-python@6.1.6';
import { HighlightStyle, syntaxHighlighting } from 'https://esm.sh/@codemirror/language@6';
import { tags } from 'https://esm.sh/@lezer/highlight@1';

/**
 * Per-role editor state.
 *
 * A multi-device game is several files -- one per device type -- and each
 * needs its own text and its own version history. There is still ONE
 * CodeMirror view on one #code-editor mount: switching role parks the
 * current document in that role's slot and loads the new one, which is
 * cheaper than N mounted editors and keeps the existing markup.
 */
import { ROLES } from './chat.js';

let editorView = null;
let activeRole = ROLES[0];

/** @returns {{doc: string, versions: {code: string, label: string}[], index: number}} */
function emptyRole() {
    return { doc: '', versions: [], index: -1 };
}

const roleState = {};
for (const r of ROLES) roleState[r] = emptyRole();

/** The slot for a role, or the active one when role is omitted. */
function slot(role) {
    return roleState[role || activeRole] || roleState[activeRole];
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
        doc: '# AI-generated code will appear here\n',
        extensions: [basicSetup, python(), syntaxHighlighting(lightHighlightStyle), lightEditorTheme],
        parent: document.getElementById('code-editor'),
    });
}

/** The code for a role: live from the view when it is the active one. */
export function getCode(role) {
    if (!role || role === activeRole) {
        return editorView ? editorView.state.doc.toString() : slot().doc;
    }
    return slot(role).doc;
}

export function setCode(code, role) {
    const target = role || activeRole;
    roleState[target].doc = code;
    if (target !== activeRole || !editorView) return;
    editorView.dispatch({
        changes: { from: 0, to: editorView.state.doc.length, insert: code },
    });
}

export function getActiveRole() { return activeRole; }

/** Roles that currently hold code -- what the device tab rail shows. */
export function rolesWithCode() {
    return ROLES.filter(r => getCode(r).trim().length > 0);
}

/**
 * Park the current document in its own slot and show another role's.
 * A no-op for an unknown role, so a stale tab cannot blank the editor.
 */
export function setActiveRole(role) {
    if (!roleState[role] || role === activeRole) return activeRole;
    roleState[activeRole].doc = getCode();
    activeRole = role;
    if (editorView) {
        editorView.dispatch({
            changes: { from: 0, to: editorView.state.doc.length, insert: slot().doc },
        });
    }
    updateVersionUI();
    return activeRole;
}

/** Drop every role's code and history -- starting a different game. */
export function clearAllRoles() {
    for (const r of ROLES) roleState[r] = emptyRole();
    activeRole = ROLES[0];
    setCode('');
    updateVersionUI();
}

export function saveVersion(code, label = "AI generated", role) {
    const st = slot(role);
    st.versions.push({ code, label });
    st.index = st.versions.length - 1;
    st.doc = code;
    updateVersionUI();
}

export function getVersionCount(role) { return slot(role).versions.length; }
export function getVersionIndex(role) { return slot(role).index; }

export function updateVersionUI() {
    const labelEl = document.getElementById("version-label");
    const prevBtn = document.getElementById("btn-prev");
    const nextBtn = document.getElementById("btn-next");
    if (!labelEl || !prevBtn || !nextBtn) return;
    const st = slot();
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

export function onPrevVersion(addMsg) {
    const st = slot();
    if (st.index > 0) {
        st.index--;
        const v = st.versions[st.index];
        setCode(v.code);
        updateVersionUI();
        addMsg(`Loaded v${st.index + 1}: ${v.label}`, "system");
    }
}

export function onNextVersion(addMsg) {
    const st = slot();
    if (st.index < st.versions.length - 1) {
        st.index++;
        const v = st.versions[st.index];
        setCode(v.code);
        updateVersionUI();
        addMsg(`Loaded v${st.index + 1}: ${v.label}`, "system");
    }
}

/**
 * Download the active role's code.
 * @param {(msg: string, kind: string) => void} addMsg
 * @param {string} [baseName]  defaults to the game's slug where the caller
 *                             knows it, else the role name
 */
export function onDownload(addMsg, baseName) {
    const code = getCode().trim();
    if (!code) { addMsg("Nothing to download.", "system"); return; }
    const st = slot();
    const base = baseName || activeRole;
    const blob = new Blob([code], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = st.index >= 0 ? `${base}_v${st.index + 1}.py` : `${base}.py`;
    a.click();
    URL.revokeObjectURL(url);
    addMsg(`Downloaded as ${a.download}`, "system");
}

export function onClearCode() {
    setCode("# Code will appear here\n");
}
