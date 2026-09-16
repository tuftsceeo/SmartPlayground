/**
 * Bare CodeMirror stub for host imports of ChatBroadcast/js/editor.js.
 *
 * editor.js imports CodeMirror from four esm.sh URLs, and the module-level
 * code (a HighlightStyle and an EditorView.theme, both built at import
 * time) runs whether or not initEditor() is ever called. This stands in
 * for just enough of that surface to import cleanly under Node -- nothing
 * here draws anything or is exercised by the host devtests, which never
 * call initEditor() and so never touch editorView.
 */

export const EditorView = {
    theme: () => ({}),
};

export const basicSetup = {};

export function python() {
    return {};
}

export class HighlightStyle {
    static define() {
        return {};
    }
}

export function syntaxHighlighting() {
    return {};
}

// Every `tags.<name>` is a plain style tag value; a few (special, function,
// definition) are also called as functions. A Proxy that returns a callable
// for any property covers both without listing each tag by name.
function tagFn() {
    return {};
}
export const tags = new Proxy({}, { get: () => tagFn });
