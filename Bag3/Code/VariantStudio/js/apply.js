/**
 * Apply a compiled variant (variant.js compile()) to a same-origin
 * Chat Broadcast document. Nothing is removed and no app state classes
 * (.hidden, [hidden]) are touched: only an injected stylesheet, a font
 * link, and label text the app renders.
 */
const STYLE_ID = 'variant-style';
const FONT_ID = 'variant-font';
const MODE_KEY = 'wandcoder.uiMode';

const states = new WeakMap(); // document -> {labels, observer, originals}

/** The element's own first non-empty text node (icons and children stay). */
function ownTextNode(el) {
    for (const n of el.childNodes) {
        if (n.nodeType === 3 && n.data.trim()) return n;
    }
    return null;
}

function setLabel(el, label, originals) {
    if (label.attr) {
        if (!originals.has(el)) originals.set(el, { attr: label.attr, value: el.getAttribute(label.attr) });
        if (el.getAttribute(label.attr) !== label.text) el.setAttribute(label.attr, label.text);
        return;
    }
    let node = ownTextNode(el);
    if (!node) {
        node = el.ownerDocument.createTextNode('');
        el.appendChild(node);
    }
    if (!originals.has(el)) originals.set(el, { text: node.data });
    // Keep the app's surrounding whitespace so inline layout doesn't shift.
    const lead = node.data.match(/^\s*/)[0];
    const trail = node.data.match(/\s*$/)[0];
    const want = lead + label.text + trail;
    if (node.data !== want) node.data = want;
}

function applyLabels(doc, st) {
    for (const label of st.labels) {
        for (const el of doc.querySelectorAll(label.sel)) setLabel(el, label, st.originals);
    }
}

function restoreLabels(st) {
    for (const [el, orig] of st.originals) {
        if (orig.attr) {
            if (orig.value == null) el.removeAttribute(orig.attr);
            else el.setAttribute(orig.attr, orig.value);
        } else {
            const node = ownTextNode(el) || el.appendChild(el.ownerDocument.createTextNode(''));
            node.data = orig.text;
        }
    }
    st.originals.clear();
}

/**
 * @param {Window} win  the Chat Broadcast window (iframe contentWindow)
 * @param {{css, labels, fontUrl, mode}} compiled
 * @param {{switchMode?: boolean}} opts  switchMode: also flip simple/advanced live
 */
export function applyVariant(win, compiled, opts = {}) {
    const doc = win.document;
    doc.documentElement.setAttribute('data-variant', compiled.name || '');

    let style = doc.getElementById(STYLE_ID);
    if (!style) {
        style = doc.createElement('style');
        style.id = STYLE_ID;
        doc.head.appendChild(style);
    }
    style.textContent = compiled.css;

    let link = doc.getElementById(FONT_ID);
    if (compiled.fontUrl) {
        if (!link) {
            link = doc.createElement('link');
            link.id = FONT_ID;
            link.rel = 'stylesheet';
            doc.head.appendChild(link);
        }
        if (link.href !== compiled.fontUrl) link.href = compiled.fontUrl;
    } else if (link) {
        link.remove();
    }

    let st = states.get(doc);
    if (!st) {
        st = { labels: [], originals: new Map(), observer: null, pending: false };
        states.set(doc, st);
    }
    restoreLabels(st);
    st.labels = compiled.labels || [];
    applyLabels(doc, st);

    if (!st.observer) {
        // The app rewrites some labels (e.g. "Send to Box →" when the
        // device changes); put the variant's wording back after each change.
        st.observer = new win.MutationObserver(() => {
            if (st.pending || !st.labels.length) return;
            st.pending = true;
            win.queueMicrotask(() => {
                st.pending = false;
                applyLabels(doc, st);
            });
        });
        st.observer.observe(doc.body, {
            subtree: true, childList: true, characterData: true,
            attributes: true, attributeFilter: ['placeholder'],
        });
    }

    if (compiled.mode && opts.switchMode) setMode(win, compiled.mode);
}

/** Set simple/advanced the way the app's own switch does. */
export function setMode(win, mode) {
    try { win.localStorage.setItem(MODE_KEY, mode); } catch (_) {}
    win.document.dispatchEvent(new win.CustomEvent('uimode:change', { detail: { mode } }));
}

/** Set the stored mode before the app boots (no event needed). */
export function presetMode(mode) {
    if (!mode) return;
    try { localStorage.setItem(MODE_KEY, mode); } catch (_) {}
}

/**
 * Call `fn(win)` every time the frame loads a Chat Broadcast document,
 * as early as its <head> and <body> exist (before first paint where possible).
 */
export function onFrameDocument(frame, fn) {
    let lastDoc = null;
    const tick = () => {
        const win = frame.contentWindow;
        const doc = win && win.document;
        if (doc && doc !== lastDoc && doc.URL !== 'about:blank' && doc.body && doc.head) {
            lastDoc = doc;
            try { fn(win); } catch (e) { console.error('variant apply failed', e); }
        }
    };
    frame.addEventListener('load', tick);
    const iv = setInterval(tick, 30);
    return () => clearInterval(iv);
}
