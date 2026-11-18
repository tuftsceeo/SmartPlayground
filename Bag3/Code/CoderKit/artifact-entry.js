/**
 * The kit for a claude.ai artifact: chat runs on the viewer's own Claude
 * account through the `sample` capability, primed with Chat Broadcast's
 * knowledge (bundled in). Web Serial is blocked in artifacts, so connect
 * and send use a simulated controller; real devices go through run.html.
 * Sets window.kit before any page script runs.
 */
import { createKit } from './coderkit.js';
import { sampleBrain } from './brains.js';
import KNOWLEDGE from './build/knowledge.json';
import EXAMPLE_GAMES from './build/examples.json';
import { makeSimRoomSimulator } from './sim-core.js';

let samplePromise = null;
const getSample = () => (samplePromise ||= (window.claude?.use ? window.claude.use('sample') : Promise.resolve(null)));

const brain = async (req) => {
    const sample = await getSample();
    if (!sample) return { text: '', error: { message: 'Claude is not available here. Publish this page as an artifact with capabilities: {sample: {}}.' } };
    return sampleBrain(sample)(req);
};

/**
 * A pretend Dial: answers identity after a moment, accepts any game, keeps
 * a game list, and has two pretend devices nearby for Distribute.
 */
function simulatedDevice() {
    const on = {};
    const emit = (t, o) => (on[t] || []).forEach(f => f(o));
    const wait = (ms) => new Promise(r => setTimeout(r, ms));
    let open = false, active = null;
    const games = [];
    const NEARBY = [
        { mac: 'sim:wand:01', kind: 'wand', battery: 88, g: [] },
        { mac: 'sim:icon:01', kind: 'icon_display', battery: 74, g: [] },
    ];
    const answers = {
        'games.list': () => ({ list: games.slice(), active }),
        'games.select': ({ slug }) => { active = slug; return { ok: true }; },
        'games.delete': ({ slug }) => { const i = games.findIndex(g => g.slug === slug); if (i >= 0) games.splice(i, 1); if (active === slug) active = null; return { ok: true }; },
        'fleet.scan': () => {
            NEARBY.forEach((r, i) => setTimeout(() => emit('status_report', { type: 'status_report', ...r }), 300 * (i + 1)));
            setTimeout(() => emit('status_done', { type: 'status_done' }), 300 * (NEARBY.length + 1));
            return { ok: true };
        },
        'fleet.distribute': ({ macs = [] }) => {
            macs.forEach((mac, i) => setTimeout(() => emit('dist_progress', { type: 'dist_progress', mac, ok: true, done: i + 1, total: macs.length }), 500 * (i + 1)));
            setTimeout(() => emit('dist_done', { type: 'dist_done', done: macs.length, total: macs.length }), 500 * (macs.length + 1));
            return { ok: true };
        },
    };
    return {
        simulated: true,
        on: (t, f) => { (on[t] ||= []).push(f); return () => {}; },
        connect: async () => {
            open = true;
            setTimeout(() => { emit('identity', { type: 'identity', device: 'broadcast_dial' }); emit('mode', { type: 'mode', mode: 'play' }); }, 600);
        },
        reconnect: async () => false,
        disconnect: async () => { open = false; emit('close', { reason: 'user' }); },
        nudgeIdentify: async () => true,
        isConnected: () => open,
        sendCmd: async (c) => { await wait(150); const a = answers[c.cmd]; return a ? a(c) : { ok: true }; },
        sendGame: async (code, meta, onProgress) => {
            for (let i = 0; i <= 4; i++) { onProgress?.({ current: i, total: 4, status: 'uploaded' }); await wait(250); }
            if (meta?.slug && !games.some(g => g.slug === meta.slug)) games.push({ slug: meta.slug, name: meta.prettyName });
            if (meta?.slug) active = meta.slug;
            return { ok: true, simulated: true };
        },
    };
}

const exampleCode = async (ex) => {
    const code = EXAMPLE_GAMES[ex?.vendorGame];
    if (code == null) throw new Error(`No code for example "${ex?.id}".`);
    return code;
};

/**
 * The simulator, from the artifact's own files (artifacts may only fetch
 * from their own address). Its files are published beside the page:
 * Simulator/... as in the repo, and Pyodide under pyodide/. sim-room.js
 * uses window.loadPyodide when one exists, so this one sends it to the
 * local copy. Artifacts won't serve .zip, so Python's standard library is
 * published as base64 text and handed over as a blob: URL.
 */
const here = (rel) => new URL(rel, document.baseURI).href;
const hasSimulator = () => document.querySelector('meta[name="coderkit-simulator"]') !== null;
let realLoad = null, stdLib = null;
function loadScript(src) {
    return new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = src; s.onload = resolve; s.onerror = () => reject(new Error(`Could not load ${src}`));
        document.head.appendChild(s);
    });
}
async function localLoadPyodide(opts = {}) {
    if (!realLoad) {
        await loadScript(here('pyodide/pyodide.js'));
        realLoad = window.loadPyodide;
        window.loadPyodide = localLoadPyodide;
    }
    stdLib ||= fetch(here('pyodide/python_stdlib.txt')).then(r => {
        if (!r.ok) throw new Error(`pyodide/python_stdlib.txt: ${r.status}`);
        return r.text();
    }).then(b64 => {
        const bin = Uint8Array.from(atob(b64.replace(/\s/g, '')), c => c.charCodeAt(0));
        return URL.createObjectURL(new Blob([bin], { type: 'application/zip' }));
    });
    return realLoad({ ...opts, indexURL: here('pyodide/'), stdLibURL: await stdLib });
}
let simulator = null;
if (hasSimulator()) {
    window.loadPyodide = localLoadPyodide;
    const simUrl = here('Simulator/sim-room.js');
    simulator = makeSimRoomSimulator(() => import(/* webpackIgnore: true */ simUrl));
}

const kit = createKit({ brain, device: simulatedDevice(), files: KNOWLEDGE, exampleCode, simulator });
kit.simulatedDevice = true;
window.kit = kit;
