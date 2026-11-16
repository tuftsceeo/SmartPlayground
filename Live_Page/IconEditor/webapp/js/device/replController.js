/**
 * replController.js -- MicroPython REPL control-sequence protocol, on top
 * of serialAdapter.js. Used ONLY for installing the firmware (raw REPL
 * file writes) -- once icon_server.py is running, everything goes through
 * ndjsonLink.js's JSON-line protocol instead. Ported from the pattern
 * proven in Live_Page/WebApp2/mpy/repl_controller.py and
 * Live_Page/WebApp2/mpy/firmware_manager.py; see the plan §Mode switching.
 *
 * NOTE: the raw-REPL install path here is the least-tested part of the
 * device layer -- the JSON protocol has been exercised against real
 * hardware, this byte-level dance has not.
 */

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

const CTRL_C = "\x03";
const CTRL_A = "\x01";
const CTRL_B = "\x02";
const CTRL_D = "\x04";

export class ReplController {
  constructor(adapter) {
    this.adapter = adapter;
  }

  /** Break out of a running program (icon_server.py's JSON loop, or
   * anything else) back to the `>>>` prompt. */
  async enterRepl() {
    for (let i = 0; i < 3; i++) {
      await this.adapter.write(CTRL_C);
      await sleep(50);
    }
    await sleep(200);
    this.adapter.clearBacklog();
  }

  async enterRawRepl() {
    await this.adapter.write(CTRL_A);
    const { found } = await this.adapter.readUntil("raw REPL", 5000);
    if (!found) console.warn("replController: 'raw REPL' banner not seen -- continuing anyway");
  }

  async exitRawRepl() {
    await this.adapter.write(CTRL_B);
    await this.adapter.readUntil(">>>", 1000);
  }

  /**
   * Execute a script in raw REPL. Paces the write in chunks for anything
   * over 2KB (older MicroPython builds / small USB buffers) -- same
   * threshold as firmware_manager.py's upload chunking.
   */
  async execScript(code, { timeoutMs = 5000, chunkSize = null } = {}) {
    const cs = chunkSize ?? (code.length > 2048 ? 256 : null);
    if (cs) await this.adapter.writeChunked(code, cs, 10);
    else await this.adapter.write(code);
    await this.adapter.write(CTRL_D);
    await sleep(200);

    let response = "";
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const { found, text } = await this.adapter.readUntil("\x04>", 1000);
      response += text;
      if (found) break;
    }
    if (response.includes("Traceback") || response.includes("Error:")) {
      throw new Error(`device raised: ${response.trim()}`);
    }
    return response;
  }

  async softReset() {
    await this.adapter.write(CTRL_D);
  }

  /**
   * machine.reset(). AVOID on this board unless you mean it: a hard reset
   * re-enumerates USB, which destroys the Web Serial port the page holds --
   * the device comes back but the browser's handle does not, so recovery
   * needs a reconnect (sometimes a physical power cycle). Prefer softReset()
   * (Ctrl-D), which re-runs main.py without touching the USB device.
   */
  async hardReset() {
    await this.execScript("import machine; machine.reset()", { timeoutMs: 1000 }).catch(() => {
      /* the device resets before it can reply -- expected */
    });
  }

  /** `os.mkdir` guarded against "already exists". */
  async ensureDirectory(path) {
    await this.execScript(`import os\ntry:\n os.mkdir('${path}')\nexcept OSError:\n pass\n`);
  }

  /**
   * Write one file via raw REPL, base64-encoded to sidestep quote/escape
   * bugs entirely (matches Live_Page/Flasher/js/serial.js's approach,
   * which the plan calls out as more robust than firmware_manager.py's
   * triple-quote string escaping).
   */
  async uploadFile(path, content) {
    const bytes = typeof content === "string" ? new TextEncoder().encode(content) : content;
    let binary = "";
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
    const b64 = btoa(binary);
    const code =
      `import ubinascii\n` +
      `with open('${path}', 'wb') as f:\n` +
      ` f.write(ubinascii.a2b_base64('${b64}'))\n` +
      `print('OK')\n`;
    const timeoutMs = Math.max(5000, Math.floor(b64.length / 100)); // ~10KB/s floor, matches firmware_manager.py
    const response = await this.execScript(code, { timeoutMs });
    if (!response.includes("OK")) throw new Error(`upload of ${path} did not confirm OK: ${response}`);
  }
}
