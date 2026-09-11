import { loadEncryptedKey, initAuthModal, getApiKey, hasEncryptedKey } from './auth.js';
import {
    addMsg, addThinkingMsg, removeTyping, extractCodeBlocks, extractIcons,
    stripBlockMarkers, parseNfcCards, stripNfcMarker,
    parseGameName, stripGameNameMarker,
    trimForHistory, loadKnowledgeBase, getKnowledgeText, getKnowledgeFileCount,
    KNOWN_HUBTYPES,
} from './chat.js';
import {
    initEditor, getCode, setCode, saveVersion, updateVersionUI,
    onPrevVersion, onNextVersion, getVersionCount, onDownload,
    setRole, getRole, getRoles, getHubtype, getCodeFor, resetRoles,
} from './editor.js';
import { uploadPayload } from './upload.js';
import { DeviceLink as StationLink } from './station/deviceLink.js';
import { sendToStation, moduleName } from './stationSend.js';
import { renderIconPanel } from './iconPreview/panel.js';
import { openIconEditor } from './iconPreview/editor.js';
import { showTagChecklist, updateTagChecklist } from './nfc.js';
import { EXAMPLES, CATEGORIES, findExample, loadExampleCode } from './examples.js';
import { showView, showOverlay, hideOverlay, setConnectionBadge, toast, setSendProgress, showConnectToast, syncNavTabs } from './router.js';
import { createDeviceLink, deviceShortName, deviceProductName } from './device/bboxDeviceLink.js';
import { subscribe, getEntries, toText } from './device/serialLog.js';
import { setWorkspaceHandler } from './markdown.js';
import { dbg, dbgWarn, dbgError } from './debug.js';
import { loadUiMode, toggleUiMode } from './uiMode.js';
import { loadSavedGames, saveGame, findSavedGame, renameSavedGame, deleteSavedGame } from './library.js';
import { scanCapabilities } from './sim/codeCapabilities.js';
import { buildComponentChecklist } from './checklist.js';
import { validateGameName, slugify } from './gameName.js';
import { buildHardwareReqs, formatHardwareReqs, baselineTags } from './hardware.js';
import { initPaneSplit } from './paneSplit.js';
import { initSerialSplit } from './serialSplit.js';
import { initCodeDrawerSplit } from './codeDrawerSplit.js';
import { iconSvg, exampleIcon } from './icons.js';

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

const SYSTEM_PROMPT_BASE = `You are an AI assistant helping teachers write MicroPython games for SmartPlayground devices.

RULES:
- All device details, APIs and contracts are in the KNOWLEDGE BASE below. Follow it; do not infer an API from memory.
- A game is one file per device role. Every file is def play(dev) and nothing else.
- Put each role's file in its own fenced block: \`\`\`python ... \`\`\`, immediately preceded by [ROLE: <role> <hubtype>] on its own line.
- Only write for a device whose file appears in the knowledge base.
- Do NOT use f-strings — they crash on this MicroPython build. Use % formatting only.
- No try/finally, no exit-tag tables, no radio polling of your own: while dev.running() is the only exit check a game needs.
- Keep explanations concise — each code block is auto-extracted to that role's editor tab.
- If the user sends serial output (prefixed with [HW]:), help debug it.
- Default to simple, working games over complex ones.
- If the game reads NFC cards, include exactly one line formatted as [NFC_CARDS: "value1", "value2"] listing every card the game itself reads. Omit it when the game reads no cards.
- If a role file names an icon, ship it: [ICON: name] on its own line, then a \`\`\`json block of {"w":16,"h":16,"px":[[r,g,b], ...]} with 256 triples.
- After the code blocks, include exactly one line naming the game: [GAME_NAME: Short Pretty Name]`;

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
        this.declaredTags = null;   // tags the game itself declares ([NFC_CARDS:] / example)
        this.icons = [];            // icons shipped with the game ([ICON:] blocks)
        this.stationLink = null;    // USB link to an icon display, opened on demand
        this.hardware = buildHardwareReqs({});
        this.tagWrites = {};        // live {tagLabel: count} from card_written events
        this.galleryFilter = 'all';
        this.galleryMode = 'examples'; // 'examples' | 'saved'
        this.serialOpen = false; // serial log drawer — NOT the port
        this.dirty = false;
        this.pendingSendAfterConnect = false;
        this._sim = null;
        this._simLoadPromise = null;
        this._detailSim = null;
        this._detailSimToken = 0;
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

    /** Short UI name for the linked device ("Box" or "Dial"). */
    deviceShort() {
        return deviceShortName(this.link.deviceInfo);
    }

    /** Product UI name ("Broadcast Box" or "Broadcast Dial"). */
    deviceProduct() {
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

        const knowledge = await loadKnowledgeBase(KNOWN_HUBTYPES);
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

    /** What kind of device a role runs on, for labels and icons. */
    static HUB_LABEL = { wand: 'Wands', icon_station: 'Icon Display' };
    static HUB_ICON = { wand: 'wand', icon_station: 'gamepad' };

    /**
     * Rebuild the device rail from the roles the current game has.
     *
     * Before any code exists the rail keeps its markup from index.html —
     * a Wands tab and a greyed Stations one — so the empty state still
     * shows what a game can be written for.
     */
    renderRoleRail() {
        const rail = document.querySelector('.role-rail');
        if (!rail) return;
        const roles = getRoles();
        if (roles.length < 2) return;
        rail.innerHTML = '';
        for (const role of roles) {
            const hub = getHubtype(role) || 'wand';
            const item = document.createElement('div');
            item.className = 'role-item' + (role === getRole() ? ' active' : '');
            item.title = App.HUB_LABEL[hub] || hub;
            item.innerHTML =
                `<span class="role-icon">${iconSvg(App.HUB_ICON[hub] || 'gamepad', { size: 18 })}</span>`;
            item.append(role);
            item.addEventListener('click', () => {
                setRole(role);
                this.renderRoleRail();
                this.updatePreview();
            });
            rail.appendChild(item);
        }
    }

    applyUiMode(mode) {
        const advanced = mode === 'advanced';
        const panel = document.getElementById('serial-log-panel');
        const rail = document.querySelector('.role-rail');
        const gear = document.getElementById('btn-mode-gear');

        document.body.classList.toggle('ui-advanced', advanced);

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
            gear.classList.toggle('active', advanced);
        }
        // The element itself may not be upgraded yet (setupSim() lazy-loads
        // its module) — setting the attribute is harmless either way and
        // takes effect once it is.
        document.getElementById('wand-sim')?.toggleAttribute('advanced', advanced);
        this._detailSim?.toggleAttribute('advanced', advanced);
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
        this.device.on('error', (obj) => dbgError('device', 'event: error', obj));
        this.device.on('wrong_device', (obj) => {
            dbgWarn('device', 'event: wrong_device', obj);
            toast("That device isn't a Broadcast Box or Dial — check what's plugged in.", true);
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
        document.getElementById('btn-scratch').addEventListener('click', () => {
            this.resetGameContext();
            this.openWorkspace();
        });
        document.getElementById('btn-gallery').addEventListener('click', () => this.goExamples());
        document.getElementById('btn-saved').addEventListener('click', () => this.goSaved());
        document.getElementById('gallery-search').addEventListener('input', () => this.renderGallery());
        document.getElementById('btn-detail-back').addEventListener('click', () => this.goExamples());
        document.getElementById('btn-remix').addEventListener('click', () => this.remixCurrentExample());
        document.getElementById('btn-use-as-is').addEventListener('click', () => this.useExampleAsIs());
        document.getElementById('btn-send').addEventListener('click', () => this.onSend());
        document.getElementById('btn-show-code').addEventListener('click', () => {
            document.getElementById('code-drawer').classList.remove('hidden');
        });
        document.getElementById('btn-show-icons').addEventListener('click', () => {
            openIconEditor({
                icons: this.icons,
                onChange: () => {
                    this.dirty = true;
                    this.updatePreview();
                },
            });
        });
        document.getElementById('btn-close-icon-editor').addEventListener('click', () => {
            hideOverlay('icon-editor-overlay');
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
        document.getElementById('btn-box-lib-close')?.addEventListener('click', () => hideOverlay('box-library-overlay'));
        document.getElementById('btn-box-lib-refresh')?.addEventListener('click', () => this.refreshBoxLibrary());
        document.getElementById('btn-box-lib-clear')?.addEventListener('click', () => this.clearBoxLibrary());
        document.getElementById('btn-box-stats-reset')?.addEventListener('click', () => this.resetBoxStats());

        document.getElementById('btn-mode-gear').addEventListener('click', () => toggleUiMode());
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
        // A game is one file per role, so save every role and its icons. The
        // top-level `code` stays the wand's, which is what the gallery card
        // and the simulator read.
        const roles = getRoles().map((r) => ({ role: r, hubtype: getHubtype(r), code: getCodeFor(r) }));
        const wand = roles.find((r) => (r.hubtype || 'wand') === 'wand');
        const entry = saveGame({
            name: this.gameName,
            desc: this.gameDesc,
            code: wand ? wand.code : code,
            roles,
            icons: this.icons,
            requiredTags: this.requiredTags,
            hardware: this.hardware,
            chatHistory: this.chatHistory.slice(),
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
        this.gameDesc = g.desc || '';
        this.declaredTags = g.hardware?.declaredTags || null;
        this.hardware = g.hardware || buildHardwareReqs({ gameName: g.name });
        this.chatHistory = Array.isArray(g.chatHistory) ? g.chatHistory.slice() : [];
        showView('workspace');
        const box = document.getElementById('chat-box');
        box.innerHTML = '';
        addMsg(`Loaded saved game “${g.name}”.`, 'system');
        resetRoles();
        this.icons = Array.isArray(g.icons) ? g.icons : [];
        const saved = Array.isArray(g.roles) && g.roles.length
            ? g.roles
            : (g.code ? [{ role: 'wand', hubtype: 'wand', code: g.code }] : []);
        for (const r of saved) {
            saveVersion(r.code, 'Loaded from library', { role: r.role, hubtype: r.hubtype });
        }
        if (saved.length) setRole(saved[0].role);
        this.renderRoleRail();
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
    }

    /** Show the selected example actually running, in place of the old
     * static "preview animation" placeholder. A fresh <wand-sim> is built
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
        dbg('app', `mountDetailSim("${ex.id}") — loading wand-sim module`);
        import('../../../Simulator/wand-sim.js')
            .then(() => {
                // The teacher moved on while Pyodide's module was loading —
                // don't mount a sim into a panel nobody is looking at.
                if (token !== this._detailSimToken) return;
                const sim = document.createElement('wand-sim');
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
                dbgError('sim', 'failed to load wand-sim module for the detail preview', err);
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
            chip.innerHTML = `${iconSvg(exampleIcon(ex), { size: 14 })} <span>${escapeHtml(ex.starterPrompt)}</span>`;
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

    /**
     * Forget the last game. Without this, opening an example and then starting
     * from scratch carried that example's declared tags (and name) into a game
     * that never reads them.
     */
    resetGameContext() {
        dbg('app', 'resetGameContext() — clearing name/tags/example');
        this.currentExample = null;
        this.declaredTags = null;
        this.gameName = 'Your game';
        this.gameDesc = '';
        this.chatHistory = [];
        this.tagWrites = {};
        this.icons = [];
        resetRoles();
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
        dbg('app', `remixCurrentExample("${this.currentExample.name}")`);
        this.gameName = this.currentExample.name;
        this.gameDesc = this.currentExample.description;
        this.declaredTags = [...this.currentExample.tags];
        const code = await this.fetchExampleCode(this.currentExample);
        if (code) {
            resetRoles();
            this.icons = [];
            saveVersion(code, `${this.currentExample.name} (remix base)`, { role: 'wand', hubtype: 'wand' });
            this.dirty = true;
        }
        this.openWorkspace(this.currentExample.starterPrompt);
        addMsg(`Let's remix ${this.currentExample.name}! What would you like to change?`, 'system');
        this.updatePreview();
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
        dbg('app', `useExampleAsIs("${this.currentExample.name}")`);
        this.gameName = this.currentExample.name;
        this.gameDesc = this.currentExample.description;
        this.declaredTags = [...this.currentExample.tags];
        showView('workspace');
        addMsg(`Using ${this.currentExample.name} as-is.`, 'system');

        const code = await this.fetchExampleCode(this.currentExample);
        if (code) {
            resetRoles();
            this.icons = [];
            saveVersion(code, `${this.currentExample.name} as-is`, { role: 'wand', hubtype: 'wand' });
            this.dirty = true;
        } else {
            this.updatePreview();
            return;
        }

        this.updatePreview();
        await this.startSendFlow();
    }

    updatePreview() {
        const code = getCode();

        this.refreshHardware(code);

        // The simulator is a wand. A station role file is shown but not run:
        // pushing it would load wand hardware the file never touches and
        // fail for the wrong reason. The station shows its icons instead.
        const hub = getHubtype(getRole()) || 'wand';
        const isWand = hub === 'wand';
        const runnable = isWand && isRunnableCode(code);
        const showIcons = !isWand && isRunnableCode(code);

        document.getElementById('preview-panel').classList.toggle('hidden', !runnable);
        const iconPanel = document.getElementById('icon-preview');
        iconPanel?.classList.toggle('hidden', !showIcons);
        document.querySelector('.ws-body')?.classList.toggle('no-sim', !runnable && !showIcons);

        document.getElementById('btn-show-icons')?.classList.toggle('hidden', !this.icons.length);

        if (runnable) {
            this.setupSim();
            this.pushSimSource(code);
        } else if (showIcons && iconPanel) {
            renderIconPanel(iconPanel, this.icons);
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
                // Every push of new code reloads the game; start it right away.
                this._sim.autostart = true;
                // <wand-sim> shows its own "Can't simulate" pop-up on a
                // boot/load failure, worded for this audience; the raw
                // message still lands in the debug console, so nothing is
                // swallowed.
                this._sim.addEventListener('sim-error', (e) => {
                    const { message, phase } = e.detail || {};
                    dbgError('sim', `sim-error (${phase}): ${message}`);
                });
                this._sim.addEventListener('sim-overlay-action', (e) => {
                    this.onSimOverlayAction(e.detail || {});
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
        // Only from the second push on: the first one *is* the game
        // appearing, which needs no announcement.
        const isUpdate = this._simLastSource != null;
        this._simLastSource = code;
        this._sim.hideOverlay();
        // Workspace code is pushed as source — it may have been edited — so
        // _TEACHER_TABLE can't match it and capabilities fall back to "show
        // everything". The example's own profile is what narrows that back
        // down; a game generated from scratch has none and shows the lot.
        this._sim.profile = this.currentExample?.simProfile || null;
        this._sim.source = code;
        if (isUpdate) this._sim.showOverlay('new-code');
    }

    /**
     * A button on one of the simulator's pop-ups. The element closes the
     * pop-up itself, so these only have to do the thing.
     */
    onSimOverlayAction({ kind, action }) {
        dbg('app', `sim overlay ${kind} -> ${action}`);
        if (action === 'play-it' || action === 'play-again') {
            this._sim?.restart();
        } else if (action === 'send-to-box') {
            this.startSendFlow();
        }
    }

    renderComponentList(targetId) {
        const code = getCode();
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

    async onConnect() {
        dbg('app', 'onConnect() — requesting serial port');
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
        if (s === 'opening' || s === 'sending' || s === 'rebooting') return;
        if (s === 'waiting') {
            dbg('app', 'toggleConnect() — cancel waiting');
            showConnectToast(false);
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
        // idle or lost → toast + picker (no instructional modal first)
        this.pendingSendAfterConnect = false;
        await this.onConnect();
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
        const code = getCode();
        if (!code.trim() || code.trim().startsWith('# AI-generated')) {
            dbgWarn('app', 'startSendFlow() aborted: no code in editor');
            toast('Generate some code first — describe your game in chat.', true);
            return;
        }
        this.refreshHardware(code);
        dbg('app', `required tags: [${this.requiredTags.join(', ')}]`);
        // Confirm is the FIRST screen: name the game and see what it needs.
        // Connecting and the tag to-do list both happen on the far side of Send.
        this.showSendConfirm();
    }

    /** Recompute the hardware requirements from the current code + declared tags. */
    refreshHardware(code) {
        // Cards are read by wands, so the tag list comes from the wand's file
        // whichever role is on screen.
        const wandRole = getRoles().find((r) => (getHubtype(r) || 'wand') === 'wand');
        const wandCode = wandRole ? getCodeFor(wandRole) : (code !== undefined ? code : getCode());
        this.hardware = buildHardwareReqs({
            code: wandCode,
            gameName: this.gameName,
            declared: this.declaredTags,
            stations: this.stationNames(),
        });
        return this.hardware;
    }

    /** Plain names for the non-wand devices this game needs. */
    stationNames() {
        const names = [];
        for (const role of getRoles()) {
            const hub = getHubtype(role);
            if (hub && hub !== 'wand') names.push(App.HUB_LABEL[hub] || hub);
        }
        return names;
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
        }
        this._pendingReplaceSlug = null;
        this.refreshHardware();
        this.renderSendRequirements();
        this.setSendBusy(false);
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

    async confirmSend() {
        dbg('app', 'confirmSend() — "Send" clicked on confirm overlay');
        const wandRole = getRoles().find((r) => (getHubtype(r) || 'wand') === 'wand');
        const code = wandRole ? getCodeFor(wandRole) : getCode();
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
                `"${pretty}" is already on the ${this.deviceShort()}.\n\nOK = Replace it\nCancel = pick another name`
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
        const destPath = `/flash/games/${slug}.py`;

        document.getElementById('send-progress-wrap').classList.remove('hidden');
        setSendProgress(0, 'Starting…');
        this.setSendBusy(true);

        this.setLinkState('sending');
        const result = await uploadPayload(this.device, code, window.onUploadProgress, {
            linkState: 'sending',
            deviceProduct: this.deviceProduct(),
            deviceShort: this.deviceShort(),
            // Recompute against the slug actually being written: the name can
            // change on this overlay, and the device keys its menu off the slug.
            meta: {
                destPath,
                destLabel: `${slug}.py`,
                prettyName: check.pretty,
                deviceLabel: this.deviceShort(),
                tags: buildHardwareReqs({
                    code, gameName: check.pretty, declared: this.declaredTags,
                }).tags,
            },
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

        hideOverlay('send-confirm-overlay');
        this._pendingReplaceSlug = null;

        this.setLinkState('rebooting');
        this._armRebootTimer();
        dbg('app', 'send succeeded — showing tag to-do list');
        const banner = document.getElementById('sent-banner');
        banner.classList.remove('hidden');
        setTimeout(() => banner.classList.add('hidden'), 4000);

        // Post-send to-do list. Every game needs the baseline getcode:/play pair,
        // so only open the overlay when there is more to write than that.
        // The station half goes over its own USB connection, after the Box
        // has the wand file: a station with a role file but no wand to drive
        // it is the less confusing half-sent state of the two.
        await this.sendStationHalf(slug);

        const tags = this.requiredTags;
        if (tags.length > baselineTags(slug).length) {
            this.tagWrites = {};
            await showTagChecklist({
                title: `Now write ${tags.length} tags on the ${this.deviceShort()}`,
                subtitle: `Hold each card on the ${this.deviceShort()} in turn — you can unplug it first.`,
                tags,
                written: this.tagWrites,
            });
        } else {
            toast(`Sent! Hold a card on the ${this.deviceShort()} to write the pickup tag.`);
        }
    }

    /**
     * Write every non-wand role file, and the game's icons, to its station.
     *
     * Asks for the port each time: the teacher plugs the station in for this
     * step, and Web Serial has no way to reopen a port without a gesture.
     *
     * @param {string} slug the game's slug, which names the module on flash
     */
    async sendStationHalf(slug) {
        const roles = getRoles().filter((r) => (getHubtype(r) || 'wand') !== 'wand');
        if (!roles.length) return;

        for (const role of roles) {
            const hub = getHubtype(role);
            if (hub !== 'icon_station') {
                toast(`No way to send to a ${hub} yet — ${role} was not sent.`, true);
                dbgWarn('app', `no send path for hubtype ${hub} (role ${role})`);
                continue;
            }
            const label = App.HUB_LABEL[hub] || hub;
            if (!confirm(`Plug in the ${label} and click OK to send "${role}" to it.`)) {
                toast(`${label} not sent — send it later from this game.`, true);
                return;
            }
            const link = new StationLink();
            try {
                await link.connect();
                setSendProgress(0, `${label}: starting…`);
                const sent = await sendToStation(
                    link,
                    { slug, role, code: getCodeFor(role), icons: this.icons },
                    (p) => {
                        const pct = p.total ? Math.round((p.current / p.total) * 100) : 0;
                        setSendProgress(pct, `${p.status}: ${p.file}`);
                        dbg('station', `${p.status} ${p.file} (${p.current}/${p.total})`);
                    }
                );
                dbg('app', `station send complete: ${sent.path}`, sent);
                toast(`Sent ${sent.module}.py and ${sent.icons.length} icon(s) to the ${label}.`);
            } catch (e) {
                dbgError('app', `station send failed: ${e.message}`, e);
                toast(`Could not send to the ${label}: ${e.message}`, true);
            } finally {
                await link.disconnect().catch((e) => dbgWarn('app', `station disconnect: ${e.message}`));
            }
        }
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
                del.title = 'Delete from Box';
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
        const mode = this.link.boxMode;
        const info = this.link.deviceInfo || {};
        const chip = document.getElementById('mybox-mode-chip');
        const label = document.getElementById('mybox-mode-label');
        if (chip && label) {
            chip.classList.toggle('write', mode === 'WRITE');
            if (mode === 'SERVE') {
                label.textContent = 'Code Server';
                chip.title = 'Handing out code to wands.';
            } else if (mode === 'WRITE') {
                label.textContent = 'Tag Writing';
                chip.title = 'Ready to write pickup tags.';
            } else {
                label.textContent = this.link.state === 'live' ? `${this.deviceShort()} ready` : this.deviceShort();
                chip.title = `Connect to see ${this.deviceShort()} status.`;
            }
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
        if (!alreadyConfirmed && !confirm(`Delete "${slug}" from the ${this.deviceShort()}?`)) return;
        try {
            await this.device.sendCmd({ cmd: 'games.delete', slug }, { timeoutMs: 5000 });
            toast(`Deleted ${slug}`);
            await this.refreshBoxLibrary();
        } catch (e) {
            toast(e.message || 'Delete failed', true);
        }
    }

    async clearBoxLibrary() {
        if (!confirm(`Remove ALL games from the ${this.deviceShort()}?`)) return;
        try {
            await this.device.sendCmd({ cmd: 'games.clear' }, { timeoutMs: 8000 });
            toast('Box library cleared');
            await this.refreshBoxLibrary();
        } catch (e) {
            toast(e.message || 'Clear failed', true);
        }
    }

    async resetBoxStats() {
        if (!confirm(`Reset usage stats on the ${this.deviceShort()}?`)) return;
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
            const reply = stripBlockMarkers(stripGameNameMarker(stripNfcMarker(rawReply)));
            dbg('chat', `reply received (${rawReply.length} chars)`, { nfcCards, gameName });

            removeTyping();
            this.chatHistory.push({ role: 'assistant', content: trimForHistory(reply) });
            addMsg(reply, 'bot');

            if (gameName) {
                this.gameName = gameName;
                dbg('chat', `game name from marker: ${gameName}`);
            }

            const blocks = extractCodeBlocks(reply);
            if (blocks.length) {
                dbg('chat', `${blocks.length} role block(s) extracted`, blocks.map((b) => b.role));
                const label = userMsg.length > 40 ? userMsg.slice(0, 40) + '…' : userMsg;
                for (const b of blocks) {
                    saveVersion(b.code, label, { role: b.role, hubtype: b.hubtype });
                }
                // Show the role the teacher was already looking at if the reply
                // rewrote it, otherwise the first one it did write.
                if (!blocks.some((b) => b.role === getRole())) setRole(blocks[0].role);
                this.icons = extractIcons(reply);
                this.renderRoleRail();
                addMsg(
                    blocks.length === 1
                        ? `Code updated (v${getVersionCount()})`
                        : `Code updated for ${blocks.map((b) => b.role).join(' and ')}`,
                    'system'
                );
                if (this.icons.length) {
                    addMsg(`${this.icons.length} icon${this.icons.length === 1 ? '' : 's'} to send with it`, 'system');
                }
                // New code replaces the old tag declaration outright: no marker
                // means this version reads no named tags, not "keep the old ones".
                this.declaredTags = nfcCards?.length ? nfcCards : null;
                dbg('chat', `declared tags from [NFC_CARDS]: [${(nfcCards || []).join(', ')}]`);
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
