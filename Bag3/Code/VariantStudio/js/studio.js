/**
 * Variant Studio: describe a look in words, see it on the real
 * Chat Broadcast in the preview, save and share it as a play.html link.
 */
import { loadEncryptedKey, getApiKey } from '../../ChatBroadcast/js/auth.js';
import { emptyVariant, normalize, validate, compile, describe, encodeVariant } from './variant.js';
import { applyVariant, setMode, onFrameDocument } from './apply.js';
import { describeChange } from './claude.js';

const KEY_VARIANTS = 'variantstudio.variants';
const KEY_CURRENT = 'variantstudio.current';
const KEY_PASS = 'variantstudio.pass'; // sessionStorage only

const $ = id => document.getElementById(id);
const frame = $('preview');

const IDEAS = [
    'Space theme with dark colors',
    'Bigger, friendlier buttons',
    'Hide the code extras',
    'Calm and simple for young kids',
];

// ---------- storage ----------
function readJson(store, key, fallback) {
    try { return JSON.parse(store.getItem(key)) ?? fallback; } catch (_) { return fallback; }
}
function writeJson(store, key, value) {
    try { store.setItem(key, JSON.stringify(value)); } catch (_) {}
}

let variants = readJson(localStorage, KEY_VARIANTS, {});
let currentId = readJson(localStorage, KEY_CURRENT, null);
if (!currentId || !variants[currentId]) {
    currentId = newId();
    variants[currentId] = emptyVariant('My variant');
}
let undo = [];
let redo = [];
let chatHistory = []; // plain-text turns sent to Claude
let apiKey = null;
let busy = false;
let pendingGo = null;

function newId() { return 'v' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }
function current() { return normalize(variants[currentId]); }
function save() {
    writeJson(localStorage, KEY_VARIANTS, variants);
    writeJson(localStorage, KEY_CURRENT, currentId);
}

// ---------- applying ----------
function setVariant(v, { record = true } = {}) {
    v = normalize(v);
    if (record) {
        undo.push(current());
        if (undo.length > 50) undo.shift();
        redo = [];
    }
    variants[currentId] = v;
    save();
    render();
    applyToPreview(true);
}

function applyToPreview(switchMode) {
    const win = frame.contentWindow;
    if (!win || !win.document || !win.document.body || win.document.URL === 'about:blank') return;
    applyVariant(win, compile(current()), { switchMode });
}

function render() {
    const v = current();
    if (document.activeElement !== $('variant-name')) $('variant-name').value = v.name;
    const list = $('change-list');
    list.textContent = '';
    const lines = describe(v);
    if (!lines.length) {
        const li = document.createElement('li');
        li.className = 'empty';
        li.textContent = 'No changes yet — this looks like the normal app.';
        list.appendChild(li);
    }
    for (const line of lines) {
        const li = document.createElement('li');
        li.textContent = line;
        list.appendChild(li);
    }
    $('btn-undo').disabled = !undo.length;
    $('btn-redo').disabled = !redo.length;
    $('btn-open-full').href = playLink(v);

    const pick = $('variant-pick');
    pick.textContent = '';
    for (const [id, vv] of Object.entries(variants)) {
        const o = document.createElement('option');
        o.value = id;
        o.textContent = vv.name || 'Untitled';
        o.selected = id === currentId;
        pick.appendChild(o);
    }
}

function playLink(v) {
    return new URL('play.html#v=' + encodeVariant(v), location.href).href;
}

// ---------- preview frame ----------
onFrameDocument(frame, win => {
    applyVariant(win, compile(current()), { switchMode: false });
    autoUnlockFrame(win);
});

function startFrame() {
    const m = current().mode;
    if (m) { try { localStorage.setItem('wandcoder.uiMode', m); } catch (_) {} }
    frame.src = '../ChatBroadcast/index.html';
}

/** Type the studio's magic code into the preview's own unlock screen. */
function autoUnlockFrame(win) {
    const pass = sessionStorage.getItem(KEY_PASS);
    const started = Date.now();
    const iv = setInterval(() => {
        if (frame.contentWindow !== win || Date.now() - started > 15000) { clearInterval(iv); return; }
        const doc = win.document;
        const overlay = doc.getElementById('modal-overlay');
        if (!overlay) return;
        if (overlay.classList.contains('hidden')) {
            clearInterval(iv);
            runPendingGo(doc);
            return;
        }
        if (!pass) return;
        const input = doc.getElementById('modal-passphrase');
        const btn = doc.getElementById('btn-modal-unlock');
        if (input && btn) {
            input.value = pass;
            btn.click();
        }
    }, 500);
}

function runPendingGo(doc) {
    const go = pendingGo;
    pendingGo = null;
    if (go === 'gallery') doc.getElementById('btn-gallery')?.click();
    if (go === 'workspace') doc.getElementById('btn-scratch')?.click();
}

function goTo(view) {
    pendingGo = view === 'splash' ? null : view;
    frame.contentWindow.location.reload();
}

// ---------- Claude ----------
function addMsg(kind, text) {
    const div = document.createElement('div');
    div.className = 'msg ' + kind;
    div.textContent = text;
    $('chat-log').appendChild(div);
    $('chat-log').scrollTop = $('chat-log').scrollHeight;
    return div;
}

async function onDescribe() {
    const text = $('request').value.trim();
    if (!text || busy) return;
    if (!apiKey) { $('unlock').classList.remove('hidden'); return; }
    busy = true;
    $('btn-describe').disabled = true;
    addMsg('you', text);
    $('request').value = '';
    const working = addMsg('claude working', 'Working on it…');
    try {
        const { variant, summary } = await describeChange(apiKey, current(), text, chatHistory);
        variant.name = variant.name || current().name;
        setVariant(variant);
        working.remove();
        addMsg('claude', summary);
        chatHistory.push({ role: 'user', content: text }, { role: 'assistant', content: summary });
    } catch (e) {
        working.remove();
        addMsg('error', 'That didn’t work — ' + e.message);
    } finally {
        busy = false;
        $('btn-describe').disabled = false;
    }
}

// ---------- unlock ----------
async function tryUnlock(pass, quiet) {
    await keyReady;
    const key = getApiKey(pass);
    if (!key) {
        if (!quiet) $('unlock-error').textContent = 'Wrong code. Try again.';
        return false;
    }
    apiKey = key;
    sessionStorage.setItem(KEY_PASS, pass);
    $('unlock').classList.add('hidden');
    autoUnlockFrame(frame.contentWindow);
    return true;
}

// ---------- misc UI ----------
function toast(msg) {
    const t = $('toast');
    t.textContent = msg;
    t.classList.remove('hidden');
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => t.classList.add('hidden'), 2200);
}

function slug(s) { return (s || 'variant').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'variant'; }

function exportVariant() {
    const v = current();
    const blob = new Blob([JSON.stringify(v, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = slug(v.name) + '.json';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function importFile(file) {
    try {
        const v = normalize(JSON.parse(await file.text()));
        const problems = validate(v);
        if (problems.length) { toast('Can’t import: ' + problems[0]); return; }
        switchTo(newId(), v);
        toast('Imported ' + v.name);
    } catch (_) {
        toast('That file isn’t a variant.');
    }
}

function switchTo(id, v) {
    if (v) variants[id] = normalize(v);
    currentId = id;
    undo = [];
    redo = [];
    chatHistory = [];
    $('chat-log').textContent = '';
    save();
    render();
    if (current().mode) setMode(frame.contentWindow, current().mode);
    applyToPreview(false);
}

function bind() {
    $('btn-describe').addEventListener('click', onDescribe);
    $('request').addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onDescribe(); }
    });
    for (const idea of IDEAS) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'chip';
        b.textContent = idea;
        b.addEventListener('click', () => { $('request').value = idea; $('request').focus(); });
        $('ideas').appendChild(b);
    }
    $('btn-undo').addEventListener('click', () => {
        if (!undo.length) return;
        redo.push(current());
        setVariant(undo.pop(), { record: false });
    });
    $('btn-redo').addEventListener('click', () => {
        if (!redo.length) return;
        undo.push(current());
        setVariant(redo.pop(), { record: false });
    });
    $('btn-reset').addEventListener('click', () => {
        if (!describe(current()).length) return;
        setVariant(emptyVariant(current().name));
        toast('All changes removed — Undo brings them back.');
    });
    $('variant-name').addEventListener('change', e => {
        const name = e.target.value.trim().slice(0, 60) || 'My variant';
        setVariant({ ...current(), name });
    });
    $('variant-pick').addEventListener('change', e => switchTo(e.target.value));
    $('btn-new').addEventListener('click', () => {
        switchTo(newId(), emptyVariant('Variant ' + (Object.keys(variants).length + 1)));
    });
    $('btn-export').addEventListener('click', exportVariant);
    $('btn-import').addEventListener('click', () => $('import-input').click());
    $('import-input').addEventListener('change', e => {
        const f = e.target.files?.[0];
        e.target.value = '';
        if (f) importFile(f);
    });
    $('btn-copy-link').addEventListener('click', async () => {
        const link = playLink(current());
        try {
            await navigator.clipboard.writeText(link);
            toast('Link copied — anyone on the team can open it.');
        } catch (_) {
            prompt('Copy this link:', link);
        }
    });
    for (const b of document.querySelectorAll('[data-go]')) {
        b.addEventListener('click', () => goTo(b.dataset.go));
    }
    $('btn-unlock').addEventListener('click', () => tryUnlock($('passphrase').value.trim(), false));
    $('passphrase').addEventListener('keydown', e => {
        if (e.key === 'Enter') tryUnlock($('passphrase').value.trim(), false);
    });
}

const keyReady = loadEncryptedKey();
bind();
render();
startFrame();
const saved = sessionStorage.getItem(KEY_PASS);
if (saved) tryUnlock(saved, true);
