export const MAX_UPLOAD_RETRIES = 3;

const EXEC_END = "\x04\x04";
/** Match WebApp2 repl_controller — pace serial writes on large scripts. */
const SERIAL_CHUNK = 256;
const SERIAL_CHUNK_DELAY_MS = 10;
/** Split large file bodies across multiple on-device writes. */
const FILE_WRITE_CHUNK = 4096;

function normalizeRoot(root) {
  if (!root || root === "/") return "/";
  return root.replace(/\/$/, "");
}

/** Device path for open() — e.g. root="/flash", rel="main.py" → "/flash/main.py" */
export function deviceFilePath(devicePathRoot, relPath) {
  const root = normalizeRoot(devicePathRoot);
  const rel = relPath.replace(/^\//, "");
  if (root === "/") return rel;
  return `${root}/${rel}`;
}

/** Escape for triple-quoted Python string (WebApp2 firmware_manager). */
function escapeForTripleQuoted(content) {
  return content.replace(/\\/g, "\\\\").replace(/'''/g, "\\'\\'\\'");
}

function uploadSortKey(relPath) {
  if (relPath === "main.py") return "0";
  if (relPath === "boot.py") return "1";
  if (relPath.startsWith("lib/")) return "2" + relPath;
  return "3" + relPath;
}

export class SerialEngine {
  constructor({ log = () => {} } = {}) {
    this.log = log;
    this.serialPort = null;
    this.serialWriter = null;
    this.serialReader = null;
    this.readBuf = "";
    this.readWaiters = [];
    this._onDisconnect = null;
  }

  isConnected() {
    return !!this.serialPort;
  }

  setOnDisconnect(fn) {
    this._onDisconnect = fn;
  }

  notifyWaiters() {
    this.readWaiters = this.readWaiters.filter((w) => {
      const idx = this.readBuf.indexOf(w.pattern);
      if (idx === -1) return true;
      const result = this.readBuf.slice(0, idx + w.pattern.length);
      this.readBuf = this.readBuf.slice(idx + w.pattern.length);
      clearTimeout(w.timer);
      w.resolve(result);
      return false;
    });
  }

  readUntil(pattern, timeoutMs = 2000) {
    return new Promise((resolve) => {
      const w = {
        pattern,
        resolve,
        timer: setTimeout(() => {
          this.readWaiters = this.readWaiters.filter((x) => x !== w);
          const result = this.readBuf;
          this.readBuf = "";
          resolve(result);
        }, timeoutMs),
      };
      this.readWaiters.push(w);
      this.notifyWaiters();
    });
  }

  flushBuf() {
    this.readBuf = "";
  }

  sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  async serialWrite(text) {
    await this.serialWriter.write(new TextEncoder().encode(text));
  }

  async ctrl(char, pauseMs = 100) {
    await this.serialWrite(char);
    await this.sleep(pauseMs);
  }

  /**
   * Execute Python in raw REPL. Large scripts are sent in paced chunks
   * (same strategy as WebApp2 mpy/repl_controller.py).
   */
  async execScript(script, timeoutMs = 4000) {
    const useChunks = script.length > 2048;
    if (useChunks) {
      for (let i = 0; i < script.length; i += SERIAL_CHUNK) {
        await this.serialWrite(script.slice(i, i + SERIAL_CHUNK));
        await this.sleep(SERIAL_CHUNK_DELAY_MS);
      }
    } else {
      await this.serialWrite(script);
    }

    await this.ctrl("\x04");
    const resp = await this.readUntil(EXEC_END, timeoutMs);
    const body = resp.startsWith("OK") ? resp.slice(2) : resp;
    const parts = body.split("\x04");
    const stdout = (parts[0] || "").trim();
    const stderr = (parts[1] || "").trim();

    if (resp.includes("Traceback") || stderr.includes("Traceback")) {
      return [stdout, stderr || "Traceback on device"];
    }
    return [stdout, stderr];
  }

  async enterRawRepl() {
    this.flushBuf();
    for (let i = 0; i < 3; i++) {
      await this.ctrl("\x03", 50);
    }
    await this.sleep(200);
    this.flushBuf();

    await this.ctrl("\x01", 300);
    const banner = await this.readUntil("raw REPL", 5000);
    if (!banner.includes("raw REPL")) {
      await this.readUntil(">", 2000);
    }
    this.flushBuf();
  }

  async exitRawRepl() {
    await this.ctrl("\x02", 200);
    await this.sleep(200);
    this.flushBuf();
  }

  async connect(baudRate) {
    if (!("serial" in navigator)) {
      throw new Error("Web Serial not supported. Use Chrome or Edge.");
    }

    this.serialPort = await navigator.serial.requestPort();
    await this.serialPort.open({ baudRate });
    const dec = new TextDecoder();

    const startReadLoop = () => {
      this.serialWriter = this.serialPort.writable.getWriter();
      this.readBuf = "";
      this.serialReader = this.serialPort.readable.getReader();
      let reenumDetected = false;
      (async () => {
        try {
          while (true) {
            const { value, done } = await this.serialReader.read();
            if (done) {
              reenumDetected = true;
              break;
            }
            this.readBuf += dec.decode(value, { stream: true });
            this.notifyWaiters();
          }
        } catch (_) {
          reenumDetected = true;
        }
      })();
      return () => reenumDetected;
    };

    let wasReenumed = startReadLoop();
    await this.sleep(1500);

    if (wasReenumed() || !this.readBuf) {
      this.log("⏳ USB re-enumeration detected — waiting for MicroPython CDC…", "info");
      try {
        await this.serialReader.cancel();
      } catch (_) {}
      try {
        this.serialReader.releaseLock();
      } catch (_) {}
      this.serialReader = null;
      try {
        this.serialWriter.releaseLock();
      } catch (_) {}
      this.serialWriter = null;
      try {
        await this.serialPort.close();
      } catch (_) {}
      await this.sleep(2500);
      await this.serialPort.open({ baudRate });
      startReadLoop();
      await this.sleep(500);
    }
    this.flushBuf();

    this.serialPort.addEventListener("disconnect", () => {
      this._onDisconnect?.();
    });

    this.log(`Connected at ${baudRate} baud.`, "dim");
  }

  async disconnect() {
    this.readWaiters.forEach((w) => {
      clearTimeout(w.timer);
      w.resolve("");
    });
    this.readWaiters = [];
    try {
      if (this.serialReader) {
        await this.serialReader.cancel();
        this.serialReader.releaseLock();
        this.serialReader = null;
      }
      if (this.serialWriter) {
        this.serialWriter.releaseLock();
        this.serialWriter = null;
      }
      if (this.serialPort) {
        await this.serialPort.close();
        this.serialPort = null;
      }
    } catch (_) {}
    this.readBuf = "";
    this.log("Disconnected.");
  }

  async readDeviceInfo(devicePathRoot = "/") {
    const root = normalizeRoot(devicePathRoot);
    const rootLit = JSON.stringify(root);
    await this.enterRawRepl();
    const [stdout, stderr] = await this.execScript(
      `import os\n` +
        `root=${rootLit}\n` +
        `files={f.lower():f for f in os.listdir(root)}\n` +
        `def fp(k):\n` +
        `  if k not in files: raise OSError\n` +
        `  return (root+"/"+files[k]) if root!="/" else files[k]\n` +
        `try:\n  f=open(fp("hubtype.txt"));t=f.read().strip();f.close()\nexcept:t=""\n` +
        `try:\n  f=open(fp("hubname.txt"));n=f.read().strip();f.close()\nexcept:n=""\n` +
        `print(t+"\\n"+n)\n`,
      3000
    );
    await this.exitRawRepl();
    if (stderr) {
      this.log(`  ⚠ ${stderr}`, "err");
      return { hubType: null, hubName: null };
    }
    const lines = stdout.split("\n");
    const hubType = lines[0]?.trim() || null;
    const hubName = lines[1]?.trim() || null;
    this.log(`  hubType: "${hubType}", hubName: "${hubName}"`, "dim");
    return { hubType, hubName };
  }

  async readBoardInfo() {
    await this.enterRawRepl();
    const [stdout, stderr] = await this.execScript(
      `import os\nu=os.uname()\nprint("MicroPython "+u.version+"; "+u.machine)\n`,
      4000
    );
    await this.exitRawRepl();
    if (stderr) throw new Error(stderr);
    const line = stdout.split("\n").find((l) => l.trim().startsWith("MicroPython "));
    if (!line) throw new Error("Could not read board info from device");
    this.log(`  board: ${line.trim()}`, "dim");
    return line.trim();
  }

  async writeHubType(hubType, hubName, devicePathRoot = "/") {
    const hubPath = deviceFilePath(devicePathRoot, "hubType.txt");
    const namePath = deviceFilePath(devicePathRoot, "hubName.txt");
    await this.enterRawRepl();
    const [, e1] = await this.execScript(
      `f=open(${JSON.stringify(hubPath)},"w")\nf.write(${JSON.stringify(hubType)})\nf.close()\nprint('OK')\n`,
      3000
    );
    if (e1) throw new Error(e1);
    if (hubName) {
      const [, e2] = await this.execScript(
        `f=open(${JSON.stringify(namePath)},"w")\nf.write(${JSON.stringify(hubName)})\nf.close()\nprint('OK')\n`,
        3000
      );
      if (e2) throw new Error(e2);
    }
    await this.exitRawRepl();
  }

  async ensureDirectory(dirPath) {
    if (!dirPath || dirPath === "/" || dirPath === ".") return true;
    const [, stderr] = await this.execScript(
      `import os\ntry:\n os.mkdir(${JSON.stringify(dirPath)})\nexcept OSError:\n pass\nprint('OK')\n`,
      3000
    );
    if (stderr) {
      this.log(`  mkdir '${dirPath}' → err: ${stderr}`, "err");
      return false;
    }
    return true;
  }

  /**
   * Upload one file using WebApp2 firmware_manager text-write strategy.
   * open(path,'w') truncates existing files — no filesystem wipe needed.
   */
  async uploadOne(devicePath, content) {
    this.log(`  → '${devicePath}' (${content.length.toLocaleString()} bytes) …`);
    const pathLit = JSON.stringify(devicePath);
    const chunks = [];
    for (let i = 0; i < content.length; i += FILE_WRITE_CHUNK) {
      chunks.push(content.slice(i, i + FILE_WRITE_CHUNK));
    }
    if (chunks.length === 0) chunks.push("");

    for (let i = 0; i < chunks.length; i++) {
      const mode = i === 0 ? "w" : "a";
      const escaped = escapeForTripleQuoted(chunks[i]);
      const script =
        `with open(${pathLit},'${mode}') as f:\n` +
        ` f.write('''${escaped}''')\n` +
        `print('OK')\n`;
      const timeoutMs = Math.max(8000, chunks[i].length * 2);
      const [, stderr] = await this.execScript(script, timeoutMs);
      if (stderr) {
        this.log(`    ✗ ${stderr}`, "err");
        return false;
      }
    }
    this.log("    ✓ ok", "dim");
    return true;
  }

  async softReset() {
    this.log("🔄 Rebooting …");
    await this.exitRawRepl();
    this.flushBuf();
    await this.ctrl("\x04", 300);
    await this.sleep(1500);
    const resp = await this.readUntil(">>>", 4000);
    this.log(`Boot: ${resp.slice(0, 80).replace(/\r\n/g, " ")}`, "dim");
    this.log("✅ Running main.py");
  }

  getDirsToCreate(relPaths) {
    const dirs = new Set();
    for (const p of relPaths) {
      const parts = p.split("/");
      for (let i = 1; i < parts.length; i++) {
        dirs.add(parts.slice(0, i).join("/"));
      }
    }
    return [...dirs].sort((a, b) => a.split("/").length - b.split("/").length);
  }

  async attemptUpload(fetchedFiles, device) {
    this.log("── Starting upload (WebApp2-style, no wipe) ──");
    await this.enterRawRepl();

    const relPaths = Object.keys(fetchedFiles).sort((a, b) =>
      uploadSortKey(a).localeCompare(uploadSortKey(b))
    );

    const dirs = this.getDirsToCreate(relPaths);
    if (dirs.length) {
      this.log(`📁 Creating dirs: ${dirs.join(", ")}`, "dim");
      for (const d of dirs) {
        const absDir = deviceFilePath(device.devicePathRoot, d);
        if (!(await this.ensureDirectory(absDir))) {
          await this.exitRawRepl();
          return { success: false, index: 0, total: relPaths.length };
        }
      }
    }

    for (let i = 0; i < relPaths.length; i++) {
      const relPath = relPaths[i];
      const absPath = deviceFilePath(device.devicePathRoot, relPath);
      if (!(await this.uploadOne(absPath, fetchedFiles[relPath]))) {
        this.log(`  ✗ Failed on '${relPath}', will retry.`, "err");
        await this.exitRawRepl();
        return { success: false, index: i, total: relPaths.length };
      }
    }

    await this.softReset();
    this.log(`✅ ${relPaths.length} file(s) uploaded.`);
    return { success: true, total: relPaths.length };
  }

  async uploadWithRetry(fetchedFiles, device, { onProgress, onStatus } = {}) {
    let attempt = 0;
    while (attempt <= MAX_UPLOAD_RETRIES) {
      if (attempt > 0) {
        this.log(
          `⚠ Retrying upload (attempt ${attempt}/${MAX_UPLOAD_RETRIES}) …`,
          "err"
        );
        onStatus?.("⏳ Resetting device before retry …");
        await this.exitRawRepl();
        this.flushBuf();
        await this.ctrl("\x04", 300);
        await this.sleep(2000);
        await this.readUntil(">>>", 4000);
        this.flushBuf();
      }

      onProgress?.(15);
      onStatus?.("⏳ Uploading files …");
      const result = await this.attemptUpload(fetchedFiles, device);
      if (result.success) {
        onProgress?.(100);
        return result;
      }
      attempt++;
    }
    throw new Error("Upload failed after retries");
  }
}
