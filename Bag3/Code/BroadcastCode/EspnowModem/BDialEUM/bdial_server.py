"""
bdial_server.py — JSON serial dispatcher + NFC card flow + ESP-NOW code serving.

BDialEUM copy of BroadcastDial/BDialFirmware/bdial_server.py. The Dial uses
no WiFi: game code goes to wands over ESP-NOW through an external ESP-NOW
UART modem (code_link.py). Pairs with EspnowModem/MockWandEUM wands only;
stock wands pull over WiFi and get nothing from this build.

Differences from the WiFi Dial:
  - Code is served continuously, in every mode. There is no SERVE mode, no
    DONE / "Enable Share" row and no hold-to-exit: the modem is a separate
    chip, so serving never conflicts with the NFC field.
  - arm is accepted and changes nothing; disarm is refused (always_serving).
    No "armed" event; "ssid" is always null.
  - identity carries "variant": "eum". info carries the modem and sender
    counters. New events: "pull" (one per finished or dropped transfer)
    and "modem" (modem link up / lost).
  - Result-screen holds keep servicing the modem instead of sleeping, so a
    card write does not stall wands mid-pull.

Modes:

    WRITE  Game on flash. Reader polled only while scanning.
    IDLE   No game on flash. Nothing to write; code_req gets a refusal.

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
from code_link import CodeLink, HOST_ID
from card_writer import existing_text, write_text
from dial_ui import DialUI
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

# How long the top-level breadcrumb reads "Pull Failed" after one wand's
# pull fails or is dropped. See _on_code_event().
PULL_FAIL_NOTE_MS = 3000

# Same paths code_sender.py serves from.
GAMES_DIR = '/flash/games'
ACTIVE_PATH = '/flash/active.txt'
INDEX_PATH = GAMES_DIR + '/index.json'

# Legacy single-game tags — replaced at boot by _rebuild_entries() from the
# games index. Kept as a fallback if the index is empty.
TAG_LIST = ("getcode", "jumpin")

# Writable no matter which games are loaded. "stop" exits any running game;
# "battery" asks the wand to report its charge. These are plain NDEF card
# text, like every other entry -- card_writer.py does not use opcodes.
UTILITY_TAGS = ("stop", "battery")
UTILITY_GROUP = "Utility Tags"

# Not a write target -- a sentinel _scan_step() special-cases before it is
# ever treated as NDEF text. Lets a teacher check what's already on a card
# without writing anything to it, and read several cards back to back (see
# the SCAN sub-state note above) rather than one-at-a-time. Lives in the
# utility group alongside the real write tags so it shows up in the same
# menu.
READ_ENTRY = "Read Card"

MODE_IDLE = "IDLE"
MODE_WRITE = "WRITE"

# WRITE-mode sub-states. Dial intents: ACT confirms, NEXT/PREV scroll,
# BACK cancels. EXIT (button hold) is unused in this build.
#   MENU      list of groups   ACT = open                     NEXT/PREV
#   GROUP     one group's tags ACT = scan                     NEXT/PREV
#   SCAN      RF field on      BACK = group
#
# SCAN also covers the Utility Tags -> Read Card entry (READ_ENTRY below),
# a read-only "NFC Reader" utility -- see _scan_step()'s READ_ENTRY branch
# and dial_ui.paint_reader(). It never triggers a write result screen: each
# card read just repaints the same SCAN screen in place, so a teacher can
# read several cards back to back without re-entering the menu between
# them. BACK still exits it to GROUP like any other scan.
#
# The menu is two-level because a single game can contribute a dozen tags
# (melody alone has eleven).
#
# Deliberately no OVERWRITE confirmation state (same as bbox_server.py,
# the Box peer -- both dropped this): on the Dial the antenna is under the
# screen, so a card that's actually on the reader covers the same touch
# targets a confirm/cancel prompt would need. Any tag SCAN detects gets
# written immediately; beep_success()/beep_fail() in _write_card() is the
# only confirmation that's reachable.
#
# A write result (success/already/failure) is not its own sub-state -- the
# result screen is painted, held on screen for a fixed delay below, and
# then _write_card()/_scan_step() transition on their own (success/already
# back to GROUP, failure back into a fresh SCAN of the same target). A
# "tap to continue" SPLASH state used to sit between the result and that
# transition; testing showed the extra tap was a nuisance given the
# screen+beep already say what happened, so it was removed -- these are
# the only holds left standing in for it.
RESULT_HOLD_OK_MS = 1000
RESULT_HOLD_FAIL_MS = 500
W_MENU = "menu"
W_GROUP = "group"
W_SCAN = "scan"


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
    """Card bytes for a menu row. getcode rows carry this host's id, so a
    scanning wand or icon display can pin to this exact host instead of
    whichever SP-FILEPUSH* AP its scan happened to see first (see
    code_puller.py's _find_ap()). Only getcode rows: a bare "<slug>"/"stop"/
    "battery" card is not host-specific and must keep working on any host
    exactly as it read before this change. Called only where a card is
    actually written (_write_card()), never where the menu/group rows
    themselves are built (_rebuild_entries()), so the on-screen label a
    teacher picks stays "getcode:<slug>" and only the written bytes gain
    the suffix.
    """
    if label == 'getcode' or label.startswith('getcode:'):
        return label + '@' + HOST_ID
    return label


def _boot_grace(ui):
    # The booting screen is painted either way -- it is what the teacher sees
    # while the rest of boot runs, not part of the countdown.
    ui.paint_booting()
    if GRACE_S <= 0:
        return
    print("# booting -- Ctrl-C within %ds to stay at the REPL" % GRACE_S)
    for remaining in range(GRACE_S, 0, -1):
        print("# %d..." % remaining)
        time.sleep_ms(1000)


class BdialServer:
    def __init__(self, debug=False):
        self._input = DialInput()
        self.ui = DialUI(self._input)
        self.link = JsonLink(self.dispatch, debug=debug)
        self.code = CodeLink(on_event=self._on_code_event)
        self.nfc = None
        self.running = True
        self.linked = True

        self._mode = MODE_IDLE
        self._nfc_ok = False  # real _init_nfc() result -- reported in identity
        self._nfc_field_on = False
        self._nfc_fail_count = 0  # consecutive detect_tag errors -- see _scan_step
        self._write_state = W_MENU  # WRITE sub-state; see W_* above

        # (title, [tag, ...]) per game, then the utility group. Top-level
        # rows are these titles; _group_cursor indexes into the
        # open group's tags directly (BACK exits the group from any
        # cursor position -- see _poll_write()'s W_GROUP handling).
        self._groups = [(UTILITY_GROUP, list(UTILITY_TAGS) + [READ_ENTRY])]
        self._entries = [UTILITY_GROUP]
        self._cursor = 0
        self._group_cursor = 0
        # entry label -> cumulative successful writes, seeded from
        # stats_log at boot by _load_stats() and incremented in memory.
        self._written = {}
        self._pulls_total = 0  # cumulative games handed to wands, all boots
        self._pull_fail_until = 0  # ticks_ms() deadline for the "Pull Failed" crumb, 0 = none
        self._index = {}  # slug -> {name, added}
        self._active = None

        self._reader_last_uid = None  # debounce for READ_ENTRY; see _scan_step()
        self._crumb_shown = None  # last share-crumb text painted

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
        """Diagnostic only. gc.collect() first so mem_free() reports real
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
        """The one place modes change. Leaving WRITE puts the reader down.
        Code serving is unaffected by mode."""
        if new_mode == self._mode:
            return
        old = self._mode
        if announce:
            self.ui.paint_mode_change(new_mode)
        if old == MODE_WRITE:
            self._nfc_field(False)
            self._clear_pending()
        self._mode = new_mode
        reset_log.note_mode(new_mode)
        # A gesture that caused the switch must not carry into the new mode.
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
            "ssid": None,
        }

    def _emit_mode(self, rid=None):
        self.link.send(self._mode_payload(rid))

    def _repaint(self):
        if self._mode == MODE_WRITE:
            if self._write_state == W_GROUP:
                group = self._current_group()
                self.ui.paint_tag_group(
                    group[0] if group else "", self._group_rows(),
                    self._group_cursor, self._written,
                    read_only=(self._current_entry() == READ_ENTRY))
            else:
                self._crumb_shown = self._share_crumb()
                self.ui.paint_tag_list(self._entries, self._cursor,
                                       self._crumb_shown)
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
            return ""  # defensive only -- NEXT/PREV wrap on len(rows), so
            # _group_cursor should never actually reach here
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
            # Fixed for the life of the boot (see code_link.HOST_ID); the
            # "@<id>" suffix on every getcode card this Dial writes.
            "host_id": HOST_ID,
            # "device" stays "broadcast_dial" so ChatBroadcast accepts the
            # link; this says code goes over ESP-NOW, not SoftAP.
            "variant": "eum",
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
        msg = {
            "type": "info", "id": rid,
            "version": VERSION, "mem": gc.mem_free(),
            "armed": self.code.linked, "linked": self.linked,
            "payload_ready": self._payload_ready(),
            "written": sum(self._written.values()), "up": time.ticks_ms(),
        }
        msg.update(self.code.stats())
        self.link.send(msg)

    def do_arm(self, cmd, rid):
        """Kept for the wire contract. Code is always served in this build,
        so there is nothing to arm: reply ok when there is a game to serve,
        with the modem state, and change nothing."""
        if not self._payload_ready():
            self.link.send({"type": "error", "id": rid, "code": "no_payload",
                             "msg": "no game on device"})
            return
        self.link.send({"type": "ok", "id": rid, "cmd": "arm", "ssid": None,
                        "modem": self.code.linked})

    def do_disarm(self, cmd, rid):
        """Refused: this build cannot stop serving."""
        self.link.send({"type": "error", "id": rid, "code": "always_serving",
                        "msg": "ESP-NOW build serves continuously"})

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

        A name ending "_icon.py" is a display game staged under the suffix
        ROLE_FILES uses to pick it out for an icon_display pull in the WiFi
        build (code_sender.py has no icon leg) -- it is never itself a
        playable game on this device, so it never enters the menu or
        becomes active.
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
            if not name.endswith('.py') or name.endswith('_icon.py'):
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

        self._rebuild_entries()
        print("# games: %d active=%s" % (len(self._index), self._active))

    def _pick_active_fallback(self):
        if not self._index:
            self._set_active(None)
            return
        # First remaining slug (stable-ish dict order on MicroPython).
        for slug in self._index:
            self._set_active(slug)
            return

    def _rebuild_entries(self):
        """Group the writable tags: one group per game, then the utilities.

        A game's group is its two pickup tags -- getcode:<slug> pulls the code,
        a bare <slug> plays the copy already on the wand -- followed by the
        tags the game itself needs, as pushed alongside it in <slug>.tags.json.
        The utility group is always present, so "stop" can be written even
        with no games loaded. Top-level rows are the group titles.
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
        self._entries = [title for title, _ in groups]
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
        """(title, tags) of the group the cursor is on, or None."""
        if self._cursor < len(self._groups):
            return self._groups[self._cursor]
        return None

    def _group_rows(self):
        """The open group's tags. No trailing "< back" row -- BACK (the
        on-screen button / touchscreen back gesture) already exits the
        group from any cursor position (see _poll_write()'s W_GROUP
        handling), so a selectable back row in the list was a second,
        redundant way to do the same thing."""
        group = self._current_group()
        return list(group[1]) if group else []

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
        self._reader_last_uid = None

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
        entry = self._current_entry()
        if entry == READ_ENTRY:
            self.ui.paint_reader()  # "nothing scanned yet" state
        else:
            self.ui.paint_scanning(entry)

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

    # Consecutive detect_tag() OSErrors before we assume the reader's
    # internal state machine is wedged (not just one bad I2C beat) and
    # try a fresh init() to recover it.
    NFC_REINIT_AFTER = 15

    def _scan_step(self):
        """One polling pass while in W_SCAN. The field is already on.

        Detection ends a write scan straight into SPLASH -- the write
        happens immediately, no on-screen confirmation step -- so there is
        no same-card debounce to keep for that case: nothing polls the
        reader again until the teacher starts a new scan from the menu.

        READ_ENTRY (the "NFC Reader" utility) is the exception: it never
        reaches SPLASH, so without a debounce a card just resting on the
        reader would re-trigger a beep/repaint on every ~80ms poll. Guarded
        below by tracking the last UID reported and skipping repeats of it;
        the guard clears the moment the card is lifted (tag is None), so
        the *same* card placed back down still reads again.
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
                self._hold(200)  # let the bus settle either way
            return
        self._nfc_fail_count = 0
        if tag is None:
            if entry == READ_ENTRY:
                self._reader_last_uid = None  # lifted -- arm for the next card
            return  # nothing on the reader yet -- keep scanning
        if entry == READ_ENTRY and tag['uid_hex'] == self._reader_last_uid:
            return  # same card still resting -- already reported, stay quiet
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
            # Stays in W_SCAN afterwards (no splash/dismissal step) so the
            # teacher can read several cards back to back -- see
            # dial_ui.paint_reader() and the debounce above.
            self._reader_last_uid = tag['uid_hex']
            _log("READ: uid=%s existing=%s" % (tag['uid_hex'], repr(existing)))
            self.ui.paint_reader(existing, scanned=True)
            self.ui.beep_success()
            return
        if existing == _card_text(entry):
            # Already carries the bytes we would write (getcode rows compare
            # against the @<id>-suffixed text, since that's what actually
            # landed on the card -- see _card_text()) -- report, don't rewrite.
            _log("card already carries %s -- no write" % repr(entry))
            self.ui.paint_already(entry)
            self.ui.beep_success()
            self._hold(RESULT_HOLD_OK_MS)
            self._to_group()
            return
        if existing:
            _log("card has %s, want %s -> auto-overwrite" % (repr(existing), repr(entry)))
        self._write_card(tag, entry)

    def _write_card(self, tag, entry):
        """Write, then hold the result on screen briefly before moving on.

        Success holds RESULT_HOLD_OK_MS and returns to the group's tag
        list -- one write attempt done, ready for the next card. Failure
        holds the shorter RESULT_HOLD_FAIL_MS and goes straight back into
        a fresh scan on the *same* target, since the most likely next step
        is just trying the tap again. Screen + beep already communicate
        the result, so neither case waits on a button any more (that
        "tap to continue" step was the original design but testing showed
        it was just a nuisance -- see dial_ui.py's painters).
        """
        card_text = _card_text(entry)
        _log("WRITE attempt: target=%s (card=%s) uid=%s"
             % (repr(entry), repr(card_text), tag['uid_hex']))
        self.ui.paint_writing(entry)
        ok = write_text(self.nfc, tag, card_text)
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
            self._hold(RESULT_HOLD_OK_MS)
            self._to_group()
        else:
            self.ui.paint_write_failed(entry)
            self.ui.beep_fail()
            self._hold(RESULT_HOLD_FAIL_MS)
            self._to_scan()

    # ─────────────────────────────────────────────
    # CODE SERVING (ESP-NOW via the EUM modem)
    # ─────────────────────────────────────────────

    def _hold(self, ms):
        """Keep a result screen up for ms while still serving wands.

        Stands in for the WiFi build's time.sleep_ms() holds: a 1 s sleep
        would leave every in-flight wand re-requesting its window.
        """
        deadline = time.ticks_add(time.ticks_ms(), ms)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            self.code.service()
            time.sleep_ms(1)

    def _on_code_event(self, kind, info):
        """CodeLink events: "serving", "done", "dropped" (from CodeSender)
        and "modem". Reports each finished transfer as a "pull" event,
        records it in stats_log, and refreshes the share crumb."""
        if kind == "done" or kind == "dropped":
            ok = kind == "done" and bool(info.get("ok"))
            slug = info.get("slug") or "?"
            if ok:
                self._pulls_total += 1
            else:
                self._pull_fail_until = time.ticks_add(time.ticks_ms(),
                                                       PULL_FAIL_NOTE_MS)
            self.link.send({
                "type": "pull", "mac": info.get("mac"), "slug": slug,
                "ok": ok, "why": info.get("why", ""),
                "bytes": info.get("bytes"), "ms": info.get("ms"),
            })
            import stats_log
            stats_log.record_pull(slug, ok)
        elif kind == "modem":
            self.link.send({"type": "modem", "up": info["up"],
                            "why": info["why"] or None})
        self._refresh_crumb()

    def _share_crumb(self):
        """Top-level breadcrumb text for the current sharing state."""
        c = self.code
        if not c.modem_ok:
            state = "nomodem"
        elif not c.linked:
            state = "down"
        elif (self._pull_fail_until
              and time.ticks_diff(self._pull_fail_until, time.ticks_ms()) > 0):
            state = "failed"
        elif c.serving_count:
            state = "sending"
        else:
            state = "ready"
        return self.ui.share_crumb(state, c.serving_count, HOST_ID)

    def _refresh_crumb(self):
        """Re-text the crumb in place if the top-level list is showing and
        the text changed. Other screens pick it up on their next repaint."""
        if self._mode != MODE_WRITE or self._write_state != W_MENU:
            return
        text = self._share_crumb()
        if text != self._crumb_shown:
            self._crumb_shown = text
            self.ui.set_share_crumb(text)

    def _tick_crumb(self):
        """Clear an expired "Pull Failed" note."""
        if (self._pull_fail_until
                and time.ticks_diff(time.ticks_ms(), self._pull_fail_until) >= 0):
            self._pull_fail_until = 0
            self._refresh_crumb()

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

        self._input.begin()
        self.ui.begin()  # calls m5ui.init(); builds LVGL screens once
        self._log_mem("after ui.begin (3 LVGL screens)")
        _boot_grace(self.ui)
        try:
            self._init_nfc()
            self._nfc_ok = True
        except Exception as e:
            print("# NFC init failed: %s" % str(e))
            self._nfc_ok = False
        self._log_mem("after _init_nfc")
        # Up to espnow_manager.HELLO_WAIT_MS (2 s) if the modem is still
        # booting or absent; the booting screen covers it.
        self.code.begin()
        self._log_mem("after code.begin (EUM modem)")

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
                # Every mode: a wand's code_req gets an answer (a refusal
                # in IDLE) rather than silence.
                self.code.service()
                self._tick_crumb()
                if self._mode == MODE_WRITE:
                    self._poll_write()
                else:
                    self._input.pop()  # IDLE has nothing to act on
                now = time.ticks_ms()
                if time.ticks_diff(now, last_hb) > HEARTBEAT_MS:
                    self.link.send({"type": "heartbeat", "up": now, "mem": gc.mem_free()})
                    last_hb = now
                # Required by root AGENTS.md; Dial_Music.py is missing it.
                time.sleep_ms(1)
        finally:
            self._shutdown_radios()

    def _shutdown_radios(self):
        """Put the reader down and deactivate the modem's RX queue on the
        way out of run(), whatever the reason. Each half is guarded
        separately so one failing cannot stop the other."""
        try:
            self.code.shutdown()
            _log("shutdown: modem deactivated")
        except Exception as e:
            print("# shutdown: modem deactivate FAILED: %s" % str(e))
        try:
            self._nfc_field(False)
        except Exception as e:
            print("# shutdown: NFC field off FAILED: %s" % str(e))
