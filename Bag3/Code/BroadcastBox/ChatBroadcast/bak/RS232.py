from pyscript import document, window
from pyscript.js_modules.micro_repl import default as Board
from pyodide.ffi import create_proxy
import json, asyncio, base64 as b64

# ============================================================
#  Config
# ============================================================

ENCRYPTED_KEY = ""   # Loaded from GitHub on startup

ENCRYPTED_KEY_URL = "https://raw.githubusercontent.com/tuftsceeo/SmartPlayground/refs/heads/beta_January_2026/Bag2/Utilities/encrypted_key.txt"  # Set this to your raw GitHub URL, e.g.:
# "https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/encrypted_key.txt"

KNOWLEDGE_FILES = [
    "knowledge/knowledge.py",
]

# NFC Writer — local file or GitHub raw URL
NFC_WRITER_URL = "https://raw.githubusercontent.com/tuftsceeo/SmartPlayground/refs/heads/beta_January_2026/Bag2/Utilities/writetoNFCcards.py"
# e.g. "https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/write_nfc.py"

FIFO_SIZE = 10000

# ============================================================
#  Encryption helper
# ============================================================

def xor_decrypt(encrypted_b64, passphrase):
    raw = b64.b64decode(encrypted_b64).decode('latin-1')
    result = []
    for i, ch in enumerate(raw):
        key_ch = passphrase[i % len(passphrase)]
        result.append(chr(ord(ch) ^ ord(key_ch)))
    return ''.join(result)

# ============================================================
#  Knowledge base loader
# ============================================================

async def load_knowledge_base():
    knowledge = ""
    for filepath in KNOWLEDGE_FILES:
        try:
            resp = await window.fetch(filepath)
            if resp.ok:
                text = await resp.text()
                knowledge += f"\n\n--- FILE: {filepath} ---\n{text}"
                window.console.log(f"Loaded knowledge: {filepath}")
        except Exception as e:
            window.console.log(f"Could not load {filepath}: {e}")
    return knowledge

# ============================================================
#  Chat helpers
# ============================================================

def add_msg(text, cls="bot"):
    box = document.getElementById("chat-box")
    div = document.createElement("div")
    div.classList.add("msg", cls)
    div.textContent = text
    box.appendChild(div)
    box.scrollTop = box.scrollHeight
    return div

def remove_typing():
    box = document.getElementById("chat-box")
    for m in box.querySelectorAll(".msg.system"):
        if m.textContent == "Thinking...":
            box.removeChild(m)

def extract_code(text):
    if "```" in text:
        blocks = text.split("```")
        for i in range(1, len(blocks), 2):
            code = blocks[i]
            lines = code.split("\n")
            if lines and lines[0].strip().lower() in ["python", "py", "micropython", ""]:
                code = "\n".join(lines[1:])
            return code.strip()
    return None

def trim_for_history(text):
    """Strip code blocks from assistant messages to save tokens.
    The code is already in the editor — no need to resend it."""
    if "```" not in text:
        return text
    parts = text.split("```")
    trimmed = []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            # Regular text — keep it
            trimmed.append(part)
        else:
            # Code block — replace with short note
            lines = part.strip().split("\n")
            line_count = len(lines) - 1  # subtract language identifier
            trimmed.append(f"\n[code: {line_count} lines, sent to editor]\n")
    return "".join(trimmed).strip()


# ============================================================
#  uRepl — your original class
# ============================================================

class uRepl():
    def __init__(self, baudrate=115200, buffer_size=256):
        self.connected = False
        self.terminal = None
        self.disconnect_callback = None
        self.newData_callback = None
        self.buffer = ''
        self.buffer_size = buffer_size
        self.path = None
        self.board = Board({
            "baudRate": baudrate,
            "dataType": "string",
            "onconnect": self.on_connect,
            "ondisconnect": self.on_disconnect,
            "ondata": self.on_data,
            "onresult": json.loads,
            "onerror": window.alert,
            "fontSize": '14',
            "fontFamily": 'Courier New',
            "theme": {
                "background": "#f8f9fa",
                "foreground": "#1f2937",
            },
        })

    async def on_data(self, chunk):
        self.buffer += chunk
        self.buffer = self.buffer[-FIFO_SIZE:]
        if self.newData_callback:
            await self.newData_callback(chunk)

    def on_connect(self):
        window.console.log('connected')
        self.connected = True
        self.terminal = self.board.terminal

    async def on_disconnect(self):
        self.connected = False
        self.terminal = None
        if self.disconnect_callback:
            await self.disconnect_callback()

    async def eval(self, payload, hidden=False):
        return await self.board.eval(payload, hidden=hidden)

    async def paste(self, payload, hidden=False):
        return await self.board.paste(payload, hidden=hidden)

    def focus(self):
        if self.terminal:
            self.terminal.focus()

# ============================================================
#  App
# ============================================================

class App():

    def __init__(self):
        self.uboard = uRepl()
        self.chat_history = []
        self.is_generating = False
        self.knowledge_text = ""
        self.code_versions = []    # list of {code, label, timestamp}
        self.version_index = -1    # current position in version list

        self.system_prompt_base = """You are an AI assistant helping users write MicroPython games for the PlaygroundV5 wand.

RULES:
- All board details, APIs, and hardware specs are in the KNOWLEDGE BASE below. Reference it.
- Generated code MUST follow the jumpin.py format with def play(nfc, leds, buz, accel, i2c)
- Put all code inside a fenced code block: ```python ... ```
- Do NOT use f-strings — they crash on this MicroPython build. Use % formatting only.
- Keep explanations concise — the code block is auto-extracted to the editor
- If the user sends serial output (prefixed with [HW]:), help debug it
- Always include try/finally cleanup and periodic NFC stop-tag polling
- Default to simple, working examples over complex ones"""

        self.uboard.disconnect_callback = self.on_disconnect
        self.bind_events()
        self.setup_disconnect_detection()
        self.update_version_ui()
        asyncio.ensure_future(self.init_knowledge())
        window.console.log("App ready!")

    # --------------------------------------------------------
    #  Startup
    # --------------------------------------------------------

    async def init_knowledge(self):
        global ENCRYPTED_KEY
        # Load encrypted API key from GitHub
        if ENCRYPTED_KEY_URL:
            try:
                resp = await window.fetch(ENCRYPTED_KEY_URL)
                if resp.ok:
                    ENCRYPTED_KEY = (await resp.text()).strip()
                    window.console.log("Encrypted key loaded.")
                else:
                    window.console.log("Failed to load encrypted key: HTTP %d" % resp.status)
            except Exception as e:
                window.console.log("Error loading encrypted key: %s" % str(e))

        # Load knowledge files
        self.knowledge_text = await load_knowledge_base()
        if self.knowledge_text:
            add_msg("Loaded %d knowledge file(s)." % len(KNOWLEDGE_FILES), "system")

    def setup_disconnect_detection(self):
        """Listen for USB disconnect via Web Serial API."""
        def on_serial_disconnect(event):
            if self.uboard.connected:
                self.uboard.connected = False
                self.uboard.terminal = None
                self.set_status(False)
                add_msg("Board disconnected.", "system")

        window.navigator.serial.addEventListener(
            "disconnect", create_proxy(on_serial_disconnect)
        )

    def get_system_prompt(self):
        prompt = self.system_prompt_base
        if self.knowledge_text:
            prompt += "\n\nPROJECT KNOWLEDGE BASE:\n" + self.knowledge_text
        return prompt

    # --------------------------------------------------------
    #  Event binding
    # --------------------------------------------------------

    def bind_events(self):
        def click(el_id, fn):
            document.getElementById(el_id).addEventListener("click", create_proxy(fn))

        click("btn-connect",      self.on_connect)
        click("btn-ctrlc",        self.send_CtrlC)
        click("btn-reset",        self.on_reset)
        click("btn-upload",       self.on_upload)
        click("btn-send",         self.on_send)
        click("btn-stop",         self.on_stop)
        click("btn-clear-code",   self.on_clear_code)
        click("btn-prev",         self.on_prev_version)
        click("btn-next",         self.on_next_version)
        click("btn-download",     self.on_download)
        click("btn-modal-unlock", self.on_unlock)
        click("btn-help",         self.on_help_open)
        click("btn-help-close",   self.on_help_close)
        click("help-overlay",     self.on_help_overlay_click)
        click("btn-tools",        self.on_tools_toggle)
        click("btn-write-nfc",    self.on_write_nfc)

        document.getElementById("user-input").addEventListener(
            "keydown", create_proxy(self.on_input_keydown))
        document.getElementById("modal-passphrase").addEventListener(
            "keydown", create_proxy(self.on_modal_keydown))
        document.getElementById("resizer").addEventListener(
            "mousedown", create_proxy(self.start_resize))
        document.addEventListener(
            "mousemove", create_proxy(self.do_resize))
        document.addEventListener(
            "mouseup", create_proxy(self.stop_resize))

        editor = document.getElementById("mpCode")
        if editor:
            editor.handleEvent = self.handle_board

    # --------------------------------------------------------
    #  Serial — from your original CEEO_RS232
    # --------------------------------------------------------

    async def on_connect(self, event=None):
        if self.uboard.connected:
            await self.uboard.board.disconnect()
            await self.on_disconnect()
        else:
            stop = document.getElementById("freshStart").checked
            name = await self.uboard.board.connect("repl", stop)
            window.console.log(name)
            if not name:
                return
            self.uboard.connected = True
            self.uboard.terminal = self.uboard.board.terminal
            self.set_status(True)
            add_msg(f"Connected to {name}", "system")

    async def on_disconnect(self, event=None):
        self.set_status(False)
        self.uboard.connected = False
        self.uboard.buffer = ''
        add_msg("Disconnected.", "system")

    async def send_CtrlC(self, event=None):
        if self.uboard.connected:
            await self.uboard.board.write('\x03')

    async def on_reset(self, event=None):
        if self.uboard.connected:
            await self.uboard.board.write('\x03')
            await asyncio.sleep(0.3)
            await self.uboard.board.write('\x03')
            await asyncio.sleep(0.5)
            await self.uboard.paste('import machine; machine.reset()')
            self.uboard.focus()

    async def on_run(self, event=None):
        """Test button — paste code into REPL and run."""
        if self.uboard.connected:
            editor = document.getElementById("mpCode")
            if editor and editor.code:
                await self.uboard.paste(editor.code)
                self.uboard.focus()
        else:
            add_msg("Connect your board first.", "system")

    def validate_jumpin(self, code):
        """Check if code follows jumpin.py format before uploading.
        Returns (ok, error_message)."""

        # 1. Syntax check
        try:
            compile(code, 'jumpin.py', 'exec')
        except SyntaxError as e:
            return False, "Syntax error on line %d: %s" % (e.lineno, e.msg)

        # 2. Must have a play() function
        has_play = False
        for line in code.split('\n'):
            stripped = line.strip()
            if stripped.startswith('def play(') or stripped.startswith('def play ('):
                has_play = True
                # 3. Check parameters
                expected_params = {'nfc', 'leds', 'buz', 'accel', 'i2c'}
                try:
                    params_str = stripped.split('(', 1)[1].split(')', 1)[0]
                    params = {p.strip() for p in params_str.split(',')}
                    missing = expected_params - params
                    if missing:
                        return False, (
                            "play() is missing parameters: %s\n"
                            "Expected: def play(nfc, leds, buz, accel, i2c)"
                            % ', '.join(sorted(missing))
                        )
                except:
                    return False, "Could not parse play() parameters."
                break

        if not has_play:
            return False, (
                "Missing def play(nfc, leds, buz, accel, i2c) function.\n"
                "main.py imports: from jumpin import play"
            )

        return True, None

    async def on_upload(self, event=None):
        """Upload button — validate, write to jumpin.py, then reset."""
        if self.uboard.connected:
            editor = document.getElementById("mpCode")
            if editor and editor.code:
                # Validate before upload
                ok, error = self.validate_jumpin(editor.code)
                if not ok:
                    add_msg(
                        "Upload rejected — this code doesn't follow jumpin.py format:\n\n"
                        "%s\n\n"
                        "To run code directly, use the editor's green play button.\n\n"
                        "Upload requires a def play(nfc, leds, buz, accel, i2c) function "
                        "because main.py calls: from jumpin import play" % error,
                        "system"
                    )
                    return

                code_bytes = editor.code.encode('utf-8')
                encoded = b64.b64encode(code_bytes).decode('ascii')

                CHUNK_SIZE = 512
                chunks = [encoded[i:i+CHUNK_SIZE] for i in range(0, len(encoded), CHUNK_SIZE)]

                if len(chunks) <= 1:
                    upload_cmd = (
                        "import ubinascii\n"
                        f"_d=ubinascii.a2b_base64('{encoded}')\n"
                        "f=open('jumpin.py','wb')\n"
                        "f.write(_d)\n"
                        "f.close()\n"
                        "print('jumpin.py uploaded:',len(_d),'bytes')\n"
                        "del _d\n"
                    )
                    await self.uboard.paste(upload_cmd)
                else:
                    open_cmd = (
                        "import ubinascii\n"
                        "f=open('jumpin.py','wb')\n"
                    )
                    await self.uboard.paste(open_cmd)
                    await asyncio.sleep(0.2)

                    for i, chunk in enumerate(chunks):
                        chunk_cmd = f"f.write(ubinascii.a2b_base64('{chunk}'))\n"
                        await self.uboard.paste(chunk_cmd)
                        await asyncio.sleep(0.1)

                    close_cmd = (
                        "f.close()\n"
                        f"print('jumpin.py uploaded: {len(code_bytes)} bytes in {len(chunks)} chunks')\n"
                    )
                    await self.uboard.paste(close_cmd)

                add_msg("Uploaded as jumpin.py. Resetting...", "system")
                await asyncio.sleep(0.5)
                await self.uboard.paste('import machine; machine.reset()')
                self.uboard.focus()
        else:
            add_msg("Connect your board first.", "system")

    async def handle_board(self, event):
        """Intercept mpy-editor run → send to board."""
        code = event.code
        if self.uboard.connected:
            await self.uboard.paste(code)
            self.uboard.focus()
            return False
        else:
            return True

    def on_clear_code(self, event=None):
        editor = document.getElementById("mpCode")
        if editor:
            editor.code = "# Code will appear here\n"

    # --------------------------------------------------------
    #  Version history
    # --------------------------------------------------------
    def save_version(self, code, label="AI generated"):
        """Save a new code version to history."""
        import time as pytime
        self.code_versions.append({
            "code": code,
            "label": label,
        })
        self.version_index = len(self.code_versions) - 1
        self.update_version_ui()

    def update_version_ui(self):
        """Update the version label and button states."""
        label_el = document.getElementById("version-label")
        prev_btn = document.getElementById("btn-prev")
        next_btn = document.getElementById("btn-next")

        total = len(self.code_versions)
        if total == 0:
            label_el.textContent = "v0/0"
            prev_btn.disabled = True
            next_btn.disabled = True
        else:
            current = self.version_index + 1
            label_el.textContent = "v%d/%d" % (current, total)
            prev_btn.disabled = (self.version_index <= 0)
            next_btn.disabled = (self.version_index >= total - 1)

    def on_prev_version(self, event=None):
        if self.version_index > 0:
            self.version_index -= 1
            v = self.code_versions[self.version_index]
            editor = document.getElementById("mpCode")
            if editor:
                editor.code = v["code"]
            self.update_version_ui()
            add_msg("Loaded v%d: %s" % (self.version_index + 1, v["label"]), "system")

    def on_next_version(self, event=None):
        if self.version_index < len(self.code_versions) - 1:
            self.version_index += 1
            v = self.code_versions[self.version_index]
            editor = document.getElementById("mpCode")
            if editor:
                editor.code = v["code"]
            self.update_version_ui()
            add_msg("Loaded v%d: %s" % (self.version_index + 1, v["label"]), "system")

    def on_download(self, event=None):
        """Download current code as a .py file."""
        editor = document.getElementById("mpCode")
        if not editor or not editor.code.strip():
            add_msg("Nothing to download.", "system")
            return

        code = editor.code
        # Create blob and trigger download via JS
        blob = window.Blob.new(
            [code],
            window.eval("({type:'text/plain'})")
        )
        url = window.URL.createObjectURL(blob)
        a = document.createElement("a")
        a.href = url
        # Name file with version number if available
        if self.version_index >= 0:
            a.download = "jumpin_v%d.py" % (self.version_index + 1)
        else:
            a.download = "jumpin.py"
        a.click()
        window.URL.revokeObjectURL(url)
        add_msg("Downloaded as %s" % a.download, "system")

    # --------------------------------------------------------
    #  Passphrase modal
    # --------------------------------------------------------

    def on_unlock(self, event=None):
        passphrase = document.getElementById("modal-passphrase").value.strip()
        error_el = document.getElementById("modal-error")

        if not passphrase:
            error_el.textContent = "Please enter the magic code."
            return
        if not ENCRYPTED_KEY:
            error_el.textContent = "No key configured. Contact your instructor."
            return
        try:
            key = xor_decrypt(ENCRYPTED_KEY, passphrase)
        except:
            error_el.textContent = "Invalid code. Try again."
            return
        if not key.startswith("sk-ant-"):
            error_el.textContent = "Wrong code. Try again."
            return

        document.getElementById("passphrase").value = passphrase
        document.getElementById("modal-overlay").classList.add("hidden")
        add_msg("Unlocked! You're ready to go.", "system")

    async def on_modal_keydown(self, event):
        if event.key == "Enter":
            self.on_unlock()

    # --------------------------------------------------------
    #  Help modal
    # --------------------------------------------------------
    def on_help_open(self, event=None):
        document.getElementById("help-overlay").classList.remove("hidden")

    def on_help_close(self, event=None):
        document.getElementById("help-overlay").classList.add("hidden")

    def on_help_overlay_click(self, event=None):
        # Close only if clicking the overlay background, not the modal itself
        if event and event.target.id == "help-overlay":
            self.on_help_close()

    # --------------------------------------------------------
    #  Tools toggle & Write NFC
    # --------------------------------------------------------
    def on_tools_toggle(self, event=None):
        nfc_btn = document.getElementById("btn-write-nfc")
        nfc_btn.classList.toggle("hidden")

    async def on_write_nfc(self, event=None):
        """Fetch the NFC writer script and paste it into the REPL."""
        if not self.uboard.connected:
            add_msg("Connect your board first.", "system")
            return

        add_msg("Loading NFC Tag Writer...", "system")
        try:
            resp = await window.fetch(NFC_WRITER_URL)
            if not resp.ok:
                add_msg("Failed to load NFC writer: HTTP %d" % resp.status, "system")
                return
            code = await resp.text()

            # Stop any running code first
            await self.uboard.board.write('\x03')
            await asyncio.sleep(0.3)

            # Paste the writer code and run it
            await self.uboard.paste(code)
            self.uboard.focus()
            add_msg(
                "NFC Tag Writer loaded! Follow the prompts in the REPL:\n"
                "1. Type the text you want on the tag\n"
                "2. Place a tag on the wand\n"
                "3. Press the button on the wand to write\n"
                "4. Type 'quit' when done",
                "system"
            )
        except Exception as e:
            add_msg("Error loading NFC writer: %s" % str(e), "system")

    # --------------------------------------------------------
    #  Chat
    # --------------------------------------------------------

    async def on_send(self, event=None):
        inp = document.getElementById("user-input")
        msg = inp.value.strip()
        if not msg or self.is_generating:
            return
        inp.value = ""
        add_msg(msg, "user")
        await self.call_claude(msg)

    async def on_input_keydown(self, event):
        if event.key == "Enter" and not event.shiftKey:
            event.preventDefault()
            await self.on_send()

    def on_stop(self, event=None):
        self.is_generating = False
        remove_typing()
        self.show_stop(False)
        add_msg("Stopped.", "system")

    # --------------------------------------------------------
    #  Claude API (with prompt caching)
    # --------------------------------------------------------

    async def call_claude(self, user_msg):
        passphrase = document.getElementById("passphrase").value.strip()
        if not passphrase:
            add_msg("Enter the magic code first.", "system")
            return
        if not ENCRYPTED_KEY:
            add_msg("No API key configured.", "system")
            return

        try:
            api_key = xor_decrypt(ENCRYPTED_KEY, passphrase)
        except:
            add_msg("Invalid passphrase.", "system")
            return
        if not api_key.startswith("sk-ant-"):
            add_msg("Wrong passphrase.", "system")
            return

        self.chat_history.append({"role": "user", "content": user_msg})
        add_msg("Thinking...", "system")
        self.show_stop(True)
        self.is_generating = True

        try:
            body = json.dumps({
                "model": "claude-sonnet-4-6",
                "max_tokens": 16384,
                "system": [
                    {
                        "type": "text",
                        "text": self.get_system_prompt(),
                        "cache_control": {"type": "ephemeral"}
                    }
                ],
                "messages": self.chat_history[-10:]
            })

            headers = window.eval(
                "({'Content-Type':'application/json',"
                "'x-api-key':'" + api_key.replace("'", "\\'") + "',"
                "'anthropic-version':'2023-06-01',"
                "'anthropic-dangerous-direct-browser-access':'true'})"
            )
            opts = window.eval("({method:'POST'})")
            opts.headers = headers
            opts.body = body

            resp = await window.fetch(
                "https://api.anthropic.com/v1/messages", opts
            )
            remove_typing()

            if not resp.ok:
                err_data = await resp.json()
                try:
                    err_msg = err_data.error.message
                except:
                    err_msg = f"HTTP {resp.status}"
                add_msg(f"API Error: {err_msg}", "system")
                self.chat_history.pop()
                return

            data = await resp.json()
            reply = ""
            for i in range(data.content.length):
                block = data.content[i]
                if block.type == "text":
                    reply += block.text

            self.chat_history.append({"role": "assistant", "content": trim_for_history(reply)})
            add_msg(reply, "bot")

            code = extract_code(reply)
            if code:
                editor = document.getElementById("mpCode")
                if editor:
                    editor.code = code
                # Save to version history
                # Use first line of user message as label
                label = user_msg[:40]
                if len(user_msg) > 40:
                    label += "..."
                self.save_version(code, label)
                add_msg("Code extracted to editor (v%d) →" % len(self.code_versions), "system")

        except Exception as e:
            remove_typing()
            add_msg(f"Error: {str(e)}", "system")
        finally:
            self.is_generating = False
            self.show_stop(False)

    # --------------------------------------------------------
    #  UI helpers
    # --------------------------------------------------------

    def set_status(self, connected):
        dot = document.getElementById("serial-status")
        txt = document.getElementById("status-text")
        btn = document.getElementById("btn-connect")
        if connected:
            dot.classList.add("connected")
            txt.textContent = "Connected"
            btn.textContent = "Disconnect"
            btn.classList.add("on")
        else:
            dot.classList.remove("connected")
            txt.textContent = "Disconnected"
            btn.textContent = "Connect"
            btn.classList.remove("on")

    def show_stop(self, show):
        send = document.getElementById("btn-send")
        stop = document.getElementById("btn-stop")
        send.style.display = "none" if show else "block"
        stop.style.display = "block" if show else "none"

    # --------------------------------------------------------
    #  Panel resizer
    # --------------------------------------------------------

    _resizing = False

    def start_resize(self, event):
        self._resizing = True
        document.body.style.cursor = 'col-resize'
        document.body.style.userSelect = 'none'

    def do_resize(self, event):
        if not self._resizing:
            return
        layout = document.getElementById("main-layout")
        left = document.getElementById("left-panel")
        rect = layout.getBoundingClientRect()
        pct = ((event.clientX - rect.left) / rect.width) * 100
        pct = max(25, min(75, pct))
        left.style.width = f"{pct}%"

    def stop_resize(self, event):
        if self._resizing:
            self._resizing = False
            document.body.style.cursor = ''
            document.body.style.userSelect = ''