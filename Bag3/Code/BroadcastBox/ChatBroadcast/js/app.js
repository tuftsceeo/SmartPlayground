import { loadEncryptedKey, initAuthModal, getApiKey, hasEncryptedKey } from './auth.js';
import {
    addMsg, addThinkingMsg, removeTyping, extractCode, parseNfcCards, stripNfcMarker,
    trimForHistory, loadKnowledgeBase, getKnowledgeText, getKnowledgeFileCount,
} from './chat.js';
import {
    initEditor, getCode, setCode, saveVersion, updateVersionUI,
    onPrevVersion, onNextVersion, getVersionCount,
} from './editor.js';
import { uploadPayload } from './upload.js';
import { showTagChecklist, deriveRequiredTags, tagCountLabel } from './nfc.js';
import { EXAMPLES, CATEGORIES, findExample } from './examples.js';
import { showView, showOverlay, hideOverlay, setConnectionBadge, toast, setSendProgress } from './router.js';
import { createDeviceLink } from './device/bboxDeviceLink.js';
import { subscribe, getEntries, toText } from './device/serialLog.js';
import { setWorkspaceHandler } from './markdown.js';
import { dbg, dbgWarn, dbgError } from './debug.js';

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

const EMPTY_PROMPTS = [
    'Try: "Make a jump game where shaking lights up the wand"',
    'Try: "A melody game with 4 notes"',
    'Try: "Rainbow colors when you shake"',
];

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
        this.serialDropHandled = false;
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
        showView('splash');
        dbg('app', 'initial view: splash (modal-overlay is persistent — showView must not touch it)');

        dbg('app', 'loading encrypted key…');
        await loadEncryptedKey();
        initAuthModal();
        dbg('app', 'auth modal initialized — waiting for app:unlocked');

        document.addEventListener('app:unlocked', () => {
            dbg('app', 'received app:unlocked event');
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
            addMsg(`Code sent to editor (v${getVersionCount()})`, 'system');
            document.getElementById('code-drawer').classList.remove('hidden');
        });

        dbg('app', 'init() complete');
    }

    getSystemPrompt() {
        const knowledge = getKnowledgeText();
        return knowledge
            ? SYSTEM_PROMPT_BASE + '\n\nPROJECT KNOWLEDGE BASE:\n' + knowledge
            : SYSTEM_PROMPT_BASE;
    }

    setupSerialLog() {
        const panel = document.getElementById('serial-log-panel');
        const pre = document.getElementById('serial-log-text');
        panel.classList.remove('hidden');
        subscribe((entry) => {
            if (entry === null) {
                pre.textContent = '';
                return;
            }
            const lines = getEntries().slice(-80).map((e) => {
                const tag = e.dir.toUpperCase().padEnd(5);
                return `${tag} ${e.text}`;
            });
            pre.textContent = lines.join('\n');
            pre.scrollTop = pre.scrollHeight;
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
            showView('gallery');
            this.renderGallery();
        });
        document.getElementById('gallery-search').addEventListener('input', () => this.renderGallery());
        document.getElementById('btn-detail-back').addEventListener('click', () => showView('gallery'));
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
        document.getElementById('btn-prev').addEventListener('click', () => onPrevVersion(addMsg));
        document.getElementById('btn-next').addEventListener('click', () => onNextVersion(addMsg));
        document.getElementById('btn-connect-usb').addEventListener('click', () => this.onConnect());
        document.getElementById('btn-send-confirm').addEventListener('click', () => this.confirmSend());
        document.getElementById('btn-send-cancel').addEventListener('click', () => hideOverlay('send-confirm-overlay'));

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
        const q = document.getElementById('gallery-search').value.toLowerCase();
        const grid = document.getElementById('gallery-grid');
        grid.innerHTML = '';
        EXAMPLES.filter((ex) => {
            if (this.galleryFilter !== 'all' && ex.category !== this.galleryFilter) return false;
            if (q && !ex.name.toLowerCase().includes(q)) return false;
            return true;
        }).forEach((ex) => {
            const card = document.createElement('div');
            card.className = 'example-card';
            card.innerHTML =
                `<div class="example-thumb">${ex.id} clip</div>` +
                `<h3>${ex.emoji} ${ex.name}</h3>` +
                `<p>${ex.description}</p>` +
                (ex.tagNote ? `<div class="tag-badge">${ex.tagNote}</div>` : '');
            card.addEventListener('click', () => this.openDetail(ex.id));
            grid.appendChild(card);
        });
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

    openWorkspace(starterMsg = null) {
        dbg('app', `openWorkspace(${starterMsg ? JSON.stringify(starterMsg) : 'no starter message'})`);
        showView('workspace');
        const box = document.getElementById('chat-box');
        if (box.children.length === 0) {
            addMsg(EMPTY_PROMPTS[Math.floor(Math.random() * EMPTY_PROMPTS.length)], 'system');
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
        this.updatePreview();
        await this.startSendFlow();
    }

    updatePreview() {
        document.getElementById('preview-name').textContent = this.gameName;
        document.getElementById('preview-desc').textContent = this.gameDesc || 'Chat to describe your game.';
        const ul = document.getElementById('preview-tags');
        ul.innerHTML = '';
        this.requiredTags.forEach((t) => {
            const li = document.createElement('li');
            li.textContent = t;
            ul.appendChild(li);
        });
    }

    async onConnect() {
        dbg('app', 'onConnect() — requesting serial port');
        const errEl = document.getElementById('connect-error');
        errEl.textContent = '';
        try {
            await this.device.connect();
            dbg('app', 'device.connect() resolved (port open; awaiting hello/heartbeat)');
            hideOverlay('connect-overlay');
            setConnectionBadge(true, false, false, false);
            toast('Connected — waiting for the Box…');
        } catch (e) {
            dbgError('app', `device.connect() rejected: ${e.message}`, e);
            errEl.textContent = "Couldn't find a Broadcast Box — check the cable.";
        }
    }

    async startSendFlow() {
        dbg('app', 'startSendFlow() — "Send to Broadcast Box" clicked');
        const code = getCode();
        if (!code.trim()) {
            dbgWarn('app', 'startSendFlow() aborted: no code in editor');
            toast('Generate some code first — describe your game in chat.', true);
            return;
        }
        this.requiredTags = deriveRequiredTags(null, code, this.gameName.toLowerCase());
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
            showOverlay('connect-overlay');
            return;
        }

        document.getElementById('send-confirm-sub').textContent =
            `🪄 Wand code · ${this.gameName}`;
        const tagEl = document.getElementById('send-confirm-tags');
        const label = tagCountLabel(this.requiredTags.length);
        if (label) {
            tagEl.textContent = label;
            tagEl.classList.remove('hidden');
        } else {
            tagEl.classList.add('hidden');
        }
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
        addMsg(msg, 'user');
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

const app = new App();
app.init();
