import { loadEncryptedKey, initAuthModal, getApiKey, hasEncryptedKey } from './auth.js';
import {
    addMsg, addThinkingMsg, removeTyping, extractCode, parseNfcCards, stripNfcMarker,
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
import { renderSim, bindSimControls, setTickHandler } from './sim/wandSim.js';
import { buildComponentChecklist, checklistIcons, checklistLines } from './checklist.js';
import { startSimLoop, stopSimLoop, triggerTick, preloadPyodide } from './sim/pyodide/pyodideRuntime.js';
import { renderNfcButtons, renderEspnowButtons, setInputChangeHandler } from './sim/pyodide/inputBridge.js';

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
- If the game reads NFC tags with specific values, include exactly one line formatted as [NFC_CARDS: "value1", "value2"] listing every tag value the game uses.`;

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
        this.serialDropHandled = false;
        this.serialOpen = false;
        this.dirty = false;
        this.pendingSendAfterConnect = false;
    }

    async init() {
        dbg('app', 'init() starting');
        initEditor();
        dbg('app', 'editor initialized');
        updateVersionUI();
        this.bindEvents();
        dbg('app', 'event listeners bound');
        this.setupGallery();
        this.setupDeviceListeners();
        this.setupSerialLog();
        this.applyUiMode(loadUiMode());
        bindSimControls();
        setTickHandler(() => triggerTick(getCode()));
        setInputChangeHandler(() => triggerTick(getCode()));
        renderEspnowButtons();
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
        preloadPyodide();
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
        const refresh = () => {
            const state = {
                connected: this.device.isConnected(),
                running: this.device.isRunning(),
                atRepl: this.device.atRepl,
                wrongDevice: this.device.wrongDevice,
            };
            dbg('device', 'badge refresh', state);
            setConnectionBadge(state.connected, state.running, state.atRepl, state.wrongDevice);
            const btn = document.getElementById('btn-connect-header');
            if (btn) {
                btn.textContent = state.connected ? 'Disconnect' : 'Connect';
                btn.classList.toggle('is-connected', state.connected);
            }
        };
        this.device.on('hello', (obj) => { dbg('device', 'event: hello', obj); refresh(); });
        this.device.on('heartbeat', (obj) => { dbg('device', 'event: heartbeat', obj); refresh(); });
        this.device.on('repl', (info) => { dbgWarn('device', 'event: repl (firmware not running)', info); refresh(); });
        this.device.on('armed', (obj) => dbg('device', 'event: armed', obj));
        this.device.on('card_present', (obj) => dbg('device', 'event: card_present', obj));
        this.device.on('card_written', (obj) => dbg('device', 'event: card_written', obj));
        this.device.on('fatal', (obj) => dbgError('device', 'event: fatal', obj));
        this.device.on('wrong_device', (obj) => {
            dbgWarn('device', 'event: wrong_device', obj);
            toast("That device isn't a Broadcast Box — check what's plugged in.", true);
            refresh();
        });
        this.device.on('bye', (obj) => { dbg('device', 'event: bye', obj); refresh(); });

        if (navigator.serial) {
            navigator.serial.addEventListener('disconnect', () => {
                dbgWarn('device', 'navigator.serial disconnect event fired');
                if (this.device.isConnected()) {
                    this.onSerialDrop();
                }
            });
        } else {
            dbgWarn('device', 'Web Serial API not available in this browser (need Chrome/Edge)');
        }
    }

    onSerialDrop() {
        if (this.serialDropHandled) return;
        this.serialDropHandled = true;
        dbgWarn('device', 'serial drop detected — resetting connection badge');
        setConnectionBadge(false, false, false, false);
        toast('Broadcast Box disconnected — check the cable.', true);
        setTimeout(() => { this.serialDropHandled = false; }, 2000);
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
        document.getElementById('btn-send-confirm').addEventListener('click', () => this.confirmSend());
        document.getElementById('btn-send-cancel').addEventListener('click', () => hideOverlay('send-confirm-overlay'));

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
        stopSimLoop();
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
        document.getElementById('preview-name').textContent = this.gameName;
        document.getElementById('preview-desc').textContent = this.gameDesc || 'Chat to describe your game.';

        const code = getCode();
        const caps = scanCapabilities(code);
        renderSim(caps, { pressed: false, idle: !caps.hasCode });

        // Heuristic preview shows instantly; Python sim takes over when ready.
        this.requiredTags = deriveRequiredTags(null, code, this.gameName.toLowerCase());
        if (this.currentExample?.tags?.length > this.requiredTags.length) {
            this.requiredTags = [...this.currentExample.tags];
        }
        renderNfcButtons(this.requiredTags);

        const codeTrim = (code || '').trim();
        if (codeTrim && !codeTrim.startsWith('# AI-generated') && /def\s+play\s*\(/.test(code)) {
            startSimLoop(code, { intervalMs: 150 });
        } else {
            stopSimLoop();
        }

        // Small symbolic row only here — the full "You'll need:" list is
        // shown at the connect / send-confirm stage instead (see
        // renderComponentList()).
        const items = buildComponentChecklist(caps, this.requiredTags);
        const cl = document.getElementById('preview-checklist');
        cl.innerHTML = '';
        checklistIcons(items).forEach((icon, i) => {
            const li = document.createElement('li');
            li.textContent = icon;
            li.title = items[i].label;
            cl.appendChild(li);
        });

        const ul = document.getElementById('preview-tags');
        ul.innerHTML = '';
        this.requiredTags.forEach((t) => {
            const li = document.createElement('li');
            li.textContent = t;
            ul.appendChild(li);
        });
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
        try {
            await this.device.connect();
            dbg('app', 'device.connect() resolved (port open; awaiting hello/heartbeat)');
            hideOverlay('connect-overlay');
            setConnectionBadge(true, false, false, false);
            if (this.pendingSendAfterConnect) {
                // startSendFlow() bailed out to show this overlay before it got to
                // send-confirm -- without this, connecting silently does nothing
                // and the user has to notice the badge and click Send again.
                this.pendingSendAfterConnect = false;
                dbg('app', 'onConnect() — resuming send flow that was waiting on connection');
                toast('Connected — continuing to send…');
                this.showSendConfirm();
            } else {
                toast('Connected — waiting for the Box…');
            }
        } catch (e) {
            dbgError('app', `device.connect() rejected: ${e.message}`, e);
            errEl.textContent = "Couldn't find a Broadcast Box — check the cable.";
        }
    }

    /** Standalone header "Connect"/"Disconnect" toggle, independent of the send flow. */
    async toggleConnect() {
        if (this.device.isConnected()) {
            dbg('app', 'toggleConnect() — disconnecting');
            await this.device.disconnect();
            setConnectionBadge(false, false, false, false);
            toast('Disconnected.');
            return;
        }
        this.pendingSendAfterConnect = false;
        this.renderComponentList('connect-components');
        showOverlay('connect-overlay');
        await this.onConnect();
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

        if (!this.device.isConnected()) {
            dbg('app', 'device not connected — showing connect overlay');
            this.pendingSendAfterConnect = true;
            this.renderComponentList('connect-components');
            showOverlay('connect-overlay');
            return;
        }

        this.showSendConfirm();
    }

    showSendConfirm() {
        document.getElementById('send-confirm-sub').textContent =
            `🪄 Wand code · ${this.gameName}`;
        this.renderComponentList('send-confirm-components');
        document.getElementById('send-progress-wrap').classList.add('hidden');
        showOverlay('send-confirm-overlay');
    }

    async confirmSend() {
        dbg('app', 'confirmSend() — "Send" clicked on confirm overlay');
        const code = getCode();
        document.getElementById('send-progress-wrap').classList.remove('hidden');
        setSendProgress(0, 'Starting…');

        const result = await uploadPayload(this.device, code, window.onUploadProgress);
        dbg('app', 'uploadPayload() result', result);

        hideOverlay('send-confirm-overlay');

        if (!result.ok) {
            dbgError('app', `send failed: ${result.error}`);
            toast(result.error || 'Send failed — try again.', true);
            return;
        }

        dbg('app', 'send succeeded — showing sent banner');
        const banner = document.getElementById('sent-banner');
        banner.classList.remove('hidden');
        setTimeout(() => banner.classList.add('hidden'), 4000);
        toast('Sent! Hold a card on the Box to write the pickup tag.');
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
            const reply = stripNfcMarker(rawReply);
            dbg('chat', `reply received (${rawReply.length} chars)`, { nfcCards });

            this.chatHistory.push({ role: 'assistant', content: trimForHistory(reply) });
            addMsg(reply, 'bot');

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
