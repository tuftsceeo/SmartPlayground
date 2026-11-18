/**
 * CoderKit: Chat Broadcast's behavior with no interface.
 *
 * Chat (with the real knowledge and priming), connect to a Dial/Box, send
 * the game, plus the optional parts: code versions, examples, saved games,
 * interview, the controller's game list, distribute and the simulator.
 * Every piece of logic is imported unchanged from ../ChatBroadcast/js/ (or,
 * in the artifact build, a bundled copy). A front end draws whatever it
 * likes from kit.state and calls the methods below.
 */
import { buildSystemBlocks, knowledgeText, knowledgePaths, ADVANCED_KNOWLEDGE,
    buildInterviewSystemBlocks, interviewMessages, briefFormat, briefFromJson,
    INTERVIEW_KNOWLEDGE, INTERVIEW_MAX_QUESTIONS, INTERVIEW_FIRST_QUESTION } from '../ChatBroadcast/js/prompt/buildRequest.js';
import { extractCodeBlocks, parseGameName, parseChoices, parseNextDevice, stripAllMarkers,
    trimForHistory, hideOpenCode, parseGameBrief, stripGameBrief } from '../ChatBroadcast/js/chat.js';
import { ROLES, roleInfo } from '../ChatBroadcast/js/roles.js';
import { validateGameSignature, validateGameCode, uploadPayload } from '../ChatBroadcast/js/upload.js';
import { slugify } from '../ChatBroadcast/js/gameName.js';
import { buildHardwareReqs, baselineTags, deviceNeeds, deviceLine } from '../ChatBroadcast/js/hardware.js';
import { GAME_ICONS } from '../ChatBroadcast/js/ledicons/shapes5.js';
import { gameTint, gameIconThumb } from '../ChatBroadcast/js/ledicons/thumb5.js';
import { iconSvg } from '../ChatBroadcast/js/icons.js';
import { drawStarterIdeas } from '../ChatBroadcast/js/starterIdeas.js';
import { listSplatActions } from '../ChatBroadcast/js/splat/splatActionCheck.js';
import { listIcons, iconNamesIn, missingIconsIn, iconFileText } from '../ChatBroadcast/js/ledicons/iconLibrary.js';
import { createDeviceLink, deviceShortName } from '../ChatBroadcast/js/device/bboxDeviceLink.js';
import { EXAMPLES, CATEGORIES, findExample, loadExampleCode } from '../ChatBroadcast/js/examples.js';
import { loadSavedGames, saveGame, renameSavedGame, deleteSavedGame, findSavedGame } from '../ChatBroadcast/js/library.js';
import { DistributeState } from '../ChatBroadcast/js/distribute.js';
import { createVersions } from './versions.js';

export { ROLES };

const defaultBase = () => new URL('../ChatBroadcast/', import.meta.url).href;
const SIM_KNOWLEDGE = 'knowledge/simulator.md';

/** Fetch every knowledge file, keyed by the path buildRequest.js uses. */
export async function loadKnowledge(base = defaultBase()) {
    const files = {};
    await Promise.all([...knowledgePaths(), SIM_KNOWLEDGE].map(async (p) => {
        const r = await fetch(new URL(p, base));
        if (!r.ok) throw new Error(`Could not load ${p} (${r.status})`);
        files[p] = await r.text();
    }));
    return files;
}

/** The system blocks Chat Broadcast sends, for this kit's code. */
export function systemBlocks(files, code = {}, { advanced = false, simNotes = null } = {}) {
    return buildSystemBlocks({
        knowledge: knowledgeText(files, listSplatActions()),
        advanced: files[ADVANCED_KNOWLEDGE],
        advancedMode: advanced,
        icons: listIcons(),
        customIcons: [],
        editorCode: Object.fromEntries(ROLES.map(r => [r.key, code[r.key] || ''])),
        simNotes,
    });
}

/** What to keep from one finished reply: code per role, name, choices, next device. */
export function parseReply(raw) {
    const code = {};
    const snippets = [];
    for (const b of extractCodeBlocks(raw)) {
        const [ok] = validateGameSignature(b.code, b.role);
        if (ok) code[b.role] = b.code; else snippets.push(b);
    }
    return {
        text: stripAllMarkers(hideOpenCode(raw)),
        code, snippets,
        gameName: parseGameName(raw),
        choices: parseChoices(raw) || [],
        nextDevice: parseNextDevice(raw),
    };
}

/** The first role with a runnable game, as app.js primaryRoleCode(). */
function primary(code) {
    for (const info of ROLES) {
        const c = (code[info.key] || '').trim();
        if (c && /def\s+play\s*\(/.test(c)) return { role: info.key, info, code: c };
    }
    return null;
}

/**
 * The upload meta for a Box/Dial, as app.js confirmSend() builds it.
 * @returns {{ok:true, role, code, meta} | {ok:false, error}}
 */
export function buildSend(code, gameName, deviceLabel = 'Dial') {
    const p = primary(code);
    if (!p) return { ok: false, error: 'There is no game yet. Describe one in the chat first.' };
    const pretty = (gameName || 'My game').trim();
    const slug = slugify(pretty) || 'mygame';
    const meta = {
        slug, prettyName: pretty, deviceLabel,
        destPath: `/flash/games/${slug}${p.info.designator}.py`,
        destLabel: `${slug}${p.info.designator}.py`,
        tags: buildHardwareReqs({ code: p.code, gameName: pretty, declared: null }).tags,
    };
    const extra = [];
    for (const info of ROLES) {
        if (info.key === 'wand') continue;
        const c = (code[info.key] || '').trim();
        if (!c) continue;
        const [ok, err] = validateGameCode(c, info.key);
        if (!ok) return { ok: false, error: err };
        if (info.hasIconLeg) {
            const missing = missingIconsIn(c);
            if (missing.length) return { ok: false, error: `The display game asks for icons that do not exist: ${missing.join(', ')}.` };
        }
        if (info.key !== p.role) extra.push({ path: `/flash/games/${slug}${info.designator}.py`, content: c });
        if (info.hasIconLeg) {
            for (const name of iconNamesIn(c)) extra.push({ path: `/flash/games/${slug}_icons/${name}.py`, content: iconFileText(name) });
        }
    }
    if (extra.length) meta.extraFiles = extra;
    return { ok: true, role: p.role, code: p.code, meta, kinds: ROLES.filter(r => (code[r.key] || '').trim()).map(r => r.hubtype) };
}

/** A short summary of an interview brief, as app.js briefSummary(). */
export function briefSummary(brief) {
    const field = {};
    for (const line of brief.split('\n')) {
        const m = line.match(/^\s*[-*]\s*([^:]+):\s*(.+)$/);
        if (m) field[m[1].trim().toLowerCase()] = m[2].trim();
    }
    const play = field['how to play'] || field.play;
    if (!field.title || !play) return brief;
    const devices = [field.wands, field.extras].filter((t) => t && !/^none\b/i.test(t)).join('; ');
    return [`- Name: ${field.title}`, `- What players do: ${play}`,
        devices ? `- Devices: ${devices}` : null].filter(Boolean).join('\n');
}

const plainRows = (ds) => ds.rows.map(r => ({ ...r, games: r.games ? r.games.map(g => [...g]) : null,
    fits: ds.fits(r), needsUpdate: ds.needsUpdate(r) }));

/**
 * @param {object} opts
 *   brain({system, history, onText, format}) -> {text, stopReason, error}
 *   device: a link with connect/reconnect/disconnect/on/sendGame/sendCmd/isConnected
 *           (defaults to Chat Broadcast's Box/Dial link)
 *   files: knowledge files {path: text} (else fetched from knowledgeBase)
 *   exampleCode: async (example) -> python (defaults to Simulator/vendor/games)
 *   simulator: (element, kit) -> {update(code), destroy()} | null
 */
export function createKit({ brain, device, knowledgeBase, files, exampleCode = loadExampleCode, simulator = null } = {}) {
    const listeners = new Set();
    const versions = createVersions(ROLES.map(r => r.key));
    const state = {
        link: 'idle',          // idle | opening | live | sending
        deviceName: null,      // "teacher hub" etc. once it answers
        gameName: null,
        code: {},              // role -> current code
        versions: versions.summary(),
        messages: [],          // {role:'user'|'assistant'|'system', text, streaming?, code?}
        choices: [],
        busy: false,
        progress: null,        // 0..1 while sending
        error: null,
        log: [],               // {id, t, level:'info'|'ok'|'error'|'device', text}, newest last
        interview: null,       // {asked, max} while interviewing; then null
        brief: null,           // the last interview brief, until used
        savedId: null,         // the saved game this one came from
        example: null,         // {id, name} when opened from an example
        device: { mode: null, active: null, games: [] },  // what the controller holds
        tagWrites: {},         // NFC card label -> writes since the last send
        distribute: null,      // {open, status, scanning, running, done, total, rows, slots}
        can: { simulator: !!simulator, realDevice: !device?.simulated },
    };
    let history = [];          // what goes to the model
    let interviewTurns = [];
    let simNotes = null;
    let knowledge = files || null;
    const link = device || createDeviceLink();
    let nudge = null;

    const emit = () => listeners.forEach(fn => { try { fn(state); } catch (e) { console.error(e); } });
    const set = (patch) => { Object.assign(state, patch); emit(); };
    let logSeq = 0;
    /** Add a line to state.log. 'ok' and 'error' lines are toast-worthy. */
    const log = (text, level = 'info') => {
        state.log = [...state.log.slice(-199), { id: ++logSeq, t: Date.now(), level, text }];
        emit();
    };
    const syncCode = () => { state.code = versions.all(); state.versions = versions.summary(); };
    const safe = (fn, fallback) => { try { return fn(); } catch (e) { log(`Could not use saved games here: ${e.message}`, 'error'); return fallback; } };

    // ---------- controller link ----------
    const goLive = (obj) => {
        if (obj?.device) state.deviceName = deviceShortName(obj);
        if (state.link === 'opening') {
            log(`Connected to ${state.deviceName || 'the controller'}${obj?.version ? ` (firmware ${obj.version})` : ''}.`, 'ok');
            clearInterval(nudge); nudge = null;
            state.link = 'live';
            refreshGames().catch(() => {});
        }
        if (state.link !== 'sending') set({ link: 'live' }); else emit();
    };
    // A device that can become real later (artifacts: the Playground Serial extension) says so here.
    link.on?.('realdevice', (o) => { if (state.can.realDevice !== !!o?.real) set({ can: { ...state.can, realDevice: !!o?.real } }); });
    link.on?.('identity', goLive);
    link.on?.('heartbeat', goLive);
    link.on?.('mode', (o) => {
        state.device = { ...state.device, mode: o?.mode || null, active: o?.active || state.device.active };
        goLive(o);
    });
    link.on?.('close', (o) => {
        clearInterval(nudge);
        if (state.link !== 'idle') log(`Disconnected${o?.reason && o.reason !== 'user' ? ` (${o.reason})` : ''}.`, 'info');
        set({ link: 'idle', device: { mode: null, active: null, games: [] } });
    });
    link.on?.('fatal', (o) => {
        clearInterval(nudge);
        log(`The controller stopped answering${o?.message ? `: ${o.message}` : ''}.`, 'error');
        set({ link: 'idle', error: 'The controller stopped answering.' });
    });
    link.on?.('*', (o) => {
        if (o?.type && o.type !== 'heartbeat') log(`← ${JSON.stringify(o).slice(0, 200)}`, 'device');
    });
    link.on?.('wrong_device', (o) => log(`That is not a Dial or Box (${o?.device}). Pick another port.`, 'error'));
    link.on?.('card_written', (o) => {
        const label = o?.label || o?.tag || o?.card;
        if (!label) return;
        state.tagWrites = { ...state.tagWrites, [label]: (state.tagWrites[label] || 0) + 1 };
        log(`Card written: ${label}.`, 'ok');
    });
    // Distribute progress (app.js DistributeOverlay._listen).
    let dist = null;
    const paintDist = (patch = {}) => {
        if (!dist) return;
        state.distribute = { ...state.distribute, ...patch, scanning: dist.scanning, running: dist.running,
            done: dist.done, total: dist.total, rows: plainRows(dist), slots: dist.slotOptions(state.distribute.slug) };
        emit();
    };
    link.on?.('status_report', (o) => { if (dist) { dist.upsertReport(o); paintDist(); } });
    link.on?.('status_done', () => { if (dist) { dist.endScan(); paintDist({ status: dist.rows.length ? 'Pick the devices to update.' : 'No devices answered. Check they are on, then scan again.' }); } });
    link.on?.('dist_progress', (o) => { if (dist) { dist.applyProgress(o); paintDist(); } });
    link.on?.('dist_done', (o) => {
        if (!dist) return;
        dist.finish(o);
        const ok = dist.rows.filter(r => r.status === 'done').length;
        log(`${ok} of ${o?.total ?? dist.total} devices updated.`, ok ? 'ok' : 'error');
        paintDist({ status: `${ok} of ${o?.total ?? dist.total} devices updated.` });
    });

    const ready = knowledge ? Promise.resolve() : loadKnowledge(knowledgeBase).then(f => { knowledge = f; });

    // ---------- chat ----------
    /** One model turn. hidden: not shown as a user message (automatic follow-ups). */
    async function ask(text, { onText, hidden = false, chain = 0 } = {}) {
        if (!hidden) state.messages.push({ role: 'user', text });
        history.push({ role: 'user', content: text });
        set({ busy: true, error: null, choices: [] });
        log(hidden ? text.split('(')[0].trim() + '…' : 'Asking Claude…');
        const live = { role: 'assistant', text: '', streaming: true };
        state.messages.push(live);
        try {
            const res = await brain({
                system: systemBlocks(knowledge, state.code, { simNotes }),
                history: history.slice(),
                onText: (t) => { live.text = stripAllMarkers(t); onText?.(live.text); emit(); },
            });
            if (res.error || res.stopReason === 'refusal' || !res.text) {
                throw new Error(res.error?.message || res.error || (res.stopReason === 'refusal' ? 'Claude declined that. Try rewording it.' : 'No reply. Try again.'));
            }
            const r = parseReply(res.text);
            history.push({ role: 'assistant', content: trimForHistory(res.text) });
            live.text = r.text;
            delete live.streaming;
            const roles = Object.keys(r.code);
            if (roles.length) {
                const label = text.length > 40 ? text.slice(0, 40) + '…' : text;
                for (const role of roles) versions.save(role, r.code[role], hidden ? `${roleInfo(role).label} part` : label);
                syncCode();
                live.code = r.code;
            }
            if (r.gameName && (!state.gameName || state.gameName === 'Your game')) state.gameName = r.gameName;
            log(roles.length ? `Game code updated: ${roles.join(', ')}.` : 'Claude replied.', roles.length ? 'ok' : 'info');
            if (res.stopReason === 'max_tokens') log('The reply was cut off. Ask for a shorter version.', 'error');
            // A multi-device game is written one device per reply (app.js callClaude).
            const next = r.nextDevice;
            const nextOk = roles.length && next && roleInfo(next) && !roles.includes(next) && chain < ROLES.length - 1;
            if (next && !nextOk) log(`[NEXT_DEVICE: ${next}] ignored.`, 'device');
            set({ busy: false, choices: nextOk ? [] : r.choices });
            if (nextOk) {
                const lbl = roleInfo(next).label.toLowerCase();
                return ask(`Now write the ${lbl} file ([DEVICE: ${next}]) for this game, matching the files already in the editor.`,
                    { onText, hidden: true, chain: chain + 1 });
            }
            return { reply: r.text, code: state.code, gameName: state.gameName, choices: r.choices };
        } catch (e) {
            history.pop();
            state.messages.pop();
            state.messages.push({ role: 'system', text: e.message || String(e) });
            log(`Chat failed: ${e.message || e}`, 'error');
            set({ busy: false, error: e.message || String(e) });
            return null;
        }
    }

    async function chat(text, opts = {}) {
        text = (text || '').trim();
        if (!text || state.busy) return null;
        await ready;
        if (state.interview) return answer(text);
        return ask(text, opts);
    }

    // ---------- interview (app.js startInterview / callInterviewer) ----------
    function startInterview() {
        if (state.busy) return;
        interviewTurns = [];
        state.messages.push({ role: 'assistant', text: INTERVIEW_FIRST_QUESTION });
        log('Interview started.');
        set({ interview: { asked: 1, max: INTERVIEW_MAX_QUESTIONS }, brief: null, choices: [] });
    }

    async function answer(text, finish = false) {
        if (!state.interview || state.busy) return null;
        await ready;
        state.messages.push({ role: 'user', text: finish ? 'Make my game now' : text });
        interviewTurns.push({ role: 'user', content: text });
        const asked = state.interview.asked;
        const last = finish || asked >= INTERVIEW_MAX_QUESTIONS;
        set({ busy: true, error: null, choices: [] });
        log(last ? 'Writing the game plan…' : 'Thinking of the next question…');
        try {
            const res = await brain({
                system: buildInterviewSystemBlocks({
                    knowledge: knowledgeText(knowledge, listSplatActions()),
                    interview: knowledge[INTERVIEW_KNOWLEDGE], asked, finish,
                }),
                history: interviewMessages(interviewTurns),
                format: last ? briefFormat() : null,
                windowed: false,
            });
            if (res.error || !res.text) throw new Error(res.error?.message || 'No reply. Try again.');
            if (res.stopReason === 'max_tokens') throw new Error('The reply was cut off. Try again.');
            let lead, brief;
            if (last) ({ message: lead, brief } = briefFromJson(res.text));
            else {
                brief = parseGameBrief(res.text);
                lead = brief ? stripAllMarkers(stripGameBrief(res.text)) : '';
            }
            if (brief) {
                if (lead) state.messages.push({ role: 'assistant', text: lead });
                state.messages.push({ role: 'assistant', text: briefSummary(brief), brief });
                log('Game plan ready.', 'ok');
                set({ busy: false, interview: null, brief });
                return { brief };
            }
            interviewTurns.push({ role: 'assistant', content: res.text });
            state.messages.push({ role: 'assistant', text: stripAllMarkers(res.text) });
            set({ busy: false, interview: { asked: asked + 1, max: INTERVIEW_MAX_QUESTIONS },
                choices: asked + 1 > 2 ? parseChoices(res.text) || [] : [] });
            return { question: stripAllMarkers(res.text) };
        } catch (e) {
            interviewTurns.pop();
            state.messages.push({ role: 'system', text: e.message });
            log(`Interview failed: ${e.message}`, 'error');
            set({ busy: false, error: e.message });
            return null;
        }
    }

    function finishInterview() {
        return answer('That is all I want to say. Please write the summary now.', true);
    }

    function makeFromBrief() {
        const brief = state.brief;
        if (!brief) return null;
        set({ brief: null });
        return ask(`Make this game for my class.\n\n${brief}`);
    }

    function cancelInterview() {
        interviewTurns = [];
        set({ interview: null, choices: [] });
    }

    // ---------- connect / send ----------
    async function connect() {
        if (state.link !== 'idle') return;
        set({ link: 'opening', error: null });
        log('Choose the controller\'s port…');
        try {
            await link.connect();
        } catch (e) {
            const cancelled = /No port selected|cancel/i.test(e.message);
            log(cancelled ? 'No port chosen.' : `Could not open the port: ${e.message}`, cancelled ? 'info' : 'error');
            set({ link: 'idle', error: cancelled ? null : e.message });
            return;
        }
        if (state.link === 'opening') log('Port open. Waiting for the controller to answer…');
        let tries = 0;
        nudge = setInterval(() => {
            if (state.link !== 'opening' || ++tries > 10) {
                clearInterval(nudge); nudge = null;
                if (state.link === 'opening') {
                    const msg = 'Connected, but the controller is not answering. Try unplugging it and connecting again.';
                    log(msg, 'error');
                    set({ error: msg });
                }
                return;
            }
            if (tries % 2 === 0) log('Still waiting for the controller…');
            link.nudgeIdentify?.();
        }, 2000);
    }

    async function reconnect() {
        set({ link: 'opening' });
        const ok = await link.reconnect?.();
        if (!ok) set({ link: 'idle' });
        return !!ok;
    }

    async function disconnect() {
        clearInterval(nudge);
        if (state.link !== 'idle') log('Disconnected.');
        set({ link: 'idle', deviceName: null, device: { mode: null, active: null, games: [] } });
        try { await link.disconnect?.(); } catch (_) {}
    }

    let lastSent = null;
    async function send() {
        const plan = buildSend(state.code, state.gameName, state.deviceName || 'Dial');
        if (!plan.ok) { log(plan.error, 'error'); set({ error: plan.error }); return plan; }
        if (state.link !== 'live') {
            const r = { ok: false, error: 'Connect your controller first.' };
            log(r.error, 'error');
            set({ error: r.error });
            return r;
        }
        set({ link: 'sending', progress: 0, error: null, tagWrites: {} });
        log(`Sending "${plan.meta.prettyName}" (${plan.meta.destLabel}${plan.meta.extraFiles ? ` + ${plan.meta.extraFiles.length} more file(s)` : ''}) to ${state.deviceName || 'the controller'}…`);
        const res = await uploadPayload(link, plan.code, (p) => {
            const f = p?.total ? (p.current - (p.status === 'uploading' ? 1 : 0)) / p.total : null;
            if (f != null && isFinite(f)) set({ progress: Math.max(0, Math.min(1, f)) });
        }, { linkState: 'sending', role: plan.role, meta: plan.meta, deviceShort: state.deviceName || 'Dial' });
        set({ link: link.isConnected?.() === false ? 'idle' : 'live', progress: null, error: res?.ok ? null : (res?.error || 'Send failed.') });
        log(res?.ok ? `Sent "${plan.meta.prettyName}" to ${state.deviceName || 'the controller'}.` : `Send failed: ${res?.error || 'unknown error'}`, res?.ok ? 'ok' : 'error');
        if (res?.ok) {
            lastSent = { slug: plan.meta.slug, pretty: plan.meta.prettyName, kinds: plan.kinds, tags: plan.meta.tags };
            setTimeout(() => refreshGames().catch(() => {}), 1500);
        }
        return res?.ok ? { ok: true, slug: plan.meta.slug, tags: plan.meta.tags } : { ok: false, error: res?.error || 'Send failed.' };
    }

    // ---------- controller's games (app.js fetchBoxGames / selectBoxGame / deleteBoxGame) ----------
    async function cmd(c, timeoutMs = 5000) {
        if (state.link !== 'live' || !link.sendCmd) throw new Error('Connect your controller first.');
        return link.sendCmd(c, { timeoutMs });
    }
    async function refreshGames() {
        const obj = await cmd({ cmd: 'games.list' });
        state.device = { ...state.device, games: obj.list || [], active: obj.active || state.device.active };
        emit();
        return state.device.games;
    }
    const gameCmd = (name, verb) => async (slug) => {
        try {
            await cmd({ cmd: name, slug });
            log(`${verb} ${slug}.`, 'ok');
            await refreshGames();
            return { ok: true };
        } catch (e) {
            log(`${verb} failed: ${e.message}`, 'error');
            return { ok: false, error: e.message };
        }
    };

    // ---------- distribute (distribute.js DistributeState + DistributeOverlay protocol) ----------
    const distribute = {
        /** Open for the game just sent (or `slug`), and scan. */
        async open(slug) {
            const target = slug ? { slug, pretty: slug, kinds: null } : lastSent;
            if (!target) { log('Send a game to the controller first.', 'error'); return; }
            dist = new DistributeState(target.kinds);
            state.distribute = { open: true, slug: target.slug, pretty: target.pretty, status: '', rows: [], slots: [] };
            paintDist();
            await distribute.scan();
        },
        async scan() {
            if (!dist || dist.running) return;
            dist.startScan();
            paintDist({ status: 'Looking for wands and stations…' });
            try { await cmd({ cmd: 'fleet.scan' }); }
            catch (e) { dist.endScan(); log(`Scan failed: ${e.message}`, 'error'); paintDist({ status: `Scan failed: ${e.message}` }); }
        },
        toggle(mac, on, override = false) { if (dist) { dist.toggle(mac, on, override); paintDist(); } },
        /** slot: the slot index full devices clear (see state.distribute.slots). */
        async send(slot) {
            if (!dist) return;
            if (slot === undefined && dist.slotOptions(state.distribute.slug).length) {
                paintDist({ status: 'Some devices are full. Pick a slot to replace.', needsSlot: true });
                return;
            }
            const replace = slot === undefined ? null : dist.replaceFor(state.distribute.slug, slot);
            const macs = dist.startDistribute();
            if (!macs.length) return;
            paintDist({ status: 'Sending code…', needsSlot: false });
            const c = { cmd: 'fleet.distribute', slug: state.distribute.slug, macs };
            if (replace && Object.keys(replace).length) c.replace = replace;
            try { await cmd(c, 10000); }
            catch (e) { dist.abort(e.message); log(`Distribute failed: ${e.message}`, 'error'); paintDist({ status: `Distribute failed: ${e.message}` }); }
        },
        find(mac) { return cmd({ cmd: 'fleet.find', mac }).catch(e => log(`Find failed: ${e.message}`, 'error')); },
        close() {
            if (dist?.running) cmd({ cmd: 'fleet.cancel' }).catch(() => {});
            dist = null;
            set({ distribute: null });
        },
    };

    // ---------- games: new, examples, saved ----------
    function loadGame({ code = {}, name = null, label, messages = [], hist = [] }) {
        versions.clear();
        for (const [role, c] of Object.entries(code)) if ((c || '').trim()) versions.save(role, c, label);
        syncCode();
        history = hist.slice();
        interviewTurns = [];
        simNotes = null;
        set({ messages, gameName: name, choices: [], error: null, interview: null, brief: null, tagWrites: {} });
    }

    function newGame() {
        loadGame({ label: 'New game' });
        set({ savedId: null, example: null });
        log('Started a new game.');
    }

    async function openExample(id, { remix = false } = {}) {
        const ex = findExample(id);
        if (!ex) { log(`No example "${id}".`, 'error'); return null; }
        try {
            const code = await exampleCode(ex);
            loadGame({ code: { wand: code }, name: remix ? `${ex.name} remix` : ex.name, label: remix ? `${ex.name} (remix base)` : ex.name,
                messages: [{ role: 'system', text: `Opened the ${ex.name} example. ${remix ? 'Describe what to change.' : ''}`.trim() }],
                hist: remix ? [
                    { role: 'user', content: `I would like to remix the ${ex.name} example.` },
                    { role: 'assistant', content: `Here is the ${ex.name} example. What would you like to change?` },
                ] : [] });
            set({ savedId: null, example: { id: ex.id, name: ex.name, simProfile: ex.simProfile || null, vendorGame: ex.vendorGame } });
            log(`Opened example: ${ex.name}.`, 'ok');
            return state.code;
        } catch (e) {
            log(`Could not open ${ex.name}: ${e.message}`, 'error');
            return null;
        }
    }

    function saveCurrent(name) {
        if (!Object.keys(state.code).length) { log('There is no game to save yet.', 'error'); return null; }
        const entry = safe(() => saveGame({
            id: state.savedId || undefined,
            name: (name || state.gameName || 'Untitled game').trim(),
            desc: state.messages.find(m => m.role === 'user')?.text || '',
            code: state.code.wand || '',
            roleCode: Object.fromEntries(Object.entries(state.code).filter(([r]) => r !== 'wand')),
            requiredTags: buildSend(state.code, state.gameName).meta?.tags || [],
            chatHistory: history,
        }), null);
        if (entry) { set({ savedId: entry.id, gameName: entry.name }); log(`Saved "${entry.name}".`, 'ok'); }
        return entry;
    }

    function openSaved(id) {
        const g = safe(() => findSavedGame(id), null);
        if (!g) { log('That saved game is gone.', 'error'); return null; }
        const code = { wand: g.code, ...(g.roleCode || {}) };
        const msgs = (g.chatHistory || []).map(m => ({ role: m.role, text: m.role === 'assistant' ? stripAllMarkers(m.content) : m.content }));
        loadGame({ code, name: g.name, label: 'Loaded from library', messages: msgs, hist: g.chatHistory || [] });
        set({ savedId: g.id, example: null });
        log(`Opened "${g.name}".`, 'ok');
        return g;
    }

    // ---------- simulator ----------
    let sim = null;
    let lastSimError = null;
    function mountSimulator(el) {
        sim?.destroy?.();
        sim = simulator ? simulator(el, kitApi) : null;
        if (!sim) {
            el.textContent = 'The simulator runs in the runner (run.html), not here.';
            return null;
        }
        sim.update(state.code, state.example);
        return sim;
    }
    listeners.add(() => {
        const key = JSON.stringify(state.code);
        if (sim && key !== sim._last) { sim._last = key; sim.update(state.code, state.example); }
    });
    function simError(message) {
        lastSimError = message;
        log(`Simulator: ${message}`, 'error');
    }
    async function fixSimError() {
        if (!lastSimError) return null;
        simNotes = knowledge?.[SIM_KNOWLEDGE] || null;
        const msg = `The simulator shows this problem when it runs the game:\n\n${lastSimError}\n\nPlease fix the game.`;
        lastSimError = null;
        return chat(msg);
    }

    const kitApi = {
        state, ready, chat, connect, reconnect, disconnect, send,
        log, clearLog: () => set({ log: [] }),
        newGame, reset: newGame,
        setGameName: (n) => set({ gameName: (n || '').trim() || null }),
        setCode: (role, c) => { versions.save(role, c, 'Edited'); syncCode(); emit(); },
        prevVersion: (role) => { versions.prev(role); syncCode(); emit(); },
        nextVersion: (role) => { versions.next(role); syncCode(); emit(); },
        startInterview, answer, finishInterview, makeFromBrief, cancelInterview,
        // Each example and saved game carries ready-made pictures, as the web
        // app draws them: `thumb` (HTML for the 5x5 LED start picture),
        // `tint` (a pale CSS background in the game's color), `devices`
        // ("Wand · 8 NFC tags") and, for categories, `iconSvg`.
        examples: () => ({
            categories: CATEGORIES.map(c => ({ ...c, iconSvg: c.icon ? iconSvg(c.icon, { size: 16 }) : '' })),
            list: EXAMPLES.map(e => {
                const gi = GAME_ICONS[e.id] || null;
                return { id: e.id, name: e.name, icon: e.icon, iconSvg: iconSvg(e.icon, { size: 16 }), category: e.category, description: e.description, tagNote: e.tagNote,
                    devices: deviceLine(deviceNeeds({ nfcTags: (e.tags || []).filter(x => !baselineTags(e.id).includes(x)).length })),
                    gameIcon: gi, thumb: gameIconThumb(gi), tint: gameTint(gi) };
            }),
        }),
        /** Three starter ideas, as the web app's New game screen draws them: [{text, icon, iconSvg}]. */
        starterIdeas: () => safe(() => drawStarterIdeas().map(s => ({ text: s.text, icon: s.icon, iconSvg: iconSvg(s.icon, { size: 26, strokeWidth: 2 }) })), []),
        /** SVG markup for one of the web app's icons by name (e.g. 'music', 'plus'), or ''. */
        icon: (name, size = 16) => safe(() => iconSvg(name, { size }), ''),
        openExample, remixExample: (id) => openExample(id, { remix: true }),
        saved: () => safe(() => loadSavedGames().map(g => ({ id: g.id, name: g.name, desc: g.desc, updatedAt: g.updatedAt,
            gameIcon: g.gameIcon || null, thumb: gameIconThumb(g.gameIcon || null), tint: gameTint(g.gameIcon || null) })), []),
        saveGame: saveCurrent, openSaved,
        renameSaved: (id, n) => { const r = safe(() => renameSavedGame(id, n), null); emit(); return r; },
        deleteSaved: (id) => { safe(() => deleteSavedGame(id), null); emit(); log('Deleted the saved game.'); },
        refreshGames: () => refreshGames().catch(e => { log(`Could not list the controller's games: ${e.message}`, 'error'); return []; }),
        selectGame: gameCmd('games.select', 'Selected'),
        deleteGame: gameCmd('games.delete', 'Deleted'),
        distribute,
        mountSimulator, simError, fixSimError,
        on(type, fn) { if (type === 'change') { listeners.add(fn); return () => listeners.delete(fn); } },
        hasSerial: typeof navigator !== 'undefined' && 'serial' in navigator,
        roles: ROLES.map(r => ({ key: r.key, label: r.label })),
    };
    return kitApi;
}
