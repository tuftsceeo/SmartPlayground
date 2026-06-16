import { loadEncryptedKey, initAuthModal, getApiKey, hasEncryptedKey } from './auth.js';
import { uRepl } from './serial.js';
import { addMsg, removeTyping, extractCode, parseNfcCards, stripNfcMarker, trimForHistory, loadKnowledgeBase, getKnowledgeText, getKnowledgeFileCount } from './chat.js';
import { initEditor, getCode, setCode, saveVersion, updateVersionUI, onPrevVersion, onNextVersion, onDownload, onClearCode, getVersionCount } from './editor.js';
import { validateJumpin, uploadToSlot } from './upload.js';
import { writeNfcTag, showUploadModal, showNfcTriggerModal, showNfcCardsModal } from './nfc.js';
import { setStatus, showStop, initResizer } from './ui.js';

const SYSTEM_PROMPT_BASE = `You are an AI assistant helping users write MicroPython games for the PlaygroundV5 wand.

RULES:
- All board details, APIs, and hardware specs are in the KNOWLEDGE BASE below. Reference it.
- Generated code MUST follow the jumpin.py format with def play(nfc, leds, buz, accel, i2c)
- Put all code inside a fenced code block: \`\`\`python ... \`\`\`
- Do NOT use f-strings — they crash on this MicroPython build. Use % formatting only.
- Keep explanations concise — the code block is auto-extracted to the editor
- If the user sends serial output (prefixed with [HW]:), help debug it
- Always include try/finally cleanup and periodic NFC stop-tag polling
- Default to simple, working examples over complex ones
- If the game reads NFC tags with specific values, include exactly one line formatted as [NFC_CARDS: "value1", "value2"] listing every tag value the game uses.`;

class App {
    constructor() {
        this.uboard = new uRepl();
        this.chatHistory = [];
        this.isGenerating = false;
        this.uboard.disconnectCallback = () => this.onDisconnect();
    }

    async init() {
        setStatus(false);
        initEditor();
        initResizer();
        updateVersionUI();
        this.bindEvents();
        this.setupDisconnectDetection();

        await loadEncryptedKey();
        initAuthModal();

        const knowledge = await loadKnowledgeBase();
        if (knowledge) addMsg(`Loaded ${getKnowledgeFileCount()} knowledge file(s).`, "system");

        console.log("App ready!");
    }

    getSystemPrompt() {
        const knowledge = getKnowledgeText();
        return knowledge ? SYSTEM_PROMPT_BASE + "\n\nPROJECT KNOWLEDGE BASE:\n" + knowledge : SYSTEM_PROMPT_BASE;
    }

    setupDisconnectDetection() {
        if (navigator.serial) {
            navigator.serial.addEventListener("disconnect", () => {
                if (this.uboard.connected) {
                    this.uboard.connected = false;
                    this.uboard.terminal = null;
                    setStatus(false);
                    addMsg("Board disconnected.", "system");
                }
            });
        }
    }

    bindEvents() {
        const on = (id, fn) => document.getElementById(id).addEventListener("click", fn);

        on("btn-connect",    () => this.onConnect());
        on("btn-ctrlc",      () => this.sendCtrlC());
        on("btn-reset",      () => this.onReset());
        on("btn-upload",     () => this.onUpload());
        on("btn-send",       () => this.onSend());
        on("btn-stop",       () => this.onStop());
        on("btn-clear-code", () => onClearCode());
        on("btn-prev",       () => onPrevVersion(addMsg));
        on("btn-next",       () => onNextVersion(addMsg));
        on("btn-download",   () => onDownload(addMsg));
        on("btn-help",       () => this.onHelpOpen());
        on("btn-help-close", () => this.onHelpClose());
        on("help-overlay",   (e) => { if (e.target.id === "help-overlay") this.onHelpClose(); });
        on("btn-tools",      () => document.getElementById("btn-write-nfc").classList.toggle("hidden"));
        on("btn-write-nfc",  () => this.onWriteNfcManual());
        on("btn-run",        () => this.onRun());

        document.getElementById("user-input").addEventListener("keydown", e => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); this.onSend(); }
        });

        document.addEventListener("app:write-nfc-card", async (e) => {
            await writeNfcTag(this.uboard, addMsg, e.detail.text);
        });
    }

    // ---- Serial ----

    async onConnect() {
        if (this.uboard.connected) {
            await this.uboard.board.disconnect();
            await this.onDisconnect();
        } else {
            const stop = document.getElementById("freshStart").checked;
            const name = await this.uboard.board.connect("repl", stop);
            console.log(name);
            if (!name) return;
            this.uboard.connected = true;
            this.uboard.terminal = this.uboard.board.terminal;
            setStatus(true);
            addMsg(`Connected to ${name}`, "system");
        }
    }

    async onDisconnect() {
        setStatus(false);
        this.uboard.connected = false;
        this.uboard.buffer = '';
        addMsg("Disconnected.", "system");
    }

    async sendCtrlC() {
        if (this.uboard.connected) await this.uboard.board.write('\x03');
    }

    async onReset() {
        if (!this.uboard.connected) return;
        await this.uboard.board.write('\x03');
        await sleep(300);
        await this.uboard.board.write('\x03');
        await sleep(500);
        await this.uboard.paste('import machine; machine.reset()');
        this.uboard.focus();
    }

    async onRun() {
        if (!this.uboard.connected) { addMsg("Connect your board first.", "system"); return; }
        const code = getCode();
        if (code.trim()) {
            await this.uboard.paste(code);
            this.uboard.focus();
        }
    }

    // ---- NFC manual write ----

    async onWriteNfcManual() {
        const text = window.prompt("Enter the text to write to the NFC tag:");
        if (!text || !text.trim()) return;
        await writeNfcTag(this.uboard, addMsg, text.trim());
    }

    // ---- Upload ----

    async onUpload() {
        if (!this.uboard.connected) { addMsg("Connect your board first.", "system"); return; }
        const code = getCode();
        if (!code.trim()) return;

        const [ok, error] = validateJumpin(code);
        if (!ok) {
            addMsg(
                `Upload rejected — this code doesn't follow jumpin.py format:\n\n${error}\n\n` +
                `To run code directly, use the Run button.\n\n` +
                `Upload requires a def play(nfc, leds, buz, accel, i2c) function because main.py calls: from jumpin import play`,
                "system"
            );
            return;
        }

        const { confirmed, slot } = await showUploadModal();
        if (!confirmed) return;

        await uploadToSlot(this.uboard, code, slot, addMsg);

        const wantNfc = await showNfcTriggerModal(slot);
        if (wantNfc) await writeNfcTag(this.uboard, addMsg, `jumpin${slot}`);
    }

    // ---- Help ----

    onHelpOpen()  { document.getElementById("help-overlay").classList.remove("hidden"); }
    onHelpClose() { document.getElementById("help-overlay").classList.add("hidden"); }

    // ---- Chat ----

    async onSend() {
        const inp = document.getElementById("user-input");
        const msg = inp.value.trim();
        if (!msg || this.isGenerating) return;
        inp.value = "";
        addMsg(msg, "user");
        await this.callClaude(msg);
    }

    onStop() {
        this.isGenerating = false;
        removeTyping();
        showStop(false);
        addMsg("Stopped.", "system");
    }

    async callClaude(userMsg) {
        const passphrase = document.getElementById("passphrase").value.trim();
        if (!passphrase) { addMsg("Enter the magic code first.", "system"); return; }
        if (!hasEncryptedKey()) { addMsg("No API key configured.", "system"); return; }

        const apiKey = getApiKey(passphrase);
        if (!apiKey) { addMsg("Wrong passphrase.", "system"); return; }

        this.chatHistory.push({ role: "user", content: userMsg });
        addMsg("Thinking...", "system");
        showStop(true);
        this.isGenerating = true;

        try {
            const body = JSON.stringify({
                model: "claude-sonnet-4-6",
                max_tokens: 16384,
                system: [{ type: "text", text: this.getSystemPrompt(), cache_control: { type: "ephemeral" } }],
                messages: this.chatHistory.slice(-10),
            });

            const resp = await fetch("https://api.anthropic.com/v1/messages", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "x-api-key": apiKey,
                    "anthropic-version": "2023-06-01",
                    "anthropic-dangerous-direct-browser-access": "true",
                },
                body,
            });

            removeTyping();

            if (!resp.ok) {
                const errData = await resp.json();
                const errMsg = errData?.error?.message ?? `HTTP ${resp.status}`;
                addMsg(`API Error: ${errMsg}`, "system");
                this.chatHistory.pop();
                return;
            }

            const data = await resp.json();
            const rawReply = data.content.filter(b => b.type === "text").map(b => b.text).join("");

            const nfcCards = parseNfcCards(rawReply);
            const reply = stripNfcMarker(rawReply);

            this.chatHistory.push({ role: "assistant", content: trimForHistory(reply) });
            addMsg(reply, "bot");

            const code = extractCode(reply);
            if (code) {
                setCode(code);
                const label = userMsg.length > 40 ? userMsg.slice(0, 40) + "..." : userMsg;
                saveVersion(code, label);
                addMsg(`Code extracted to editor (v${getVersionCount()}) →`, "system");

                if (nfcCards && nfcCards.length > 0) {
                    addMsg(`This game uses NFC cards: ${nfcCards.join(", ")}. Write them before uploading.`, "system");
                    await showNfcCardsModal(nfcCards);
                }

                // Auto-prompt upload
                await this.onUpload();
            }
        } catch (e) {
            removeTyping();
            addMsg(`Error: ${e}`, "system");
        } finally {
            this.isGenerating = false;
            showStop(false);
        }
    }
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

const app = new App();
app.init();
