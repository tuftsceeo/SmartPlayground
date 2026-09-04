import { loadEncryptedKey, initAuthModal, getApiKey, hasEncryptedKey } from './auth.js';
import {
    addMsg, addThinkingMsg, removeTyping, extractCode, parseNfcCards, stripNfcMarker,
    parseGameName, stripGameNameMarker,
    trimForHistory, loadKnowledgeBase, getKnowledgeText, getKnowledgeFileCount,
} from './chat.js';
import {
    initEditor, getCode, setCode, saveVersion, updateVersionUI,
    onPrevVersion, onNextVersion, getVersionCount, onDownload,
} from './editor.js';
import { uploadPayload } from './upload.js';
import { showTagChecklist, deriveRequiredTags, tagCountLabel } from './nfc.js';
import { EXAMPLES, CATEGORIES, findExample } from './examples.js';
import { showView, showOverlay, hideOverlay, setConnectionBadge, toast, setSendProgress } from './router.js';
import { createDeviceLink } from './device/bboxDeviceLink.js';
import { subscribe, getEntries, toText } from './device/serialLog.js';
import { setWorkspaceHandler } from './markdown.js';
import { dbg, dbgWarn, dbgError } from './debug.js';
import { loadUiMode, toggleUiMode } from './uiMode.js';
import { loadSavedGames, saveGame, findSavedGame } from './library.js';
import { scanCapabilities } from './sim/codeCapabilities.js';
import { buildComponentChecklist, checklistLines } from './checklist.js';
import { validateGameName, slugify } from './gameName.js';
import { initPaneSplit } from './paneSplit.js';

const SILENCE_LIMIT_MS = 15000;
const SILENCE_SERVE_MS = 45000;
const REBOOT_LIMIT_MS = 20000;
const WATCHDOG_TICK_MS = 2000;
/* A running Box sends a heartbeat every HEARTBEAT_MS (5s, bbox_server.py) on
   top of its boot identity, and GRACE_S is now 1s. So total silence for this long
   does not mean "still waking up" -- it means the firmware is not running (or
   the port we opened is not the one it talks on). Say so instead of waiting
   forever. */
const WAITING_LIMIT_MS = 12000;
/* The Box volunteers its identity only once, at boot. If we opened the port
   after it booted, that one announcement is already gone, so re-ask on a cadence rather
   than betting everything on a single probe that may have crossed a busy
   moment. Replies arrive as ordinary `identity` events and promote us to live.
   This is a convenience, not the liveness test: `heartbeat` alone reaches live
   within 5s regardless. */
const IDENTIFY_NUDGE_MS = 2500;

const SYSTEM_PROMPT_BASE = `You are an AI assistant helping teachers write MicroPython games for the PlaygroundV5 wand.

RULES:
- All board details, APIs, and hardware specs are in the KNOWLEDGE BASE below. Reference it.
- Generated code MUST follow the jumpin.py format with def play(nfc, leds, buz, accel, i2c, enow)
- Put all code inside a fenced code block: \`\`\`python ... \`\`\`
- Do NOT use f-strings — they crash on this MicroPython build. Use % formatting only.
- Keep explanations concise — the code block is auto-extracted to the editor
- If the user sends serial output (prefixed with [HW]:), help debug it
- Always include try/finally cleanup and periodic NFC stop-tag polling
- Default to simple, working examples over complex ones
- If the game reads NFC tags with specific values, include exactly one line formatted as [NFC_CARDS: "value1", "value2"] listing every tag value the game uses.
- After the code block, include exactly one line naming the game: [GAME_NAME: Short Pretty Name]`;

/** Same placeholder-and-play() check the editor's code drawer uses to
 * decide there's real code worth doing anything with. */
function isRunnableCode(code) {
    const trimmed = (code || '').trim();
    return !!trimmed && !trimmed.startsWith('# AI-generated') && /def\s+play\s*\(/.test(trimmed);
}

class App {
    constructor() {
        this.device = createDeviceLink();
        this.chatHistory = [];
        this.isGenerating = false;
        this.currentExample = null;
        this.gameName = 'Your game';
        this.gameDesc = '';
        this.requiredTags = ['jumpin'];
        this.galleryFilter = 'all';
        this.galleryMode = 'examples'; // 'examples' | 'saved'
        this.serialOpen = false; // serial log drawer — NOT the port
        this.dirty = false;
        this.pendingSendAfterConnect = false;
        this._sim = null;
        this._simLoadPromise = null;
        this._simLastSource = null;
        this._simPendingSource = null;
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
        this._silenceLimitMs = SILENCE_LIMIT_MS;
        this._boxGames = []; // last games.list from the Box
        this._pendingReplaceSlug = null;
    }

    async init() {
        dbg('app', 'init() starting');
        initEditor();
        dbg('app', 'editor initialized');
        updateVersionUI();
        this.bindEvents();
        dbg('app', 'event listeners bound');
        initPaneSplit();
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

        const knowledge = await loadKnowledgeBase();
        if (knowledge) {
            dbg('app', `knowledge base loaded (${getKnowledgeFileCount()} file(s))`);
        } else {
            dbgWarn('app', 'knowledge base did not load — chat will run without project context');
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

    getSystemPrompt() {
        const knowledge = getKnowledgeText();
        return knowledge
            ? SYSTEM_PROMPT_BASE + '\n\nPROJECT KNOWLEDGE BASE:\n' + knowledge
            : SYSTEM_PROMPT_BASE;
    }

    applyUiMode(mode) {
        const advanced = mode === 'advanced';
        const panel = document.getElementById('serial-log-panel');
        const rail = document.querySelector('.role-rail');
        const gear = document.getElementById('btn-mode-gear');

        if (panel) {
            if (advanced) {
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
        if (rail) rail.classList.toggle('advanced', advanced);
        if (gear) {
            gear.title = advanced ? 'Switch to simple mode' : 'Switch to advanced mode';
        }
        // The element itself may not be upgraded yet (setupSim() lazy-loads
        // its module) — setting the attribute is harmless either way and
        // takes effect once it is.
        document.getElementById('wand-sim')?.toggleAttribute('advanced', advanced);
        const boxLib = document.getElementById('btn-box-library');
        if (boxLib) boxLib.classList.toggle('hidden', !advanced);
        dbg('app', `UI mode: ${mode}`);
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
        // Start hidden — simple mode default; advanced reveals via applyUiMode
        panel.classList.add('hidden');

        subscribe((entry) => {
            if (entry === null) {
                pre.textContent = '';
                if (preview) preview.textContent = '';
                return;
            }
            const lines = getEntries().slice(-80).map((e) => {
                const tag = e.dir.toUpperCase().padEnd(5);
                return `${tag} ${e.text}`;
            });
            pre.textContent = lines.join('\n');
            pre.scrollTop = pre.scrollHeight;
            if (preview && lines.length) {
                preview.textContent = lines[lines.length - 1];
            }
        });

        document.getElementById('btn-serial-toggle').addEventListener('click', () => {
            this.serialOpen = !this.serialOpen;
            panel.classList.toggle('open', this.serialOpen);
            this.reserveSerialPadding();
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
                || this.link.state === 'opening' || this.link.state === 'no-answer') {
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
                ssid: obj.ssid,
            };
            // Prefer mode==SERVE for silence threshold once mode events exist.
            this._silenceLimitMs = obj.mode === 'SERVE' ? SILENCE_SERVE_MS : SILENCE_LIMIT_MS;
            if (this.link.state === 'waiting' || this.link.state === 'rebooting'
                || this.link.state === 'no-answer') {
                this.setLinkState('live');
            } else {
                this.paintLink();
            }
        });
        this.device.on('armed', (obj) => {
            dbg('device', 'event: armed', obj);
            this._noteMessage(obj);
            // Fallback until mode events are trusted: raise silence while serving.
            if (this.link.boxMode !== 'SERVE') {
                this._silenceLimitMs = SILENCE_SERVE_MS;
            }
        });
        this.device.on('card_present', (obj) => dbg('device', 'event: card_present', obj));
        this.device.on('card_written', (obj) => dbg('device', 'event: card_written', obj));
        this.device.on('fatal', (obj) => {
            dbgError('device', 'event: fatal', obj);
            toast(obj?.msg || 'The Box reported a serious error — check the cable.', true);
        });
        this.device.on('error', (obj) => dbgError('device', 'event: error', obj));
        this.device.on('wrong_device', (obj) => {
            dbgWarn('device', 'event: wrong_device', obj);
            toast("That device isn't a Broadcast Box — check what's plugged in.", true);
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
            toast('Broadcast Box disconnected — check the cable.', true);
        });

        if (navigator.serial) {
            navigator.serial.addEventListener('disconnect', () => {
                dbgWarn('device', 'navigator.serial disconnect event fired');
                if (this.link.state !== 'idle' && this.link.state !== 'lost') {
                    this.onSerialDrop();
                }
            });
        } else {
            dbgWarn('device', 'Web Serial API not available in this browser (need Chrome/Edge)');
        }
    }

    _noteMessage(obj) {
        this.link.lastMsgAt = Date.now();
        if (obj?.type === 'identity') this.link.deviceInfo = obj;
        this._clearRebootTimer();
        if (obj?.type && this.link.boxMode !== 'SERVE') {
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
        if (state === 'live') {
            this._clearRebootTimer();
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
        setConnectionBadge(this.link);
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
            if (waited > WAITING_LIMIT_MS) {
                dbgWarn('device', `no reply ${waited}ms after port open → no-answer`);
                this.setLinkState('no-answer');
                // Deliberately does not assert the Box is broken: connecting
                // during a serve can block its main loop for ~30s
                // (SOCK_REPLY_TIMEOUT_S), which looks identical from here.
                // The state is not terminal — any inbound message promotes
                // straight back to live — so the copy suggests, not accuses.
                toast("The Box isn't answering. If it stays quiet, try Restart the Box.", true);
            }
            return;
        }
        if (!this.link.lastMsgAt) return;
        const age = Date.now() - this.link.lastMsgAt;
        if (s === 'live' || s === 'stuck') {
            if (age > this._silenceLimitMs) {
                dbgWarn('device', `watchdog silence ${age}ms > ${this._silenceLimitMs}`);
                this.setLinkState('lost');
                toast('Lost the Box — check the cable.', true);
                this.device.disconnect().catch(() => {});
            }
        }
    }

    /** Re-ask the Box to identify itself while waiting. Harmless to repeat:
     *  do_identify() just replies, and each send carries a fresh id. */
    _armIdentifyNudge() {
        if (this._identifyNudgeTimer) return;
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
                toast('The Box did not come back — check the cable.', true);
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
        toast('Broadcast Box disconnected — check the cable.', true);
    }

    bindEvents() {
        document.getElementById('btn-scratch').addEventListener('click', () => this.openWorkspace());
        document.getElementById('btn-gallery').addEventListener('click', () => {
            this.galleryMode = 'examples';
            showView('gallery');
            this.renderGallery();
        });
        document.getElementById('btn-saved').addEventListener('click', () => {
            this.galleryMode = 'saved';
            showView('gallery');
            this.renderGallery();
        });
        document.getElementById('gallery-search').addEventListener('input', () => this.renderGallery());
        document.getElementById('btn-detail-back').addEventListener('click', () => {
            this.galleryMode = 'examples';
            showView('gallery');
            this.renderGallery();
        });
        document.getElementById('btn-remix').addEventListener('click', () => this.remixCurrentExample());
        document.getElementById('btn-use-as-is').addEventListener('click', () => this.useExampleAsIs());
        document.getElementById('btn-send').addEventListener('click', () => this.onSend());
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
        document.getElementById('btn-connect-usb').addEventListener('click', () => this.onConnect());
        document.getElementById('btn-connect-cancel').addEventListener('click', () => {
            this.pendingSendAfterConnect = false;
            hideOverlay('connect-overlay');
        });
        document.getElementById('btn-connect-header').addEventListener('click', () => this.toggleConnect());
        document.getElementById('btn-restart-box')?.addEventListener('click', () => this.onRestartBox());
        document.getElementById('btn-send-confirm').addEventListener('click', () => this.confirmSend());
        document.getElementById('btn-send-cancel').addEventListener('click', () => hideOverlay('send-confirm-overlay'));
        document.getElementById('btn-box-library')?.addEventListener('click', () => this.openBoxLibrary());
        document.getElementById('btn-box-lib-close')?.addEventListener('click', () => hideOverlay('box-library-overlay'));
        document.getElementById('btn-box-lib-refresh')?.addEventListener('click', () => this.refreshBoxLibrary());
        document.getElementById('btn-box-lib-clear')?.addEventListener('click', () => this.clearBoxLibrary());
        document.getElementById('btn-box-stats-reset')?.addEventListener('click', () => this.resetBoxStats());

        document.getElementById('btn-mode-gear').addEventListener('click', () => toggleUiMode());
        document.getElementById('btn-home').addEventListener('click', () => this.goHome());
        document.getElementById('btn-gallery-home').addEventListener('click', () => showView('splash'));
        document.getElementById('btn-detail-home').addEventListener('click', () => showView('splash'));
        document.getElementById('btn-save-game').addEventListener('click', () => this.onSaveGame());
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

    goHome() {
        const hasWork = getVersionCount() > 0 || this.chatHistory.length > 0 || this.dirty;
        if (hasWork) {
            const saveFirst = confirm(
                'You have unsaved work in this session.\n\nOK = Save then go home\nCancel = Stay here'
            );
            if (!saveFirst) return;
            this.onSaveGame();
        }
        this._sim?.stop();
        showView('splash');
    }

    onSaveGame() {
        const code = getCode();
        if (!code.trim() || code.trim().startsWith('# AI-generated')) {
            toast('Nothing to save yet — generate or load some code first.', true);
            return;
        }
        const entry = saveGame({
            name: this.gameName,
            desc: this.gameDesc,
            code,
            requiredTags: this.requiredTags,
            chatHistory: this.chatHistory.slice(),
        });
        this.dirty = false;
        toast(`Saved “${entry.name}”`);
        dbg('app', `saved game ${entry.id}`);
    }

    setupGallery() {
        const chips = document.getElementById('gallery-chips');
        CATEGORIES.forEach((c) => {
            const el = document.createElement('div');
            el.className = 'chip' + (c.id === 'all' ? ' active' : '');
            el.textContent = c.label;
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

        if (this.galleryMode === 'saved') {
            title.textContent = '📂 My saved games';
            chips.classList.add('hidden');
            const saved = loadSavedGames().filter((g) => {
                if (!q) return true;
                return (g.name || '').toLowerCase().includes(q) || (g.desc || '').toLowerCase().includes(q);
            });
            if (saved.length === 0) {
                const empty = document.createElement('p');
                empty.style.cssText = 'grid-column:1/-1;color:#8b859a;padding:24px;';
                empty.textContent = 'No saved games yet — open a workspace and tap 💾 Save.';
                grid.appendChild(empty);
                return;
            }
            saved.forEach((g) => {
                const card = document.createElement('div');
                card.className = 'example-card saved-card';
                card.dataset.id = g.id;
                const when = g.updatedAt ? new Date(g.updatedAt).toLocaleString() : '';
                card.innerHTML =
                    `<div class="example-thumb">saved</div>` +
                    `<h3>${escapeHtml(g.name)}</h3>` +
                    `<p>${escapeHtml(g.desc || 'Saved session')}</p>` +
                    (when ? `<div class="tag-badge">${escapeHtml(when)}</div>` : '');
                card.addEventListener('click', () => this.openSavedGame(g.id));
                grid.appendChild(card);
            });
            return;
        }

        title.textContent = '📚 Example games';
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
                `<div class="example-thumb">${ex.id} clip</div>` +
                `<h3>${ex.emoji} ${ex.name}</h3>` +
                `<p>${ex.description}</p>` +
                (ex.tagNote ? `<div class="tag-badge">${ex.tagNote}</div>` : '');
            card.addEventListener('click', () => this.openDetail(ex.id));
            grid.appendChild(card);
        });
    }

    openSavedGame(id) {
        const g = findSavedGame(id);
        if (!g) {
            toast('Could not find that saved game.', true);
            return;
        }
        this.gameName = g.name;
        this.gameDesc = g.desc || '';
        this.requiredTags = g.requiredTags || ['jumpin'];
        this.chatHistory = Array.isArray(g.chatHistory) ? g.chatHistory.slice() : [];
        showView('workspace');
        const box = document.getElementById('chat-box');
        box.innerHTML = '';
        addMsg(`Loaded saved game “${g.name}”.`, 'system');
        if (g.code) {
            setCode(g.code);
            saveVersion(g.code, 'Loaded from library');
        }
        this.dirty = false;
        this.updatePreview();
    }

    openDetail(id) {
        const ex = findExample(id);
        if (!ex) {
            dbgWarn('app', `openDetail("${id}") — no matching example found`);
            return;
        }
        dbg('app', `openDetail("${id}")`, ex);
        this.currentExample = ex;
        document.getElementById('detail-title').textContent = `${ex.emoji} ${ex.name}`;
        document.getElementById('detail-desc').textContent = ex.description;
        const note = document.getElementById('detail-tag-note');
        if (ex.tagNote) {
            note.textContent = `needs ${ex.tags.length} NFC tags — ${ex.tagNote.toLowerCase()}`;
            note.classList.remove('hidden');
        } else {
            note.classList.add('hidden');
        }
        showView('detail');
    }

    renderStarterChips() {
        const box = document.getElementById('chat-box');
        if (box.querySelector('.starter-chips')) return;
        const wrap = document.createElement('div');
        wrap.className = 'starter-chips';
        const intro = document.createElement('div');
        intro.className = 'msg system';
        intro.textContent = 'Try one of these ideas — tap a chip to fill the box, then edit and send:';
        box.appendChild(intro);
        EXAMPLES.slice(0, 5).forEach((ex) => {
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'starter-chip';
            chip.textContent = `${ex.emoji} ${ex.starterPrompt}`;
            chip.addEventListener('click', () => {
                const inp = document.getElementById('user-input');
                inp.value = ex.starterPrompt;
                inp.focus();
                inp.style.height = 'auto';
                inp.style.height = Math.min(inp.scrollHeight, 120) + 'px';
            });
            wrap.appendChild(chip);
        });
        box.appendChild(wrap);
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

    remixCurrentExample() {
        if (!this.currentExample) {
            dbgWarn('app', 'remixCurrentExample() called with no currentExample set');
            return;
        }
        dbg('app', `remixCurrentExample("${this.currentExample.name}")`);
        this.gameName = this.currentExample.name;
        this.gameDesc = this.currentExample.description;
        this.requiredTags = [...this.currentExample.tags];
        if (this.currentExample.startingCode) {
            setCode(this.currentExample.startingCode);
            saveVersion(this.currentExample.startingCode, `${this.currentExample.name} (remix base)`);
            this.dirty = true;
        }
        this.openWorkspace(this.currentExample.starterPrompt);
        addMsg(`Let's remix ${this.currentExample.name}! What would you like to change?`, 'system');
        this.updatePreview();
    }

    async useExampleAsIs() {
        if (!this.currentExample) {
            dbgWarn('app', 'useExampleAsIs() called with no currentExample set');
            return;
        }
        dbg('app', `useExampleAsIs("${this.currentExample.name}")`);
        this.gameName = this.currentExample.name;
        this.gameDesc = this.currentExample.description;
        this.requiredTags = [...this.currentExample.tags];
        showView('workspace');
        addMsg(`Using ${this.currentExample.name} as-is.`, 'system');

        // TODO(phase E): startingCode required for send — now wired below
        if (this.currentExample.startingCode) {
            setCode(this.currentExample.startingCode);
            saveVersion(this.currentExample.startingCode, `${this.currentExample.name} as-is`);
            this.dirty = true;
        } else {
            dbgWarn('app', `useExampleAsIs("${this.currentExample.id}") — no startingCode; send may fail`);
            toast('This example has no starter code yet.', true);
            this.updatePreview();
            return;
        }

        this.updatePreview();
        await this.startSendFlow();
    }

    updatePreview() {
        const code = getCode();

        this.requiredTags = deriveRequiredTags(null, code, this.gameName.toLowerCase());
        if (this.currentExample?.tags?.length > this.requiredTags.length) {
            this.requiredTags = [...this.currentExample.tags];
        }

        const runnable = isRunnableCode(code);
        document.getElementById('preview-panel').classList.toggle('hidden', !runnable);
        document.querySelector('.ws-body')?.classList.toggle('no-sim', !runnable);

        if (runnable) {
            this.setupSim();
            this.pushSimSource(code);
        }
    }

    /** Lazily load the <wand-sim> module the first time it's needed —
     * Pyodide plus its ~37 game/shim files is a real download, and booting
     * it while the teacher is still typing their first chat message would
     * only add to that wait. Safe to call repeatedly; the import runs once. */
    setupSim() {
        if (this._simLoadPromise) return this._simLoadPromise;
        dbg('app', 'setupSim() — loading wand-sim module');
        this._simLoadPromise = import('../../../Simulator/wand-sim.js')
            .then(() => {
                this._sim = document.getElementById('wand-sim');
                const restartBtn = document.getElementById('btn-sim-restart');
                this._sim.addEventListener('sim-ready', () => {
                    restartBtn.disabled = false;
                });
                restartBtn.addEventListener('click', () => {
                    this.hideSimNotice();
                    this._sim.restart();
                });
                this._sim.addEventListener('sim-error', (e) => {
                    const { message, phase } = e.detail || {};
                    dbgError('sim', `sim-error (${phase}): ${message}`);
                    this.showSimNotice(phase);
                });
                if (this._simPendingSource !== null) {
                    const pending = this._simPendingSource;
                    this._simPendingSource = null;
                    this.pushSimSource(pending);
                }
            })
            .catch((err) => {
                dbgError('sim', 'failed to load wand-sim module', err);
            });
        return this._simLoadPromise;
    }

    /** Push code into the sim only when it actually changed — the element's
     * source setter reloads (and would restart the running game)
     * unconditionally, and updatePreview() runs on every keystroke-adjacent
     * chat/version event, not just real code changes. Only marks the code
     * as "sent" (_simLastSource) once it's actually reached the element —
     * setupSim() is still loading, this just queues it for that resolve. */
    pushSimSource(code) {
        if (!this._sim) {
            this._simPendingSource = code;
            return;
        }
        if (code === this._simLastSource) return;
        this._simLastSource = code;
        this.hideSimNotice();
        this._sim.source = code;
    }

    /** A pydiodide failure (a syntax error, an unsupported import, a
     * traceback out of play()) should never read as a scary raw error to a
     * kindergarten teacher — just a calm note that this one is better
     * tested on the real device. The raw message still goes to the debug
     * console (see setupSim() above) so nothing is actually swallowed. */
    showSimNotice(phase) {
        const el = document.getElementById('sim-notice');
        if (!el) return;
        el.textContent = phase === 'boot'
            ? "The practice window isn't available right now — you can still send this game to your wand."
            : 'This game is a bit too tricky for the practice window — send it to your wand to try it for real.';
        el.classList.remove('hidden');
    }

    hideSimNotice() {
        document.getElementById('sim-notice')?.classList.add('hidden');
    }

    renderComponentList(targetId) {
        const code = getCode();
        const caps = scanCapabilities(code);
        const items = buildComponentChecklist(caps, this.requiredTags);
        const el = document.getElementById(targetId);
        if (!el) return;
        el.innerHTML = '';
        checklistLines(items).forEach((line) => {
            const li = document.createElement('li');
            li.textContent = line;
            el.appendChild(li);
        });
    }

    async onConnect() {
        dbg('app', 'onConnect() — requesting serial port');
        this.renderComponentList('connect-components');
        const errEl = document.getElementById('connect-error');
        errEl.textContent = '';
        this.setLinkState('opening');
        try {
            await this.device.connect();
            dbg('app', 'device.connect() resolved (port open; awaiting heartbeat/identity)');
            hideOverlay('connect-overlay');
            this.setLinkState('waiting');
            if (this.pendingSendAfterConnect) {
                toast('Connected — waking up the Box, then we will send…');
            } else {
                toast('Connected — waking up the Box…');
            }
        } catch (e) {
            dbgError('app', `device.connect() rejected: ${e.message}`, e);
            errEl.textContent = "Couldn't find a Broadcast Box — check the cable.";
            this.setLinkState('idle');
        }
    }

    /** Standalone header "Connect"/"Disconnect"/"Cancel" toggle. */
    async toggleConnect() {
        const s = this.link.state;
        if (s === 'opening' || s === 'sending' || s === 'rebooting') return;
        if (s === 'waiting') {
            dbg('app', 'toggleConnect() — cancel waiting');
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
        // idle or lost → connect
        this.pendingSendAfterConnect = false;
        this.renderComponentList('connect-components');
        showOverlay('connect-overlay');
        await this.onConnect();
    }

    async onRestartBox() {
        dbg('app', 'onRestartBox() — restartFirmware');
        toast('Nudging the Box…');
        this.setLinkState('rebooting');
        this._armRebootTimer();
        try {
            const state = await this.device.restartFirmware();
            if (state === 'running') {
                this.setLinkState('live');
                toast('Box is back.');
            } else {
                toast('Still waiting for the Box…', true);
            }
        } catch (e) {
            dbgError('app', `restartFirmware failed: ${e.message}`, e);
            toast('Could not restart the Box — try unplugging.', true);
            this.setLinkState('stuck');
        }
    }

    async startSendFlow() {
        dbg('app', 'startSendFlow() — "Send to Broadcast Box" clicked');
        const code = getCode();
        if (!code.trim() || code.trim().startsWith('# AI-generated')) {
            dbgWarn('app', 'startSendFlow() aborted: no code in editor');
            toast('Generate some code first — describe your game in chat.', true);
            return;
        }
        this.requiredTags = deriveRequiredTags(null, code, this.gameName.toLowerCase());
        // Prefer example tags when present and longer
        if (this.currentExample && this.currentExample.tags && this.currentExample.tags.length > this.requiredTags.length) {
            this.requiredTags = [...this.currentExample.tags];
        }
        dbg('app', `required tags: [${this.requiredTags.join(', ')}]`);

        if (this.requiredTags.length > 1) {
            const n = this.requiredTags.length;
            dbg('app', `showing tag checklist for ${n} tags`);
            const result = await showTagChecklist({
                title: `This game needs ${n} tags`,
                subtitle: tagCountLabel(n) || 'one per card',
                tags: this.requiredTags,
            });
            dbg('app', `tag checklist resolved: ${result.action}`);
            if (result.action === 'back') return;
        }

        if (this.link.state !== 'live') {
            dbg('app', 'device not live — showing connect overlay');
            this.pendingSendAfterConnect = true;
            this.renderComponentList('connect-components');
            showOverlay('connect-overlay');
            return;
        }

        this.showSendConfirm();
    }

    async showSendConfirm() {
        document.getElementById('send-confirm-sub').textContent = '🪄 Wand code for the Broadcast Box';
        const nameInput = document.getElementById('send-game-name');
        const errEl = document.getElementById('send-name-error');
        if (errEl) errEl.textContent = '';
        if (nameInput) {
            nameInput.value = this.gameName && this.gameName !== 'Your game' ? this.gameName : '';
        }
        this._pendingReplaceSlug = null;
        this.renderComponentList('send-confirm-components');
        document.getElementById('send-progress-wrap').classList.add('hidden');
        // Refresh Box game list when live so duplicate checks work.
        if (this.link.state === 'live') {
            try {
                await this.fetchBoxGames();
            } catch (e) {
                dbgWarn('app', `games.list before send failed: ${e.message}`);
            }
        }
        showOverlay('send-confirm-overlay');
    }

    async confirmSend() {
        dbg('app', 'confirmSend() — "Send" clicked on confirm overlay');
        const code = getCode();
        const nameInput = document.getElementById('send-game-name');
        const errEl = document.getElementById('send-name-error');
        const pretty = (nameInput?.value || this.gameName || '').trim();
        const existing = (this._boxGames || []).map((g) => g.slug);
        let check = validateGameName(pretty, {
            existingSlugs: existing,
            allowReplace: this._pendingReplaceSlug === slugify(pretty),
        });
        if (!check.ok && check.reason === 'replace') {
            const ok = confirm(
                `"${pretty}" is already on the Box.\n\nOK = Replace it\nCancel = pick another name`
            );
            if (!ok) {
                if (errEl) errEl.textContent = 'Pick a different name, or confirm Replace.';
                return;
            }
            this._pendingReplaceSlug = check.slug;
            check = validateGameName(pretty, { existingSlugs: existing, allowReplace: true });
        }
        if (!check.ok) {
            if (errEl) errEl.textContent = check.reason || 'Invalid name.';
            toast(check.reason || 'Invalid name.', true);
            return;
        }
        if (errEl) errEl.textContent = '';
        this.gameName = check.pretty;
        const slug = check.slug;
        const destPath = `/flash/games/${slug}.py`;

        document.getElementById('send-progress-wrap').classList.remove('hidden');
        setSendProgress(0, 'Starting…');

        this.setLinkState('sending');
        const result = await uploadPayload(this.device, code, window.onUploadProgress, {
            linkState: 'sending',
            meta: { destPath, destLabel: `${slug}.py`, prettyName: check.pretty },
        });
        dbg('app', 'uploadPayload() result', result);

        hideOverlay('send-confirm-overlay');
        this._pendingReplaceSlug = null;

        if (!result.ok) {
            dbgError('app', `send failed: ${result.error}`);
            toast(result.error || 'Send failed — try again.', true);
            this.setLinkState(this.device.isConnected() ? 'live' : 'lost');
            return;
        }

        this.setLinkState('rebooting');
        this._armRebootTimer();
        dbg('app', 'send succeeded — showing sent banner');
        const banner = document.getElementById('sent-banner');
        banner.classList.remove('hidden');
        setTimeout(() => banner.classList.add('hidden'), 4000);
        toast('Sent! Hold a card on the Box to write the pickup tag.');
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
        if (!list) return;
        if (this.link.state !== 'live') {
            if (status) status.textContent = 'Connect to the Box first (must be live).';
            list.innerHTML = '';
            if (statsEl) statsEl.textContent = '—';
            return;
        }
        if (status) status.textContent = 'Loading…';
        try {
            const games = await this.fetchBoxGames();
            const active = this.link.detail?.active;
            if (status) {
                status.textContent = games.length
                    ? `${games.length} game(s) on the Box. Active: ${active || '—'}`
                    : 'No games on the Box yet — send one from chat.';
            }
            list.innerHTML = '';
            games.forEach((g) => {
                const li = document.createElement('li');
                if (g.slug === active) li.classList.add('active-game');
                const name = document.createElement('span');
                name.className = 'lib-name';
                name.textContent = `${g.name || g.slug}${g.slug === active ? ' ★' : ''} (${g.pulls || 0} pulls)`;
                li.appendChild(name);
                const sel = document.createElement('button');
                sel.className = 'btn-secondary';
                sel.type = 'button';
                sel.textContent = 'Select';
                sel.disabled = g.slug === active;
                sel.addEventListener('click', () => this.selectBoxGame(g.slug));
                li.appendChild(sel);
                const del = document.createElement('button');
                del.className = 'btn-secondary';
                del.type = 'button';
                del.textContent = 'Delete';
                del.addEventListener('click', () => this.deleteBoxGame(g.slug));
                li.appendChild(del);
                list.appendChild(li);
            });
            const stats = await this.device.sendCmd({ cmd: 'stats.get' }, { timeoutMs: 5000 });
            if (statsEl) {
                const pulls = JSON.stringify(stats.pulls || {}, null, 0);
                const writes = JSON.stringify(stats.writes || {}, null, 0);
                statsEl.textContent = `pulls: ${pulls}\nwrites: ${writes}\nsince: ${stats.since || 0}`;
            }
        } catch (e) {
            dbgError('app', `refreshBoxLibrary: ${e.message}`, e);
            if (status) status.textContent = `Could not load library: ${e.message}`;
            toast('Could not talk to the Box library.', true);
        }
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

    async deleteBoxGame(slug) {
        if (!confirm(`Delete "${slug}" from the Box?`)) return;
        try {
            await this.device.sendCmd({ cmd: 'games.delete', slug }, { timeoutMs: 5000 });
            toast(`Deleted ${slug}`);
            await this.refreshBoxLibrary();
        } catch (e) {
            toast(e.message || 'Delete failed', true);
        }
    }

    async clearBoxLibrary() {
        if (!confirm('Remove ALL games from the Box?')) return;
        try {
            await this.device.sendCmd({ cmd: 'games.clear' }, { timeoutMs: 8000 });
            toast('Box library cleared');
            await this.refreshBoxLibrary();
        } catch (e) {
            toast(e.message || 'Clear failed', true);
        }
    }

    async resetBoxStats() {
        if (!confirm('Reset usage stats on the Box?')) return;
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
        addMsg(msg, 'user');
        this.dirty = true;
        await this.callClaude(msg);
    }

    async callClaude(userMsg) {
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

        this.chatHistory.push({ role: 'user', content: userMsg });
        addThinkingMsg();
        this.isGenerating = true;

        try {
            const body = JSON.stringify({
                model: 'claude-sonnet-4-6',
                max_tokens: 16384,
                system: [{ type: 'text', text: this.getSystemPrompt(), cache_control: { type: 'ephemeral' } }],
                messages: this.chatHistory.slice(-10),
            });
            dbg('chat', `POST /v1/messages — ${this.chatHistory.length} history message(s)`);

            const resp = await fetch('https://api.anthropic.com/v1/messages', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-api-key': apiKey,
                    'anthropic-version': '2023-06-01',
                    'anthropic-dangerous-direct-browser-access': 'true',
                },
                body,
            });
            dbg('chat', `response status: ${resp.status}`);

            removeTyping();

            if (!resp.ok) {
                const errData = await resp.json().catch(() => ({}));
                const errMsg = errData?.error?.message ?? `Could not reach the AI (${resp.status}). Check your network.`;
                dbgError('chat', `API error (${resp.status}): ${errMsg}`, errData);
                addMsg(errMsg, 'system');
                toast(errMsg, true);
                this.chatHistory.pop();
                return;
            }

            const data = await resp.json();
            const rawReply = data.content.filter((b) => b.type === 'text').map((b) => b.text).join('');
            const nfcCards = parseNfcCards(rawReply);
            const gameName = parseGameName(rawReply);
            const reply = stripGameNameMarker(stripNfcMarker(rawReply));
            dbg('chat', `reply received (${rawReply.length} chars)`, { nfcCards, gameName });

            removeTyping();
            this.chatHistory.push({ role: 'assistant', content: trimForHistory(reply) });
            addMsg(reply, 'bot');

            if (gameName) {
                this.gameName = gameName;
                dbg('chat', `game name from marker: ${gameName}`);
            }

            const code = extractCode(reply);
            if (code) {
                dbg('chat', `code block extracted (${code.length} chars) — saving version`);
                setCode(code);
                const label = userMsg.length > 40 ? userMsg.slice(0, 40) + '…' : userMsg;
                saveVersion(code, label);
                addMsg(`Code updated (v${getVersionCount()})`, 'system');
                if (nfcCards?.length) {
                    this.requiredTags = nfcCards;
                    dbg('chat', `required tags updated from [NFC_CARDS]: [${nfcCards.join(', ')}]`);
                }
                this.gameDesc = userMsg;
                this.dirty = true;
                this.updatePreview();
            } else {
                dbg('chat', 'no code block found in reply — editor unchanged');
            }
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

const app = new App();
app.init();
