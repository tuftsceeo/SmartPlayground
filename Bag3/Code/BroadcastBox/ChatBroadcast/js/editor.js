import { EditorView, basicSetup } from 'https://esm.sh/codemirror@6.0.1';
import { python } from 'https://esm.sh/@codemirror/lang-python@6.1.6';
import { HighlightStyle, syntaxHighlighting } from 'https://esm.sh/@codemirror/language@6';
import { tags } from 'https://esm.sh/@lezer/highlight@1';

let editorView = null;
const codeVersions = [];
let versionIndex = -1;

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
    '&': { backgroundColor: 'var(--code-bg)', color: 'var(--code-text)' },
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

export function getCode() {
    return editorView ? editorView.state.doc.toString() : "";
}

export function setCode(code) {
    if (!editorView) return;
    editorView.dispatch({
        changes: { from: 0, to: editorView.state.doc.length, insert: code },
    });
}

export function saveVersion(code, label = "AI generated") {
    codeVersions.push({ code, label });
    versionIndex = codeVersions.length - 1;
    updateVersionUI();
}

export function getVersionCount() { return codeVersions.length; }
export function getVersionIndex() { return versionIndex; }

export function updateVersionUI() {
    const labelEl = document.getElementById("version-label");
    const prevBtn = document.getElementById("btn-prev");
    const nextBtn = document.getElementById("btn-next");
    const total = codeVersions.length;
    if (total === 0) {
        labelEl.textContent = "v0/0";
        prevBtn.disabled = true;
        nextBtn.disabled = true;
    } else {
        labelEl.textContent = `v${versionIndex + 1}/${total}`;
        prevBtn.disabled = versionIndex <= 0;
        nextBtn.disabled = versionIndex >= total - 1;
    }
}

export function onPrevVersion(addMsg) {
    if (versionIndex > 0) {
        versionIndex--;
        const v = codeVersions[versionIndex];
        setCode(v.code);
        updateVersionUI();
        addMsg(`Loaded v${versionIndex + 1}: ${v.label}`, "system");
    }
}

export function onNextVersion(addMsg) {
    if (versionIndex < codeVersions.length - 1) {
        versionIndex++;
        const v = codeVersions[versionIndex];
        setCode(v.code);
        updateVersionUI();
        addMsg(`Loaded v${versionIndex + 1}: ${v.label}`, "system");
    }
}

export function onDownload(addMsg) {
    const code = getCode().trim();
    if (!code) { addMsg("Nothing to download.", "system"); return; }
    const blob = new Blob([code], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = versionIndex >= 0 ? `jumpin_v${versionIndex + 1}.py` : "jumpin.py";
    a.click();
    URL.revokeObjectURL(url);
    addMsg(`Downloaded as ${a.download}`, "system");
}

export function onClearCode() {
    setCode("# Code will appear here\n");
}
