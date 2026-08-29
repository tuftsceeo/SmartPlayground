"""
json_link.py -- non-blocking newline-delimited JSON over stdin/stdout.
See the top-level plan ("ESP32-C6 firmware / Protocol") for the full
design rationale. Key points, briefly:

  - sys.stdin.read(n) for n>1 BLOCKS until n bytes arrive; read(1) does
    not. select.poll() is the only-CPU-free way to wait for the first
    byte, then we drain everything currently queued in one pass so a
    paced ~1KB frame line doesn't dribble in over many pump() calls and
    risk overflowing the small (~512B) USB stdin ring buffer.
  - micropython.kbd_intr() is left at its DEFAULT (enabled) so Ctrl-C
    still raises KeyboardInterrupt and drops back to the REPL -- the
    escape hatch the browser's repl controller depends on. This is safe
    ONLY because every byte on the wire is printable ASCII (base64/JSON)
    plus the '\\n' terminator -- never send raw binary over this link.
  - On the esp32 port sys.stderr IS sys.stdout, so there's no separate
    debug channel. Debug lines are prefixed '# '; the browser drops any
    line whose first character isn't '{', which absorbs debug lines, the
    boot banner, REPL echo, and stray tracebacks in one rule.
"""

import sys
import select
import json
import time

MAX_LINE = 4096


class JsonLink:
    def __init__(self, on_command, debug=False):
        self.on_command = on_command
        self.debug = debug
        self.buf = ""
        self.overflow = False
        self.poll = select.poll()
        self.poll.register(sys.stdin, select.POLLIN)

    def send(self, obj):
        try:
            print(json.dumps(obj))
        except Exception:
            print('{"type":"error","code":"encode"}')

    def note(self, msg):
        if self.debug:
            print("# " + str(msg))

    def pump(self, idle_ms=20, drain_ms=40):
        """Idle-wait on poll (zero CPU, returns the instant a byte lands),
        then drain everything available in one pass. Returns the number of
        complete command lines processed."""
        if not self.poll.poll(idle_ms):
            return 0
        deadline = time.ticks_add(time.ticks_ms(), drain_ms)
        chars = []
        saw_nl = False
        while True:
            try:
                c = sys.stdin.read(1)
            except UnicodeError:
                c = None  # non-UTF8 byte on the wire -- drop it
            if c:
                chars.append(c)
                if c == "\n":
                    saw_nl = True
            if self.poll.poll(0):
                continue  # more bytes already queued -- keep draining
            if saw_nl:
                break  # a whole line AND the buffer is currently empty
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                break  # bounded wait, so pump() always returns promptly
            self.poll.poll(2)  # brief wait for the next paced chunk
        if chars:
            self.buf += "".join(chars)
        if len(self.buf) > MAX_LINE and self.buf.find("\n") < 0:
            self.buf = ""
            self.overflow = True  # drop the tail of the oversized line too
            self.send({"type": "error", "code": "line_too_long", "max": MAX_LINE})
        return self._consume()

    def _consume(self):
        n = 0
        while True:
            i = self.buf.find("\n")
            if i < 0:
                break
            line = self.buf[:i].strip()
            self.buf = self.buf[i + 1:]
            if not line:
                continue
            if self.overflow:
                self.overflow = False
                continue
            if line[0] != "{":
                continue  # REPL echo / boot banner / debug line -- ignore
            n += 1
            try:
                cmd = json.loads(line)
            except Exception:
                self.send({"type": "error", "code": "bad_json"})
                continue
            try:
                self.on_command(cmd)
            except Exception as e:
                self.send({
                    "type": "error", "code": "cmd_failed",
                    "cmd": cmd.get("cmd"), "id": cmd.get("id"),
                    "msg": "%s: %s" % (type(e).__name__, e),
                })
        return n
