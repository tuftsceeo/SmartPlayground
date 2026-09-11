"""
bdial_server.py — JSON serial dispatcher + NFC card flow + TCP server poll.

Sibling of bbox_server.py for the M5 Dial 2. Same mode machine, wire
contract, card-safety rules and serial protocol; only the board, input
model and screen layer differ. Keep behavioural changes in sync with the
Box peer, or call out the divergence.

Phase A mode machine. The invariant this file exists to hold:

    at most one of {WiFi AP, NFC RF field} is energized at any instant.

    WRITE  AP down.  Reader polled only while scanning.
    SERVE  Reader antenna off, no I2C at all.  AP up, serving wand pulls.
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
from dial_input import DialInput, NEXT, PREV, ACT, BACK, EXIT
from json_link import JsonLink
from code_server import (
    CodeServer, DEFAULT_SRC, SSID, GAMES_DIR, ACTIVE_PATH, prewarm_ap)
from card_writer import existing_text, write_text
from dial_ui import DialUI
from dial_board import make_reader, SCREEN_W, SCREEN_H

VERSION = "0.1.0"
HEARTBEAT_MS = 5000
GRACE_S = 1

PAYLOAD_PATH = DEFAULT_SRC
INDEX_PATH = GAMES_DIR + '/index.json'

# Legacy single-game tags — replaced at boot by _rebuild_entries() from the
# games index. Kept as a fallback if the index is empty.
TAG_LIST = ("getcode", "jumpin")
DONE_ENTRY = "DONE"
BACK_ENTRY = "< back"

# Writable no matter which games are loaded. "stop" exits any running game;
# "battery" asks the wand to report its charge. These are plain NDEF card
# text, like every other entry -- card_writer.py does not use opcodes.
UTILITY_TAGS = ("stop", "battery")
UTILITY_GROUP = "Utility Tags"

# Not a write target -- a sentinel _scan_step() special-cases before it is
# ever treated as NDEF text. Lets a teacher check what's already on a card
# without writing anything to it. Lives in the utility group alongside the
# real write tags so it shows up in the same menu.
READ_ENTRY = "Read Card"

MODE_IDLE = "IDLE"
MODE_WRITE = "WRITE"
MODE_SERVE = "SERVE"

# WRITE-mode sub-states. Dial intents: ACT confirms, NEXT/PREV scroll,
# BACK cancels. Hold-to-EXIT is SERVE only (see dial_input.SERVE_EXIT_MS).
#   MENU      list of groups   ACT = open (or serve on DONE)  NEXT/PREV
#   GROUP     one group's tags ACT = scan (or back)           NEXT/PREV
#   SCAN      RF field on      BACK = group
#   SPLASH    result shown     ACT/BACK/NEXT = group
#
# The menu is two-level because a single game can contribute a dozen tags
# (melody alone has eleven). On one flat list, DONE -- the only way into
# SERVE mode -- would be a dozen clicks away.
#
# Deliberately no OVERWRITE confirmation state (unlike bbox_server.py, the
# Box peer, which still prompts before overwriting): on the Dial the
# antenna is under the screen, so a card that's actually on the reader
# covers the same touch targets a confirm/cancel prompt would need. Any
# tag SCAN detects gets written immediately; beep_success()/beep_fail() in
# _write_card() is the only confirmation that's reachable.
W_MENU = "menu"
W_GROUP = "group"
W_SCAN = "scan"
W_SPLASH = "splash"


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


def _boot_grace(ui):
    ui.paint_booting()
    print("# booting -- Ctrl-C within %ds to stay at the REPL" % GRACE_S)
    for remaining in range(GRACE_S, 0, -1):
        print("# %d..." % remaining)
        time.sleep_ms(1000)


class BdialServer:
    def __init__(self, debug=False):
        self._input = DialInput()
        self.ui = DialUI(self._input)
        self.link = JsonLink(self.dispatch, debug=debug)
        self.code = CodeServer()
        self.nfc = None
        self.running = True
        self.linked = True

        self._mode = MODE_IDLE
        self._nfc_ok = False  # real _init_nfc() result -- reported in identity
        self._nfc_field_on = False
        self._nfc_fail_count = 0  # consecutive detect_tag errors -- see _scan_step
        self._write_state = W_MENU  # WRITE sub-state; see W_* above

        # (title, [tag, ...]) per game, then the utility group. Top-level
        # rows are these titles plus DONE; _group_cursor indexes into the
        # open group's tags, which are followed by a "< back" row.
        self._groups = [(UTILITY_GROUP, list(UTILITY_TAGS) + [READ_ENTRY])]
        self._entries = [UTILITY_GROUP, DONE_ENTRY]
        self._cursor = 0
        self._group_cursor = 0
        # entry label -> cumulative successful writes, seeded from
        # stats_log at boot by _load_stats() and incremented in memory.
        self._written = {}
        self._pulls_total = 0  # cumulative games handed to wands, all boots
        self._index = {}  # slug -> {name, added}
        self._active = None

        self._pending_tag = None
        self._pending_existing = None

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
        """Diagnostic only -- chasing the SERVE-mode WiFi OOM (see
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
        self._nfc_field_on = False

    # ─────────────────────────────────────────────
    # INPUT
    # ─────────────────────────────────────────────
    # Encoder / button / touch collapse into dial_input intents. No fallback
    # path: a broken input must be a loud crash, not a silently-degraded mode.

    # ─────────────────────────────────────────────
    # MODES
    # ─────────────────────────────────────────────

    def _set_mode(self, new_mode, announce=True):
        """Single point of truth for the radio/reader invariant.

        Every transition leaves the mode it is leaving fully de-energized
        before energizing anything for the mode it is entering. Keeping this
        in one method is also what makes the reboot-into-mode variant a
        contained change if T1's AP-cycle probe shows in-place AP down/up is
        not reliable on this hardware: only this method would swap to writing
        a mode flag and calling machine.reset().
        """
        if new_mode == self._mode:
            return
        old = self._mode
        if announce:
            self.ui.paint_mode_change(new_mode)

        # --- leave ---
        if old == MODE_SERVE:
            self.code.disarm()  # ap.active(False) + AP_SETTLE_MS
        if old == MODE_WRITE:
            self._nfc_field(False)
            self._clear_pending()

        # --- enter ---
        if new_mode == MODE_SERVE:
            if self._active:
                self.code.set_game(self._active)
            elif self.code.resolve() is None:
                print("# SERVE refused: no active game")
                self.ui.paint_error("No Game to Serve")
                time.sleep_ms(1500)
                self._repaint()
                return
            self._log_mem("before arm()")
            armed = self.code.arm()
            self._log_mem("after arm() attempt")
            if not armed:
                # No game on flash, or the socket would not bind. Say so and
                # stay where we were rather than sitting on a dead AP.
                print("# SERVE refused: CodeServer.arm() failed")
                self.ui.paint_error("No Game to Serve")
                time.sleep_ms(1500)
                self._mode = old
                self._repaint()
                return
            self.link.send({"type": "armed", "id": None, "ssid": SSID})

        self._mode = new_mode
        reset_log.note_mode(new_mode)
        # A gesture that caused the switch must not carry into the new mode:
        # the hold that left SERVE would otherwise immediately read as EXIT
        # (or ACT on release) in WRITE.
        self._input.clear()
        self._write_state = W_MENU
        self._nfc_fail_count = 0
        print("# mode %s -> %s" % (old, new_mode))
        self._emit_mode()
        self._repaint()

    def _mode_payload(self, rid=None):
        """JSON for mode event / cmd reply."""
        return {
            "type": "mode",
            "id": rid,
            "mode": self._mode,
            "games": len(self._index),
            "active": self._active,
            "ssid": SSID if self._mode == MODE_SERVE else None,
        }

    def _emit_mode(self, rid=None):
        self.link.send(self._mode_payload(rid))

    def _repaint(self):
        if self._mode == MODE_WRITE:
            if self._write_state == W_GROUP:
                group = self._current_group()
                self.ui.paint_tag_group(
                    group[0] if group else "", self._group_rows(),
                    self._group_cursor, self._written)
            else:
                self.ui.paint_tag_list(self._entries, self._cursor)
        elif self._mode == MODE_SERVE:
            self.ui.paint_serve(SSID, self._pulls_total)
        else:
            self.ui.paint_idle(self.linked)

    def _current_entry(self):
        """The label the write path acts on.

        Every state except W_MENU is reached from inside a group, and they all
        act on the selected tag -- _to_scan() paints it, _scan_step() compares
        the card against it, _write_card() writes it -- so only the top-level
        menu resolves to a group title.
        """
        if self._write_state != W_MENU:
            rows = self._group_rows()
            if self._group_cursor < len(rows):
                return rows[self._group_cursor]
            return BACK_ENTRY
        return self._entries[self._cursor]

    # ─────────────────────────────────────────────
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
        """Legacy/REPL entry point -- now means "go to SERVE".

        Arming used to mean AP up *and* card writing at once; that pairing is
        exactly what Phase A separates. The dial no longer does this at boot:
        it starts in WRITE and a teacher chooses DONE + ACT to serve.
        """
        if not self._payload_ready():
            self.link.send({"type": "error", "id": rid, "code": "no_payload",
                             "msg": "no game on device"})
            return
        if self._active:
            self.code.set_game(self._active)
        self._set_mode(MODE_SERVE)
        if self._mode == MODE_SERVE:
            self.link.send({"type": "ok", "id": rid, "cmd": "arm", "ssid": SSID})
        else:
            self.link.send({"type": "error", "id": rid, "code": "arm_failed"})

    def do_disarm(self, cmd, rid):
        self._set_mode(MODE_WRITE if self._payload_ready() else MODE_IDLE)
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
                "pulls": 0,
                # From <slug>.tags.json. The app shows this as the game's
                # expected-card list, so a box holding a game the laptop
                # never sent still reports the right tags.
                "tags": meta.get("tags") or [],
            })
        # Enrich pulls from stats if available.
        try:
            import stats_log
            agg = stats_log.aggregate()
            pulls = agg.get("pulls") or {}
            for item in lst:
                item["pulls"] = pulls.get(item["slug"], 0)
        except Exception:
            pass
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
        self._pulls_total = 0
        self._repaint()
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
            self._pulls_total = 0
            for n in agg.get('pulls', {}).values():
                self._pulls_total += n
        except Exception as e:
            # Counters are cosmetic; a corrupt log must not stop the boot.
            print("# stats load failed: %s" % str(e))
            self._written = {}
            self._pulls_total = 0

    def _boot_scan_games(self):
        """Merge /flash/games/*.py into index.json; pick active.

        New-this-boot files (not in previous index) become active; if several,
        latest mtime wins. Otherwise keep active.txt if still present.
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
            if not name.endswith('.py'):
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
        """Group the writable tags: one group per game, then the utilities.

        A game's group is its two pickup tags -- getcode:<slug> pulls the code,
        a bare <slug> plays the copy already on the wand -- followed by the
        tags the game itself needs, as pushed alongside it in <slug>.tags.json.
        The utility group is always present, so "stop" can be written even
        with no games loaded. Top-level rows are the group titles plus DONE.
        """
        groups = []
        for slug in self._index:
            tags = ["getcode:" + slug, slug]
            for t in (self._index[slug].get("tags") or ()):
                if t and t not in tags:
                    tags.append(t)
            groups.append((self._index[slug].get("name") or slug, tags))
        if not groups:
            groups.append(("Games", list(TAG_LIST)))
        groups.append((UTILITY_GROUP, list(UTILITY_TAGS) + [READ_ENTRY]))

        self._groups = groups
        self._entries = [title for title, _ in groups] + [DONE_ENTRY]
        self._cursor = 0
        self._group_cursor = 0

        # Drop written counts for labels no longer on any group.
        live = set()
        for _, tags in groups:
            for t in tags:
                live.add(t)
        keep = {}
        for k, v in self._written.items():
            if k in live:
                keep[k] = v
        self._written = keep

    def _current_group(self):
        """(title, tags) of the group the cursor is on, or None on DONE."""
        if self._cursor < len(self._groups):
            return self._groups[self._cursor]
        return None

    def _group_rows(self):
        """The open group's tags plus the trailing "< back" row."""
        group = self._current_group()
        tags = list(group[1]) if group else []
        tags.append(BACK_ENTRY)
        return tags

    # ─────────────────────────────────────────────
    # WRITE MODE
    # ─────────────────────────────────────────────

    def _nfc_field(self, on):
        """Energize/de-energize the reader, tracking state to avoid redundant
        I2C writes on every loop iteration."""
        if self.nfc is None or on == self._nfc_field_on:
            return
        self._nfc_field_on = on
        try:
            self.nfc.antenna_on() if on else self.nfc.antenna_off()
            _dbg("field -> %s (chip reports ant=%s crypto=%s)"
                 % ("ON" if on else "off", self.nfc.antenna_is_on(),
                    self.nfc.crypto_on()))
        except Exception as e:
            print("# NFC antenna %s FAILED: %s" % ("on" if on else "off", str(e)))

    def _clear_pending(self):
        self._pending_tag = None
        self._pending_existing = None

    # ─────────────────────────────────────────────
    # WRITE MODE — sub-state machine
    # ─────────────────────────────────────────────

    def _to_menu(self):
        _dbg("state %s -> menu" % self._write_state)
        self._write_state = W_MENU
        self._nfc_field(False)
        self._clear_pending()
        self._repaint()

    def _to_group(self):
        """Back to the open group's tag list.

        Where a write lands when it finishes: a teacher writing eight note
        cards should not have to re-enter the group between each one.
        """
        _dbg("state %s -> group" % self._write_state)
        self._write_state = W_GROUP
        self._nfc_field(False)
        self._clear_pending()
        self._repaint()

    def _to_scan(self):
        _dbg("state %s -> scan (target=%s)"
             % (self._write_state, self._current_entry()))
        self._write_state = W_SCAN
        self._clear_pending()
        # Never begin a scan in encrypted mode: a MIFARE auth from an
        # earlier scan latches MFCrypto1On, and while it is set the reader
        # cannot answer a plain REQA, so nothing is ever detected. Toggling
        # the antenna does not clear it -- only this does (or a reboot,
        # which is why the first scan after boot used to be the only one
        # that worked).
        if self.nfc is not None:
            try:
                self.nfc.stop_crypto1()
            except Exception as e:
                # Transient I2C glitch (e.g. ENODEV from bus contention) --
                # same tolerance _scan_step()/_nfc_field() give every other
                # reader call. Left uncrypto'd here just means the next
                # detect_tag() may hit the same MFCrypto1On wedge that this
                # call exists to clear; _scan_step()'s own error handling
                # and reinit-after-N-failures will recover from that.
                print("# NFC stop_crypto1 FAILED: %s" % str(e))
        self._nfc_field(True)
        self.ui.paint_scanning(self._current_entry())

    def _to_splash(self):
        """Result is on screen; it stays there until a button dismisses it.

        The RF field goes down here rather than at the next menu paint --
        nothing is being scanned while a result is being read, so there is
        no reason to keep the antenna energized for it.
        """
        _dbg("state %s -> splash" % self._write_state)
        self._write_state = W_SPLASH
        self._nfc_field(False)
        self._clear_pending()

    def _poll_write(self):
        """WRITE mode. Drain one intent per loop; scan runs when idle."""
        intent = self._input.pop()
        if intent:
            _dbg("intent %s in state=%s cursor=%d(%s)"
                 % (intent, self._write_state,
                    self._cursor, self._current_entry()))

        if self._write_state == W_MENU:
            if intent == NEXT:
                self.ui.beep_click()
                self._cursor = (self._cursor + 1) % len(self._entries)
                self._repaint()
            elif intent == PREV:
                self.ui.beep_click()
                self._cursor = (self._cursor - 1) % len(self._entries)
                self._repaint()
            elif intent == ACT:
                self.ui.beep_click()
                if self._entries[self._cursor] == DONE_ENTRY:
                    self._set_mode(MODE_SERVE)
                else:
                    self._group_cursor = 0
                    self._to_group()
            return

        if self._write_state == W_GROUP:
            rows = self._group_rows()
            if intent == NEXT:
                self.ui.beep_click()
                self._group_cursor = (self._group_cursor + 1) % len(rows)
                self._repaint()
            elif intent == PREV:
                self.ui.beep_click()
                self._group_cursor = (self._group_cursor - 1) % len(rows)
                self._repaint()
            elif intent == ACT:
                self.ui.beep_click()
                if self._current_entry() == BACK_ENTRY:
                    self._to_menu()
                else:
                    self._to_scan()
            elif intent == BACK:
                self.ui.beep_click()
                self._to_menu()
            return

        if self._write_state == W_SCAN:
            if intent == BACK:
                self.ui.beep_click()
                self._to_group()
                return
            self._scan_step()
            return

        if self._write_state == W_SPLASH:
            if intent in (ACT, BACK, NEXT, PREV):
                self.ui.beep_click()
                self._to_group()
            return

    # Consecutive detect_tag() OSErrors before we assume the reader's
    # internal state machine is wedged (not just one bad I2C beat) and
    # try a fresh init() to recover it.
    NFC_REINIT_AFTER = 15

    def _scan_step(self):
        """One polling pass while in W_SCAN. The field is already on.

        Detection always ends the scan straight into SPLASH -- a write (or
        a READ_ENTRY report) happens immediately, no on-screen confirmation
        step -- so there is no same-card debounce to keep here: nothing
        polls the reader again until the teacher starts a new scan from the
        menu.
        """
        if self.nfc is None:
            return
        entry = self._current_entry()
        try:
            tag = self.nfc.detect_tag(timeout=80)
        except OSError as e:
            # The reader over I2C occasionally times out (ETIMEDOUT) on a
            # bad read -- transient, not fatal. Without this catch it took
            # down the whole run() loop (uncaught OSError -> fatal event,
            # server dead until reset).
            self._nfc_fail_count += 1
            # Only print every 5th repeat once we know it's a streak --
            # otherwise a wedged/disconnected reader floods the log with an
            # identical line on every poll forever.
            if self._nfc_fail_count <= 3 or self._nfc_fail_count % 5 == 0:
                print("# NFC detect_tag err (%d in a row): %s" % (self._nfc_fail_count, str(e)))
            if self._nfc_fail_count >= self.NFC_REINIT_AFTER:
                print("# NFC: %d consecutive errors -- attempting re-init" % self._nfc_fail_count)
                self._nfc_fail_count = 0
                try:
                    self._init_nfc()
                    print("# NFC re-init OK")
                    # _init_nfc() leaves the antenna off; we are still in
                    # W_SCAN, so put the field back up or the scan would
                    # sit there polling a de-energized reader forever.
                    self._nfc_field(True)
                except Exception as e2:
                    print("# NFC re-init failed: %s" % str(e2))
                time.sleep_ms(200)  # let the bus settle either way
            return
        self._nfc_fail_count = 0
        if tag is None:
            return  # nothing on the reader yet -- keep scanning
        self.ui.beep_scan()
        _log("DETECTED uid=%s sak=0x%02X type=%s"
             % (tag['uid_hex'], tag['sak'], tag['tag_type']))
        existing = existing_text(self.nfc, tag)
        _log("read result: existing=%s target=%s" % (repr(existing), repr(entry)))
        self.link.send({
            "type": "card_present", "uid": tag['uid_hex'], "existing": existing,
        })
        if entry == READ_ENTRY:
            # Utility entry: report what's on the card, write nothing.
            _log("READ: uid=%s existing=%s" % (tag['uid_hex'], repr(existing)))
            self.ui.paint_read_result(existing)
            self.ui.beep_success()
            self._to_splash()
            return
        if existing == entry:
            # Already carries the text we would write -- report, don't rewrite.
            _log("card already carries %s -- no write" % repr(entry))
            self.ui.paint_already(entry)
            self.ui.beep_success()
            self._to_splash()
            return
        if existing:
            _log("card has %s, want %s -> auto-overwrite" % (repr(existing), repr(entry)))
        self._write_card(tag, entry)

    def _write_card(self, tag, entry):
        """Write, then leave the result on screen until a button dismisses it."""
        _log("WRITE attempt: target=%s uid=%s" % (repr(entry), tag['uid_hex']))
        self.ui.paint_writing(entry)
        ok = write_text(self.nfc, tag, entry)
        _log("WRITE result: %s" % ("OK" if ok else "FAILED"))
        if ok:
            self._written[entry] = self._written.get(entry, 0) + 1
            self.ui.paint_written(entry, self._written[entry])
            self.ui.beep_success()
            self.link.send({
                "type": "card_written", "label": entry, "uid": tag['uid_hex'],
            })
            try:
                import stats_log
                stats_log.record_tag(entry)
            except Exception as e:
                print("# stats tag failed: %s" % str(e))
        else:
            self.ui.paint_write_failed(entry)
            self.ui.beep_fail()
        self._to_splash()

    # ─────────────────────────────────────────────
    # SERVE MODE
    # ─────────────────────────────────────────────

    def _serve_abort_requested(self):
        """should_abort hook for CodeServer.poll().

        Samples input itself: poll() blocks for the whole transfer, so the
        main loop's update() is not running and a cached reading would never
        change. Without this the hold-to-exit / CLOSE gesture is unreachable
        for the duration of a transfer.
        """
        self._input.update()
        if self._input.peek_exit():
            self._input.take(EXIT)
            return True
        return False

    def _on_serve_event(self, event):
        if event == 'serving':
            self.ui.paint_receiving()

    def _poll_serve(self):
        xfer = self.code.poll(on_event=self._on_serve_event,
                              should_abort=self._serve_abort_requested)
        if xfer == 'ok':
            # Mirrors the line stats_log just recorded, so the screen and the
            # log agree without re-reading flash on every repaint.
            self._pulls_total += 1
            self._repaint()
        elif xfer == 'fail':
            self.ui.paint_error("Transfer Failed")
            time.sleep_ms(1000)
            self._repaint()
        elif xfer == 'abort':
            # The teacher held the button (or tapped CLOSE) through a
            # transfer; that is the exit gesture. The wand sees a short
            # read, drops its .part file and retries within its budget.
            print("# serve aborted by EXIT")
            self._set_mode(MODE_WRITE if self._payload_ready() else MODE_IDLE)
            return
        intent = self._input.pop()
        if intent == EXIT:
            self._set_mode(MODE_WRITE if self._payload_ready() else MODE_IDLE)

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
        self._log_mem("after M5.begin")

        # WiFi's AP driver wants a big contiguous heap block (see
        # dial_board.py H5 -- SoftAP OOM'd in Phase 0 probing, and for real
        # in a live run). Grab it now, while the heap is still close to
        # pristine, before the LVGL screens and NFC driver below fragment
        # it with lots of small allocations. Unverified whether this
        # actually reserves anything past .active(False) -- that's exactly
        # what the surrounding _log_mem calls (and prewarm_ap()'s own) are
        # here to check on a real retry.
        try:
            prewarm_ap()
        except Exception as e:
            print("# AP prewarm failed: %s" % str(e))
        self._log_mem("after AP prewarm")

        self._input.begin()
        self.ui.begin()  # calls m5ui.init(); builds LVGL screens once
        self._log_mem("after ui.begin (4 LVGL screens)")
        _boot_grace(self.ui)
        try:
            self._init_nfc()
            self._nfc_ok = True
        except Exception as e:
            print("# NFC init failed: %s" % str(e))
            self._nfc_ok = False
        self._log_mem("after _init_nfc")

        self._load_stats()
        self._boot_scan_games()
        # Unsolicited identity, once, purely informational: it lets an
        # already-attached app fill in version/reader status without asking.
        # It is deliberately NOT an introduction or a readiness signal -- an
        # app that connects after this point never receives it and must be
        # perfectly happy, learning liveness from `heartbeat` instead.
        self._send_identity()
        # Late-connecting apps learn the mode without asking.
        # Emit after scan so games/active are accurate; _set_mode may emit again.
        self._mode = MODE_IDLE
        self._set_mode(MODE_WRITE if self._payload_ready() else MODE_IDLE,
                       announce=False)
        if self._mode == MODE_IDLE:
            self._emit_mode()
        self._repaint()

        last_hb = time.ticks_ms()
        try:
            while self.running:
                self.link.pump(idle_ms=20, drain_ms=40)
                self._input.update()
                if self._mode == MODE_SERVE:
                    self._poll_serve()
                elif self._mode == MODE_WRITE:
                    # IDLE deliberately polls nothing: no game on flash means
                    # there is neither a tag to write nor code to serve.
                    self._poll_write()
                now = time.ticks_ms()
                if time.ticks_diff(now, last_hb) > HEARTBEAT_MS:
                    self.link.send({"type": "heartbeat", "up": now, "mem": gc.mem_free()})
                    last_hb = now
                # Required by root AGENTS.md; Dial_Music.py is missing it.
                time.sleep_ms(1)
        finally:
            self._shutdown_radios()

    def _shutdown_radios(self):
        """De-energize both radios on the way out of run(), whatever the reason.

        Without this the AP stays up after the program stops: `repl` and a
        soft `reboot` both just clear self.running and return, and an
        uncaught exception unwinds straight past to main.py. In every one of
        those cases the SoftAP was left broadcasting with nothing serving it,
        which breaks the one invariant this file exists to hold. Each half is
        guarded separately so a failure to put the reader down cannot stop
        the AP coming down.
        """
        try:
            if self.code.armed:
                self.code.disarm()
                _log("shutdown: AP down")
        except Exception as e:
            print("# shutdown: AP disarm FAILED: %s" % str(e))
        try:
            self._nfc_field(False)
        except Exception as e:
            print("# shutdown: NFC field off FAILED: %s" % str(e))
