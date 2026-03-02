import asyncio
import json
from pyodide.http import pyfetch
from pyscript import window, document

# ── State ─────────────────────────────────────────────────────────────────────

fetched_files: dict[str, str] = {}   # filename → code content

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

def refresh_file_list():
    container = document.getElementById("file-list")
    if not fetched_files:
        container.innerHTML = "<em>No files fetched yet.</em>"
        return
    container.innerHTML = ""
    for fname, code in fetched_files.items():
        row = document.createElement("div")
        row.className = "file-row"

        # clicking a file loads it into preview
        row.innerHTML = (
            f'<span class="file-icon">📄</span>'
            f'<span class="file-name">{fname}</span>'
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
    """
    Convert  https://github.com/USER/REPO/tree/BRANCH/PATH
    to GitHub API  https://api.github.com/repos/USER/REPO/contents/PATH?ref=BRANCH
    Returns (api_url, user, repo, branch, path) or None on failure.
    """
    url = url.strip().rstrip("/")
    # Support both /tree/ and /blob/ (blob = single file via API)
    for marker in ["/tree/", "/blob/"]:
        if marker in url:
            after_github = url.replace("https://github.com/", "")
            parts = after_github.split(marker, 1)
            repo_part = parts[0]           # USER/REPO
            rest      = parts[1]           # BRANCH/optional/path
            branch_and_path = rest.split("/", 1)
            branch = branch_and_path[0]
            path   = branch_and_path[1] if len(branch_and_path) > 1 else ""
            api_url = f"https://api.github.com/repos/{repo_part}/contents/{path}?ref={branch}"
            return api_url
    return None

# ── Step 1a — Single file ─────────────────────────────────────────────────────

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

# ── Step 1b — Whole folder ────────────────────────────────────────────────────

async def _fetch_folder(url: str):
    api_url = parse_github_folder_url(url)
    if not api_url:
        set_status("fetch-status", "❌ Could not parse GitHub folder URL. Use a /tree/ URL.", "error")
        return

    set_status("fetch-status", "⏳ Listing folder contents via GitHub API …", "info")

    resp = await pyfetch(api_url, headers={"Accept": "application/vnd.github+json"})
    if not resp.ok:
        set_status("fetch-status", f"❌ GitHub API error {resp.status}. Private repos need a token.", "error")
        return

    items = json.loads(await resp.string())
    if not isinstance(items, list):
        set_status("fetch-status", "❌ Unexpected API response — is the URL a folder?", "error")
        return

    # Filter to files only (skip sub-directories for now)
    files = [item for item in items if item.get("type") == "file"]
    if not files:
        set_status("fetch-status", "⚠ No files found in that folder.", "warn")
        return

    total = len(files)
    set_status("fetch-status", f"⏳ Fetching {total} file(s) …", "info")

    errors = []
    for i, item in enumerate(files, 1):
        fname    = item["name"]
        raw_url  = item.get("download_url") or to_raw_url(item["html_url"])
        set_status("fetch-status", f"⏳ [{i}/{total}] Fetching {fname} …", "info")
        try:
            r = await pyfetch(raw_url)
            if r.ok:
                fetched_files[fname] = await r.string()
            else:
                errors.append(fname)
        except Exception as e:
            errors.append(f"{fname} ({e})")

    window.updatePreview(fetched_files)
    refresh_file_list()

    summary = f"✅ Fetched {len(fetched_files)} file(s)."
    if errors:
        summary += f" ⚠ Skipped: {', '.join(errors)}"
        set_status("fetch-status", summary, "warn")
    else:
        set_status("fetch-status", summary, "success")

# ── Dispatcher ────────────────────────────────────────────────────────────────

async def fetch_github():
    url       = document.getElementById("github-url").value.strip()
    save_name = document.getElementById("save-filename").value.strip()
    mode      = window._uploadMode   # "file" or "folder"

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
        set_status("fetch-status", f"❌ Unexpected error: {e}", "error")

# ── Step 2 — Serial ───────────────────────────────────────────────────────────

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
        document.getElementById("btn-upload").disabled     = False
        document.getElementById("btn-disconnect").disabled = False
        log(f"Connected at {baud} baud.")
    else:
        err = result.error if hasattr(result, "error") else "Unknown error"
        set_status("serial-status", f"❌ {err}", "error")

async def disconnect_serial():
    await window.disconnectSerial()
    set_status("serial-status", "⏏ Disconnected.", "info")
    document.getElementById("btn-connect").disabled    = False
    document.getElementById("btn-upload").disabled     = True
    document.getElementById("btn-disconnect").disabled = True
    log("Disconnected.")

# ── Raw REPL helpers ──────────────────────────────────────────────────────────

async def _write(text: str):
    await window.writeSerial(text)

async def _read(ms: int = 400) -> str:
    return await window.readSerialFor(ms)

async def _ctrl(char: str, pause: float = 0.15):
    await window.writeSerial(char)
    await asyncio.sleep(pause)

async def _upload_one(fname: str, code: str, target: str):
    """Upload a single file via MicroPython raw REPL."""
    log(f"  → Uploading as '{target}' ({len(code):,} bytes) …")
    safe = code.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    script = f'f=open("{target}","w")\nf.write("""{safe}""")\nf.close()\nprint("UPLOAD_OK")\n'
    await _write(script)
    await _ctrl("\x04", 1.8)           # Ctrl-D: execute
    resp = await _read(2500)
    log(f"    < {repr(resp[:120])}")
    return "UPLOAD_OK" in resp

# ── Upload dispatcher ─────────────────────────────────────────────────────────

async def upload_to_esp32():
    if not fetched_files:
        set_status("serial-status", "⚠ No files fetched yet.", "error")
        return

    mode = window._uploadMode

    # Interrupt + enter raw REPL (once, shared across all files)
    log("── Starting upload ──")
    set_status("serial-status", "⏳ Preparing device …", "info")

    await _ctrl("\x03", 0.3)   # Ctrl-C × 2
    await _ctrl("\x03", 0.3)
    await _ctrl("\x01", 0.4)   # Ctrl-A → raw REPL
    resp = await _read(600)
    log(f"Raw REPL: {repr(resp[:60])}")

    if mode == "file":
        # Single file: use the target-filename input
        fname  = next(iter(fetched_files))
        code   = fetched_files[fname]
        target = document.getElementById("target-filename").value.strip() or fname
        ok = await _upload_one(fname, code, target)
        if ok:
            set_status("serial-status", f"✅ '{target}' uploaded!", "success")
            log(f"✅ Done.")
        else:
            set_status("serial-status", "⚠ No confirmation received. Check log.", "warn")

    else:
        # Folder: upload every fetched file, preserve filenames
        total   = len(fetched_files)
        success = 0
        for fname, code in fetched_files.items():
            ok = await _upload_one(fname, code, fname)
            if ok:
                success += 1
            else:
                log(f"  ⚠ No UPLOAD_OK for '{fname}'")

        if success == total:
            set_status("serial-status", f"✅ All {total} file(s) uploaded!", "success")
            log(f"✅ {total}/{total} files uploaded.")
        else:
            set_status("serial-status", f"⚠ {success}/{total} files uploaded. Check log.", "warn")

    await _ctrl("\x02", 0.2)   # Ctrl-B → exit raw REPL

from pyscript import when

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