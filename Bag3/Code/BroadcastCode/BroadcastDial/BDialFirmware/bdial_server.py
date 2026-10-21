"""
bdial_server.py — JSON serial dispatcher + NFC card flow + TCP server poll.

Sibling of bbox_server.py for the M5 Dial 2. Same mode machine, wire
contract, card-safety rules and serial protocol; only the board, input
model and screen layer differ. Keep behavioural changes in sync with the
Box peer, or call out the divergence.

One user-facing state: the tag menus. The invariant this file holds:

    at most one of {radio, NFC RF field} is energized at any instant.

    WRITE  The menus. ESP-NOW serves the active game to wands
           (code_link.py) whenever the reader field is off; the radio goes
           down only while a card is being scanned or written.
    IDLE   Neither.  No game on flash, so there is nothing to do.

There is deliberately no RECEIVING mode: the app pushes code over the raw
REPL, which interrupts this program and soft-resets the board
(ChatBroadcast's boxFirmwareInstaller.pushPayload), so an upload is not a
state this firmware is ever in. It comes back from that reset, finds a game
on flash, and starts in WRITE.

See serial_protocol_notes.md for connection/identify/recovery rules.
"""

import gc
import time
import machine
import os

import reset_log
from json_link import JsonLink
from code_link import CodeLink, HOST_ID, GAMES_DIR, ACTIVE_PATH, prewarm
from dial_board import make_reader, SCREEN_W, SCREEN_H

VERSION = "0.1.0"
HEARTBEAT_MS = 5000
# Seconds of countdown before the firmware takes the board, so a Ctrl-C
# can land and leave you at the REPL. ZERO by default: Ctrl-C is never
# disabled here (json_link.py leaves micropython.kbd_intr() at its
# default), so it lands whenever the board is running Python -- the
# countdown buys nothing. Set it on a test rig whose REPL is hard to
# catch; that is the only thing it is for.
GRACE_S = 0

SHARE_RETRY_MS = 2000        # wait after a failed menu-share arm()

INDEX_PATH = GAMES_DIR + '/index.json'


# PEER: BBoxFirmware/bbox_server.py, BDialFirmware/bdial_server.py.
# Every non-wand ROLE_FILES suffix (in code_sender.py) goes here too,
# so _boot_scan_games() never enrols another device's staged file.
STAGING_SUFFIXES = ('_icon.py', '_splat.py')

# Writable no matter which games are loaded. "stop" exits any running game;
# "battery" asks the wand to report its charge. These are plain NDEF card
# text, like every other entry -- card_writer.py does not use opcodes.
UTILITY_TAGS = ("stop", "battery")
UTILITY_GROUP = "Utility Tags"


MODE_IDLE = "IDLE"
MODE_WRITE = "WRITE"

# The screens are station.py (the NFC Station's mode machine) painted by
# station_ui.py. Both, and dial_input, are imported in run() after the
# radio is up (docs_and_design/2026-09-23-ap-memory-order.md).

# Chatty tracing (intents, state transitions, antenna toggles).
# Off by default. Failures, card events and write outcomes are NOT gated by
# this -- they always print.
VERBOSE = False


def _log(msg):
    if reset_log.LOG_ENABLED:
        print("# [dial] %s" % msg)


def _dbg(msg):
    if VERBOSE:
        print("# [dial] %s" % msg)


def _card_text(label):
    """Card bytes for a tag. getcode tags carry this host's id, so a
    scanning wand or icon display can pin to this host; other tags are
    written as they are. Text already carrying an id is left alone."""
    if (label == 'getcode' or label.startswith('getcode:')) and '@' not in label:
        return label + '@' + HOST_ID
    return label


def _boot_grace(ui):
    # The booting screen is painted either way -- it is what the teacher sees
    # while the rest of boot runs, not part of the countdown.
    ui.show_result("busy", "Starting")
    if GRACE_S <= 0:
        return
    print("# booting -- Ctrl-C within %ds to stay at the REPL" % GRACE_S)
    for remaining in range(GRACE_S, 0, -1):
        print("# %d..." % remaining)
        time.sleep_ms(1000)


class BdialServer:
    def __init__(self, debug=False):
        self._input = None      # DialInput, built in run()
        self.ui = None          # StationUI, built in run()
        self.st = None          # station.Station, built in run()
        self.link = JsonLink(self.dispatch, debug=debug)
        self.code = CodeLink()
        self.nfc = None
        self.running = True
        self.linked = True

        self._mode = MODE_IDLE
        self._nfc_ok = False  # real _init_nfc() result -- reported in identity
        # (name, [(label, tag), ...], all_ok) per game, then Utility.
        self._groups = [(UTILITY_GROUP, [(t, t) for t in UTILITY_TAGS], False)]
        # entry label -> cumulative successful writes, seeded from
        # stats_log at boot by _load_stats() and incremented in memory.
        self._written = {}
        # slug -> wands that pulled it since boot. A new game arrives by a
        # reset (module docstring), so this restarts with each code update.
        self._pulls = {}
        self._share_retry_at = 0
        self._index = {}  # slug -> {name, added}
        self._active = None


        self.handlers = {
            "identify": self.do_identify,
            "info": self.do_info,
            "mode": self.do_mode,
            "arm": self.do_arm,
            "disarm": self.do_disarm,
            "repl": self.do_repl,
            "reboot": self.do_reboot,
            "games.list": self.do_games_list,
            "games.select": self.do_games_select,
            "games.delete": self.do_games_delete,
            "games.clear": self.do_games_clear,
            "stats.get": self.do_stats_get,
            "stats.reset": self.do_stats_reset,
        }

    # ─────────────────────────────────────────────
    # HARDWARE INIT
    # ─────────────────────────────────────────────

    def _log_mem(self, label):
        """Diagnostic only -- chasing the WiFi OOM (see
        dial_board.py H5). gc.collect() first so mem_free() reports real
        garbage-collected headroom, not just whatever hasn't been swept yet.
        mem_info(1) (verbose) is ESP32-port-dependent -- some builds print a
        free-block/fragmentation breakdown, some don't recognize the arg, so
        it's wrapped and silently skipped rather than guessed at.
        """
        try:
            gc.collect()
            print("# mem[%s]: free=%d alloc=%d" % (label, gc.mem_free(), gc.mem_alloc()))
            try:
                import micropython
                micropython.mem_info(1)
            except Exception:
                pass
        except Exception as e:
            print("# mem[%s] log failed: %s" % (label, str(e)))

    def _init_nfc(self):
        self.nfc = make_reader()

    # ─────────────────────────────────────────────
    # MODES
    # ─────────────────────────────────────────────

    def _set_mode(self, new_mode, announce=True):
        """IDLE (no game on flash) <-> WRITE (a game to serve). Reported
        over serial; the screens are the same in both."""
        if new_mode == self._mode:
            return
        old = self._mode
        if old == MODE_WRITE:
            self.code.disarm()
        self._mode = new_mode
        reset_log.note_mode(new_mode)
        print("# mode %s -> %s" % (old, new_mode))
        self._emit_mode()

    def _mode_payload(self, rid=None):
        """JSON for mode event / cmd reply."""
        return {
            "type": "mode",
            "id": rid,
            "mode": self._mode,
            "games": len(self._index),
            "active": self._active,
            "ssid": None,
        }

    def _emit_mode(self, rid=None):
        self.link.send(self._mode_payload(rid))

    # JSON API
    # ─────────────────────────────────────────────

    def dispatch(self, cmd):
        name = cmd.get("cmd")
        rid = cmd.get("id")
        handler = self.handlers.get(name)
        if handler is None:
            self.link.send({"type": "error", "id": rid, "code": "unknown_cmd", "cmd": name})
            return
        handler(cmd, rid)

    def _identity_payload(self, rid=None):
        """Who and what this device is -- NOT a status report and NOT a
        connection handshake.

        Every field here is fixed for the life of a boot: device kind,
        firmware version, screen size, and whether the reader initialized.
        Live status (memory, mode, armed, counters) belongs to `info` and
        `mode`; do not add changing values here.

        The host must never treat this as the signal that a link is up --
        `heartbeat` is what proves the box is alive, because this is only
        volunteered once per boot and a host that connects afterwards will
        never see it. See do_identify() for the request form.
        """
        return {
            "type": "identity", "id": rid,
            "device": "broadcast_dial", "version": VERSION,
            # Report what _init_nfc() actually did. Never hardcode True —
            # a failed init must surface as nfc:false so the app can say so.
            "w": SCREEN_W, "h": SCREEN_H, "nfc": self._nfc_ok,
            # Fixed for the life of the boot (see code_link.HOST_ID).
            "host_id": HOST_ID,
        }

    def _send_identity(self, rid=None):
        self.link.send(self._identity_payload(rid))

    def do_identify(self, cmd, rid):
        """Answer {"cmd":"identify"} with this boot's identity payload.

        Safe to call at any time and as often as the host likes: it reads
        no hardware and changes no state.
        """
        self._send_identity(rid)

    def do_mode(self, cmd, rid):
        self._emit_mode(rid)

    def do_info(self, cmd, rid):
        self.link.send({
            "type": "info", "id": rid,
            "version": VERSION, "mem": gc.mem_free(),
            "armed": self.code.armed, "linked": self.linked,
            "payload_ready": self._payload_ready(),
            "written": sum(self._written.values()), "up": time.ticks_ms(),
        })

    def do_arm(self, cmd, rid):
        """Sharing follows the menus (_serve); this only reports it.
        Kept for hosts that still send it."""
        if not self._payload_ready():
            self.link.send({"type": "error", "id": rid, "code": "no_payload",
                             "msg": "no game on device"})
            return
        if self.st is not None:
            self._serve()
        self.link.send({"type": "ok", "id": rid, "cmd": "arm", "ssid": None,
                        "armed": self.code.armed})

    def do_disarm(self, cmd, rid):
        """No-op kept for hosts that still send it: sharing is not
        user-controlled."""
        self.link.send({"type": "ok", "id": rid, "cmd": "disarm"})

    def do_repl(self, cmd, rid):
        self.link.send({"type": "bye", "id": rid, "reboot": "soft"})
        self.running = False

    def do_reboot(self, cmd, rid):
        hard = bool(cmd.get("hard"))
        self.link.send({"type": "bye", "id": rid, "reboot": "hard" if hard else "soft"})
        self.running = False
        if hard:
            machine.reset()

    def do_games_list(self, cmd, rid):
        lst = []
        for slug, meta in self._index.items():
            path = GAMES_DIR + '/' + slug + '.py'
            try:
                nbytes = os.stat(path)[6]
            except OSError:
                nbytes = 0
            lst.append({
                "slug": slug,
                "name": meta.get("name", slug),
                "bytes": nbytes,
                "pulls": self._pulls.get(slug, 0),
                # From <slug>.tags.json. The app shows this as the game's
                # expected-card list, so a box holding a game the laptop
                # never sent still reports the right tags.
                "tags": meta.get("tags") or [],
            })
        self.link.send({
            "type": "games", "id": rid,
            "list": lst, "active": self._active,
        })

    def do_games_select(self, cmd, rid):
        slug = cmd.get("slug")
        if not slug or slug not in self._index:
            self.link.send({"type": "error", "id": rid, "code": "unknown_slug",
                             "msg": "no such game"})
            return
        self._set_active(slug)
        self.code.set_game(slug)
        self.link.send({"type": "ok", "id": rid, "cmd": "games.select", "active": slug})
        self._emit_mode()

    def do_games_delete(self, cmd, rid):
        slug = cmd.get("slug")
        if not slug or slug not in self._index:
            self.link.send({"type": "error", "id": rid, "code": "unknown_slug"})
            return
        for path in (GAMES_DIR + '/' + slug + '.py',
                     GAMES_DIR + '/' + slug + '.tags.json'):
            try:
                os.remove(path)
            except OSError:
                pass
        try:
            del self._index[slug]
        except KeyError:
            pass
        self._save_index()
        if self._active == slug:
            self._active = None
            self._pick_active_fallback()
        self._rebuild_entries()
        self.link.send({"type": "ok", "id": rid, "cmd": "games.delete", "slug": slug})
        # Drop to IDLE if nothing left; otherwise stay / re-emit mode.
        if not self._index:
            self._set_mode(MODE_IDLE)
        else:
            self._emit_mode()
            if self._mode == MODE_IDLE:
                self._set_mode(MODE_WRITE)

    def do_games_clear(self, cmd, rid):
        try:
            for name in os.listdir(GAMES_DIR):
                if name.endswith('.py') or name.endswith('.tags.json'):
                    try:
                        os.remove(GAMES_DIR + '/' + name)
                    except OSError:
                        pass
        except OSError:
            pass
        self._index = {}
        self._active = None
        self._save_index()
        self._write_active('')
        self._rebuild_entries()
        self.link.send({"type": "ok", "id": rid, "cmd": "games.clear"})
        self._set_mode(MODE_IDLE)

    def do_stats_get(self, cmd, rid):
        try:
            import stats_log
            agg = stats_log.aggregate()
        except Exception as e:
            agg = {"pulls": {}, "writes": {}, "since": 0}
            print("# stats.get failed: %s" % str(e))
        self.link.send({
            "type": "stats", "id": rid,
            "pulls": agg.get("pulls") or {},
            "writes": agg.get("writes") or {},
            "since": agg.get("since") or 0,
        })

    def do_stats_reset(self, cmd, rid):
        try:
            import stats_log
            stats_log.reset()
        except Exception as e:
            self.link.send({"type": "error", "id": rid, "code": "stats_reset_failed",
                             "msg": str(e)})
            return
        self._written = {}
        self._pulls = {}
        self.link.send({"type": "ok", "id": rid, "cmd": "stats.reset"})

    def _payload_ready(self):
        return len(self._index) > 0

    # ─────────────────────────────────────────────
    # GAME LIBRARY (boot-scan + index)
    # ─────────────────────────────────────────────

    def _ensure_games_dir(self):
        try:
            os.mkdir(GAMES_DIR)
        except OSError:
            pass

    def _load_index(self):
        try:
            import json
            with open(INDEX_PATH, 'r') as f:
                data = json.loads(f.read() or '{}')
            if isinstance(data, dict):
                self._index = data
            else:
                self._index = {}
        except Exception:
            self._index = {}

    def _save_index(self):
        try:
            import json
            self._ensure_games_dir()
            with open(INDEX_PATH, 'w') as f:
                f.write(json.dumps(self._index))
        except Exception as e:
            print("# save index failed: %s" % str(e))

    def _read_active(self):
        try:
            with open(ACTIVE_PATH, 'r') as f:
                return f.read().strip()
        except OSError:
            return ''

    def _write_active(self, slug):
        try:
            with open(ACTIVE_PATH, 'w') as f:
                f.write(slug or '')
        except Exception as e:
            print("# write active failed: %s" % str(e))

    def _set_active(self, slug):
        self._active = slug
        self._write_active(slug or '')

    def _read_tags(self, slug):
        """Tags the game needs, from /flash/games/<slug>.tags.json.

        Written by ChatBroadcast in the same REPL session as the .py. A game
        pushed by other means has no sidecar and simply contributes no extra
        tags -- but a file that exists and will not parse is a real fault and
        says so, because the symptom otherwise is a menu quietly missing the
        cards the game cannot run without.
        """
        path = GAMES_DIR + '/' + slug + '.tags.json'
        try:
            f = open(path, 'r')
        except OSError:
            return []
        try:
            import json
            data = json.loads(f.read() or '[]')
        except Exception as e:
            print("# tags for %s unreadable: %s" % (slug, str(e)))
            return []
        finally:
            f.close()
        if not isinstance(data, list):
            print("# tags for %s: expected a list, got %s" % (slug, type(data)))
            return []
        return [t for t in data if isinstance(t, str) and t]

    def _pretty_from_slug(self, slug):
        parts = slug.replace('_', '-').split('-')
        return ' '.join(p[:1].upper() + p[1:] for p in parts if p)

    def _load_stats(self):
        """Seed the on-screen counters from the persistent stats log.

        The screen used to show per-session counts, which reset to zero on
        every reboot -- a teacher who power-cycled the Box saw "(0)" next to
        a tag they had already written a dozen of, and "pickups: 0" on a box
        that had served all morning. stats_log is the durable record.

        Read once here and incremented in memory afterwards, so a repaint
        (which happens on every cursor move) never touches flash.
        """
        try:
            import stats_log
            agg = stats_log.aggregate()
            self._written = agg.get('writes', {})
        except Exception as e:
            # Counters are cosmetic; a corrupt log must not stop the boot.
            print("# stats load failed: %s" % str(e))
            self._written = {}

    def _boot_scan_games(self):
        """Merge /flash/games/*.py into index.json; pick active.

        New-this-boot files (not in previous index) become active; if several,
        latest mtime wins. Otherwise keep active.txt if still present.

        A name ending in a staging suffix (STAGING_SUFFIXES below) is another
        device's game, staged under the suffix ROLE_FILES uses to pick it
        out for that device's pull (see code_sender.py) -- it is never
        itself a playable game on this device, so it never enters the menu
        or becomes active.
        """
        self._ensure_games_dir()
        self._load_index()
        prev = dict(self._index)

        files = []
        try:
            names = os.listdir(GAMES_DIR)
        except OSError:
            names = []
        for name in names:
            if not name.endswith('.py') or any(
                    name.endswith(suf) for suf in STAGING_SUFFIXES):
                continue
            slug = name[:-3]
            path = GAMES_DIR + '/' + name
            try:
                st = os.stat(path)
                size = st[6]
                mtime = st[8] if len(st) > 8 else 0
            except OSError:
                continue
            if size <= 0:
                continue
            files.append((slug, path, mtime))

        new_slugs = []
        next_index = {}
        for slug, path, mtime in files:
            if slug in prev:
                next_index[slug] = prev[slug]
            else:
                next_index[slug] = {
                    "name": self._pretty_from_slug(slug),
                    "added": time.ticks_ms(),
                }
                new_slugs.append((slug, mtime))
            # Re-read every boot: a re-sent game overwrites its sidecar
            # without changing the index entry.
            next_index[slug]["tags"] = self._read_tags(slug)

        self._index = next_index
        self._save_index()

        if new_slugs:
            new_slugs.sort(key=lambda x: x[1], reverse=True)
            self._set_active(new_slugs[0][0])
        else:
            want = self._read_active()
            if want and want in self._index:
                self._active = want
            else:
                self._pick_active_fallback()

        if self._active:
            self.code.set_game(self._active)
        self._rebuild_entries()
        print("# games: %d active=%s" % (len(self._index), self._active))

    def _pick_active_fallback(self):
        if not self._index:
            self._set_active(None)
            return
        # First remaining slug (stable-ish dict order on MicroPython).
        for slug in self._index:
            self._set_active(slug)
            self.code.set_game(slug)
            return

    def _rebuild_entries(self):
        """One group per game -- Code (getcode:<slug>), Play (<slug>), then
        the tags the game pushed in <slug>.tags.json, with All -- then
        Utility (stop, battery)."""
        groups = []
        for slug in self._index:
            rows = [("Code", "getcode:" + slug), ("Play", slug)]
            for t in (self._index[slug].get("tags") or ()):
                if t and t not in ("getcode:" + slug, slug):
                    rows.append((t, t))
            groups.append((self._index[slug].get("name") or slug, rows, True))
        groups.append((UTILITY_GROUP, [(t, t) for t in UTILITY_TAGS], False))
        self._groups = groups

        # Drop written counts for tags no longer on any group.
        live = set()
        for _, rows, _ in groups:
            for _, t in rows:
                live.add(t)
        keep = {}
        for k, v in self._written.items():
            if k in live:
                keep[k] = v
        self._written = keep
        if self.st is not None:
            self.st.reload()

    # ─────────────────────────────────────────────
    # STATION HOST (see station.py)
    # ─────────────────────────────────────────────

    def init_nfc(self):
        self._init_nfc()

    def tag_groups(self):
        return self._groups

    def has_games(self):
        return bool(self._index)

    def words(self):
        """Keyboard word bank: the loaded games' tags, then
        /flash/words.json if present. Read when the keyboard opens."""
        out = []
        for _, rows, _ in self._groups:
            for _, t in rows:
                if t not in out and not t.startswith("getcode:"):
                    out.append(t)
        try:
            import json
            with open("/flash/words.json") as f:
                extra = json.loads(f.read() or "[]")
        except OSError:
            extra = []
        except Exception as e:
            print("# words.json unreadable: %s" % str(e))
            extra = []
        if isinstance(extra, list):
            for w in extra:
                if isinstance(w, str) and w and w not in out:
                    out.append(w.lower())
        return out

    def card_text(self, tag):
        return _card_text(tag)

    def radio_off(self):
        if self.code.armed:
            self.code.disarm()

    def on_card(self, tag, existing):
        _log("card uid=%s existing=%s" % (tag['uid_hex'], repr(existing)))
        self.link.send({
            "type": "card_present", "uid": tag['uid_hex'], "existing": existing,
        })

    def on_written(self, label, uid, wrote):
        if not wrote:
            return
        label = label.split('@', 1)[0]      # a copied getcode card
        self._written[label] = self._written.get(label, 0) + 1
        self.link.send({"type": "card_written", "label": label, "uid": uid})
        try:
            import stats_log
            stats_log.record_tag(label)
        except Exception as e:
            print("# stats tag failed: %s" % str(e))

    # ─────────────────────────────────────────────
    # RADIO
    # ─────────────────────────────────────────────

    def _serve(self):
        """Serve the active game over ESP-NOW on the menu screens; the
        radio is down everywhere else (Read, scans, results, keyboard)."""
        if self.code.armed:
            if self.st.serving():
                self.code.poll(on_event=self._on_share_event)
            else:
                self.code.disarm()
            return
        if (self._mode != MODE_WRITE or not self.st.serving()
                or time.ticks_diff(self._share_retry_at, time.ticks_ms()) > 0):
            return
        if self._active:
            self.code.set_game(self._active)
        elif self.code.resolve() is None:
            return
        if not self.code.arm():
            print("# share: CodeLink.arm() failed")
            self._share_retry_at = time.ticks_add(time.ticks_ms(), SHARE_RETRY_MS)

    def _on_share_event(self, event):
        if event in ('ok', 'fail'):
            self._emit_pull()
        r = self.code.last_result
        if event == 'ok' and r is not None and r.get("hub", "wand") == "wand":
            slug = r.get("slug")
            self._pulls[slug] = self._pulls.get(slug, 0) + 1

    def _emit_pull(self):
        r = self.code.last_result
        if r is None:
            return
        path = r["path"] or ""
        self.link.send({"type": "pull", "id": None,
                        "slug": r.get("slug") or (path.rsplit("/", 1)[-1][:-3] if path else None),
                        "role": r.get("hub") or "wand", "wand": r["mac"], "ok": r["ok"],
                        "ms": r["ms"], "why": r["why"] or None})

    # ─────────────────────────────────────────────
    # RUN
    # ─────────────────────────────────────────────

    def run(self):
        # First, before the grace window or anything that can raise: this
        # boot's reset_cause(). The board's USB is native CDC, so a reset
        # drops the port and the cause has to be read on the *next* boot
        # (known_issue.md discriminating test 1).
        reset_log.record()

        import M5
        M5.begin()

        # The radio's first allocation must precede the UI and NFC
        # allocations (docs_and_design/2026-09-23-ap-memory-order.md).
        try:
            prewarm()
        except Exception as e:
            print("# radio prewarm failed: %s" % str(e))

        import card_writer
        from dial_input import DialInput
        from station import Station
        from station_ui import StationUI
        self._input = DialInput()
        self.ui = StationUI(self._input)
        self._input.begin()
        self.ui.begin()  # calls m5ui.init(); builds the LVGL pages
        self._log_mem("after ui.begin")
        _boot_grace(self.ui)
        try:
            self._init_nfc()
            self._nfc_ok = True
        except Exception as e:
            print("# NFC init failed: %s" % str(e))
            self._nfc_ok = False
        self._log_mem("after _init_nfc")

        self.st = Station(self.ui, self._input, self, card_writer)
        self._load_stats()
        self._boot_scan_games()
        # Unsolicited identity, once, purely informational: an app that
        # connects later learns liveness from `heartbeat` instead.
        self._send_identity()
        self._mode = MODE_IDLE
        self._set_mode(MODE_WRITE if self._payload_ready() else MODE_IDLE,
                       announce=False)
        if self._mode == MODE_IDLE:
            self._emit_mode()
        self.st.go_home()

        last_hb = time.ticks_ms()
        try:
            while self.running:
                self.link.pump(idle_ms=20, drain_ms=40)
                self.st.step()
                self.ui.tick()
                self._serve()
                now = time.ticks_ms()
                if time.ticks_diff(now, last_hb) > HEARTBEAT_MS:
                    self.link.send({"type": "heartbeat", "up": now, "mem": gc.mem_free()})
                    last_hb = now
                time.sleep_ms(1)
        finally:
            self._shutdown_radios()

    def _shutdown_radios(self):
        """De-energize both radios on the way out of run(), whatever the reason.

        `repl` and a soft `reboot` both just clear self.running and return,
        and an uncaught exception unwinds straight past to main.py; without
        this the radio would stay up with nothing serving. Each half is
        guarded separately so a failure to put the reader down cannot stop
        the radio coming down.
        """
        try:
            if self.code.armed:
                self.code.disarm()
                _log("shutdown: radio down")
        except Exception as e:
            print("# shutdown: radio disarm FAILED: %s" % str(e))
        try:
            if self.st is not None:
                self.st.field_off()
        except Exception as e:
            print("# shutdown: NFC field off FAILED: %s" % str(e))
