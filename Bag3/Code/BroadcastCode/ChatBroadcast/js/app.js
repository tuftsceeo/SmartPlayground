import { loadEncryptedKey, initAuthModal, getApiKey, hasEncryptedKey } from './auth.js';
import {
    addMsg, addThinkingMsg, removeTyping, extractCodeBlocks,
    parseNfcCards, parseGameName, parseChoices, parseGameSettings, stripAllMarkers,
    parseGameBrief, stripGameBrief,
    trimForHistory, loadKnowledgeBase, getKnowledgeFiles, getKnowledgeFileCount,
} from './chat.js';
import {
    knowledgeText, buildSystemBlocks, buildRequestBody, requestHeaders, ADVANCED_KNOWLEDGE,
    buildInterviewSystemBlocks, interviewMessages, INTERVIEW_KNOWLEDGE,
    INTERVIEW_MAX_QUESTIONS, INTERVIEW_FIRST_QUESTION,
} from './prompt/buildRequest.js';
import { readMessageStream } from './prompt/stream.js';
import { renderMarkdown, buildCodeBlock } from './markdown.js';
import { drawStarterIdeas, GUIDED_STEPS, guidedPrompt } from './starterIdeas.js';
import {
    initEditor, getCode, setCode, saveVersion, updateVersionUI,
    onPrevVersion, onNextVersion, getVersionCount, onDownload, resetEditor,
    setActiveRole, getActiveRole, rolesWithCode, clearAllRoles,
} from './editor.js';
import { uploadPayload, validateGameCode, validateGameSignature, codeBytes, MAX_WAND_GAME_BYTES } from './upload.js';
import { ROLES as ROLE_TABLE, roleInfo, DEFAULT_ROLE } from './roles.js';
import { listSplatActions } from './splat/splatActionCheck.js';
import { updateTagChecklist } from './nfc.js';
import { EXAMPLES, CATEGORIES, findExample, loadExampleCode } from './examples.js';
import { showView, showOverlay, hideOverlay, setConnectionBadge, toast, setSendProgress, showConnectToast, syncNavTabs } from './router.js';
import { createDeviceLink, deviceShortName, deviceProductName } from './device/bboxDeviceLink.js';
import { SerialAdapter } from './device/serialAdapter.js';
import { NfcStationLink } from './device/nfcStationLink.js';
import { formatPullEvent } from './device/pullEvent.js';
import { createWandDeviceLink } from './device/wandDeviceLink.js';
import { subscribe, getEntries, toText } from './device/serialLog.js';
import { setWorkspaceHandler } from './markdown.js';
import { dbg, dbgWarn, dbgError } from './debug.js';
import { loadUiMode, toggleUiMode, getUiMode } from './uiMode.js';
import { loadDevMode, toggleDevMode } from './devMode.js';
import { loadSavedGames, saveGame, findSavedGame, renameSavedGame, deleteSavedGame } from './library.js';
import { scanCapabilities } from './sim/codeCapabilities.js';
import { buildComponentChecklist } from './checklist.js';
import { validateGameName, slugify, remixName } from './gameName.js';
import { buildHardwareReqs, formatHardwareReqs, baselineTags } from './hardware.js';
import { initPaneSplit } from './paneSplit.js';
import { initSerialSplit } from './serialSplit.js';
import { initCodeDrawerSplit } from './codeDrawerSplit.js';
import { iconSvg, exampleIcon } from './icons.js';
// LED icons for the display panel -- unrelated to icons.js, which is UI chrome.
import {
    iconNamesIn, missingIconsIn, iconFileText, listIcons,
    getIcon, saveIcon, revertIcon, isCustom,
    setGameIcons, getGameIcons, onIconsChange,
} from './ledicons/iconLibrary.js';
import { gameIconEntries, startingIcon, drawIcon } from './ledicons/iconView.js';

const SILENCE_LIMIT_MS = 15000;
const SIM_IDLE_PAUSE_MS = 60000;
const SIM_KNOWLEDGE = 'knowledge/simulator.md';
const SIM_LOG_FOR_CHAT = 40;
const SILENCE_GAME_MS = 45000;
const REBOOT_LIMIT_MS = 20000;
const WATCHDOG_TICK_MS = 2000;
/* Auto-reconnect (tryAutoReconnect()) is a convenience for the ordinary
   post-send reboot, not a guarantee -- cap it so a device that genuinely
   isn't coming back (or one that keeps bouncing its USB) doesn't turn into
   an endless silent retry loop. REBOOT_LIMIT_MS is the other half of that
   ceiling; whichever is hit first ends the wait, and the teacher can always
   cancel out sooner via the header button. */
const MAX_AUTO_RECONNECT_ATTEMPTS = 2;
/* A running Box sends a heartbeat every HEARTBEAT_MS (5s, bbox_server.py) on
   top of its boot identity, and GRACE_S is now 1s. So total silence for this long
   does not mean "still waking up" -- it means the firmware is not running (or
   the port we opened is not the one it talks on). Say so instead of waiting
   forever. */
const WAITING_LIMIT_MS = 12000;
/* The wand's full boot (grace + sensor init) runs >20s (HARDWARE_PROTOCOL.md)
   vs. the Box's ~5s -- untested against real hardware as of this writing, so
   generous rather than tuned. Only matters for a connect made while the wand
   is mid-boot; once running, its heartbeat is every 5s same as the Box's. */
const WAITING_LIMIT_WAND_MS = 25000;
/* The Box volunteers its identity only once, at boot. If we opened the port
   after it booted, that one announcement is already gone, so re-ask on a cadence rather
   than betting everything on a single probe that may have crossed a busy
   moment. Replies arrive as ordinary `identity` events and promote us to live.
   This is a convenience, not the liveness test: `heartbeat` alone reaches live
   within 5s regardless. */
const IDENTIFY_NUDGE_MS = 2500;

/** Minimum interval between redraws of a streaming chat reply. */
const STREAM_RENDER_MS = 80;

/** Same placeholder-and-play() check the editor's code drawer uses to
 * decide there's real code worth doing anything with. */
function isRunnableCode(code) {
    const trimmed = (code || '').trim();
    return !!trimmed && !trimmed.startsWith('# AI-generated') && /def\s+play\s*\(/.test(trimmed);
}

/**
 * The game's primary file: the first role (ROLE_TABLE order, wand first)
 * with runnable code. A display-only game's primary role is `icon`.
 * @returns {{role: string, info: object, code: string}|null}
 */
function primaryRoleCode() {
    for (const info of ROLE_TABLE) {
        const code = getCode(info.key);
        if (isRunnableCode(code)) return { role: info.key, info, code };
    }
    return null;
}

class App {
    constructor() {
        // Default to a Box/Dial link; onConnect(kind) swaps this for a
        // WandDeviceLink when the teacher picks "Wand" on the connect
        // overlay, and re-runs setupDeviceListeners() -- see onConnect().
        this.device = createDeviceLink();
        this.chatHistory = [];
        // Interview mode state, or null: {turns, asked} (startInterview).
        this.interview = null;
        this.isGenerating = false;
        this.currentExample = null;
        this.gameName = 'Your game';
        this.gameDesc = '';
        this.declaredTags = null;   // tags the game itself declares ([NFC_CARDS:] / example)
        this.simSettings = null;    // [GAME_SETTINGS:] for the practice window, or null
        this.hardware = buildHardwareReqs({});
        this.tagWrites = {};        // live {tagLabel: count} from card_written events
        this.galleryFilter = 'all';
        this.galleryMode = 'examples'; // 'examples' | 'saved'
        this.serialOpen = false; // log footer drawer — NOT the port
        this.dirty = false;
        this.pendingSendAfterConnect = false;
        this._sim = null;
        this._simLoadPromise = null;
        this._detailSim = null;
        this._detailSimToken = 0;
        this._simLastSource = null;
        this._simLastDisplay = null;
        this._simLastSettings = null;
        this._simPendingSource = null;
        this._simForcePlayPending = false;
        // One store for connection UI — badge and button share this.
        this.link = {
            state: 'idle',
            boxMode: null,
            deviceInfo: null,
            lastMsgAt: 0,
            waitingSince: 0,
            detail: null,
        };
        this._watchdogTimer = null;
        this._rebootTimer = null;
        this._identifyNudgeTimer = null;
        this._reconnecting = false;
        this._reconnectAttempts = 0;
        this._silenceLimitMs = SILENCE_LIMIT_MS;
        this._boxGames = []; // last games.list from the Box
        this._pendingReplaceSlug = null;
    }

    /** Short UI name for the linked device ("Box", "Dial" or "Wand").
     *  `this.device.kind` is known the instant a WandDeviceLink is picked on
     *  the connect overlay -- checked first so labels read right before the
     *  wand's own `identity` has even arrived (link.deviceInfo is still
     *  null then). deviceShortName() covers Box vs. Dial, which share one
     *  link class and are told apart only by that identity. */
    deviceShort() {
        if (this.device.kind === 'wand') return 'Wand';
        return deviceShortName(this.link.deviceInfo);
    }

    /** Product UI name ("Broadcast Box", "Broadcast Dial" or "Wand"). */
    deviceProduct() {
        if (this.device.kind === 'wand') return 'Wand';
        return deviceProductName(this.link.deviceInfo);
    }

    async init() {
        dbg('app', 'init() starting');
        hydrateIcons(document);
        initEditor();
        dbg('app', 'editor initialized');
        updateVersionUI();
        this.bindEvents();
        dbg('app', 'event listeners bound');
        initPaneSplit();
        initCodeDrawerSplit();
        this.watchDetailView();
        this.setupGallery();
        this.setupDeviceListeners();
        this.setupSerialLog();
        this.applyUiMode(loadUiMode());
        showView('splash');
        dbg('app', 'initial view: splash (modal-overlay is persistent — showView must not touch it)');

        dbg('app', 'loading encrypted key…');
        await loadEncryptedKey();
        initAuthModal();
        dbg('app', 'auth modal initialized — waiting for app:unlocked');

        document.addEventListener('app:unlocked', () => {
            dbg('app', 'received app:unlocked event');
        });

        document.addEventListener('uimode:change', (e) => {
            this.applyUiMode(e.detail.mode);
        });
        document.addEventListener('devmode:change', () => this.applyLogFooter());

        // An edited icon is unsaved work like any other.
        //
        // EVENT `game-icons-changed` on document, detail {icons}: the open
        // game's own icons ({name: duty[768]}, getGameIcons()) after any
        // change to them -- an Icons view save or revert, or a game being
        // opened or cleared. Built-in icons are not in detail.icons; read
        // them through listIcons()/getIcon(). The Simulator's display panel
        // listens for it to reload the game's icons.
        onIconsChange(() => {
            this.dirty = true;
            document.dispatchEvent(new CustomEvent('game-icons-changed', {
                detail: { icons: getGameIcons() },
            }));
            this.updatePreview();
        });

        // No knowledge, no chat: callClaude() refuses while this is set.
        this.knowledgeError = null;
        try {
            await loadKnowledgeBase();
            dbg('app', `knowledge base loaded (${getKnowledgeFileCount()} file(s))`);
        } catch (e) {
            this.knowledgeError = e.message;
            dbgError('app', e.message);
        }

        window.onUploadProgress = (p) => {
            const pct = p.total ? Math.round((p.current / p.total) * 100) : 0;
            dbg('upload', `${p.status} ${p.file} (${p.current}/${p.total}, ${pct}%)`);
            setSendProgress(pct, `${p.status}: ${p.file}`);
        };

        setWorkspaceHandler((code) => {
            dbg('app', `workspace handler: code block sent to editor (${code.length} chars)`);
            setCode(code);
            saveVersion(code, 'From chat (sent manually)');
            this.dirty = true;
            addMsg(`Code sent to editor (v${getVersionCount()})`, 'system');
            document.getElementById('code-drawer').classList.remove('hidden');
            this.updatePreview();
        });

        this.updatePreview();
        dbg('app', 'init() complete');
    }

    /**
     * System blocks for the next request (js/prompt/buildRequest.js):
     * the cached knowledge base, the Advanced-mode addendum when that mode
     * is on, then this turn's icon names and editor code.
     */
    getSystemBlocks() {
        const files = getKnowledgeFiles();
        // The editor's placeholder comment is not code; send it as empty.
        const editorCode = Object.fromEntries(ROLE_TABLE.map((r) => {
            const code = getCode(r.key);
            return [r.key, code.trim().startsWith('# AI-generated') ? '' : code];
        }));
        return buildSystemBlocks({
            knowledge: knowledgeText(files, listSplatActions()),
            advanced: files[ADVANCED_KNOWLEDGE],
            advancedMode: getUiMode() === 'advanced',
            icons: listIcons(),
            customIcons: Object.keys(getGameIcons()),
            editorCode,
            simNotes: this.simNotes,
        });
    }

    /**
     * Reflect the roles the current game has onto the code drawer's device
     * tabs (wand and display).
     *
     * A tab is enabled once that role holds code, and marked active when it
     * is the one the editor is showing. The wand tab always stays enabled:
     * it is where a new game starts. With only wand code there is nothing to
     * switch between, so the whole group hides rather than showing a lone
     * tab next to a permanently dead one.
     */
    syncRoleRail() {
        const have = new Set(rolesWithCode());
        const active = getActiveRole();
        // The rail is worth showing once ANY non-wand role has code -- the
        // wand tab is otherwise the only one ever enabled, so a single-role
        // (wand-only) game keeps the rail hidden exactly as before.
        const hasOther = [...have].some(r => r !== DEFAULT_ROLE);

        document.querySelectorAll('.device-tab').forEach((el) => {
            const role = el.dataset.role;
            const info = role && roleInfo(role);
            if (!info) return;
            const enabled = role === DEFAULT_ROLE || have.has(role);
            el.classList.toggle('disabled', !enabled);
            el.classList.toggle('active', enabled && role === active);
            el.disabled = !enabled;
            el.title = enabled ? info.label : `No ${info.label.toLowerCase()} code in this game yet`;
        });
        document.getElementById('code-device-tabs')?.classList.toggle('hidden', !hasOther);
    }

    closeMoreMenu() {
        document.getElementById('more-panel')?.classList.add('hidden');
        document.getElementById('btn-more')?.setAttribute('aria-expanded', 'false');
    }

    /**
     * The Icons view: shown in place of the preview stage. The Maker
     * iframe's src is set on first open so it (Tailwind, Lucide, Cropper) is
     * not downloaded by teachers who never edit an icon.
     */
    openIconsView() {
        const view = document.getElementById('icons-view');
        const frame = document.getElementById('icon-maker-frame');
        if (!view || !frame) return;
        // ?embed=1 tells the Maker it is a panel inside this app rather than
        // its own page -- see iconmaker/js/api.js. Its capabilities are
        // reachable as frame.contentWindow.iconMaker.
        if (!frame.getAttribute('src')) {
            frame.setAttribute('src', 'iconmaker/?embed=1');
            frame.addEventListener('load', () => this.wireIconMaker(frame), { once: true });
        } else {
            // Already loaded: re-point it, because the open game may have
            // changed since it was last used.
            this.wireIconMaker(frame);
        }
        view.classList.remove('hidden');
        document.querySelector('.preview-stage')?.classList.add('hidden');
        document.getElementById('btn-icons-view')?.setAttribute('aria-pressed', 'true');
        document.getElementById('btn-icons-view')?.classList.add('active');
        this.renderIconsList();
        dbg('app', 'icons view opened');
    }

    closeIconsView() {
        const view = document.getElementById('icons-view');
        if (!view || view.classList.contains('hidden')) return;
        this.closeIconMenu();
        view.classList.add('hidden');
        document.querySelector('.preview-stage')?.classList.remove('hidden');
        document.getElementById('btn-icons-view')?.setAttribute('aria-pressed', 'false');
        document.getElementById('btn-icons-view')?.classList.remove('active');
        dbg('app', 'icons view closed');
    }

    iconsViewOpen() {
        return !document.getElementById('icons-view')?.classList.contains('hidden');
    }

    /**
     * Fill the Icons view's list: every icon the wand and display code use
     * plus this game's own, each marked built-in, custom or missing, with a
     * thumbnail drawn as the panel shows it. Selecting one opens it in the
     * Maker; a missing one opens as a new icon under that name.
     */
    renderIconsList() {
        const list = document.getElementById('icons-list');
        const note = document.getElementById('icons-list-note');
        if (!list) return;
        const entries = gameIconEntries([getCode('wand'), getCode('icon')]);
        const openName = this.iconApi()?.getState().name;
        list.innerHTML = '';
        for (const { name, status } of entries) {
            const li = document.createElement('li');
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = `icons-item ${status}` + (name === openName ? ' active' : '');
            btn.dataset.name = name;
            const canvas = document.createElement('canvas');
            canvas.className = 'icons-thumb';
            canvas.width = 48;
            canvas.height = 48;
            const label = document.createElement('span');
            label.className = 'icons-name';
            label.textContent = name;
            const badge = document.createElement('span');
            badge.className = `icons-badge ${status}`;
            badge.textContent = status;
            btn.append(canvas, label, badge);
            btn.addEventListener('click', () => this.openIconInMaker(name, status));
            li.appendChild(btn);
            list.appendChild(li);
            if (status !== 'missing') drawIcon(canvas, name, 0.3);
        }
        const missing = entries.filter((e) => e.status === 'missing').map((e) => e.name);
        if (note) {
            note.textContent = !entries.length
                ? 'This game uses no icons yet.'
                : missing.length
                    ? `Missing icons stop the game being sent: ${missing.join(', ')}. Select one to draw it.`
                    : '';
        }
        const editing = document.getElementById('icons-editing');
        if (editing) editing.textContent = openName ? `Editing “${openName}”` : 'Select an icon';
    }

    /** Open one listed icon in the Maker. A missing name has no pixels to
     * open, so the Maker's current picture is kept and renamed to it; Save
     * then creates it. */
    async openIconInMaker(name, status) {
        const api = this.iconApi();
        if (!api) {
            toast('The icon editor is still loading.', true);
            return;
        }
        try {
            if (status === 'missing') api.doc.rename(name);
            else await api.library.open(name);
        } catch (e) {
            toast(String(e?.message || e), true);
            return;
        }
        this.renderIconsList();
    }

    /** The embedded editor's API, or null before the drawer has loaded. */
    iconApi() {
        return document.getElementById('icon-maker-frame')?.contentWindow?.iconMaker || null;
    }

    /**
     * The drawer's own toolbar. The editor iframe shows the canvas only, so
     * these are its verbs -- each one a call into iconmaker/js/api.js rather
     * than a click synthesised on chrome this app does not own.
     */
    bindIconToolbar() {
        const api = () => this.iconApi();
        const fail = (e) => toast(String(e?.message || e), true);
        const run = async (fn) => { try { await fn(); } catch (e) { fail(e); } };

        const fileInput = document.getElementById('icon-file-input');
        document.getElementById('btn-icon-import')?.addEventListener('click', () => fileInput?.click());
        fileInput?.addEventListener('change', (e) => {
            const file = e.target.files?.[0];
            e.target.value = '';
            if (file) run(() => api()?.source.importImage(file));
        });

        document.getElementById('btn-icon-undo')?.addEventListener('click', () => run(() => api()?.doc.undo()));
        document.getElementById('btn-icon-save')?.addEventListener('click', () => run(async () => {
            const saved = await api()?.library.save();
            this.renderIconsList();
            toast(`Saved “${saved}” into this game`);
        }));

        const moreBtn = document.getElementById('btn-icon-more');
        const panel = document.getElementById('icon-more-panel');
        moreBtn?.addEventListener('click', () => {
            const open = panel.classList.toggle('hidden') === false;
            moreBtn.setAttribute('aria-expanded', String(open));
            if (!open) document.getElementById('icon-samples-list')?.classList.add('hidden');
        });
        document.addEventListener('click', (e) => {
            if (!e.target.closest('#icon-more-panel, #btn-icon-more')) this.closeIconMenu();
        });

        document.getElementById('btn-icon-adjust')?.addEventListener('click', () => run(() => {
            const on = api()?.doc.toggleAdjust();
            document.getElementById('btn-icon-adjust').classList.toggle('active', !!on);
        }));
        document.getElementById('btn-icon-export')?.addEventListener('click', () => run(() => {
            api()?.exportFile.icon();
            this.closeIconMenu();
        }));
        document.getElementById('btn-icon-samples')?.addEventListener('click', () => {
            const list = document.getElementById('icon-samples-list');
            if (!list) return;
            if (!list.dataset.filled) {
                list.innerHTML = (api()?.source.listSamples() || [])
                    .map((n) => `<button type="button" class="more-item" data-sample="${n}">${n}</button>`)
                    .join('');
                list.dataset.filled = '1';
                list.querySelectorAll('[data-sample]').forEach((b) => {
                    b.addEventListener('click', () => run(async () => {
                        await api()?.source.loadSample(b.dataset.sample);
                        this.closeIconMenu();
                    }));
                });
            }
            list.classList.toggle('hidden');
        });
    }

    closeIconMenu() {
        document.getElementById('icon-more-panel')?.classList.add('hidden');
        document.getElementById('icon-samples-list')?.classList.add('hidden');
        document.getElementById('btn-icon-more')?.setAttribute('aria-expanded', 'false');
    }

    /**
     * The names the Maker's library lists: every icon the game uses (see
     * gameIconEntries) that exists. Only an icon the display code names is
     * uploaded by the send flow; one authored but not yet named is kept with
     * the game until the code asks for it.
     */
    gameIconNames() {
        return gameIconEntries([getCode('wand'), getCode('icon')])
            .filter((e) => e.status !== 'missing')
            .map((e) => e.name);
    }

    /**
     * Point the embedded Maker at THIS GAME's icons.
     *
     * The iframe imports its own copy of iconLibrary.js, with its own empty
     * per-game map, so without this its saves would land in a store nothing
     * ever reads. These closures run in this window, against the open game.
     */
    wireIconMaker(frame) {
        const api = frame.contentWindow?.iconMaker;
        if (!api) {
            dbgWarn('app', 'icons view: iconMaker API not present — is iconmaker/js/api.js loaded?');
            return;
        }
        api.library.setBackend({
            list: () => this.gameIconNames(),
            get: (name) => getIcon(name),
            save: (name, duty) => saveIcon(name, duty),
            revert: (name) => revertIcon(name),
            isCustom: (name) => isCustom(name),
        });
        if (!this._makerChangeHooked) {
            api.on('change', () => this.renderIconsList());
            this._makerChangeHooked = true;
        }
        this.renderIconsList();
        this.openStartingIcon(api);
        dbg('app', 'icon maker wired to the open game’s icon store');
    }

    /**
     * Start the editor on the display game's starting icon, rather than on
     * the Maker's own apple sample.
     *
     * The Maker boots by loading that sample asynchronously, so opening
     * immediately would be overwritten when the sample lands. Waiting for the
     * first state with an icon in it is the reliable point to take over.
     */
    openStartingIcon(api) {
        const wanted = startingIcon(getCode('icon'))
            || this.gameIconNames()[0];
        if (!wanted) return;

        const open = () => {
            try {
                api.library.open(wanted);
                this.renderIconsList();
                dbg('app', `icon maker opened on "${wanted}" (the starting icon)`);
            } catch (e) {
                dbgWarn('app', `icon maker: could not open "${wanted}" — ${e.message}`);
            }
        };

        if (api.getState().hasIcon) { open(); return; }
        const off = api.on('change', (s) => {
            if (!s.hasIcon) return;
            off();
            open();
        });
    }

    /** Rename in place from the title bar. The name still gets its real
     * validation at send time (a slug has to be a legal module name on the
     * device); this only rejects what is obviously unusable. */
    bindGameNameEditor() {
        const btn = document.getElementById('btn-game-name');
        const input = document.getElementById('ws-name-input');
        if (!btn || !input) return;

        const commit = (save) => {
            if (input.classList.contains('hidden')) return;
            const next = input.value.trim();
            if (save && next && next !== this.gameName) {
                const check = validateGameName(next);
                if (!check.ok && check.reason !== 'replace') {
                    toast(check.reason, true);
                } else {
                    this.gameName = check.pretty || next;
                    this.dirty = true;
                    dbg('app', `game renamed to ${JSON.stringify(this.gameName)}`);
                }
            }
            input.classList.add('hidden');
            btn.classList.remove('hidden');
            this.syncGameName();
        };

        btn.addEventListener('click', () => {
            input.value = this.gameName && this.gameName !== 'Your game' ? this.gameName : '';
            btn.classList.add('hidden');
            input.classList.remove('hidden');
            input.focus();
            input.select();
        });
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') commit(true);
            else if (e.key === 'Escape') commit(false);
        });
        input.addEventListener('blur', () => commit(true));
    }

    /** Title-bar label follows this.gameName, which chat, examples and saved
     * games all write to. */
    syncGameName() {
        const label = document.getElementById('ws-name-label');
        if (!label) return;
        const name = (this.gameName || '').trim();
        label.textContent = !name || name === 'Your game' ? 'Untitled game' : name;
    }

    /** Show a role's file in the editor, if that role has one. */
    selectRole(role) {
        if (role !== DEFAULT_ROLE && !rolesWithCode().includes(role)) return;
        setActiveRole(role);
        this.syncRoleRail();
        this.updatePreview();
        dbg('app', `editor showing role: ${role}`);
    }

    applyUiMode(mode) {
        const advanced = mode === 'advanced';
        const gear = document.getElementById('btn-mode-gear');

        document.body.classList.toggle('ui-advanced', advanced);

        this.applyLogFooter();
        this.syncRoleRail();
        if (gear) {
            gear.title = advanced ? 'Switch to simple mode' : 'Switch to advanced mode';
            gear.classList.toggle('active', advanced);
        }
        // The element itself may not be upgraded yet (setupSim() lazy-loads
        // its module) — setting the attribute is harmless either way and
        // takes effect once it is.
        document.getElementById('wand-sim')?.toggleAttribute('advanced', advanced);
        this._detailSim?.toggleAttribute('advanced', advanced);
        dbg('app', `UI mode: ${mode}`);
    }

    /** The log footer shows only with advanced mode and Developer mode both on. */
    applyLogFooter() {
        const panel = document.getElementById('serial-log-panel');
        const dev = document.getElementById('btn-dev-mode');
        const on = loadDevMode();
        if (dev) {
            dev.classList.toggle('active', on);
            dev.setAttribute('aria-pressed', String(on));
        }
        if (!panel) return;
        if (getUiMode() === 'advanced' && on) {
            panel.classList.remove('hidden');
            if (!this.serialOpen) panel.classList.remove('open');
            this.reserveSerialPadding();
        } else {
            panel.classList.add('hidden');
            panel.classList.remove('open');
            this.serialOpen = false;
            document.body.style.paddingBottom = '';
        }
    }

    reserveSerialPadding() {
        const panel = document.getElementById('serial-log-panel');
        if (!panel || panel.classList.contains('hidden')) {
            document.body.style.paddingBottom = '';
            return;
        }
        requestAnimationFrame(() => {
            document.body.style.paddingBottom = `${panel.offsetHeight}px`;
        });
    }

    setupSerialLog() {
        const panel = document.getElementById('serial-log-panel');
        const pre = document.getElementById('serial-log-text');
        const preview = document.getElementById('serial-log-preview');
        // Start hidden; applyLogFooter reveals it
        panel.classList.add('hidden');
        panel.dataset.log = 'serial';
        // Simulator and radio lines live here, not in the serial log store,
        // so Copy still copies only the device log.
        this._logLines = { serial: [], sim: [], radio: [] };
        const showPreview = () => {
            const lines = this._logLines[panel.dataset.log];
            if (preview) preview.textContent = lines[lines.length - 1] || '';
        };
        this.appendLog = (section, text) => {
            const lines = this._logLines[section];
            lines.push(text);
            if (lines.length > 200) lines.splice(0, lines.length - 200);
            const out = document.getElementById(`${section}-log-text`);
            out.textContent = lines.join('\n');
            out.scrollTop = out.scrollHeight;
            if (panel.dataset.log === section) showPreview();
        };

        subscribe((entry) => {
            const lines = entry === null ? [] : getEntries().slice(-80).map((e) => {
                const tag = e.dir.toUpperCase().padEnd(5);
                return `${tag} ${e.text}`;
            });
            this._logLines.serial = lines;
            pre.textContent = lines.join('\n');
            pre.scrollTop = pre.scrollHeight;
            if (panel.dataset.log === 'serial') showPreview();
        });

        // A section tab opens the drawer on that section; the open one's tab
        // collapses it.
        panel.querySelectorAll('.log-tab').forEach((tab) => {
            tab.addEventListener('click', () => {
                const section = tab.dataset.log;
                this.serialOpen = !(this.serialOpen && panel.dataset.log === section);
                panel.dataset.log = section;
                panel.querySelectorAll('.log-tab').forEach((t) => {
                    t.classList.toggle('active', t === tab);
                    t.setAttribute('aria-selected', String(t === tab));
                });
                panel.querySelectorAll('.log-pane').forEach((p) => {
                    p.classList.toggle('active', p.dataset.log === section);
                });
                panel.classList.toggle('open', this.serialOpen);
                showPreview();
                this.reserveSerialPadding();
            });
        });
        initSerialSplit({
            onResize: () => this.reserveSerialPadding(),
            onOpenChange: (open) => {
                this.serialOpen = open;
                this.reserveSerialPadding();
            },
        });
        document.getElementById('btn-copy-log').addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(toText());
                toast('Serial log copied');
            } catch {
                toast('Could not copy log', true);
            }
        });
    }

    setupDeviceListeners() {
        this.paintLink();
        this._startWatchdog();

        const onTyped = (obj, label) => {
            dbg('device', `event: ${label}`, obj);
            this._noteMessage(obj);
            if (this.link.state === 'wrong') return;
            // 'no-answer' is included deliberately: giving up must not be a
            // one-way door. If the Box is restarted, finally finishes booting,
            // or comes back from a blocking serve, its first message promotes
            // us straight back to live with no user action.
            if (this.link.state === 'waiting' || this.link.state === 'rebooting'
                || this.link.state === 'opening' || this.link.state === 'no-answer'
                || this.link.state === 'sending') {
                this.setLinkState('live');
            } else if (this.link.state === 'stuck' && obj?.type && obj.type !== 'repl') {
                this.setLinkState('live');
            } else {
                this.paintLink();
            }
        };

        this.device.on('identity', (obj) => onTyped(obj, 'identity'));
        this.device.on('heartbeat', (obj) => onTyped(obj, 'heartbeat'));
        this.device.on('mode', (obj) => {
            dbg('device', 'event: mode', obj);
            this._noteMessage(obj);
            this.link.boxMode = obj.mode || null;
            const active = obj.active || null;
            const pretty = (this._boxGames || []).find((g) => g.slug === active)?.name;
            this.link.detail = {
                ...(this.link.detail || {}),
                active,
                activeName: pretty || active,
                games: obj.games,
            };
            if (this.link.state === 'waiting' || this.link.state === 'rebooting'
                || this.link.state === 'no-answer' || this.link.state === 'sending') {
                this.setLinkState('live');
            } else {
                this.paintLink();
            }
        });
        this.device.on('armed', (obj) => {
            dbg('device', 'event: armed', obj);
            this._noteMessage(obj);
        });
        this.device.on('pull', (obj) => {
            dbg('device', 'event: pull', obj);
            this._noteMessage(obj);
            const name = (this._boxGames || []).find((g) => g.slug === obj?.slug)?.name;
            const { msg, isError } = formatPullEvent(obj, name);
            toast(msg, isError);
        });
        this.device.on('card_present', (obj) => dbg('device', 'event: card_present', obj));
        this.device.on('card_written', (obj) => {
            dbg('device', 'event: card_written', obj);
            const label = obj?.label || obj?.tag || obj?.card;
            if (!label) return;
            this.tagWrites[label] = (this.tagWrites[label] || 0) + 1;
            updateTagChecklist(this.tagWrites);
        });
        this.device.on('fatal', (obj) => {
            dbgError('device', 'event: fatal', obj);
            toast(obj?.msg || `The ${this.deviceShort()} reported a serious error — check the cable.`, true);
        });
        // Wand-only (MockWand/main.py's _launch_game()): a running game blocks
        // the wand's idle loop -- raise the silence limit while it runs.
        // Never fires on a BboxDeviceLink.
        this.device.on('game_start', (obj) => {
            dbg('device', 'event: game_start', obj);
            this._noteMessage(obj);
            this._silenceLimitMs = SILENCE_GAME_MS;
            if (this.link.state === 'waiting' || this.link.state === 'rebooting'
                || this.link.state === 'no-answer') {
                this.setLinkState('live');
            } else {
                this.paintLink();
            }
        });
        this.device.on('game_end', (obj) => {
            dbg('device', 'event: game_end', obj);
            this._noteMessage(obj);
            this._silenceLimitMs = SILENCE_LIMIT_MS;
            this.paintLink();
        });
        this.device.on('error', (obj) => {
            dbgError('device', 'event: error', obj);
            // Wand-only shape (MockWand/main.py's _game_load_failed()): a
            // pushed game that will not import. Box `error` events don't
            // carry `where`, so this never toasts for the Box path.
            if (obj?.where === 'game_load') {
                toast(`The wand couldn't start "${obj.slug}": ${obj.err || 'unknown error'}`, true);
            }
        });
        this.device.on('wrong_device', (obj) => {
            dbgWarn('device', 'event: wrong_device', obj);
            const label = this.device.kind === 'wand' ? 'a wand' : 'a Broadcast Box or Dial';
            toast(`That device isn't ${label} — check what's plugged in.`, true);
            this.setLinkState('wrong');
        });
        this.device.on('bye', (obj) => {
            dbg('device', 'event: bye', obj);
            this.setLinkState('rebooting');
            this._armRebootTimer();
        });
        this.device.on('booting', (obj) => {
            dbg('device', 'event: booting', obj);
            // Also from 'no-answer': a `# booting` line is proof the Box is
            // alive after all, so stop saying it isn't answering and wait out
            // the boot instead.
            if (this.link.state === 'live' || this.link.state === 'sending'
                || this.link.state === 'waiting' || this.link.state === 'rebooting'
                || this.link.state === 'no-answer') {
                this.setLinkState('rebooting');
                this._armRebootTimer();
            }
        });
        this.device.on('repl', (info) => {
            dbgWarn('device', 'event: repl (firmware not running)', info);
            if (this.link.state === 'sending' || this.link.state === 'rebooting') return;
            this.setLinkState('stuck');
        });
        this.device.on('close', async (info) => {
            dbgWarn('device', 'adapter close', info);
            try {
                await this.device.disconnect();
            } catch (_) { /* already gone */ }
            this.setLinkState('lost');
            toast(`${this.deviceProduct()} disconnected — check the cable.`, true);
        });

        // Guarded: setupDeviceListeners() now re-runs whenever onConnect()
        // swaps device kinds (see onConnect()), and this listener must not
        // stack a new closure onto navigator.serial (a global, not
        // per-device) each time.
        if (navigator.serial && !this._globalSerialWired) {
            this._globalSerialWired = true;
            navigator.serial.addEventListener('disconnect', () => {
                dbgWarn('device', 'navigator.serial disconnect event fired');
                if (this.link.state !== 'idle' && this.link.state !== 'lost') {
                    this.onSerialDrop();
                }
            });
            // The device's own reboot (after a send, or a manual restart)
            // re-enumerates its native USB, which the browser reports here
            // the moment the port is available again -- well before any
            // fixed timeout would give up. Device-agnostic: Box and Dial
            // both reopen the same way (see BboxDeviceLink.reconnect()).
            navigator.serial.addEventListener('connect', () => {
                dbg('device', 'navigator.serial connect event fired');
                this.tryAutoReconnect();
            });
        } else if (!navigator.serial) {
            dbgWarn('device', 'Web Serial API not available in this browser (need Chrome/Edge)');
        }
    }

    /**
     * Reopen a previously granted port without prompting, when the browser
     * reports the device's port is available again. Only fires while we
     * are actively expecting or hoping for the device back (rebooting, or
     * lost after being connected) -- never for an intentional disconnect
     * (state 'idle'), never more than one attempt at a time, and never more
     * than MAX_AUTO_RECONNECT_ATTEMPTS total per drop -- this is a
     * convenience for the ordinary post-send reboot, not a promise to keep
     * retrying against a device that genuinely isn't coming back. The
     * teacher can also always cancel out via the header button (see
     * toggleConnect()'s 'rebooting' case) rather than wait on either the
     * cap or the reboot timer.
     */
    async tryAutoReconnect() {
        if (this.link.state !== 'rebooting' && this.link.state !== 'lost') return;
        if (this._reconnecting) return;
        if (this._reconnectAttempts >= MAX_AUTO_RECONNECT_ATTEMPTS) {
            dbg('device', `tryAutoReconnect(): already made ${this._reconnectAttempts} attempt(s) — not retrying again`);
            return;
        }
        this._reconnecting = true;
        this._reconnectAttempts += 1;
        dbg('device', `tryAutoReconnect() attempt ${this._reconnectAttempts}/${MAX_AUTO_RECONNECT_ATTEMPTS} — link state is ${this.link.state}`);
        try {
            const reopened = await this.device.reconnect();
            if (reopened) {
                this._clearRebootTimer();
                this._reconnectAttempts = 0;
                this.setLinkState('waiting');
                toast(`Reconnected — waking up the ${this.deviceShort()}…`);
            } else {
                dbg('device', 'tryAutoReconnect(): no matching granted port to reopen yet');
            }
        } catch (e) {
            dbgWarn('device', `tryAutoReconnect() failed: ${e.message}`);
        } finally {
            this._reconnecting = false;
        }
    }

    _noteMessage(obj) {
        this.link.lastMsgAt = Date.now();
        if (obj?.type === 'identity') this.link.deviceInfo = obj;
        this._clearRebootTimer();
        if (obj?.type && obj.type !== 'game_start') {
            this._silenceLimitMs = SILENCE_LIMIT_MS;
        }
    }

    setLinkState(state) {
        const prev = this.link.state;
        dbg('device', `link state ${prev} → ${state}`);
        this.link.state = state;
        // Only `waiting` re-asks the Box to identify itself; every other state
        // either already has an answer or has given up, so stop nudging.
        if (state === 'waiting') {
            if (prev !== 'waiting') this.link.waitingSince = Date.now();
            this._armIdentifyNudge();
        } else {
            this._clearIdentifyNudge();
        }
        if (state === 'idle' || state === 'lost') {
            this.link.boxMode = null;
            this.link.deviceInfo = null;
            this.link.detail = null;
            this.link.lastMsgAt = 0;
            this.link.waitingSince = 0;
            this._silenceLimitMs = SILENCE_LIMIT_MS;
            this._clearRebootTimer();
        }
        if (state === 'idle') {
            // A fresh cycle (explicit disconnect, or the teacher cancelling
            // out of a reboot/reconnect wait) earns a full new attempt
            // budget next time -- 'lost' does NOT reset this: it's usually
            // mid-drop, on the way to 'rebooting', and resetting there would
            // make the attempt cap meaningless.
            this._reconnectAttempts = 0;
        }
        if (state === 'live') {
            this._clearRebootTimer();
            this._reconnectAttempts = 0;
            if (this.pendingSendAfterConnect) {
                this.pendingSendAfterConnect = false;
                dbg('app', 'link live — resuming deferred send confirm');
                toast('Connected — continuing to send…');
                this.showSendConfirm();
            }
        }
        this.paintLink();
    }

    paintLink() {
        setConnectionBadge({ ...this.link, kind: this.device.kind });
        // Use as-is is a send shortcut — only useful when a device is live.
        const useBtn = document.getElementById('btn-use-as-is');
        if (useBtn) {
            const live = this.link.state === 'live';
            useBtn.disabled = !live;
            if (!live) {
                useBtn.title = `Connect to the ${this.deviceShort()} first`;
            } else {
                const name = this.currentExample?.name || 'this game';
                useBtn.title = `Send ${name} to the ${this.deviceShort()}`;
            }
        }
    }

    _startWatchdog() {
        if (this._watchdogTimer) return;
        this._watchdogTimer = setInterval(() => this._watchdogTick(), WATCHDOG_TICK_MS);
    }

    _watchdogTick() {
        const s = this.link.state;
        if (s === 'sending' || s === 'rebooting' || s === 'opening' || s === 'idle'
            || s === 'lost' || s === 'no-answer') return;
        // `waiting` is checked against when we started waiting, NOT against
        // lastMsgAt — before first contact lastMsgAt is 0, so keying off it
        // here is what let this state hang indefinitely.
        if (s === 'waiting') {
            const waited = Date.now() - (this.link.waitingSince || Date.now());
            const limit = this.device.kind === 'wand' ? WAITING_LIMIT_WAND_MS : WAITING_LIMIT_MS;
            if (waited > limit) {
                dbgWarn('device', `no reply ${waited}ms after port open → no-answer`);
                this.setLinkState('no-answer');
                // Deliberately does not assert the Box is broken: connecting
                // during a serve can block its main loop for ~30s
                // (SOCK_REPLY_TIMEOUT_S), which looks identical from here.
                // The state is not terminal — any inbound message promotes
                // straight back to live — so the copy suggests, not accuses.
                toast(`The ${this.deviceShort()} isn't answering. If it stays quiet, try Restart the ${this.deviceShort()}.`, true);
            }
            return;
        }
        if (!this.link.lastMsgAt) return;
        const age = Date.now() - this.link.lastMsgAt;
        if (s === 'live' || s === 'stuck') {
            if (age > this._silenceLimitMs) {
                dbgWarn('device', `watchdog silence ${age}ms > ${this._silenceLimitMs}`);
                this.setLinkState('lost');
                toast(`Lost the ${this.deviceShort()} — check the cable.`, true);
                this.device.disconnect().catch(() => {});
            }
        }
    }

    /** Re-ask the Box to identify itself while waiting. Harmless to repeat:
     *  do_identify() just replies, and each send carries a fresh id.
     *  No-op for a wand: it has no command listener at all (see
     *  wandDeviceLink.js), so there is nothing to nudge -- its identity is
     *  volunteered once at boot and heartbeat is what proves it is alive. */
    _armIdentifyNudge() {
        if (this._identifyNudgeTimer) return;
        if (this.device.kind === 'wand') return;
        this._identifyNudgeTimer = setInterval(() => {
            if (this.link.state !== 'waiting') {
                this._clearIdentifyNudge();
                return;
            }
            this.device.nudgeIdentify().catch(() => {});
        }, IDENTIFY_NUDGE_MS);
    }

    _clearIdentifyNudge() {
        if (this._identifyNudgeTimer) {
            clearInterval(this._identifyNudgeTimer);
            this._identifyNudgeTimer = null;
        }
    }

    _armRebootTimer() {
        this._clearRebootTimer();
        this._rebootTimer = setTimeout(() => {
            if (this.link.state === 'rebooting') {
                dbgWarn('device', 'reboot timer expired → lost');
                this.setLinkState('lost');
                toast(`The ${this.deviceShort()} did not come back — check the cable.`, true);
            }
        }, REBOOT_LIMIT_MS);
    }

    _clearRebootTimer() {
        if (this._rebootTimer) {
            clearTimeout(this._rebootTimer);
            this._rebootTimer = null;
        }
    }

    onSerialDrop() {
        // Legacy path — real unplug goes through adapter onClose → 'close'.
        dbgWarn('device', 'onSerialDrop (navigator.serial) — delegating to lost');
        this.device.disconnect().catch(() => {});
        this.setLinkState('lost');
        toast(`${this.deviceProduct()} disconnected — check the cable.`, true);
    }

    bindEvents() {
        document.getElementById('btn-scratch').addEventListener('click', () => this.startNewGame());
        document.getElementById('btn-new-game').addEventListener('click', () => this.startNewGame());
        document.getElementById('btn-gallery').addEventListener('click', () => this.goExamples());
        document.getElementById('btn-saved').addEventListener('click', () => this.goSaved());
        document.getElementById('gallery-search').addEventListener('input', () => this.renderGallery());
        document.getElementById('btn-station-catalog')
            .addEventListener('click', () => this.sendCatalogToStation());
        document.getElementById('btn-detail-back').addEventListener('click', () => this.goExamples());
        document.getElementById('btn-remix').addEventListener('click', () => this.remixCurrentExample());
        document.getElementById('btn-use-as-is').addEventListener('click', () => this.useExampleAsIs());
        document.getElementById('btn-send').addEventListener('click', () => this.onSend());
        document.getElementById('btn-guided').addEventListener('click', () => this.startGuidedMode());
        document.getElementById('btn-interview').addEventListener('click', () => this.startInterview());
        document.getElementById('btn-show-code').addEventListener('click', () => {
            document.getElementById('code-drawer').classList.remove('hidden');
        });
        document.getElementById('btn-close-code').addEventListener('click', () => {
            document.getElementById('code-drawer').classList.add('hidden');
        });
        document.getElementById('btn-send-box').addEventListener('click', () => this.startSendFlow());
        document.getElementById('btn-prev').addEventListener('click', () => {
            onPrevVersion(addMsg);
            this.updatePreview();
        });
        document.getElementById('btn-next').addEventListener('click', () => {
            onNextVersion(addMsg);
            this.updatePreview();
        });
        document.getElementById('btn-connect-box').addEventListener('click', () => this.onConnect('box'));
        document.getElementById('btn-connect-wand').addEventListener('click', () => this.onConnect('wand'));
        document.getElementById('btn-connect-cancel').addEventListener('click', () => {
            this.pendingSendAfterConnect = false;
            hideOverlay('connect-overlay');
            showConnectToast(false);
        });
        // Kill switch: same effect as Cancel, but never disabled/hidden by
        // any busy state -- always a way out of this overlay.
        document.getElementById('btn-connect-close-x')?.addEventListener('click', () => {
            this.pendingSendAfterConnect = false;
            hideOverlay('connect-overlay');
            showConnectToast(false);
        });
        document.querySelectorAll('.btn-connect-header').forEach((btn) => {
            btn.addEventListener('click', () => this.toggleConnect());
        });
        document.querySelectorAll('.btn-restart-box').forEach((btn) => {
            btn.addEventListener('click', () => this.onRestartBox());
        });
        document.querySelectorAll('.mode-pill').forEach((btn) => {
            btn.addEventListener('click', () => {
                if (btn.disabled) return;
                this.openBoxLibrary();
            });
        });
        document.querySelectorAll('.app-tab').forEach((btn) => {
            btn.addEventListener('click', () => this.onNavTab(btn.dataset.nav));
        });
        document.getElementById('btn-send-confirm').addEventListener('click', () => this.confirmSend());
        document.getElementById('btn-send-cancel').addEventListener('click', () => hideOverlay('send-confirm-overlay'));
        // Editing the name after a duplicate-name warning armed the
        // "Replace existing game" second click (see confirmSend()) cancels
        // that arming -- otherwise a corrected, non-duplicate name would
        // still show "Replace existing game" on the button.
        document.getElementById('send-game-name')?.addEventListener('input', () => {
            if (!this._pendingReplaceSlug) return;
            this._pendingReplaceSlug = null;
            document.getElementById('btn-send-confirm').textContent = 'Send';
            const errEl = document.getElementById('send-name-error');
            if (errEl) errEl.textContent = '';
        });
        document.getElementById('btn-send-done').addEventListener('click', () => this.finishSend());
        document.getElementById('btn-send-another-wand')?.addEventListener('click', () => this.installOnAnotherWand());
        // Kill switch: unlike Cancel (hidden by setSendBusy(true) while a
        // send is in flight -- there is no safe abort mid-write, see
        // setSendBusy()'s docstring), this button is never hidden or
        // disabled. On the form it does not try to cancel the upload --
        // that keeps running in the background and will resolve into the
        // usual toast/link-state path -- it only frees the UI so the
        // teacher isn't stuck looking at "Sending..." if something never
        // resolves. On the success screen it's equivalent to Done.
        document.getElementById('btn-send-close-x')?.addEventListener('click', () => {
            const inSuccess = !document.getElementById('send-confirm-success').classList.contains('hidden');
            if (inSuccess) {
                this.finishSend();
                return;
            }
            this.setSendBusy(false);
            document.getElementById('send-progress-wrap').classList.add('hidden');
            hideOverlay('send-confirm-overlay');
        });
        document.getElementById('btn-box-lib-close')?.addEventListener('click', () => hideOverlay('box-library-overlay'));
        document.getElementById('btn-box-lib-refresh')?.addEventListener('click', () => this.refreshBoxLibrary());
        document.getElementById('btn-box-lib-clear')?.addEventListener('click', () => this.clearBoxLibrary());
        document.getElementById('btn-box-stats-reset')?.addEventListener('click', () => this.resetBoxStats());

        document.getElementById('btn-mode-gear').addEventListener('click', () => {
            toggleUiMode();
            this.closeMoreMenu();
        });
        document.getElementById('btn-dev-mode').addEventListener('click', () => {
            toggleDevMode();
            this.closeMoreMenu();
        });
        document.querySelectorAll('.device-tab').forEach((el) => {
            el.addEventListener('click', () => this.selectRole(el.dataset.role));
        });
        document.getElementById('btn-save-game').addEventListener('click', () => this.onSaveGame());

        // The brand replaced the Home tab on every screen that had one, so it
        // routes through onNavTab: that keeps the unsaved-work guard on the
        // way out of the workspace, which a bare showView('splash') skips.
        document.querySelectorAll('.brand-home').forEach((btn) => {
            btn.addEventListener('click', () => this.onNavTab('home'));
        });

        const moreBtn = document.getElementById('btn-more');
        moreBtn?.addEventListener('click', () => {
            const panel = document.getElementById('more-panel');
            const open = panel.classList.toggle('hidden') === false;
            moreBtn.setAttribute('aria-expanded', String(open));
        });
        // Dismiss on a click anywhere outside the menu. Tested by what was
        // clicked rather than by stopPropagation, so it cannot race the
        // button's own toggle.
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.more-menu')) this.closeMoreMenu();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.closeMoreMenu();
        });

        document.getElementById('btn-icons-view')?.addEventListener('click', () => {
            if (this.iconsViewOpen()) this.closeIconsView();
            else this.openIconsView();
        });
        this.bindIconToolbar();

        this.bindGameNameEditor();
        document.getElementById('btn-download').addEventListener('click', () => onDownload(addMsg));

        const userInput = document.getElementById('user-input');
        userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.onSend();
            }
        });
        userInput.addEventListener('input', () => {
            userInput.style.height = 'auto';
            userInput.style.height = Math.min(userInput.scrollHeight, 120) + 'px';
        });
    }

    onNavTab(nav) {
        if (nav === 'home') {
            // From workspace Home tab → splash (with unsaved confirm). From
            // gallery/detail, Home still means splash.
            const ws = document.getElementById('view-workspace');
            if (ws && !ws.classList.contains('hidden')) {
                this.goHome();
            } else {
                showView('splash');
            }
            return;
        }
        if (nav === 'saved') this.goSaved();
        else if (nav === 'examples') this.goExamples();
    }

    goSaved() {
        this.galleryMode = 'saved';
        document.body.dataset.galleryMode = 'saved';
        showView('gallery');
        this.renderGallery();
        syncNavTabs('gallery');
    }

    goExamples() {
        this.galleryMode = 'examples';
        document.body.dataset.galleryMode = 'examples';
        showView('gallery');
        this.renderGallery();
        syncNavTabs('gallery');
    }

    async goHome() {
        const action = await this.confirmUnsavedWork();
        if (action === 'cancel') return;
        this._sim?.stop();
        showView('splash');
    }

    /** "New game": the button near Save, and the splash "Start from
     * scratch" tile -- both routed through the same unsaved-work check and
     * the same clearWorkspace(), so there's exactly one way this happens
     * rather than two that can drift. */
    async startNewGame() {
        const action = await this.confirmUnsavedWork();
        if (action === 'cancel') return;
        this.resetGameContext();
        this.clearWorkspace();
        this.openWorkspace();
    }

    /**
     * Save/Discard/Cancel for leaving a dirty workspace, replacing
     * window.confirm(). Resolves 'continue' (proceed -- saved first if the
     * teacher chose Save) or 'cancel' (stay put). No-ops straight to
     * 'continue' when there's nothing to lose.
     */
    confirmUnsavedWork() {
        // this.dirty alone, not getVersionCount()/chatHistory.length -- those
        // stay > 0 for the rest of the session once you've done anything at
        // all, save or no save, so ORing them in meant this prompted every
        // time regardless of whether there was anything actually unsaved
        // (e.g. right after clicking Save, which does clear this.dirty).
        if (!this.dirty) return Promise.resolve('continue');
        return new Promise((resolve) => {
            const saveBtn = document.getElementById('btn-unsaved-save');
            const discardBtn = document.getElementById('btn-unsaved-discard');
            const cancelBtn = document.getElementById('btn-unsaved-cancel');
            const xBtn = document.getElementById('btn-unsaved-close-x');
            const cleanup = () => {
                saveBtn.removeEventListener('click', onSave);
                discardBtn.removeEventListener('click', onDiscard);
                cancelBtn.removeEventListener('click', onCancel);
                xBtn.removeEventListener('click', onCancel);
            };
            const onSave = () => { cleanup(); hideOverlay('unsaved-overlay'); this.onSaveGame(); resolve('continue'); };
            const onDiscard = () => { cleanup(); hideOverlay('unsaved-overlay'); resolve('continue'); };
            const onCancel = () => { cleanup(); hideOverlay('unsaved-overlay'); resolve('cancel'); };
            saveBtn.addEventListener('click', onSave);
            discardBtn.addEventListener('click', onDiscard);
            cancelBtn.addEventListener('click', onCancel);
            xBtn.addEventListener('click', onCancel);
            showOverlay('unsaved-overlay');
        });
    }

    /**
     * Generic yes/no confirm, replacing window.confirm() for destructive
     * device actions. Resolves true/false.
     */
    confirmDialog({ title = 'Are you sure?', message = '', okLabel = 'Confirm' } = {}) {
        return new Promise((resolve) => {
            document.getElementById('confirm-title').textContent = title;
            document.getElementById('confirm-message').textContent = message;
            const okBtn = document.getElementById('btn-confirm-ok');
            okBtn.textContent = okLabel;
            const cancelBtn = document.getElementById('btn-confirm-cancel');
            const xBtn = document.getElementById('btn-confirm-close-x');
            const cleanup = () => {
                okBtn.removeEventListener('click', onOk);
                cancelBtn.removeEventListener('click', onCancel);
                xBtn.removeEventListener('click', onCancel);
            };
            const onOk = () => { cleanup(); hideOverlay('confirm-overlay'); resolve(true); };
            const onCancel = () => { cleanup(); hideOverlay('confirm-overlay'); resolve(false); };
            okBtn.addEventListener('click', onOk);
            cancelBtn.addEventListener('click', onCancel);
            xBtn.addEventListener('click', onCancel);
            showOverlay('confirm-overlay');
        });
    }

    /**
     * Clear the workspace's visible state: chat transcript, editor code +
     * version history, and the sim. resetGameContext() alone never touched
     * any of this (it only clears bookkeeping like gameName/declaredTags),
     * which is why "Start from scratch" used to leave the old code and
     * chat sitting there even though it looked like a fresh session.
     */
    clearWorkspace() {
        document.getElementById('chat-box').innerHTML = '';
        document.getElementById('user-input').value = '';
        resetEditor();
        this.retiredRoleCode = {};
        this.syncRoleRail();
        this.dirty = false;
        this._sim?.stop();
        this._simLastSource = null;
        this._simLastDisplay = null;
        this._simLastSettings = null;
        this.updatePreview();
    }

    onSaveGame() {
        // `code` stays the wand file (library.js shape); a display-only game
        // saves an empty one and its display code under roleCode.icon.
        const wand = getCode(DEFAULT_ROLE);
        const code = isRunnableCode(wand) ? wand : '';
        if (!primaryRoleCode()) {
            toast('Nothing to save yet — generate or load some code first.', true);
            return;
        }
        const roleCode = {};
        for (const info of ROLE_TABLE) {
            if (info.key === DEFAULT_ROLE) continue;
            const c = getCode(info.key).trim();
            if (c) roleCode[info.key] = c;
        }
        for (const [key, c] of Object.entries(this.retiredRoleCode || {})) {
            if (!(key in roleCode)) roleCode[key] = c;
        }
        const entry = saveGame({
            name: this.gameName,
            desc: this.gameDesc,
            code,
            roleCode,
            requiredTags: this.requiredTags,
            hardware: this.hardware,
            chatHistory: this.chatHistory.slice(),
            // Only what this game edited. Anything it merely uses still
            // resolves to the shipped icon when it is reopened.
            icons: getGameIcons(),
            simSettings: this.simSettings,
        });
        this.dirty = false;
        toast(`Saved “${entry.name}”`);
        dbg('app', `saved game ${entry.id}`);
    }

    setupGallery() {
        const chips = document.getElementById('gallery-chips');
        CATEGORIES.forEach((c) => {
            const el = document.createElement('button');
            el.type = 'button';
            el.className = 'chip' + (c.id === 'all' ? ' active' : '');
            el.innerHTML = (c.icon ? iconSvg(c.icon, { size: 14 }) + ' ' : '') + escapeHtml(c.label);
            el.dataset.id = c.id;
            el.addEventListener('click', () => {
                this.galleryFilter = c.id;
                chips.querySelectorAll('.chip').forEach((x) => x.classList.toggle('active', x.dataset.id === c.id));
                this.renderGallery();
            });
            chips.appendChild(el);
        });
    }

    renderGallery() {
        const title = document.getElementById('gallery-title');
        const chips = document.getElementById('gallery-chips');
        const q = document.getElementById('gallery-search').value.toLowerCase();
        const grid = document.getElementById('gallery-grid');
        grid.innerHTML = '';
        document.body.dataset.galleryMode = this.galleryMode;
        syncNavTabs('gallery');

        document.getElementById('btn-station-catalog')
            .classList.toggle('hidden', this.galleryMode !== 'saved');
        document.getElementById('station-catalog-status')
            .classList.toggle('hidden', this.galleryMode !== 'saved');
        if (this.galleryMode === 'saved') {
            title.textContent = 'My saved games';
            chips.classList.add('hidden');
            const saved = loadSavedGames().filter((g) => {
                if (!q) return true;
                return (g.name || '').toLowerCase().includes(q) || (g.desc || '').toLowerCase().includes(q);
            });
            if (saved.length === 0) {
                const empty = document.createElement('p');
                empty.style.cssText = 'grid-column:1/-1;color:#8b859a;padding:24px;';
                empty.textContent = 'No saved games yet — open a workspace and tap Save.';
                grid.appendChild(empty);
                return;
            }
            saved.forEach((g) => {
                const card = document.createElement('div');
                card.className = 'example-card saved-card';
                card.dataset.id = g.id;
                const when = relativeTime(g.updatedAt);
                card.innerHTML =
                    `<div class="example-thumb">${iconSvg('wand', { size: 26, strokeWidth: 1.5 })}</div>` +
                    `<div class="card-body" data-card-body>` +
                    `<h3>${escapeHtml(g.name)}</h3>` +
                    `<p>${escapeHtml(when)}</p>` +
                    `<div class="card-actions">` +
                    `<button type="button" class="card-action-btn" data-rename title="Rename">${iconSvg('pencil', { size: 14 })}</button>` +
                    `<button type="button" class="card-action-btn" data-delete title="Delete">${iconSvg('trash', { size: 14 })}</button>` +
                    `</div></div>`;
                card.addEventListener('click', (e) => {
                    if (e.target.closest('[data-rename],[data-delete],[data-confirm-del],[data-cancel-del],.card-rename-row')) return;
                    this.openSavedGame(g.id);
                });
                card.querySelector('[data-rename]')?.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.startRenameSaved(card, g);
                });
                card.querySelector('[data-delete]')?.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.askDeleteSaved(card, g);
                });
                grid.appendChild(card);
            });
            return;
        }

        title.textContent = 'Example games';
        chips.classList.remove('hidden');
        EXAMPLES.filter((ex) => {
            if (this.galleryFilter !== 'all' && ex.category !== this.galleryFilter) return false;
            if (q && !ex.name.toLowerCase().includes(q)) return false;
            return true;
        }).forEach((ex) => {
            const card = document.createElement('div');
            card.className = 'example-card';
            card.dataset.id = ex.id;
            card.innerHTML =
                `<div class="example-thumb">${iconSvg(exampleIcon(ex), { size: 26, strokeWidth: 1.5 })}</div>` +
                `<h3>${escapeHtml(ex.name)}</h3>` +
                `<p>${escapeHtml(ex.description)}</p>` +
                (ex.tagNote ? `<div class="tag-badge">${escapeHtml(ex.tagNote)}</div>` : '');
            card.addEventListener('click', () => this.openDetail(ex.id));
            grid.appendChild(card);
        });
    }

    startRenameSaved(card, g) {
        const body = card.querySelector('[data-card-body]');
        if (!body) return;
        body.innerHTML =
            `<div class="card-rename-row">` +
            `<input type="text" value="${escapeHtml(g.name)}" maxlength="48" />` +
            `<button type="button" class="card-rename-ok" title="Save name">${iconSvg('circle-check', { size: 16 })}</button>` +
            `<button type="button" class="card-rename-cancel" title="Cancel">${iconSvg('close', { size: 16 })}</button>` +
            `</div>`;
        const input = body.querySelector('input');
        input.focus();
        input.select();
        body.querySelector('.card-rename-ok').addEventListener('click', (e) => {
            e.stopPropagation();
            renameSavedGame(g.id, input.value);
            this.renderGallery();
        });
        body.querySelector('.card-rename-cancel').addEventListener('click', (e) => {
            e.stopPropagation();
            this.renderGallery();
        });
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                renameSavedGame(g.id, input.value);
                this.renderGallery();
            } else if (e.key === 'Escape') {
                this.renderGallery();
            }
        });
    }

    askDeleteSaved(card, g) {
        const actions = card.querySelector('.card-actions');
        if (!actions) return;
        actions.innerHTML =
            `<button type="button" class="card-action-btn danger" data-confirm-del>Delete?</button>` +
            `<button type="button" class="card-action-btn" data-cancel-del title="Cancel">${iconSvg('close', { size: 14 })}</button>`;
        actions.querySelector('[data-confirm-del]').addEventListener('click', (e) => {
            e.stopPropagation();
            deleteSavedGame(g.id);
            toast(`Deleted “${g.name}”`);
            this.renderGallery();
        });
        actions.querySelector('[data-cancel-del]').addEventListener('click', (e) => {
            e.stopPropagation();
            this.renderGallery();
        });
    }

    openSavedGame(id) {
        const g = findSavedGame(id);
        if (!g) {
            toast('Could not find that saved game.', true);
            return;
        }
        this.gameName = g.name;
        // DIAGNOSTIC (temporary -- name-field investigation, see chat).
        dbg('app', `openSavedGame(${id}): stored name=${JSON.stringify(g.name)} -> this.gameName=${JSON.stringify(this.gameName)}`);
        this.gameDesc = g.desc || '';
        this.declaredTags = g.hardware?.declaredTags || null;
        this.simSettings = g.simSettings || null;
        this.hardware = g.hardware || buildHardwareReqs({ gameName: g.name });
        this.chatHistory = Array.isArray(g.chatHistory) ? g.chatHistory.slice() : [];
        // The pictures this game was saved with. A game saved before icons
        // were per-game has none, and falls back to the shared starter
        // palette and the shipped defaults -- which is what it was drawing
        // from at the time.
        setGameIcons(g.icons || {});
        showView('workspace');
        const box = document.getElementById('chat-box');
        box.innerHTML = '';
        addMsg(`Loaded saved game “${g.name}”.`, 'system');
        clearAllRoles();
        // Replay the conversation, not just a one-line note -- the data was
        // already being saved and restored into this.chatHistory (for the
        // API's context) but never shown again, so a reopened game looked
        // like a blank chat despite the model still "remembering" it. Code
        // blocks in old assistant turns were already replaced with a
        // "[code: N lines, sent to editor]" placeholder when saved (see
        // trimForHistory() in chat.js), which reads fine here too: the
        // actual current code is loaded into the editor below regardless.
        this.chatHistory.forEach((turn) => {
            addMsg(turn.content, turn.role === 'assistant' ? 'bot' : 'user');
        });
        if (g.code) {
            setCode(g.code, DEFAULT_ROLE);
            saveVersion(g.code, 'Loaded from library', DEFAULT_ROLE);
        }
        // g.iconCode predates roleCode and is read as roleCode.icon's
        // fallback (see saveGame() in library.js); either way it ends up
        // set on roleCode by the time an entry reaches here.
        const roleCode = { ...(g.roleCode || {}) };
        if (g.iconCode && !roleCode.icon) roleCode.icon = g.iconCode;
        for (const info of ROLE_TABLE) {
            if (info.key === DEFAULT_ROLE) continue;
            const code = roleCode[info.key];
            if (!code) continue;
            setCode(code, info.key);
            saveVersion(code, 'Loaded from library', info.key);
        }
        this.retainRetiredRoleCode(g.name, roleCode);
        this.syncRoleRail();
        this.dirty = false;
        this.updatePreview({ forcePlay: true });
    }

    /**
     * A saved game can carry code for a role that no longer exists (the
     * retired Splat Companion role, `roleCode.splat`). That code is kept
     * read-only: shown in the chat, never sent, and written back unchanged
     * by onSaveGame so it is not dropped.
     */
    retainRetiredRoleCode(gameName, roleCode) {
        this.retiredRoleCode = {};
        const known = new Set(ROLE_TABLE.map((r) => r.key));
        for (const [key, code] of Object.entries(roleCode)) {
            if (known.has(key) || !code) continue;
            this.retiredRoleCode[key] = code;
            const label = key === 'splat' ? 'Splat Companion' : key;
            const div = addMsg(`“${gameName}” has ${label} code. That device is retired, so this code `
                + `will not be sent; it is kept read-only with the saved game. `
                + `Splats are now driven from the wand game.`, 'system');
            div.classList.add('retired-role-warning');
            const det = document.createElement('details');
            const sum = document.createElement('summary');
            sum.textContent = `${label} code (read-only)`;
            const pre = document.createElement('pre');
            pre.textContent = code;
            det.append(sum, pre);
            div.appendChild(det);
            dbgWarn('app', `saved game "${gameName}" has retired role code: ${key}`);
        }
    }

    /**
     * Connect the NFC Station on its own serial port (the Box/Dial link, if
     * any, is left alone), push the saved-games catalog, then close the port.
     */
    async sendCatalogToStation() {
        const btn = document.getElementById('btn-station-catalog');
        const status = document.getElementById('station-catalog-status');
        const show = (text) => { status.textContent = text; status.classList.remove('hidden'); };
        const games = loadSavedGames();
        if (!games.length) {
            show('No saved games to send yet.');
            return;
        }
        const adapter = new SerialAdapter();
        let link = null;
        btn.disabled = true;
        try {
            show('Pick the NFC Station in the port list…');
            await adapter.connect();
            link = new NfcStationLink(adapter);
            link.start();
            show(`Sending ${games.length} game${games.length === 1 ? '' : 's'}…`);
            const r = await link.pushCatalog(games);
            if (r.ok) {
                show(`NFC Station has the games list (${r.groups ?? games.length} groups).`);
                toast('Games sent to the NFC Station.');
            } else {
                show(`NFC Station refused the list: ${r.code}${r.msg ? ` (${r.msg})` : ''}`);
                toast('The NFC Station refused the games list.', true);
            }
            dbg('app', 'catalog.set result', r);
        } catch (e) {
            dbgError('app', `NFC Station catalog push failed: ${e.message}`, e);
            show(`Could not send to the NFC Station: ${e.message}`);
            toast('Could not send to the NFC Station.', true);
        } finally {
            link?.stop();
            if (adapter.isConnected()) {
                await adapter.disconnect().catch((e) => dbgWarn('app', `station disconnect: ${e.message}`));
            }
            btn.disabled = false;
        }
    }

    openDetail(id) {
        const ex = findExample(id);
        if (!ex) {
            dbgWarn('app', `openDetail("${id}") — no matching example found`);
            return;
        }
        dbg('app', `openDetail("${id}")`, ex);
        this.currentExample = ex;
        document.getElementById('detail-title').textContent = ex.name;
        document.getElementById('detail-desc').textContent = ex.description;
        const note = document.getElementById('detail-tag-note');
        if (ex.tagNote) {
            note.textContent = `needs ${ex.tags.length} NFC tags — ${ex.tagNote.toLowerCase()}`;
            note.classList.remove('hidden');
        } else {
            note.classList.add('hidden');
        }
        this.mountDetailSim(ex);
        showView('detail');
        this.paintLink();
    }

    /** Show the selected example actually running, in place of the old
     * static "preview animation" placeholder. A fresh <sim-room> is built
     * per visit and torn down on the way out (see watchDetailView) rather
     * than kept alive hidden — each instance boots its own Pyodide, and a
     * gallery browse would otherwise leave one running per example opened. */
    mountDetailSim(ex) {
        const host = document.getElementById('detail-preview');
        if (!host) return;
        this.teardownDetailSim();
        const empty = document.getElementById('detail-preview-empty');
        if (empty) {
            empty.textContent = 'loading the practice window…';
            empty.classList.remove('hidden');
        }
        const token = ++this._detailSimToken;
        dbg('app', `mountDetailSim("${ex.id}") — loading sim-room module`);
        import('../../../Simulator/sim-room.js')
            .then(() => {
                // The teacher moved on while Pyodide's module was loading —
                // don't mount a sim into a panel nobody is looking at.
                if (token !== this._detailSimToken) return;
                // <sim-room>: the wand plus whatever the game uses beside it
                // (Splats and peer wands for a party game, the icon display
                // for a two-device one).
                const sim = document.createElement('sim-room');
                sim.id = 'detail-sim';
                sim.toggleAttribute('advanced', loadUiMode() === 'advanced');
                // Look-what-it-does preview — already playing when the
                // teacher gets here.
                sim.autostart = true;
                // Load the real game by name rather than pushing source:
                // Pyodide reads the vendored .py it already has, and
                // get_capabilities() finds its _TEACHER_TABLE entry instead
                // of falling back to "show everything" — so no profile is
                // needed here, unlike a generated game.
                sim.profile = null;
                sim.source = null;
                sim.game = ex.vendorGame;
                host.appendChild(sim);
                host.classList.add('has-sim');
                this._detailSim = sim;
                if (empty) empty.classList.add('hidden');
            })
            .catch((err) => {
                dbgError('sim', 'failed to load sim-room module for the detail preview', err);
                if (token !== this._detailSimToken || !empty) return;
                empty.textContent = "The practice window isn't available right now — you can still remix or send this game.";
            });
    }

    teardownDetailSim() {
        this._detailSimToken = (this._detailSimToken || 0) + 1;
        // remove() fires disconnectedCallback, which stops the running game
        // and disposes its audio; dropping the reference lets Pyodide go.
        this._detailSim?.remove();
        this._detailSim = null;
        document.getElementById('detail-preview')?.classList.remove('has-sim');
    }

    /** Every exit from the detail screen (back, home, remix, use-as-is,
     * deep-link) goes through showView() toggling .hidden, so watch that
     * one class rather than hanging a teardown off each button. */
    watchDetailView() {
        const panel = document.getElementById('view-detail');
        if (!panel) return;
        new MutationObserver(() => {
            if (panel.classList.contains('hidden')) this.teardownDetailSim();
        }).observe(panel, { attributes: true, attributeFilter: ['class'] });
    }

    /**
     * One-tap follow-ups from a reply's [CHOICES: ...] marker. Tapping one
     * sends it as the teacher's next message.
     */
    renderChoiceChips(choices) {
        const box = document.getElementById('chat-box');
        box.querySelectorAll('.choice-chips').forEach(el => el.remove());
        const wrap = document.createElement('div');
        wrap.className = 'choice-chips';
        for (const text of choices) {
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'starter-chip';
            chip.textContent = text;
            chip.addEventListener('click', () => {
                if (this.isGenerating) return;
                wrap.remove();
                document.getElementById('user-input').value = text;
                this.onSend();
            });
            wrap.appendChild(chip);
        }
        box.appendChild(wrap);
        box.scrollTop = box.scrollHeight;
    }

    /**
     * Guided mode: the GUIDED_STEPS questions as tap-to-answer cards in the
     * chat, answered instantly in the app; the answers are then sent as one
     * request (starterIdeas.js guidedPrompt).
     */
    startGuidedMode() {
        if (this.isGenerating) return;
        const box = document.getElementById('chat-box');
        box.querySelector('.starter-chips')?.remove();
        box.querySelectorAll('.guided-card, .choice-chips').forEach(el => el.remove());
        const answers = [];
        const card = document.createElement('div');
        card.className = 'guided-card';
        box.appendChild(card);
        const showStep = (i) => {
            if (i === GUIDED_STEPS.length) {
                card.remove();
                document.getElementById('user-input').value = guidedPrompt(answers);
                this.onSend();
                return;
            }
            const step = GUIDED_STEPS[i];
            card.innerHTML = '';
            const q = document.createElement('div');
            q.className = 'msg system';
            q.textContent = `${step.question} (${i + 1} of ${GUIDED_STEPS.length})`;
            card.appendChild(q);
            const row = document.createElement('div');
            row.className = 'choice-chips';
            for (const opt of step.options) {
                const chip = document.createElement('button');
                chip.type = 'button';
                chip.className = 'starter-chip';
                chip.textContent = opt.label;
                chip.addEventListener('click', () => { answers[i] = opt; showStep(i + 1); });
                row.appendChild(chip);
            }
            card.appendChild(row);
            box.scrollTop = box.scrollHeight;
        };
        showStep(0);
    }

    /**
     * Interview mode: the model asks one short question per turn, starting
     * with INTERVIEW_FIRST_QUESTION (asked here, without a model call), until
     * it replies with a [GAME_BRIEF] block or INTERVIEW_MAX_QUESTIONS have
     * been asked. The brief is then offered as a normal game request.
     * The interview transcript is kept apart from chatHistory.
     */
    startInterview() {
        if (this.isGenerating) return;
        const box = document.getElementById('chat-box');
        box.querySelector('.starter-chips')?.remove();
        box.querySelectorAll('.guided-card, .choice-chips').forEach(el => el.remove());
        this.interview = { turns: [], asked: 1 };
        dbg('chat', 'interview started');
        addMsg(INTERVIEW_FIRST_QUESTION, 'bot');
        document.getElementById('user-input').focus();
    }

    /** The teacher's answer to the current interview question. */
    async answerInterview(answer, finish = false) {
        this.interview.turns.push({ role: 'user', content: answer });
        await this.callInterviewer(finish);
    }

    /** Ask the model for the next interview question, or for the brief. */
    async callInterviewer(finish) {
        const iv = this.interview;
        const apiKey = this.resolveApiKey();
        if (!apiKey) { iv.turns.pop(); return; }
        const files = getKnowledgeFiles();
        addThinkingMsg();
        this.isGenerating = true;
        try {
            const body = JSON.stringify(buildRequestBody({
                system: buildInterviewSystemBlocks({
                    knowledge: knowledgeText(files, listSplatActions()),
                    interview: files[INTERVIEW_KNOWLEDGE],
                    asked: iv.asked,
                    finish,
                }),
                history: interviewMessages(iv.turns),
                stream: false,
                windowed: false,
            }));
            dbg('chat', `interview POST — ${iv.asked} asked, finish=${finish}`);
            const resp = await fetch('https://api.anthropic.com/v1/messages', {
                method: 'POST',
                headers: requestHeaders(apiKey),
                body,
            });
            const data = await resp.json().catch(() => ({}));
            removeTyping();
            if (!resp.ok) {
                const errMsg = data?.error?.message ?? `Could not reach the AI (${resp.status}). Check your network.`;
                dbgError('chat', `interview API error (${resp.status}): ${errMsg}`, data);
                addMsg(errMsg, 'system');
                iv.turns.pop();
                return;
            }
            if (data.stop_reason === 'refusal') {
                dbgWarn('chat', 'interview refusal', data.stop_details);
                addMsg('The AI declined to answer that. Try rewording it.', 'system');
                iv.turns.pop();
                return;
            }
            const raw = (data.content || []).filter(b => b.type === 'text').map(b => b.text).join('');
            const brief = parseGameBrief(raw);
            if (brief) {
                this.interview = null;
                dbg('chat', `interview finished after ${iv.asked} question(s)`, { brief });
                const lead = stripAllMarkers(stripGameBrief(raw));
                if (lead) addMsg(lead, 'bot');
                addMsg(brief, 'bot');
                this.renderBriefChips(brief);
                return;
            }
            iv.turns.push({ role: 'assistant', content: raw });
            if (finish || iv.asked >= INTERVIEW_MAX_QUESTIONS) {
                // The status block told the model to write the brief.
                dbgError('chat', 'interview: last turn returned no [GAME_BRIEF]', raw);
                addMsg('The interviewer did not write a game summary. Tap “Make my game now” to try again.', 'system');
                iv.turns.pop();
                this.renderInterviewChips([]);
                return;
            }
            iv.asked++;
            addMsg(stripAllMarkers(raw), 'bot');
            // The first two questions are answered in the teacher's own
            // words (interview.md); choices start at question 3.
            this.renderInterviewChips(iv.asked > 2 ? parseChoices(raw) || [] : []);
        } catch (e) {
            removeTyping();
            dbgError('chat', `interview network/fetch error: ${e.message}`, e);
            addMsg('Network error — check your connection and try again.', 'system');
            iv.turns.pop();
        } finally {
            this.isGenerating = false;
        }
    }

    /** Suggested answers, plus a chip that ends the interview early. */
    renderInterviewChips(choices) {
        this.renderChoiceChips(choices);
        const wrap = document.querySelector('#chat-box .choice-chips:last-child');
        const done = document.createElement('button');
        done.type = 'button';
        done.className = 'starter-chip starter-chip-guided';
        done.textContent = 'Make my game now';
        done.addEventListener('click', () => {
            if (this.isGenerating || !this.interview) return;
            wrap.remove();
            addMsg('Make my game now', 'user');
            this.answerInterview('That is all I want to say. Please write the summary now.', true);
        });
        wrap.appendChild(done);
    }

    /** After the brief: build the game from it, or interview again. */
    renderBriefChips(brief) {
        this.renderChoiceChips([]);
        const wrap = document.querySelector('#chat-box .choice-chips:last-child');
        const make = document.createElement('button');
        make.type = 'button';
        make.className = 'starter-chip starter-chip-guided';
        make.textContent = 'Make this game';
        make.addEventListener('click', () => {
            if (this.isGenerating) return;
            wrap.remove();
            document.getElementById('user-input').value = `Make this game for my class.\n\n${brief}`;
            this.onSend();
        });
        const again = document.createElement('button');
        again.type = 'button';
        again.className = 'starter-chip';
        again.textContent = 'Start the interview over';
        again.addEventListener('click', () => { wrap.remove(); this.startInterview(); });
        wrap.append(make, again);
        wrap.scrollIntoView({ block: 'end' });
    }

    renderStarterChips() {
        const box = document.getElementById('chat-box');
        if (box.querySelector('.starter-chips')) return;
        const wrap = document.createElement('div');
        wrap.className = 'starter-chips';
        // Intro lives INSIDE wrap (not a sibling) so removing '.starter-chips'
        // on the first sent message takes both with it in one go -- it used
        // to be a sibling appended straight to `box`, which meant onSend()'s
        // wrap.remove() left this line behind permanently.
        const intro = document.createElement('div');
        intro.className = 'msg system';
        intro.textContent = 'Tap “Interview me” to design a game by answering a few questions, '
            + '“Help me make a game” to choose step by step, or tap an idea to fill the box, then edit and send:';
        wrap.appendChild(intro);
        const interview = document.createElement('button');
        interview.type = 'button';
        interview.className = 'starter-chip starter-chip-guided';
        interview.innerHTML = `${iconSvg('message-circle', { size: 14 })} <span>Interview me</span>`;
        interview.addEventListener('click', () => this.startInterview());
        wrap.appendChild(interview);
        const guided = document.createElement('button');
        guided.type = 'button';
        guided.className = 'starter-chip starter-chip-guided';
        guided.innerHTML = `${iconSvg('sparkles', { size: 14 })} <span>Help me make a game</span>`;
        guided.addEventListener('click', () => this.startGuidedMode());
        wrap.appendChild(guided);
        drawStarterIdeas(4).forEach((sp) => {
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'starter-chip';
            chip.innerHTML = `${iconSvg(sp.icon, { size: 14 })} <span>${escapeHtml(sp.text)}</span>`;
            chip.addEventListener('click', () => {
                const inp = document.getElementById('user-input');
                inp.value = sp.text;
                inp.focus();
                inp.style.height = 'auto';
                inp.style.height = Math.min(inp.scrollHeight, 120) + 'px';
            });
            wrap.appendChild(chip);
        });
        box.appendChild(wrap);
    }

    /**
     * Forget the last game. Without this, opening an example and then starting
     * from scratch carried that example's declared tags (and name) into a game
     * that never reads them.
     */
    resetGameContext() {
        dbg('app', 'resetGameContext() — clearing name/tags/example');
        // Every role's code and history goes with the game it belonged to:
        // a display file left behind would be sent alongside the next game.
        // Edited icons go the same way, for the same reason -- and so a new
        // game starts from the shipped pictures, not the last game's.
        clearAllRoles();
        setGameIcons({});
        this.syncRoleRail();
        this.currentExample = null;
        this.declaredTags = null;
        this.simSettings = null;
        this.gameName = 'Your game';
        this.gameDesc = '';
        this.chatHistory = [];
        this.simNotes = null;
        this.interview = null;
        this.tagWrites = {};
        this.refreshHardware();
    }

    openWorkspace(starterMsg = null) {
        dbg('app', `openWorkspace(${starterMsg ? JSON.stringify(starterMsg) : 'no starter message'})`);
        showView('workspace');
        const box = document.getElementById('chat-box');
        if (box.children.length === 0) {
            this.renderStarterChips();
        }
        if (starterMsg) {
            document.getElementById('user-input').value = starterMsg;
        }
        this.updatePreview();
    }

    async remixCurrentExample() {
        if (!this.currentExample) {
            dbgWarn('app', 'remixCurrentExample() called with no currentExample set');
            return;
        }
        const action = await this.confirmUnsavedWork();
        if (action === 'cancel') return;

        const ex = this.currentExample;
        dbg('app', `remixCurrentExample("${ex.name}")`);

        this.resetGameContext();
        this.clearWorkspace();

        this.currentExample = ex;
        this.gameName = remixName(ex.name);
        this.gameDesc = ex.description;
        this.declaredTags = [...ex.tags];
        this.simSettings = null;
        this.chatHistory = [];
        this.simNotes = null;
        this.refreshHardware();

        const code = await this.fetchExampleCode(ex);
        if (!code) return;

        setCode(code);
        saveVersion(code, `${ex.name} (remix base)`);
        this.dirty = true;

        // One leading user turn: ask + real fenced code (not trimForHistory —
        // that would replace fences with a placeholder and hide the example
        // from Claude). callClaude shows it and posts it as the first message.
        const userMsg = [
            `I would like to remix the ${ex.name} example as a starting point. Here is the ${ex.name} code:`,
            '',
            '```python',
            code,
            '```',
        ].join('\n');

        this.openWorkspace();
        this.updatePreview({ forcePlay: true });
        await this.callClaude(userMsg);
    }

    /** The example's real Python, or null if it couldn't be read. A failure
     * is surfaced, not swallowed: without the code there is nothing to
     * remix, save or send. */
    async fetchExampleCode(ex) {
        try {
            return await loadExampleCode(ex);
        } catch (err) {
            dbgError('app', `could not read ${ex.vendorGame}.py: ${err.message}`);
            toast("Couldn't read that game's code — check the Simulator folder is being served.", true);
            return null;
        }
    }

    async useExampleAsIs() {
        if (!this.currentExample) {
            dbgWarn('app', 'useExampleAsIs() called with no currentExample set');
            return;
        }
        if (this.link.state !== 'live') {
            toast(`Connect to the ${this.deviceShort()} first.`, true);
            return;
        }
        const action = await this.confirmUnsavedWork();
        if (action === 'cancel') return;

        const ex = this.currentExample;
        dbg('app', `useExampleAsIs("${ex.name}")`);
        this.gameName = remixName(ex.name);
        this.gameDesc = ex.description;
        this.declaredTags = [...ex.tags];
        this.simSettings = null;
        // A new game starts from the shipped pictures, not the last one's edits.
        setGameIcons({});

        const code = await this.fetchExampleCode(ex);
        if (!code) {
            this.updatePreview();
            return;
        }

        setCode(code);
        saveVersion(code, `${ex.name} as-is`);
        this.dirty = true;
        showView('workspace');
        this.syncGameName();
        this.updatePreview({ forcePlay: true });
        await this.startSendFlow();
    }

    /** @param {{forcePlay?: boolean}} [opts] forcePlay: this is an explicit
     * "load this specific game" action (saved game, remix, use-as-is), not
     * an incidental chat/version-navigation refresh -- see pushSimSource(). */
    updatePreview(opts = {}) {
        const wandCode = getCode('wand');

        const primary = primaryRoleCode();
        this.refreshHardware(primary?.code ?? wandCode);

        // The preview shows the wand simulator whenever there is wand code,
        // whichever role the code drawer is editing. A display-only game
        // falls to the placeholder; its icons are in the Icons view.
        const runnable = isRunnableCode(wandCode);

        document.getElementById('preview-panel').classList.toggle('hidden', !runnable);
        document.querySelector('.ws-body')?.classList.toggle('no-sim', !runnable);

        this.syncGameName();
        this.syncPreviewEmpty();

        // Send is gated on having something to send as well as somewhere to
        // send it; setConnectionBadge() owns the button and reads this back,
        // because it runs on link changes and this runs on code changes.
        const sendable = !!primary;
        document.body.dataset.wsHasCode = sendable ? '1' : '';
        this.paintLink();

        if (this.iconsViewOpen()) this.renderIconsList();
        if (runnable) {
            this.setupSim();
            this.pushSimSource(wandCode, opts);
        }
    }

    /** The placeholder behind an empty stage names the game's primary
     * device (the wand for a new game). */
    syncPreviewEmpty() {
        const empty = document.getElementById('preview-empty');
        if (!empty) return;
        const info = roleInfo(primaryRoleCode()?.role) || roleInfo(DEFAULT_ROLE);
        const host = empty.querySelector('.preview-empty-icon');
        const caption = empty.querySelector('.preview-empty-caption');
        // Built here rather than left to the load-time [data-icon] pass, which
        // runs once and would keep whichever glyph the markup started with.
        if (host) host.innerHTML = iconSvg(info.previewGlyph, { size: 46, strokeWidth: 1.3 });
        if (caption) caption.textContent = info.previewCaption;
    }

    /** Lazily load the <sim-room> module the first time it's needed —
     * Pyodide plus its game/shim files is a real download, and booting
     * it while the teacher is still typing their first chat message would
     * only add to that wait. Safe to call repeatedly; the import runs once.
     *
     * #wand-sim is a <sim-room>: the wand, plus the panels the game uses
     * (the icon display for a two-device game, Splats and virtual peer
     * wands for a party game). It takes the same calls <wand-sim> did. */
    setupSim() {
        if (this._simLoadPromise) return this._simLoadPromise;
        dbg('app', 'setupSim() — loading sim-room module');
        this._simLoadPromise = import('../../../Simulator/sim-room.js')
            .then(() => {
                this._sim = document.getElementById('wand-sim');
                // An icon edit reaches the running display: the room rewrites
                // the display game's icon files.
                document.addEventListener('game-icons-changed', () => {
                    if (this._sim && this._simLastDisplay) this._sim.displayIcons = this.simDisplayIcons(this._simLastDisplay);
                });
                // Every push of new code reloads the game; start it right away.
                this._sim.autostart = true;
                // <wand-sim> shows its own "Can't simulate" pop-up on a
                // boot/load failure, worded for this audience; the raw
                // message still lands in the debug console, so nothing is
                // swallowed.
                this._sim.addEventListener('sim-error', (e) => {
                    const { message, phase } = e.detail || {};
                    this._simLastError = { message, phase };
                    dbgError('sim', `sim-error (${phase}): ${message}`);
                });
                this._sim.addEventListener('sim-overlay-action', (e) => {
                    this.onSimOverlayAction(e.detail || {});
                });
                this._setupSimIdlePause();
                // The simulator draws no logs; its lines go to the footer.
                this._simRecentLog = [];
                this._sim.addEventListener('sim-log', (e) => {
                    this.appendLog('sim', `wand    ${e.detail.text}`);
                    this._simRecentLog.push(e.detail.text);
                    if (this._simRecentLog.length > SIM_LOG_FOR_CHAT) this._simRecentLog.shift();
                });
                this._sim.addEventListener('display-print', (e) => this.appendLog('sim', `display ${e.detail.text}`));
                this._sim.addEventListener('sim-error', (e) => {
                    this.appendLog('sim', `error   ${e.detail.phase}: ${e.detail.message}`);
                });
                this._sim.addEventListener('room-radio', (e) => this.appendLog('radio', e.detail.text));
                this._sim.addEventListener('sim-enow-sent', (e) => {
                    const { kind, mac, data } = e.detail;
                    this.appendLog('radio', `wand → ${mac || 'all'}: ${kind} ${data}`);
                });
                if (this._simPendingSource !== null) {
                    const pending = this._simPendingSource;
                    const forcePlay = this._simForcePlayPending;
                    this._simPendingSource = null;
                    this._simForcePlayPending = false;
                    this.pushSimSource(pending, { forcePlay });
                }
            })
            .catch((err) => {
                dbgError('sim', 'failed to load sim-room module', err);
            });
        return this._simLoadPromise;
    }

    /** A running simulation pauses after SIM_IDLE_PAUSE_MS without input
     * on the page, and at once when the tab is hidden: a game that sends
     * radio frames continuously allocates faster than an idle tab collects.
     * The paused banner's Play it restarts the game. */
    _setupSimIdlePause() {
        this._simPaused = false;
        const pause = () => {
            if (!this._sim || this._simPaused) return;
            this._simPaused = true;
            dbg('sim', 'paused (idle or hidden)');
            Promise.resolve(this._sim.stop()).catch(() => {});
            this._sim.showOverlay('paused');
        };
        const arm = () => {
            clearTimeout(this._simIdleTimer);
            this._simIdleTimer = setTimeout(pause, SIM_IDLE_PAUSE_MS);
        };
        for (const ev of ['pointerdown', 'pointermove', 'keydown', 'wheel']) {
            document.addEventListener(ev, arm, { passive: true, capture: true });
        }
        this._sim.addEventListener('sim-loaded', () => { this._simPaused = false; });
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) pause(); else arm();
        });
        arm();
    }

    /**
     * Push code into the sim. Normally only when it actually changed — the
     * element's source setter reloads (and would restart the running game)
     * unconditionally, and updatePreview() runs on every keystroke-adjacent
     * chat/version event, not just real code changes -- an organic chat
     * edit gets a passive "new code is ready, play it" banner rather than
     * yanking control from someone mid-test.
     *
     * `forcePlay` is for the opposite case: an explicit "load this game"
     * action (a saved game, remix, use-as-is), where the teacher clicked
     * something specifically to see THIS game, not incidentally touched
     * code that happens to match what's already loaded (bypassing the
     * equality check too -- reopening the same saved game twice in a row
     * should still visibly restart it) -- and restart()s it immediately
     * instead of leaving it to the passive banner.
     *
     * Only marks the code as "sent" (_simLastSource) once it's actually
     * reached the element -- setupSim() is still loading, this just queues
     * it for that resolve.
     */
    pushSimSource(code, { forcePlay = false } = {}) {
        if (!this._sim) {
            this._simPendingSource = code;
            this._simForcePlayPending = forcePlay;
            return;
        }
        // The display half runs beside the wand when the game has one.
        const display = getCode('icon') || null;
        const settings = this.simSettings || null;
        const settingsKey = JSON.stringify(settings);
        if (code === this._simLastSource && display === this._simLastDisplay
            && settingsKey === this._simLastSettings && !forcePlay) return;
        // Only from the second push on: the first one *is* the game
        // appearing, which needs no announcement.
        const isUpdate = this._simLastSource != null;
        this._simLastSource = code;
        this._simLastDisplay = display;
        this._simLastSettings = settingsKey;
        this._sim.hideOverlay();
        this._simPaused = false;
        this._sim.displayIcons = display ? this.simDisplayIcons(display) : null;
        this._sim.displaySource = display;
        // Workspace code is pushed as source — it may have been edited — so
        // _TEACHER_TABLE can't match it and capabilities fall back to "show
        // everything". The example's own profile is what narrows that back
        // down; a game generated from scratch has none and shows the lot.
        this._sim.profile = this.currentExample?.simProfile || null;
        // Before the source: the room hands the Splat count to the wand
        // ahead of the game loading.
        this._sim.settings = settings;
        this._sim.source = code;
        if (forcePlay) {
            this._sim.restart?.();
        } else if (isUpdate) {
            this._sim.showOverlay('new-code');
        }
    }

    /** {name: duty[768]} for every icon the display code names, this
     * game's own version where it has one (getIcon's order). */
    simDisplayIcons(displayCode) {
        const out = {};
        for (const name of iconNamesIn(displayCode)) {
            const duty = getIcon(name);
            if (duty) out[name] = duty;
        }
        return out;
    }

    /**
     * A button on one of the simulator's pop-ups. The element closes the
     * pop-up itself, so these only have to do the thing.
     */
    onSimOverlayAction({ kind, action }) {
        dbg('app', `sim overlay ${kind} -> ${action}`);
        if (action === 'play-it' || action === 'play-again') {
            this._simPaused = false;
            this._sim?.restart();
        } else if (action === 'send-to-box') {
            this.startSendFlow();
        } else if (action === 'debug-in-chat') {
            this.sendSimProblemToChat();
        }
    }

    /** Ask the chat to fix the game the simulator could not run. The
     * editor's code already travels in the system blocks, so the message
     * carries the phase and the simulator's error text. From the first
     * such message on, knowledge/simulator.md is a cached system block for
     * the rest of the chat (getSystemBlocks), so it does not age out of
     * the history window. */
    async sendSimProblemToChat() {
        const err = this._simLastError;
        if (!err || this.isGenerating) return;
        const when = err.phase === 'load' ? 'loading the game' : 'running the game';
        // A run-phase error carries only the traceback's last line; the
        // full traceback is in the recent log.
        const log = err.phase === 'run' && this._simRecentLog?.length
            ? `\n\nRecent simulator log:\n${this._simRecentLog.join('\n')}` : '';
        const ask = `The simulator failed while ${when}. Please find the problem in the current code and fix it.`;
        const details = `${err.message}${log}`;
        const msg = `${ask}\n\n<error>\n${details}\n</error>`;
        if (!this.simNotes) {
            try {
                const resp = await fetch(SIM_KNOWLEDGE);
                if (resp.ok) this.simNotes = await resp.text();
            } catch (e) {
                dbgWarn('chat', `could not read ${SIM_KNOWLEDGE}: ${e.message}`);
            }
        }
        document.querySelector('.starter-chips')?.remove();
        document.querySelectorAll('.choice-chips').forEach(el => el.remove());
        addMsg(ask, 'user').appendChild(buildCodeBlock('error', details, { collapsed: true, editor: false }));
        this.dirty = true;
        await this.callClaude(msg);
    }

    renderComponentList(targetId) {
        const code = getCode('wand');
        const caps = scanCapabilities(code);
        const items = buildComponentChecklist(caps, this.requiredTags);
        const el = document.getElementById(targetId);
        if (!el) return;
        el.innerHTML = '';
        el.classList.add('send-icons-row');
        items.forEach((item) => {
            const div = document.createElement('div');
            div.className = `send-icon-item ${item.kind || 'other'}`;
            div.title = item.label;
            div.innerHTML = iconSvg(item.icon, { size: 20, strokeWidth: 1.6 });
            el.appendChild(div);
        });
    }

    /**
     * @param {'box'|'wand'} kind — which link implementation to open the
     *   port with. Chosen on the connect overlay (Broadcast Box/Dial share
     *   one protocol, told apart only after connecting, per
     *   HARDWARE_PROTOCOL.md; Wand is the direct-USB path, a different
     *   protocol entirely -- see wandDeviceLink.js).
     */
    async onConnect(kind) {
        dbg('app', `onConnect(${kind}) — requesting serial port`);
        if (this.device.kind !== kind) {
            this.device = kind === 'wand' ? createWandDeviceLink() : createDeviceLink();
            this._boxGames = []; // stale Box/Dial library from a previous session must not leak in
            this.setupDeviceListeners();
        }
        this.renderComponentList('connect-components');
        const errEl = document.getElementById('connect-error');
        if (errEl) errEl.textContent = '';
        this.setLinkState('opening');
        showConnectToast(true);
        try {
            await this.device.connect();
            dbg('app', 'device.connect() resolved (port open; awaiting heartbeat/identity)');
            hideOverlay('connect-overlay');
            showConnectToast(false);
            this.setLinkState('waiting');
            if (this.pendingSendAfterConnect) {
                toast(`Connected — waking up the ${this.deviceShort()}, then we will send…`);
            } else {
                toast(`Connected — waking up the ${this.deviceShort()}…`);
            }
        } catch (e) {
            dbgError('app', `device.connect() rejected: ${e.message}`, e);
            showConnectToast(false);
            // Header connect: show overlay so the error is visible; send-flow already has it open.
            showOverlay('connect-overlay');
            if (errEl) errEl.textContent = `Couldn't find a ${this.deviceProduct()} — check the cable.`;
            this.setLinkState('idle');
        }
    }

    /** Standalone header "Connect"/"Disconnect"/"Cancel" toggle. */
    async toggleConnect() {
        const s = this.link.state;
        if (s === 'opening' || s === 'sending') return;
        if (s === 'waiting' || s === 'rebooting') {
            // 'rebooting' included: the auto-reconnect attempts this state
            // waits for are a convenience, not something the teacher should
            // be stuck watching -- always a way to bail out to idle instead
            // of waiting on the reboot timer or an attempt limit.
            dbg('app', `toggleConnect() — cancel ${s}`);
            showConnectToast(false);
            this._clearRebootTimer();
            await this.device.disconnect();
            this.setLinkState('idle');
            toast('Cancelled.');
            return;
        }
        if (s === 'live' || s === 'stuck' || s === 'wrong' || s === 'no-answer') {
            dbg('app', 'toggleConnect() — disconnecting');
            await this.device.disconnect();
            this.setLinkState('idle');
            toast('Disconnected.');
            return;
        }
        // idle or lost → show the overlay and let the teacher pick a device
        // kind; each of its buttons calls onConnect(kind) directly (needed
        // for requestPort()'s user-gesture requirement anyway).
        this.pendingSendAfterConnect = false;
        this.renderComponentList('connect-components');
        showOverlay('connect-overlay');
    }

    async onRestartBox() {
        dbg('app', 'onRestartBox() — restartFirmware');
        toast(`Nudging the ${this.deviceShort()}…`);
        this.setLinkState('rebooting');
        this._armRebootTimer();
        try {
            const state = await this.device.restartFirmware();
            if (state === 'running') {
                this.setLinkState('live');
                toast(`${this.deviceShort()} is back.`);
            } else {
                toast(`Still waiting for the ${this.deviceShort()}…`, true);
            }
        } catch (e) {
            dbgError('app', `restartFirmware failed: ${e.message}`, e);
            toast(`Could not restart the ${this.deviceShort()} — try unplugging.`, true);
            this.setLinkState('stuck');
        }
    }

    async startSendFlow() {
        dbg('app', 'startSendFlow() — "Send to Broadcast Box" clicked');
        const primary = primaryRoleCode();
        if (!primary) {
            dbgWarn('app', 'startSendFlow() aborted: no code in editor');
            toast('Generate some code first — describe your game in chat.', true);
            return;
        }
        this.refreshHardware(primary.code);
        dbg('app', `required tags: [${this.requiredTags.join(', ')}]`);
        // Confirm is the FIRST screen: name the game and see what it needs.
        // Connecting and the tag to-do list both happen on the far side of Send.
        this.showSendConfirm();
    }

    /** Recompute the hardware requirements from the current code + declared tags. */
    refreshHardware(code) {
        this.hardware = buildHardwareReqs({
            code: code !== undefined ? code : getCode(DEFAULT_ROLE),
            gameName: this.gameName,
            declared: this.declaredTags,
            // Every non-wand role with no simulator is a physical station
            // the game needs, named for the send-confirm overlay.
            stations: ROLE_TABLE
                .filter(r => r.key !== DEFAULT_ROLE && !r.hasPreview && getCode(r.key).trim())
                .map(r => r.label),
        });
        return this.hardware;
    }

    /** The tag list every consumer reads — derived, never assigned directly. */
    get requiredTags() {
        return this.hardware?.tags || [];
    }

    renderSendRequirements() {
        const el = document.getElementById('send-requirements');
        if (!el) return;
        el.innerHTML = '';
        formatHardwareReqs(this.hardware).forEach((row) => {
            const li = document.createElement('li');
            li.className = 'send-req-row';
            li.innerHTML =
                `<span class="send-req-icon">${iconSvg(row.icon, { size: 17, strokeWidth: 1.7 })}</span>` +
                `<span class="send-req-label"></span>`;
            li.querySelector('.send-req-label').textContent = row.label;
            el.appendChild(li);
        });
    }

    async showSendConfirm() {
        const nameInput = document.getElementById('send-game-name');
        const errEl = document.getElementById('send-name-error');
        if (errEl) errEl.textContent = '';
        if (nameInput) {
            nameInput.value = this.gameName && this.gameName !== 'Your game' ? this.gameName : '';
            // DIAGNOSTIC (temporary -- name-field-appears-blank investigation,
            // see chat): confirmSend() falls back to this.gameName when the
            // input is empty, so a duplicate-name warning naming the right
            // game even with a blank-looking field is consistent with EITHER
            // this line failing to actually set .value, OR it succeeding but
            // something visual hiding it. Logging both the source and the
            // result right after assignment settles which one it is.
            dbg('app', `showSendConfirm(): populated name field from gameName=${JSON.stringify(this.gameName)} -> input.value=${JSON.stringify(nameInput.value)}`);
        }
        this._pendingReplaceSlug = null;
        this.refreshHardware(primaryRoleCode()?.code);
        this.renderSendRequirements();
        this.setSendBusy(false);
        document.getElementById('send-progress-wrap').classList.add('hidden');
        // Always reopen on the name/requirements form, never mid-way
        // through a previous send's success screen.
        document.getElementById('send-confirm-form').classList.remove('hidden');
        document.getElementById('send-confirm-success').classList.add('hidden');
        clearTimeout(this._sendSuccessTimer);
        // Refresh Box game list when live so duplicate checks work. The wand
        // has no such command (no command listener at all -- see
        // wandDeviceLink.js); its duplicate check instead reads the games
        // list from its boot `identity` event (deviceInfo.games).
        if (this.link.state === 'live' && this.device.kind !== 'wand') {
            try {
                await this.fetchBoxGames();
            } catch (e) {
                dbgWarn('app', `games.list before send failed: ${e.message}`);
            }
        }
        showOverlay('send-confirm-overlay');
    }

    /**
     * Lock the confirm overlay while the file is streaming.
     * There is no abort: sendGame() writes the .py over the raw REPL, so
     * stopping halfway leaves a truncated game on the Box. Better to take the
     * choice away than to offer a Cancel that corrupts the file.
     */
    setSendBusy(busy) {
        const btn = document.getElementById('btn-send-confirm');
        const cancel = document.getElementById('btn-send-cancel');
        const nameInput = document.getElementById('send-game-name');
        if (btn) {
            btn.disabled = busy;
            btn.textContent = busy ? 'Sending…' : 'Send';
        }
        if (cancel) cancel.classList.toggle('hidden', busy);
        if (nameInput) nameInput.disabled = busy;
    }

    /**
     * Switch the send-confirm overlay from the name/requirements form to a
     * success screen, once the device has confirmed the file write (the
     * real point of success -- see pushPayload()/boxFirmwareInstaller.js).
     * The device's own reboot happens after this and is expected; the
     * overlay does not wait on it. Auto-closes on a timer as well as Done,
     * since a teacher mid-classroom may not click through every dialog.
     */
    showSendSuccess(prettyName) {
        document.getElementById('send-confirm-form').classList.add('hidden');
        document.getElementById('send-confirm-success').classList.remove('hidden');
        document.getElementById('send-success-title').textContent = `"${prettyName}" is on the ${this.deviceShort()}!`;
        document.getElementById('send-success-note').textContent =
            `The ${this.deviceShort()} will restart now — give it a few seconds.`;
        // Direct USB install reaches one wand per send: offer the next one.
        document.getElementById('btn-send-another-wand')?.classList.toggle('hidden', this.device.kind !== 'wand');
        clearTimeout(this._sendSuccessTimer);
        this._sendSuccessTimer = setTimeout(() => this.finishSend(), 5000);
    }

    /** Close the send-confirm overlay after a successful send (Done, its
     * auto-close timer, or the kill-switch X all land here) and put the
     * link into 'rebooting' -- the state that quietly rides out the
     * device's own reboot instead of reporting it as a disconnect. */
    finishSend() {
        clearTimeout(this._sendSuccessTimer);
        hideOverlay('send-confirm-overlay');
        this._pendingReplaceSlug = null;
        // Only claim 'rebooting' if we're still sitting on the disconnect
        // from the send's own reboot. tryAutoReconnect() can already have
        // gotten us to 'waiting' or 'live' by the time Done is clicked (or
        // the auto-close timer fires) -- forcing 'rebooting' here would
        // wrongly downgrade an already-recovered connection.
        if (this.link.state === 'lost') {
            this.setLinkState('rebooting');
            this._armRebootTimer();
        }
    }

    /** "Install on another wand" on the success screen of a direct wand
     * install: release this wand's port and reopen the connect overlay with
     * the send armed, so connecting the next wand returns to the send
     * confirm with the same game and name. */
    async installOnAnotherWand() {
        clearTimeout(this._sendSuccessTimer);
        hideOverlay('send-confirm-overlay');
        this._pendingReplaceSlug = null;
        this._clearRebootTimer();
        try {
            await this.device.disconnect();
        } catch (e) {
            dbgWarn('app', `disconnect before next wand: ${e.message}`);
        }
        this.setLinkState('idle');
        this.pendingSendAfterConnect = true;
        this.renderComponentList('connect-components');
        showOverlay('connect-overlay');
        toast('Plug in the next wand, then choose Wand.');
    }

    async confirmSend() {
        dbg('app', 'confirmSend() — "Send" clicked on confirm overlay');
        const primary = primaryRoleCode();
        const errEl0 = document.getElementById('send-name-error');
        if (!primary) {
            toast('Generate some code first — describe your game in chat.', true);
            return;
        }
        const { role: primaryRole, info: primaryInfo, code } = primary;
        if (this.device.kind === 'wand' && primaryRole !== DEFAULT_ROLE) {
            // wandGameInstaller.js installs only <slug>.py on the wand.
            const msg = `This game has no wand code, so it cannot be installed on a wand. Send it to a Box or Dial instead.`;
            if (errEl0) errEl0.textContent = msg;
            toast(msg, true);
            return;
        }
        const nameInput = document.getElementById('send-game-name');
        const errEl = document.getElementById('send-name-error');
        const pretty = (nameInput?.value || this.gameName || '').trim();
        const existing = this.device.kind === 'wand'
            ? (this.device.deviceInfo?.games || [])
            : (this._boxGames || []).map((g) => g.slug);
        const btn = document.getElementById('btn-send-confirm');
        let check = validateGameName(pretty, {
            existingSlugs: existing,
            allowReplace: this._pendingReplaceSlug === slugify(pretty),
        });
        if (!check.ok && check.reason === 'replace') {
            // First click on a duplicate name: explain inline and arm the
            // button for a second click that actually replaces it, instead
            // of a native confirm() popup. Editing the name (see its input
            // listener in bindEvents()) disarms this.
            this._pendingReplaceSlug = check.slug;
            if (errEl) errEl.textContent = `"${pretty}" is already on the ${this.deviceShort()}. Click Replace to overwrite it, or change the name.`;
            if (btn) btn.textContent = 'Replace existing game';
            return;
        }
        if (!check.ok) {
            this._pendingReplaceSlug = null;
            if (btn) btn.textContent = 'Send';
            if (errEl) errEl.textContent = check.reason || 'Invalid name.';
            return;
        }
        if (errEl) errEl.textContent = '';
        if (btn) btn.textContent = 'Send';
        this.gameName = check.pretty;
        const slug = check.slug;
        // The name is settled now, so the baseline getcode:/play tags are too.
        this.refreshHardware(code);

        if (this.link.state !== 'live') {
            dbg('app', 'confirmSend() — not live; connecting first');
            hideOverlay('send-confirm-overlay');
            this.pendingSendAfterConnect = true;
            this.renderComponentList('connect-components');
            showOverlay('connect-overlay');
            return;
        }
        const isWand = this.device.kind === 'wand';
        // wandGameInstaller.js derives /games/<slug>.py itself from `slug`;
        // `destPath` is Box-only. `tags` drives the post-send NFC-card-write
        // checklist below, which is Box-only too (the wand plays the game
        // itself -- no card writing on this path).
        const meta = {
            slug,
            destLabel: `${slug}.py`,
            prettyName: check.pretty,
            deviceLabel: this.deviceShort(),
        };
        if (!isWand) {
            meta.destPath = `/flash/games/${slug}${primaryInfo.designator}.py`;
            meta.destLabel = `${slug}${primaryInfo.designator}.py`;
            // Recompute against the slug actually being written: the name can
            // change on this overlay, and the device keys its menu off the slug.
            meta.tags = buildHardwareReqs({
                code, gameName: check.pretty, declared: this.declaredTags,
            }).tags;
        }

        // A multi-device game ships as several files in one raw-REPL session:
        // the wand's <slug>.py, and one <slug><designator>.py per other role
        // that has code (plus, for icon, every icon that game names, under
        // <slug>_icons/). The Box then serves each device whichever file its
        // hubtype asks for.
        const extraFiles = [];
        for (const info of ROLE_TABLE) {
            if (info.key === DEFAULT_ROLE) continue;
            const roleCode = getCode(info.key).trim();
            if (!roleCode) continue;
            // Every non-wand role is checked here, the primary one too (its
            // icon leg is queued below); uploadPayload checks the primary
            // file again and sends it as meta.destPath.
            const [ok, err] = validateGameCode(roleCode, info.key);
            if (!ok) {
                if (errEl) errEl.textContent = err;
                toast(err, true);
                return;
            }
            if (info.unknownNamesIn) {
                const unknown = info.unknownNamesIn(roleCode);
                if (unknown.length) {
                    // The device would print [ERR] and do nothing for each.
                    const msg = `The ${info.label} game uses names the device does not have: ${unknown.join(', ')}.`;
                    if (errEl) errEl.textContent = msg;
                    toast(msg, true);
                    return;
                }
            }
            if (info.hasIconLeg) {
                const missing = missingIconsIn(roleCode);
                if (missing.length) {
                    // Sending blanks would leave a dark panel and no explanation.
                    const msg = `The display game asks for icons that do not exist: ${missing.join(', ')}.`;
                    if (errEl) errEl.textContent = msg;
                    toast(msg, true);
                    return;
                }
            }
            if (info.key !== primaryRole) {
                extraFiles.push({ path: `/flash/games/${slug}${info.designator}.py`, content: roleCode });
            }
            if (info.hasIconLeg) {
                for (const name of iconNamesIn(roleCode)) {
                    extraFiles.push({
                        path: `/flash/games/${slug}_icons/${name}.py`,
                        content: iconFileText(name),
                    });
                }
            }
            dbg('app', `${info.label} file plus its extras queued (${extraFiles.length} so far)`);
        }
        if (!isWand && extraFiles.length) {
            meta.extraFiles = extraFiles;
        }

        document.getElementById('send-progress-wrap').classList.remove('hidden');
        setSendProgress(0, 'Starting…');
        this.setSendBusy(true);

        this.setLinkState('sending');
        const result = await uploadPayload(this.device, code, window.onUploadProgress, {
            linkState: 'sending',
            deviceProduct: this.deviceProduct(),
            deviceShort: this.deviceShort(),
            role: primaryRole,
            meta,
        });
        dbg('app', 'uploadPayload() result', result);

        this.setSendBusy(false);

        if (!result.ok) {
            // Stay on the overlay so the teacher can fix the name and retry.
            document.getElementById('send-progress-wrap').classList.add('hidden');
            dbgError('app', `send failed: ${result.error}`);
            toast(result.error || 'Send failed — try again.', true);
            this.setLinkState(this.device.isConnected() ? 'live' : 'lost');
            return;
        }

        dbg('app', 'send succeeded — showing success screen');
        // Tag-writing to-do list is out of scope here now -- the device
        // manages that itself. The overlay's job is just to make "it worked,
        // the device is restarting" visible and unambiguous. A wand says
        // something different because it auto-launches what it was just sent
        // (see wandGameInstaller.js) rather than waiting for a card.
        this.showSendSuccess(check.pretty);
        if (isWand) toast('Sent! The wand is starting the game now.');

    }

    async openBoxLibrary() {
        showOverlay('box-library-overlay');
        await this.refreshBoxLibrary();
    }

    async fetchBoxGames() {
        if (this.link.state !== 'live') return [];
        const obj = await this.device.sendCmd({ cmd: 'games.list' }, { timeoutMs: 5000 });
        this._boxGames = obj.list || [];
        if (obj.active) {
            this.link.detail = { ...(this.link.detail || {}), active: obj.active };
        }
        return this._boxGames;
    }

    async refreshBoxLibrary() {
        const status = document.getElementById('box-library-status');
        const list = document.getElementById('box-library-list');
        const statsEl = document.getElementById('box-stats-text');
        this.paintMyBoxHealth();
        if (!list) return;
        if (this.link.state !== 'live') {
            if (status) status.textContent = `Connect to the ${this.deviceShort()} first.`;
            list.innerHTML = '';
            if (statsEl) statsEl.textContent = '—';
            return;
        }
        if (status) status.textContent = 'Loading…';
        try {
            const games = await this.fetchBoxGames();
            let stats = {};
            try {
                stats = await this.device.sendCmd({ cmd: 'stats.get' }, { timeoutMs: 5000 });
            } catch (e) {
                dbgWarn('app', `stats.get failed: ${e.message}`);
            }
            const writes = stats.writes || {};
            const active = this.link.detail?.active;
            if (status) {
                status.textContent = games.length
                    ? ''
                    : `No games on the ${this.deviceShort()} yet — send one from chat.`;
                status.classList.toggle('hidden', !!games.length);
            }
            list.innerHTML = '';
            games.forEach((g) => {
                const li = document.createElement('li');
                const isActive = g.slug === active;
                const radio = document.createElement('button');
                radio.type = 'button';
                radio.className = 'box-lib-radio' + (isActive ? ' active' : '');
                radio.title = isActive ? `Active on the ${this.deviceShort()}` : `Select "${g.name || g.slug}"`;
                radio.innerHTML = iconSvg(isActive ? 'radioOn' : 'radio', { size: 17 });
                radio.addEventListener('click', () => {
                    if (!isActive) this.selectBoxGame(g.slug);
                });
                const name = document.createElement('span');
                name.className = 'box-lib-name';
                name.textContent = g.name || g.slug;
                const pulls = document.createElement('span');
                pulls.className = 'box-lib-pulls';
                pulls.title = 'Times handed out';
                pulls.textContent = `${g.pulls || 0}×`;
                const del = document.createElement('button');
                del.type = 'button';
                del.className = 'box-lib-del';
                del.title = `Delete from ${this.deviceShort()}`;
                del.innerHTML = iconSvg('trash', { size: 15 });
                del.addEventListener('click', () => this.askDeleteBoxGame(li, g));

                // Written-tag checklist: the durable answer to "which cards have
                // I made?", available whenever the Box is connected -- not only
                // during the moments right after a send.
                const expand = document.createElement('button');
                expand.type = 'button';
                expand.className = 'box-lib-expand';
                expand.title = 'Which tags are written?';
                expand.innerHTML = iconSvg('chevronDown', { size: 15 });
                const tagsWrap = document.createElement('div');
                tagsWrap.className = 'box-lib-tags hidden';
                this.renderWrittenChecklist(tagsWrap, g, writes);
                expand.addEventListener('click', () => {
                    const open = tagsWrap.classList.toggle('hidden');
                    expand.classList.toggle('open', !open);
                });

                li.appendChild(radio);
                li.appendChild(name);
                li.appendChild(pulls);
                li.appendChild(expand);
                li.appendChild(del);
                li.appendChild(tagsWrap);
                list.appendChild(li);
            });
            if (statsEl) {
                const pulls = JSON.stringify(stats.pulls || {}, null, 0);
                const writes = JSON.stringify(stats.writes || {}, null, 0);
                statsEl.textContent = `pulls: ${pulls}\nwrites: ${writes}\nsince: ${stats.since || 0}`;
            }
            this.paintMyBoxHealth();
        } catch (e) {
            dbgError('app', `refreshBoxLibrary: ${e.message}`, e);
            if (status) {
                status.classList.remove('hidden');
                status.textContent = `Could not load library: ${e.message}`;
            }
            toast(`Could not talk to the ${this.deviceShort()} library.`, true);
        }
    }

    /**
     * Expected tags for a Box game vs. how many of each the Box has written.
     *
     * The Box's own list wins: it comes from the <slug>.tags.json pushed with
     * the game, so it is right even for a game this laptop never sent — which
     * the saved-game lookup below, keyed on a local name, cannot be. The
     * fallbacks keep a Box on older firmware (no `tags` in games.list) working.
     */
    renderWrittenChecklist(wrap, g, writes) {
        const saved = loadSavedGames().find((x) => slugify(x.name || '') === g.slug);
        const tags = g.tags?.length
            ? [...new Set([...baselineTags(g.slug), ...g.tags])]
            : (saved?.hardware?.tags?.length
                ? saved.hardware.tags
                : (saved?.requiredTags?.length
                    ? [...new Set([...baselineTags(g.slug), ...saved.requiredTags])]
                    : baselineTags(g.slug)));
        wrap.innerHTML = '';
        tags.forEach((tag) => {
            const n = (writes && writes[tag]) || 0;
            const row = document.createElement('div');
            row.className = 'box-tag-row' + (n > 0 ? ' done' : '');
            row.innerHTML =
                `<span class="box-tag-icon">${iconSvg(n > 0 ? 'circle-check' : 'nfcCard', { size: 14 })}</span>` +
                `<span class="box-tag-name"></span>` +
                `<span class="box-tag-count">${n > 0 ? n + '\u00d7' : 'not written'}</span>`;
            row.querySelector('.box-tag-name').textContent = tag;
            wrap.appendChild(row);
        });
        if (!saved) {
            const note = document.createElement('p');
            note.className = 'box-tag-note';
            note.textContent = 'Sent from another computer — only the pickup and play cards are known.';
            wrap.appendChild(note);
        }
    }

    paintMyBoxHealth() {
        const info = this.link.deviceInfo || {};
        const chip = document.getElementById('mybox-mode-chip');
        const label = document.getElementById('mybox-mode-label');
        // Same "connected or not" rule as the header mode pill (router.js)
        // -- this chip can't change the device's mode either, so it never
        // names one ("Code Server"/"Tag Writing"), which read as if it
        // reflected something this overlay controls.
        if (chip && label) {
            chip.classList.remove('write');
            label.textContent = this.link.state === 'live' ? `${this.deviceShort()} ready` : this.deviceShort();
            chip.title = this.link.state === 'live'
                ? `Games, health & battery on the ${this.deviceShort()}.`
                : `Connect to see ${this.deviceShort()} status.`;
        }
        const nfc = document.getElementById('mybox-nfc');
        const nfcStatus = document.getElementById('mybox-nfc-status');
        const hasNfcField = Object.prototype.hasOwnProperty.call(info, 'nfc');
        const nfcOk = hasNfcField ? !!info.nfc : true;
        if (nfc) {
            nfc.classList.toggle('ok', nfcOk);
            nfc.classList.toggle('bad', hasNfcField && !nfcOk);
            nfc.title = !hasNfcField
                ? 'NFC reader'
                : nfcOk
                  ? 'NFC reader OK'
                  : 'NFC reader not responding';
        }
        if (nfcStatus) {
            nfcStatus.innerHTML = iconSvg(hasNfcField && !nfcOk ? 'close' : 'check', { size: 12 });
        }
        const fw = document.getElementById('mybox-fw-version');
        if (fw) {
            fw.textContent = info.version ? `v${info.version}` : 'v—';
        }
    }

    askDeleteBoxGame(li, g) {
        const existing = li.querySelector('.box-lib-del, .box-lib-del-confirm');
        if (!existing) return;
        const confirmBtn = document.createElement('button');
        confirmBtn.type = 'button';
        confirmBtn.className = 'box-lib-del-confirm';
        confirmBtn.textContent = 'Delete?';
        confirmBtn.addEventListener('click', () => this.deleteBoxGame(g.slug, true));
        existing.replaceWith(confirmBtn);
    }

    async selectBoxGame(slug) {
        try {
            await this.device.sendCmd({ cmd: 'games.select', slug }, { timeoutMs: 5000 });
            toast(`Selected ${slug}`);
            await this.refreshBoxLibrary();
        } catch (e) {
            toast(e.message || 'Select failed', true);
        }
    }

    async deleteBoxGame(slug, alreadyConfirmed = false) {
        // The library UI always confirms inline first (askDeleteBoxGame()'s
        // "Delete?" button), so alreadyConfirmed is normally already true;
        // this is only a fallback for a hypothetical direct call.
        if (!alreadyConfirmed) {
            const ok = await this.confirmDialog({
                title: 'Delete this game?',
                message: `This removes "${slug}" from the ${this.deviceShort()}.`,
                okLabel: 'Delete',
            });
            if (!ok) return;
        }
        try {
            await this.device.sendCmd({ cmd: 'games.delete', slug }, { timeoutMs: 5000 });
            toast(`Deleted ${slug}`);
            await this.refreshBoxLibrary();
        } catch (e) {
            toast(e.message || 'Delete failed', true);
        }
    }

    async clearBoxLibrary() {
        const ok = await this.confirmDialog({
            title: 'Remove all games?',
            message: `This removes every game from the ${this.deviceShort()}.`,
            okLabel: 'Remove all',
        });
        if (!ok) return;
        try {
            await this.device.sendCmd({ cmd: 'games.clear' }, { timeoutMs: 8000 });
            toast('Library cleared');
            await this.refreshBoxLibrary();
        } catch (e) {
            toast(e.message || 'Clear failed', true);
        }
    }

    async resetBoxStats() {
        const ok = await this.confirmDialog({
            title: 'Reset usage stats?',
            message: `This resets pull/write counters on the ${this.deviceShort()}.`,
            okLabel: 'Reset stats',
        });
        if (!ok) return;
        try {
            await this.device.sendCmd({ cmd: 'stats.reset' }, { timeoutMs: 5000 });
            toast('Stats reset');
            await this.refreshBoxLibrary();
        } catch (e) {
            toast(e.message || 'Reset failed', true);
        }
    }

    async onSend() {
        const inp = document.getElementById('user-input');
        const msg = inp.value.trim();
        if (!msg || this.isGenerating) {
            dbg('chat', `onSend() ignored (empty=${!msg}, isGenerating=${this.isGenerating})`);
            return;
        }
        dbg('chat', `onSend(): "${msg}"`);
        inp.value = '';
        // Remove starter chips once conversation starts
        document.querySelector('.starter-chips')?.remove();
        document.querySelectorAll('.choice-chips').forEach(el => el.remove());
        addMsg(msg, 'user');
        if (this.interview) {
            await this.answerInterview(msg);
            return;
        }
        this.dirty = true;
        await this.callClaude(msg);
    }

    /**
     * The API key from the passphrase, or null after telling the teacher
     * why (no passphrase, no key, wrong passphrase, knowledge not loaded).
     */
    resolveApiKey() {
        const modalPass = document.getElementById('modal-passphrase');
        const passphrase = modalPass?.value?.trim() || '';
        dbg('chat', `callClaude() — passphrase field length ${passphrase.length}, hasEncryptedKey=${hasEncryptedKey()}`);

        if (!passphrase) {
            dbgWarn('chat', 'blocked: passphrase input is empty — re-showing modal');
            toast('Enter the magic code first.', true);
            showOverlay('modal-overlay');
            return;
        }
        if (!hasEncryptedKey()) {
            dbgWarn('chat', 'blocked: encrypted key never loaded (see [auth] logs above for fetch failure)');
            toast('No API key configured.', true);
            return;
        }

        const apiKey = getApiKey(passphrase);
        if (!apiKey) {
            dbgWarn('chat', 'blocked: passphrase decrypted but did not produce a valid sk-ant- key');
            toast('Wrong passphrase — try again.', true);
            return;
        }
        dbg('chat', 'passphrase accepted — API key derived, calling Claude');

        if (this.knowledgeError) {
            // Without the knowledge base the model answers from general
            // memory and invents device behavior. Refuse instead.
            addMsg(`The assistant's knowledge files did not load, so it cannot help right now. `
                + `Reload the page; if this keeps happening, contact the SmartPlayground team. `
                + `(${this.knowledgeError})`, 'system');
            return null;
        }
        return apiKey;
    }

    async callClaude(userMsg) {
        const apiKey = this.resolveApiKey();
        if (!apiKey) return;

        this.chatHistory.push({ role: 'user', content: userMsg });
        addThinkingMsg();
        this.isGenerating = true;

        try {
            const body = JSON.stringify(buildRequestBody({
                system: this.getSystemBlocks(),
                history: this.chatHistory,
            }));
            dbg('chat', `POST /v1/messages (stream) — ${this.chatHistory.length} history message(s)`);

            const resp = await fetch('https://api.anthropic.com/v1/messages', {
                method: 'POST',
                headers: requestHeaders(apiKey),
                body,
            });
            dbg('chat', `response status: ${resp.status}`);

            if (!resp.ok) {
                removeTyping();
                const errData = await resp.json().catch(() => ({}));
                const errMsg = errData?.error?.message ?? `Could not reach the AI (${resp.status}). Check your network.`;
                dbgError('chat', `API error (${resp.status}): ${errMsg}`, errData);
                addMsg(errMsg, 'system');
                toast(errMsg, true);
                this.chatHistory.pop();
                return;
            }

            // Stream the reply into one bot message, redrawn at most every
            // STREAM_RENDER_MS so long code blocks do not re-render per token.
            let botDiv = null;
            let pending = null;
            let renderTimer = null;
            const draw = () => {
                renderTimer = null;
                if (pending === null) return;
                if (!botDiv) { removeTyping(); botDiv = addMsg('', 'bot'); }
                renderMarkdown(botDiv, stripAllMarkers(pending));
                const box = document.getElementById('chat-box');
                box.scrollTop = box.scrollHeight;
            };
            const result = await readMessageStream(resp, (text) => {
                pending = text;
                if (!renderTimer) renderTimer = setTimeout(draw, STREAM_RENDER_MS);
            });
            if (renderTimer) { clearTimeout(renderTimer); }
            removeTyping();
            dbg('chat', `stream done: stop_reason=${result.stopReason}, first text ${result.firstTextMs} ms`, result.usage);

            if (result.error) {
                const msg = `The AI stopped with an error: ${result.error.message || result.error.type}. Try again.`;
                dbgError('chat', 'stream error event', result.error);
                if (botDiv) botDiv.remove();
                addMsg(msg, 'system');
                this.chatHistory.pop();
                return;
            }
            if (result.stopReason === 'refusal') {
                dbgWarn('chat', 'refusal', result.stopDetails);
                if (botDiv) botDiv.remove();
                addMsg('The AI declined to answer that request. Try rewording it.', 'system');
                this.chatHistory.pop();
                return;
            }
            const rawReply = result.text;
            const reply = stripAllMarkers(rawReply);
            if (!botDiv) botDiv = addMsg('', 'bot');
            renderMarkdown(botDiv, reply);

            if (result.stopReason === 'max_tokens') {
                // A truncated reply usually ends mid-code-block; extracting it
                // would put broken code in the editor.
                dbgWarn('chat', 'reply truncated at max_tokens');
                addMsg('The reply was too long and got cut off, so your game was not changed. '
                    + 'Ask for a simpler or shorter version.', 'system');
                this.chatHistory.pop();
                return;
            }

            const nfcCards = parseNfcCards(rawReply);
            const gameName = parseGameName(rawReply);
            const choices = parseChoices(rawReply);
            const simSettings = parseGameSettings(rawReply);
            dbg('chat', `reply received (${rawReply.length} chars)`, { nfcCards, gameName, choices, simSettings });
            this.chatHistory.push({ role: 'assistant', content: trimForHistory(reply) });

            // A reply may carry one file per device: the markers were read
            // off rawReply before they were stripped for display. Only a
            // complete game file for its device replaces the editor; a
            // snippet stays in the chat.
            const blocks = extractCodeBlocks(rawReply);
            const games = [];
            const snippets = [];
            for (const blk of blocks) {
                // Signature only: an over-size wand file is still a complete
                // game, kept in the editor with a warning below.
                const [ok, err] = validateGameSignature(blk.code, blk.role);
                if (ok) {
                    games.push(blk);
                } else {
                    snippets.push(blk);
                    dbg('chat', `[${blk.role}] block is not a complete game, editor unchanged: ${err}`);
                }
            }
            if (snippets.length && !games.length) {
                addMsg('This is a code snippet — your game was not changed.', 'system');
            }
            if (games.length) {
                if (gameName) {
                    this.gameName = gameName;
                    dbg('chat', `game name from marker: ${gameName}`);
                }
                const label = userMsg.length > 40 ? userMsg.slice(0, 40) + '…' : userMsg;
                const seen = [];
                for (const { role, code } of games) {
                    dbg('chat', `[${role}] game file extracted (${code.length} chars)`);
                    if (role === 'wand' && codeBytes(code) > MAX_WAND_GAME_BYTES) {
                        addMsg(`This wand game is ${Math.round(codeBytes(code) / 1000)} KB, over the `
                            + `${MAX_WAND_GAME_BYTES / 1000} KB the wand can load. Ask for a shorter version before sending it.`,
                            'system');
                    }
                    setCode(code, role);
                    saveVersion(code, label, role);
                    seen.push(role);
                }
                // Show the first role this reply wrote for, so the editor is
                // looking at something the teacher just asked for.
                setActiveRole(seen[0]);
                this.syncRoleRail();
                addMsg(seen.length > 1
                    ? `Code updated for ${seen.join(' and ')} (v${getVersionCount()})`
                    : `Code updated (v${getVersionCount()})`, 'system');
                // New code replaces the old tag declaration outright: no marker
                // means this version reads no named tags, not "keep the old ones".
                this.declaredTags = nfcCards?.length ? nfcCards : null;
                dbg('chat', `declared tags from [NFC_CARDS]: [${(nfcCards || []).join(', ')}]`);
                // The same for the simulator's settings: none means the defaults.
                this.simSettings = simSettings;
                this.gameDesc = userMsg;
                this.dirty = true;
                this.updatePreview();
            } else if (!blocks.length) {
                dbg('chat', 'no code block found in reply — editor unchanged');
            }
            if (choices?.length) this.renderChoiceChips(choices);
        } catch (e) {
            removeTyping();
            dbgError('chat', `network/fetch error: ${e.message}`, e);
            const msg = 'Network error — check your connection and try again.';
            addMsg(msg, 'system');
            toast(msg, true);
        } finally {
            this.isGenerating = false;
            dbg('chat', 'callClaude() finished');
        }
    }
}

function escapeHtml(s) {
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

/** Fill any [data-icon] host with an inline SVG from icons.js. */
function hydrateIcons(root = document) {
    root.querySelectorAll('[data-icon]').forEach((el) => {
        if (el.dataset.iconHydrated) return;
        const name = el.dataset.icon;
        const size = Number(el.dataset.iconSize) || 15;
        const stroke = el.dataset.iconStroke;
        el.innerHTML = iconSvg(name, { size, strokeWidth: stroke });
        el.dataset.iconHydrated = '1';
    });
}

function relativeTime(ts) {
    if (!ts) return 'saved';
    const diff = Date.now() - Number(ts);
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins} min ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`;
    const days = Math.floor(hours / 24);
    if (days === 1) return 'yesterday';
    if (days < 14) return `${days} days ago`;
    if (days < 60) return `${Math.floor(days / 7)} week${days < 21 ? '' : 's'} ago`;
    return new Date(ts).toLocaleDateString();
}

const app = new App();
app.init();
