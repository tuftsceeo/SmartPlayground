import { EditorView, basicSetup } from 'https://esm.sh/codemirror@6.0.1';
import { python } from 'https://esm.sh/@codemirror/lang-python@6.1.6';

let editorView = null;
const codeVersions = [];
let versionIndex = -1;

export function initEditor() {
    editorView = new EditorView({
        doc: '# AI-generated code will appear here\n',
        extensions: [basicSetup, python()],
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
