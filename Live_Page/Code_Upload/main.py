import asyncio
import json
from pyodide.http import pyfetch
from pyscript import window, document, when

# ── State ─────────────────────────────────────────────────────────────────────

fetched_files: dict[str, str] = {}

# ── UI helpers ────────────────────────────────────────────────────────────────

def set_status(elem_id: str, msg: str, kind: str = "info"):
    el = document.getElementById(elem_id)
    el.textContent = msg
    el.className = f"status {kind}"

def log(msg: str):
    document.getElementById("log-wrap").classList.remove("hidden")
    box = document.getElementById("serial-log")
    entry = document.createElement("div")
    entry.textContent = msg
    box.appendChild(entry)
    box.scrollTop = box.scrollHeight

def update_upload_btn():
    has_files = len(fetched_files) > 0
    connected = document.getElementById("btn-connect").disabled
    document.getElementById("btn-upload").disabled = not (has_files and connected)

def refresh_file_list():
    container = document.getElementById("file-list")
    if not fetched_files:
        container.innerHTML = "<em>No files fetched yet.</em>"
        return
    container.innerHTML = ""
    for fpath, code in fetched_files.items():
        row = document.createElement("div")
        row.className = "file-row"
        row.innerHTML = (
            f'<span class="file-icon">📄</span>'
            f'<span class="file-name">{fpath}</span>'
            f'<span class="file-size">{len(code):,} bytes</span>'
        )
        container.appendChild(row)

def to_raw_url(url: str) -> str:
    url = url.strip()
    if "raw.githubusercontent.com" in url:
        return url
    url = url.replace("https://github.com/", "https://raw.githubusercontent.com/")
    url = url.replace("/blob/", "/")
    return url

def parse_github_folder_url(url: str):
    url = url.strip().rstrip("/")
    for marker in ["/tree/", "/blob/"]:
        if marker in url:
            after = url.replace("https://github.com/", "")
            repo_part, rest = after.split(marker, 1)
            parts  = rest.split("/", 1)
            branch = parts[0]
            path   = parts[1] if len(parts) > 1 else ""
            return f"https://api.github.com/repos/{repo_part}/contents/{path}?ref={branch}"
    return None

def get_dirs_to_create(file_paths: list[str]) -> list[str]:
    dirs = set()
    for path in file_paths:
        parts = path.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))
    return sorted(dirs, key=lambda d: d.count("/"))

# ── GitHub fetch ──────────────────────────────────────────────────────────────

async def _fetch_single_file(url: str, save_name: str):
    raw_url = to_raw_url(url)
    set_status("fetch-status", f"⏳ Fetching {raw_url} …", "info")
    resp = await pyfetch(raw_url)
    if not resp.ok:
        set_status("fetch-status", f"❌ HTTP {resp.status}", "error")
        return
    code = await resp.string()
    fetched_files[save_name] = code
    window.updatePreview(fetched_files)
    document.getElementById("target-filename").value = save_name
    refresh_file_list()
    set_status("fetch-status", f"✅ Fetched '{save_name}' ({len(code):,} bytes)", "success")
    update_upload_btn()

async def _fetch_folder_recursive(api_url: str, prefix: str = "", counter: list = None):
    if counter is None:
        counter = [0]

    resp = await pyfetch(api_url, headers={"Accept": "application/vnd.github+json"})
    if not resp.ok:
        log(f"  ⚠ API error {resp.status} for {api_url}")
        return

    items = json.loads(await resp.string())
    if not isinstance(items, list):
        log(f"  ⚠ Unexpected response at {api_url}")
        return

    for item in items:
        name     = item.get("name", "")
        rel_path = f"{prefix}/{name}" if prefix else name

        if item.get("type") == "file":
            raw_url = item.get("download_url") or to_raw_url(item["html_url"])
            set_status("fetch-status", f"⏳ Fetching {rel_path} …", "info")
            try:
                r = await pyfetch(raw_url)
                if r.ok:
                    fetched_files[rel_path] = await r.string()
                    counter[0] += 1
                else:
                    log(f"  ⚠ HTTP {r.status} for {rel_path}")
            except Exception as e:
                log(f"  ⚠ Error fetching {rel_path}: {e}")

        elif item.get("type") == "dir":
            sub_api_url = item.get("url")
            if sub_api_url:
                log(f"  📁 Entering: {rel_path}/")
                await _fetch_folder_recursive(sub_api_url, rel_path, counter)

async def _fetch_folder(url: str):
    api_url = parse_github_folder_url(url)
    if not api_url:
        set_status("fetch-status", "❌ Could not parse GitHub folder URL. Use a /tree/ URL.", "error")
        return
    set_status("fetch-status", "⏳ Listing folder contents …", "info")
    fetched_files.clear()
    counter = [0]
    await _fetch_folder_recursive(api_url, "", counter)
    if not fetched_files:
        set_status("fetch-status", "⚠ No files found.", "warn")
        return
    window.updatePreview(fetched_files)
    refresh_file_list()
    set_status("fetch-status", f"✅ Fetched {counter[0]} file(s).", "success")
    update_upload_btn()

async def fetch_github():
    url       = document.getElementById("github-url").value.strip()
    save_name = document.getElementById("save-filename").value.strip()
    mode      = window._uploadMode
    if not url:
        set_status("fetch-status", "⚠ Please enter a GitHub URL.", "error")
        return
    try:
        if mode == "folder":
            await _fetch_folder(url)
        else:
            if not save_name:
                save_name = url.rstrip("/").split("/")[-1] or "code.py"
                document.getElementById("save-filename").value = save_name
            await _fetch_single_file(url, save_name)
    except Exception as e:
        set_status("fetch-status", f"❌ {e}", "error")

# ── Serial connection ─────────────────────────────────────────────────────────

async def connect_serial():
    if not window.isSerialSupported():
        set_status("serial-status", "❌ Web Serial not supported. Use Chrome or Edge.", "error")
        return
    baud = document.getElementById("baud-rate").value
    set_status("serial-status", "⏳ Requesting serial port …", "info")
    result = await window.connectSerial(baud)
    ok = result.ok if hasattr(result, "ok") else result.to_py().get("ok")
    if ok:
        set_status("serial-status", f"✅ Connected at {baud} baud.", "success")
        document.getElementById("btn-connect").disabled    = True
        document.getElementById("btn-disconnect").disabled = False
        update_upload_btn()
        log(f"Connected at {baud} baud.")
    else:
        err = getattr(result, "error", "Unknown error")
        set_status("serial-status", f"❌ {err}", "error")

async def disconnect_serial():
    await window.disconnectSerial()
    set_status("serial-status", "⏏ Disconnected.", "info")
    document.getElementById("btn-connect").disabled    = False
    document.getElementById("btn-upload").disabled     = True
    document.getElementById("btn-disconnect").disabled = True
    log("Disconnected.")

# ── Raw REPL helpers ──────────────────────────────────────────────────────────

EXEC_END = "\x04\x04"

async def _write(text: str):
    await window.writeSerial(text)

async def _ctrl(char: str, pause: float = 0.1):
    await window.writeSerial(char)
    await asyncio.sleep(pause)

async def _read_until(pattern: str, timeout_ms: int = 2000) -> str:
    return await window.readUntil(pattern, timeout_ms)

async def _flush():
    window.flushReadBuf()
    await asyncio.sleep(0.05)

async def _exec(script: str, timeout_ms: int = 3000) -> tuple[str, str]:
    await _write(script)
    await _ctrl("\x04")
    resp = await _read_until(EXEC_END, timeout_ms)
    if resp.startswith("OK"):
        resp = resp[2:]
    parts  = resp.split("\x04")
    stdout = parts[0] if len(parts) > 0 else ""
    stderr = parts[1] if len(parts) > 1 else ""
    return stdout.strip(), stderr.strip()

async def _mkdir(dir_path: str) -> bool:
    script = (
        "import os\n"
        "try:\n"
        f'  os.mkdir("{dir_path}")\n'
        "except OSError:\n"
        "  pass\n"
    )
    stdout, stderr = await _exec(script, 2000)
    log(f"  mkdir '{dir_path}' → {'ok' if not stderr else repr(stderr)}")
    return not stderr

async def _upload_one(rel_path: str, code: str) -> bool:
    log(f"  → '{rel_path}' ({len(code):,} bytes) …")
    hex_str = code.encode("utf-8").hex()
    script = (
        "import ubinascii\n"
        f'f = open("{rel_path}", "wb")\n'
        f'f.write(ubinascii.unhexlify("{hex_str}"))\n'
        "f.close()\n"
    )
    stdout, stderr = await _exec(script, 5000)
    if stderr:
        log(f"    ✗ stderr: {repr(stderr)}")
        return False
    log(f"    ✓ ok")
    return True

async def _soft_reset():
    """Exit raw REPL then send Ctrl-D to soft-reset — MicroPython will run main.py."""
    log("🔄 Soft resetting device …")
    await _ctrl("\x02", 0.3)      # Ctrl-B: exit raw REPL → friendly REPL
    await _flush()
    await _ctrl("\x04", 0.3)      # Ctrl-D: soft reset → runs main.py
    await asyncio.sleep(1.5)      # give the device time to boot
    resp = await _read_until(">>>", 3000)
    log(f"Boot output: {repr(resp[:120])}")
    log("✅ Device rebooted and running main.py.")

# ── Upload dispatcher ─────────────────────────────────────────────────────────

async def upload_to_esp32():
    if not fetched_files:
        set_status("serial-status", "⚠ No files fetched yet.", "error")
        return

    mode = window._uploadMode
    log("── Starting upload ──")
    set_status("serial-status", "⏳ Preparing device …", "info")

    # Interrupt + enter raw REPL
    await _ctrl("\x03", 0.3)
    await _ctrl("\x03", 0.3)
    await _flush()
    await _ctrl("\x01", 0.4)
    resp = await _read_until(">", 1500)
    log(f"Raw REPL entry: {repr(resp[-30:])}")
    await _flush()

    if mode == "file":
        fname  = next(iter(fetched_files))
        code   = fetched_files[fname]
        target = document.getElementById("target-filename").value.strip() or fname
        ok = await _upload_one(target, code)
        if ok:
            set_status("serial-status", "⏳ Upload done, rebooting …", "info")
            await _soft_reset()
            set_status("serial-status", f"✅ '{target}' uploaded and running!", "success")
        else:
            set_status("serial-status", "⚠ Upload may have failed. Check log.", "warn")

    else:
        # Create directories first
        dirs = get_dirs_to_create(list(fetched_files.keys()))
        if dirs:
            log(f"📁 Creating {len(dirs)} director(y/ies): {dirs}")
            for d in dirs:
                await _mkdir(d)

        # Upload all files
        total   = len(fetched_files)
        success = 0
        for i, (rel_path, code) in enumerate(fetched_files.items(), 1):
            set_status("serial-status", f"⏳ Uploading {i}/{total}: {rel_path} …", "info")
            ok = await _upload_one(rel_path, code)
            if ok:
                success += 1

        if success == total:
            set_status("serial-status", "⏳ All files uploaded, rebooting …", "info")
            await _soft_reset()
            set_status("serial-status", f"✅ All {total} file(s) uploaded and running!", "success")
            log(f"✅ {total}/{total} files uploaded.")
        else:
            set_status("serial-status", f"⚠ {success}/{total} uploaded. Check log.", "warn")
            log(f"⚠ {total - success} file(s) may have failed.")

# ── Event bindings ────────────────────────────────────────────────────────────

@when("click", "#btn-fetch")
async def on_fetch(event):
    await fetch_github()

@when("click", "#btn-connect")
async def on_connect(event):
    await connect_serial()

@when("click", "#btn-upload")
async def on_upload(event):
    await upload_to_esp32()

@when("click", "#btn-disconnect")
async def on_disconnect(event):
    await disconnect_serial()