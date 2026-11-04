# ESP32 ↔ Web Serial: Rules

## Connection lifecycle

*Why: the device may be booting, resetting on port-open, or mid-task when you connect. Any awaited handshake can lose that race and latch a permanent false negative.*

- `connect()` resolves when the port opens. Never gate connection state on an awaited handshake reply.

```js
// BROKEN — one lost race latches "no firmware" forever
async connect() {
  await adapter.connect();
  try { await link.hello(); return "running"; }
  catch { return "needs-install"; }
}

// CORRECT — opening the port and learning what's there are separate events
async connect() {
  await adapter.connect();
  const link = attachJsonLink();
  link.on("hello", () => { running = true; });      // fires whenever it arrives
  link.hello({ timeoutMs: 4000 }).catch(() => {});  // fire-and-forget nudge
}
```

- Device identity must arrive via a persistent event listener, not a timed await.
- Firmware announces identity at boot **and** answers an explicit `hello` query, with identical payloads — so the host has one code path for both.
- Attach the parser before opening the port. Send a probe after attaching to cover the already-booted case.

---

## Device state detection

*Why: the REPL is connected, responsive, and echoes input. It mimics a working link while answering nothing, so a two-state model hangs forever.*

- Model three states: firmware running, at REPL prompt, absent.

```
TX  {"cmd":"hello","id":9002}
RX  {"cmd":"hello","id":9002}      ← echo, not a reply
```

- Make commands and replies structurally distinguishable: host→device carries `cmd`, device→host carries `type`. An inbound `cmd` without `type` can only be an echo.

```js
if (obj.cmd !== undefined && obj.type === undefined) {
  emit("repl", { reason: "command echoed" });
  continue;
}
```

- Also detect the textual signals:

```js
if (line.includes(">>>") || line.includes("MicroPython v") || line.includes('Type "help()"')) {
  emit("repl", { reason: "prompt/banner seen" });
}
```

---

## Recovery

*Why: Ctrl-C-to-reach-a-known-state is correct in REPL tooling and wrong in an application — it kills healthy firmware and reports the breakage it caused.*

- Diagnostics are read-only. Never send Ctrl-C from a probe.

```js
// BROKEN — a "diagnostic" that destroys a working connection
async probe() {
  await write('{"cmd":"hello"}\n');
  await write("\x03");                  // kills running firmware
  await write('{"cmd":"hello"}\n');
}
// Observed: TX <CTRL-C> → RX {"type":"bye"} → RX MicroPython v1.27.0 ... >>>

// CORRECT — read-only, safe to click at any time
async probe() {
  await logSignals("probe start");
  await write("\r\n");                        // does anything respond?
  await write('{"cmd":"hello","id":9001}\n'); // reply=running, echo/'>>>'=REPL, silence=nothing
}
```

- Recovery from REPL is Ctrl-C (clear partial line) then Ctrl-D (soft reset, re-runs `main.py`).

```js
async restartFirmware({ timeoutMs = 12000 } = {}) {
  await write("\x03");        // clear partial REPL line; harmless at the prompt
  await sleep(200);
  await write("\x04");        // soft reset → re-runs main.py
  return await waitForHello(timeoutMs);
}
```

- Auto-recover once per connect, loop-guarded, then defer to manual.

```js
if (this._autoRecoverArmed) {
  this._autoRecoverArmed = false;   // one-shot; never hammer Ctrl-D
  this.restartFirmware().catch(() => {});
}
```

- Every detectable bad state needs a recovery cheaper than reflashing.
- Leave `micropython.kbd_intr` at default. `kbd_intr(-1)` makes a wedged device unrecoverable without `erase_flash`.
- That default is only safe if every payload byte is printable ASCII (0x20–0x7E) plus `\n`. Base64 and JSON satisfy this by construction.

---

## Stream ownership

*Why: two consumers on one port silently eat each other's bytes, and the symptom is an unexplained `readUntil` timeout.*

- One consumer per stream at a time. Detach the protocol parser before raw-REPL work, reattach after.

```js
async installFirmware(onProgress) {
  this._detachJson();   // its clearBacklog() would erase bytes readUntil() needs
  await installFirmware(this.repl, this.adapter, onProgress);
  this._attachJson();   // the reboot's hello arrives through this
}
```

---

## Framing

*Why: fragmentation scales with payload size, so `JSON.parse(chunk)` passes short-command testing and fails only in production.*

- One read ≠ one message. Accumulate into a buffer, split on the terminator.

```
RX {"list": [{"name": "apple", "bytes": 3317}, {"name": "cher   (69B)
RX ies", "bytes": 3377}, ... "type": "icons"}                   (181B)
RX \r\n                                                          (2B)
```

- Use `indexOf("\n")` + slice. Per-byte scanning is O(n²) on kilobyte lines.

```js
this._buf += chunk;
let i;
while ((i = this._buf.indexOf("\n")) >= 0) {
  const line = this._buf.slice(0, i).trim();
  this._buf = this._buf.slice(i + 1);
  handle(line);
}
if (this._buf.length) logInfo(`holding ${this._buf.length}B partial line`);
```

---

## Firmware I/O

*Why: byte-at-a-time polling is ~100 B/s — fine for short commands, and it overflows the ~512 B USB stdin ring buffer on anything carrying a payload.*

- Any loop doing serial I/O needs an unconditional `time.sleep_ms(1)` every iteration.
- Never read one byte per main-loop iteration.

```python
# BROKEN — ~100 bytes/second; a 1KB frame takes 10 seconds
def check_input(self):
    rlist, _, _ = select.select([sys.stdin], [], [], 0)
    if rlist:
        chunk = sys.stdin.read(1)
    # ... main loop sleeps 10ms
```

- `sys.stdin.read(n)` for `n>1` blocks. Use `read(1)` in a greedy drain with `select.poll` as the idle wait.

```python
def pump(self, idle_ms=20, drain_ms=40):
    if not self.poll.poll(idle_ms):          # zero CPU; returns instantly on data
        return 0
    deadline = time.ticks_add(time.ticks_ms(), drain_ms)
    chars, saw_nl = [], False
    while True:
        c = sys.stdin.read(1)
        if c:
            chars.append(c)
            if c == "\n": saw_nl = True
        if self.poll.poll(0): continue       # more queued — keep draining
        if saw_nl: break                     # complete line, buffer empty
        if time.ticks_diff(deadline, time.ticks_ms()) <= 0: break
        self.poll.poll(2)                    # brief wait for next paced chunk
    self.buf += "".join(chars)
    return self._consume()
```

*Why: on the ESP32 port `sys.stderr` **is** `sys.stdout`, so debug output interleaves into the protocol stream.*

- Host drops any line whose first character is not `{`. One rule absorbs banner, echo, debug, and tracebacks.
- Prefix intentional firmware debug with `# `.
- Emit exactly one JSON object per line on stdout. Nothing else, ever.
- Wrap every dispatch; reply `{"type":"error",...}` rather than raising.
- Capture init tracebacks into a JSON `fatal`. A bare traceback is discarded by the `{` filter, making a crashed device indistinguishable from a silent one.

```python
try:
    from icon_server import IconServer
    IconServer().run()
except Exception as e:
    import io, sys, json
    b = io.StringIO()
    sys.print_exception(e, b)
    print(json.dumps({"type": "fatal",
                      "msg": "%s: %s" % (type(e).__name__, e),
                      "tb": b.getvalue()[-400:]}))
```

- Parse stored data files line-at-a-time; do not `__import__` them. Import caches in `sys.modules` and returns stale data after a write.
- Write files tmp-then-rename so a mid-write disconnect cannot leave a corrupt importable file.
- Prefer `int()` over `round()` for arithmetic shared between host and device. MicroPython rounds half away from zero; CPython 3 rounds half to even.

---

## Observability

*Why: without a wire log every diagnosis is a guess. Two were wrong here — DTR/RTS was blamed and cleared, and a port renumber was misread as a device reset. A pasted log resolved both remaining bugs in minutes.*

- Log every byte in both directions with control characters escaped, before writing any protocol logic.

```js
export function escapeControl(s) {
  return String(s)
    .replace(/\x01/g, "<CTRL-A>").replace(/\x02/g, "<CTRL-B>")
    .replace(/\x03/g, "<CTRL-C>").replace(/\x04/g, "<CTRL-D>")
    .replace(/\r/g, "\\r").replace(/\n/g, "\\n");
}
```

- Log dropped lines **with the reason**. A correct-but-silent filter is undebuggable.

```js
if (line[0] !== "{") {
  logDrop(line, { reason: "does not start with '{'" });
  continue;
}
```

- Log request/reply `id` correlation, `readUntil` waits and timeouts, port VID/PID, DTR/RTS, read-loop lifecycle, and `navigator.serial` disconnect events.
- Mirror to a ring buffer and the console, so a page crash still leaves a trail.
- Provide copy-to-clipboard for the whole log.

---

## Verified non-issues

- **DTR/RTS**: no effect on native USB Serial/JTAG — all four combinations replied. Relevant only on USB-UART bridge boards.
- **Baud rate**: ignored by native USB CDC.
- **Write pacing**: a 1058-byte unpaced single write completed in 15 ms. 256 B/10 ms chunking is precautionary, not required.
- **Port renumbering** (`usbmodem1101` → `3101`): caused by replugging into a different physical port, not by a device reset.
- **ES module caching**: submodules are not cache-busted by a query string on the entry point. Hard-reload after editing them.