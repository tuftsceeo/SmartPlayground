# Broadcast Box ↔ ChatBroadcast: connection state, game library, and usage stats

**Written 2026-09-04. Status: plan, not implemented.**

**Evidence basis:** current code only — every claim below carries a `file:line` and was verified
against the tree at commit `cb01388`. Every other prose document under `Bag3/Code/BroadcastBox/`
was treated as **stale and excluded as evidence**; where a doc and the code disagreed, the code won.
Two such disagreements are recorded inline (§1.4 on where the power fix lives, §3.2 on whether mode
is exposed as a JSON event) — both cases the docs had wrong.

For the three subjects in the title, prefer this file over the older documents in `design/` until
it is implemented and superseded in turn.

**Vocabulary note.** After this was written, the `hello` command/event was renamed to
`identify`/`identity` to stop it being reused as a connection handshake — it reports fixed
identity, never status or liveness (`info` is status, `heartbeat` is liveness). The text below
uses the new names throughout, including where it quotes code that predated the rename.

---

## Context

ChatBroadcast connects to the Broadcast Box over Web Serial and generally *does* connect. What it
lacks is **recovery** and **timely, truthful feedback**: the badge and the Connect/Disconnect button
are written from different places and routinely disagree, a dead port keeps reporting "connected",
and there is no watchdog of any kind. `Live_Page/WebApp2` (app ↔ hub) is the working reference in
this repo and does none of these things wrong; the fix is to adopt its propagation discipline.

Alongside that, the Box is to gain capabilities it does not have today: report which mode it is in,
store and manage **multiple** games rather than one hardcoded payload, and keep a persistent count of
game pulls and successful tag writes that the app can display and reset.

There is exactly one Box (bench), one MockWand, and ChatBroadcast is not hosted. **Forward and
backward compatibility are explicitly moot** — protocol and on-flash layout may change freely.

---

# PART 1 — Report: current state

## 1.1 Box firmware — what it actually signals

Modes are `MODE_IDLE` / `MODE_WRITE` / `MODE_SERVE` (`BBoxFirmware/bbox_server.py:67-69`).
`IDLE` means *booted with no game on flash*; `_payload_ready()` (`:303-306`) picks WRITE vs IDLE at
boot (`:577`) and after every mode exit (`:543`, `:546`).

**Boot timeline** — this is load-bearing and currently unaccounted for by the app:

| t | Box action | On the wire |
|---|---|---|
| 0 | reset | port re-enumerates (native USB CDC) |
| 0 | `_boot_grace()` `:97-102` | `# booting -- Ctrl-C within 5s to stay at the REPL` |
| 0–5 s | `GRACE_S = 5` `:40`, one print/sec | `# 5...` `# 4...` … `# 1...` |
| ~5 s | `_init_nfc()` `:143-147` | (silent; may fail → `_nfc_ok = False`) |
| ≥5 s | `_send_identity()` `:569` | first `identity` |
| +5 s | main loop `:593-594` | `heartbeat` every `HEARTBEAT_MS = 5000` `:39` |

**`GRACE_S` is reducible, not a fixed cost** (user-confirmed): the grace only has to leave a window
for a Ctrl-C into the REPL, and the running main loop already yields every iteration
(`time.sleep_ms(1)` `:596`, plus `link.pump(idle_ms=20, drain_ms=40)` `:583`), so an interrupt lands
fine once the loop is up. Shrinking it is the cheapest available win on feedback latency — see §3.6.

**Outbound message types** (grep-verified, `bbox_server.py`): `identity`, `heartbeat`, `armed`,
`card_present`, `card_written`, `info`, `ok`, `error`, `bye`.

- `identity` `:246-254` — `{type, id, device:"broadcast_box", version, w:240, h:135, nfc:<real init result>}`.
  Sent **unsolicited at boot** (`:569`) *and* in reply to `{"cmd":"identify"}` (`:259-260`).
- `armed` `:207` — `{type:"armed", id:null, ssid:SSID}`, emitted on **entering** `SERVE`.
- `bye` — only from the `repl` (`:293`) and `reboot` (`:298`) handlers, i.e. **only when the app asked
  for it**. Never emitted on unexpected loss.
- Accepted commands (`self.handlers`, `:130-136`): `identify`, `info`, `arm`, `disarm`, `repl`, `reboot`.
  **No game-management or stats commands exist.**

**Gap A — mode is only half-announced.** Entering `SERVE` emits `armed`. *Leaving* `SERVE`, and every
`WRITE`↔`IDLE` transition, emits nothing but `print("# mode %s -> %s")` (`:219`) — and the app drops
every line not starting with `{` (`ChatBroadcast/js/device/bboxLink.js:54-59`). So the app cannot
currently tell WRITE from IDLE at all, and sees SERVE entry but never SERVE exit.

**Gap B — one hardcoded game.** `PAYLOAD_PATH = /flash/payload.py` (`:52`), served under the fixed
destination name `jumpin.py` (`code_server.py:29-30`). `TAG_LIST = ("getcode", "jumpin")` (`:59`) is
hardcoded. There is no notion of a library, a selection, or a name.

**Gap C — counters are in-memory, lost on every reset.** `self._written = {}` is commented "count
written **this session**" (`:122`); `CodeServer._pickups = 0` (`code_server.py:117`). `do_info`
reports `sum(self._written.values())` (`:268`). Nothing is persisted. `reset_log.py` is the only
flash-persistence code in the tree and is a good idiom to copy (append-only, temp-file+rename trim,
never raises) — but it has **no global on/off switch**, which the user wants.

**Constraint — serving blocks the main loop.** `CodeServer.poll()`'s own docstring says `on_event('serving')`
fires "before the blocking serve"; `_serve_client` (`code_server.py:~160-200`) then runs to completion.
`SOCK_REPLY_TIMEOUT_S = 30` (`:25`) bounds the final `cs.read(2)`; `CHUNK = 512` with `YIELD_MS = 20`
adds ~20 ms per 512 B. While that runs, `self.link.pump()` is not called, so **heartbeats stop and
inbound commands are not read for up to ~30 s on a stalled wand.** Any heartbeat watchdog must
tolerate this or it will declare a healthy serving Box dead.

## 1.2 App — connect/disconnect states and indicators

The only state is four booleans read at paint time (`ChatBroadcast/js/app.js:207-212`):
`connected` / `running` / `atRepl` / `wrongDevice`, rendered by `setConnectionBadge()`
(`js/router.js:43-61`) into five strings: `● wrong device`, `● at REPL`, `● connected`,
`● connecting…`, `● not connected`. Badge colors at `css/app.css:224-233`; the header button is
always visible and only ever changes its label (`index.html:74-75`).

## 1.3 Identified issues

**I1 — a dead port still reports connected.** `isConnected()` is
`this.port !== null && this.port.readable !== null` (`js/device/serialAdapter.js:53-55`). On unplug or
reset, `port.readable` remains a non-null *errored* stream until `port.close()`, which never runs. So
`isConnected()` cannot ever report a dead port.

**I2 — the read loop is a dead end (root cause).** Both exits only log:
`if (done) { logWarn(...); break; }` and `catch (e) { logError(...) }`
(`serialAdapter.js:189-221`). `SerialAdapter` has **no** `onClose`/`onError`/`onDisconnect` hook —
`onData` is the only callback (`:34`) — and the port is not nulled. Nothing upstream is ever told.
This is exactly the chain WebApp2 has and ChatBroadcast does not
(`WebApp2/js/adapters/serialAdapter.js:392-396` → `mpy/hub_serial.py:194-198` → `main.py:461-477` →
`js/main.js:436-455`).

**I3 — badge and button desynchronise.** The button label is written *only* inside the `refresh()`
closure (`app.js:207-219`), reachable only from `identity`/`heartbeat`/`repl`/`wrong_device`/`bye`
events. Three call sites write the badge **directly**, bypassing it: `:250` (drop), `:663` (connect),
`:686` (disconnect). Observable results: after unplug the badge says "not connected" while the button
still says **"Disconnect"**; after clicking Disconnect the button *stays* "Disconnect" because no
further device event will ever arrive to correct it.

**I4 — unplug handling is cosmetic.** `onSerialDrop()` (`:247-253`) repaints the badge and toasts but
never calls `device.disconnect()`. The reader lock stays held, `running` stays `true`, and any
buffered late message triggers `refresh()`, which repaints **"● connected"** over the drop notice.
The 2 s `serialDropHandled` debounce (`:252`) only re-permits the toast.

**I5 — no watchdog of any kind.** `grep setInterval js/` returns nothing. Heartbeats arrive every 5 s
and only trigger a repaint; nothing notices when they stop.

**I6 — the validation probe cannot succeed on a booting Box.** `connect()` fires
`json.identify({ timeoutMs: 4000 }).catch((e) => logWarn(...))` (`js/device/bboxDeviceLink.js:125`) —
fire-and-forget, so a failure is invisible; and **4000 ms is shorter than the Box's ≥5 s boot grace**,
so connecting to a booting or just-reset Box guarantees a timeout. The badge then sits at
"● connecting…" with no explanation.

**I7 — any typed message means "connected".** `_markRunning` (`bboxDeviceLink.js:66-69`) sets
`running = true` on *any* object with a `type`. `error` and `fatal` both qualify. There is no real
identity gate beyond the `device !== "broadcast_box"` check, which only runs if a `identity` happens to
arrive.

**I8 — `bye` is misinterpreted as a failure.** `json.on("bye", () => { this.running = false; })`
(`:90-92`) leaves `connected=true, running=false`, which `router.js` renders as **"● connecting…"
indefinitely**. But the Box only sends `bye` when the app asked it to reboot — it means "back
shortly", and there is no state for that.

**I9 — the whole send window is unreported.** `sendGame` calls `_detachJson()` → REPL takeover →
`uploadFile` → `softReset()` → wait ≤10 s for a typed message → `_attachJson()`
(`bboxDeviceLink.js:187-200`, `js/device/boxFirmwareInstaller.js:39-53`). Throughout, no events flow
and `refresh()` never fires, so the badge shows a **stale "connected"** across an upload and a
reboot, then may take up to 5 s more to correct.

**I10 — `uploadPayload` guards on the wrong thing.** `if (!device?.isConnected())`
(`js/upload.js:30`) — true on a dead port (I1), so sending to an unplugged Box passes the guard and
fails deep inside the REPL push with a raw error surfaced via `toast(result.error)`.

**I11 — the entire recovery API is unreachable.** `probe()`, `restartFirmware()`,
`installFirmware()`, `arm()`, `disarm()`, `sendRaw()`, `copySerialLog()` all exist on
`BboxDeviceLink` and have **zero callers** anywhere in `js/` or `index.html` (grep-verified). The only
recovery that runs is the one-shot `_autoRecoverArmed` REPL restart (`:97-104`). A teacher has no
"try again" affordance.

**I12 — real Box events are logged and nothing else.** `armed`, `card_present`, `card_written`,
`fatal`, `error` handlers are bare `dbg()`/`dbgError()` calls (`app.js:221-230`). A `fatal` from the
Box produces **no teacher-visible message at all**.

**I13 — developer language in a teacher UI.** `● at REPL` and `● wrong device` are the two strings a
kindergarten teacher is least equipped to act on.

**Naming trap for the implementer:** `this.serialOpen` (`app.js:55`, read at `:134`, `:191`) is the
**serial log drawer** open/closed flag, *not* the port. It is easy to misread as connection state.

## 1.4 The power fix is already here — and it is the same mechanism this plan reports on

Confirmed merged into `Chat_to_Tap_Doggle`. All three `claude/broadcast-box-exploration-7f9qs8*`
branches are **0 commits ahead** of it (the single extra commit on `-jvxg27`, `e496141`, is a stale
earlier draft of `bbox_ui.py` — the version on this branch is 58 insertions newer), as is
`origin/broadcast_multigame`.

The fix is architectural rather than keyword-findable, which is why a `grep` for
brownout/power turned up nothing but comments. It is the **Phase A mode machine**: `9b86d4c`
(`reset_log.py`), `54d4c9d` (`code_server.py`), `4c8525a` (`buttons.py`), `40ffba7` (`bbox_ui.py`),
`44560ce` (`bbox_server.py` — the mode machine itself). `_set_mode()` enforces a radio/reader
mutual-exclusion invariant: its `--- leave ---` block runs `self.code.disarm()` (→ `ap.active(False)`)
when leaving `SERVE` and `self._nfc_field(False)` when leaving `WRITE`, **before** its `--- enter ---`
block energizes anything, so the WiFi AP and the NFC antenna are never powered at once.

This matters to the plan in two ways:

1. **`WRITE` / `SERVE` / `IDLE` are not cosmetic labels** — they are the power states. Stage 2 is
   surfacing a mechanism that already exists and is load-bearing, not inventing UI vocabulary.
2. Long-run bench testing (Part 5) starts from a Box that should now be reset-free — but see the
   reset-attribution rule below before calling any reset a finding.

**Reset attribution rule (do not skip).** The Box's boot/reset button is physically easy to hit by
accident while handling the device, so **a reset observed during hands-on testing is not evidence of
a fault.** Treat a reset as a finding only when *either*:
- the test was hands-off (no fingers near the board — tethered idle, or driven purely from the app), *or*
- the user explicitly reports the reset as unexpected.

`reset_log.py`'s `_CAUSE_NAMES` (`:29-36`) is the discriminator and it already exists: `HARD` /
`PWRON` is consistent with the physical button; **`BROWNOUT` or `WDT` is a real result regardless of
who was touching the board.** Read the cause on the next boot before attributing anything.

---

# PART 2 — Objectives (from this session only)

1. App reflects the tethered Box's real state: **write / serve / idle**, plus honest
   connecting/rebooting/lost states.
2. Recovery and **timely** feedback on link loss — the reported pain.
3. Box stores and serves **multiple** games; app can add / remove / clear / select.
4. Box persists **pulls per game** and **successful tag writes per tag**; app displays and resets it.
5. Chat agent proposes a short game name; teacher sees and may edit it at send time; validated against
   reserved and existing names; slug hidden from the teacher.
6. A **global switch** to disable debug logging while leaving the logging code in place.
7. Tag text carries the game name (`getcode:<slug>`). **Wand-side honoring of that name is out of
   scope** — see Stage 3's fallback.
8. Sequence: Box capability → bench-verify → app.

---

# PART 3 — Design

## 3.1 App connection state machine

One store, one derived view — the WebApp2 discipline. Replace the four scattered booleans with a
single `this.link = { state, boxMode, deviceInfo, lastMsgAt, detail }` and **one** renderer that owns
badge *and* button together.

| State | Entered when | Badge (teacher words) | Button |
|---|---|---|---|
| `idle` | no port | `● not connected` | **Connect** |
| `opening` | `requestPort`/`open` in flight | `● connecting…` | disabled |
| `waiting` | port open, no typed msg yet | `● waking up the Box…` | **Cancel** |
| `live` | any typed msg seen | mode-specific, see 3.2 | **Disconnect** |
| `sending` | payload push in flight | `● sending your game…` | disabled |
| `rebooting` | `bye`, or post-push reset | `● restarting the Box…` | disabled |
| `lost` | port died / watchdog fired | `● lost the Box — check the cable` | **Connect** |
| `wrong` | `identity.device !== "broadcast_box"` | `● that's not a Broadcast Box` | **Disconnect** |
| `stuck` | REPL detected | `● the Box needs a nudge` + **Restart the Box** | **Disconnect** |

Two independent liveness mechanisms, deliberately split — this is what fixes objective 2:

- **Fast path (milliseconds), the one that matters.** New `onClose(reason)` callback on
  `SerialAdapter`, fired from *both* the `done` break and the `catch` in `_startReadLoop()`
  (`serialAdapter.js:196-219`), which also nulls `this.port` so I1 is structurally fixed. → `lost`.
  This covers unplug and reset, i.e. the common cases, with no delay.
- **Slow path (backstop only).** A heartbeat-age watchdog, `setInterval` ~2 s, comparing
  `Date.now() - lastMsgAt`. Threshold must clear the ~30 s serve block (§1.1): use
  **`SILENCE_LIMIT_MS = 15000` normally, raised to `45000` once an `armed` event has been seen and no
  message has arrived since**; any inbound message resets both. Catches "port open but firmware
  wedged", which the fast path cannot see.

Other transition rules:
- **Validation gate = any typed message** (`heartbeat` *or* `identity`), not the `identity` probe.
  `VALIDATE_LIMIT_MS` must exceed grace + NFC init (§1.1); 4 s today is unwinnable (I6). Set it from
  whatever `GRACE_S` ends up as after §3.6: **15 s while the grace is 5 s, 8 s once it is ~1 s.**
  Keep the probe, raise its timeout to match, and `await` it only to populate `deviceInfo` — timing
  out on the probe alone must never fail the connection.
- **`bye` → `rebooting`**, not a failure (I8), with a `REBOOT_LIMIT_MS = 20000` timer → `lost` if
  nothing comes back.
- **Parse the boot-grace lines as proof of life.** `# booting…` / `# 5...` currently hit
  `logDrop` (`bboxLink.js:54-59`). Emit a `booting` signal from that branch and use it to enter
  `rebooting` and to reset the reboot timer. Cheap, and it turns a silent 5 s into visible progress.
- `sending` wraps `sendGame`, suppressing the watchdog and blocking Disconnect (fixes I9).
- Replace `upload.js:30`'s guard with `state === 'live'` (fixes I10).

**Copy rule:** raw errors go to `dbgError` and `serialLog` (both already exist); the badge and toasts
get the teacher-facing strings above. Never a traceback in the UI, never a silent failure in the log.

## 3.2 Box mode reporting (objective 1)

Firmware: emit a `mode` event from the **single** existing choke point `_set_mode()`
(`bbox_server.py:~195-224`) on *every* transition, including exits — the fix for Gap A. This is the
same method that enforces the power invariant (§1.4), so it is already the one place every transition
must pass through; adding one `link.send()` there cannot miss a transition:

```json
{"type":"mode","mode":"WRITE|SERVE|IDLE","games":2,"active":"jumping-frogs","ssid":"SP-FILEPUSH"}
```

Also emit it once at boot right after `_send_identity()` (`:569`) so a late-connecting app learns the
mode without asking, and answer a new `{"cmd":"mode"}` for explicit resync. Add `"mode"` to
`FORWARDED_EVENTS` (`bboxDeviceLink.js:12-15`) — `armed` then becomes redundant for state purposes but
should stay, since the watchdog uses it.

App `live` sub-states: `IDLE` → `● Box ready — no games yet`; `WRITE` → `● ready to make cards`;
`SERVE` → `● handing out <name>`.

> **Open for feedback (user deferred this to me):** I am proposing the boot window (`waiting` /
> "waking up the Box…") and the empty library (`IDLE` / "no games yet") as **two distinct states**,
> because for a teacher one means *wait* and the other means *act*. Say the word and I'll collapse
> them.

## 3.3 Game library on the Box (objective 3)

On-flash layout:

```
/flash/games/<slug>.py        one game per file
/flash/games/index.json       {"<slug>": {"name": "Pretty Name", "added": <ticks>}}
/flash/active.txt             slug currently served
```

New JSON commands, added to `self.handlers` (`bbox_server.py:130-136`), each replying `ok` or `error`:

| Command | Reply |
|---|---|
| `{"cmd":"games.list"}` | `{type:"games", list:[{slug,name,bytes,pulls}], active}` |
| `{"cmd":"games.select","slug":…}` | sets `/flash/active.txt`, re-emits `mode` |
| `{"cmd":"games.delete","slug":…}` | removes file + index entry; clears active if it was |
| `{"cmd":"games.clear"}` | removes all games, index, active |
| `{"cmd":"stats.get"}` | see 3.4 |
| `{"cmd":"stats.reset"}` | truncates the stats log |

`CodeServer` gains `src_path` resolution at serve time: `serve(slug=None)` → resolve `slug` if given,
else `/flash/active.txt`, else refuse with the existing "no game to serve" path (`:200-206`).
`_payload_ready()` (`:303-306`) becomes "index non-empty". `TAG_LIST` (`:59`) becomes derived from the
index: one `getcode:<slug>` and one `<slug>` entry per game, plus `DONE`.

**Upload path:** keep the existing REPL push (`boxFirmwareInstaller.pushPayload`) — it works and is
already wired — but parameterise the hardcoded `/flash/payload.py` destination
(`boxFirmwareInstaller.js:43`) to `/flash/games/<slug>.py`, and add an index-update step. Do **not**
invent a chunked JSON upload command; that is a rewrite for no gain at this scale.

**Wand out-of-scope handling (objective 7).** The current wire protocol is server-speaks-first
(`_serve_client` writes size/digest/name immediately; the client sends only a trailing `OK`), so a
wand *cannot* request a game by name without the wand change the user excluded. Therefore: the Box
writes `getcode:<slug>` tags now and serves **the active game** to any wand that connects. When the
wand is later taught to send a requested name, `serve(slug)` already accepts it. This keeps the
existing MockWand usable for bench verification of every stage below.

## 3.4 Usage stats (objective 4)

Append-only event log at `/flash/stats.log`, copying `reset_log.py`'s idiom (append, never raise,
`_trim()` via temp-file + rename) — chosen because it is the established pattern in this tree and
gives history/timestamps for free, not because of brownouts:

```
<ticks> pull <slug> ok|fail
<ticks> tag  <slug>|getcode:<slug> ok
```

Write sites already exist and just need a line appended: pull at `code_server.py:200-202` (where
`_pickups` increments), tag write at `bbox_server.py:499` (inside the `if ok:` branch). Keep the
in-memory counters as the live/session view; the log is the persistent truth.
`stats.get` aggregates and returns `{type:"stats", pulls:{slug:n}, writes:{label:n}, since:<ticks>}`.

## 3.5 Debug-logging switch (objective 6)

Add a module-level `LOG_ENABLED = False` (one flag, one place — put it in `reset_log.py` and honor it
in `record()` / `note_mode()`, plus the `_log()` helper in `bbox_server.py`). All logging code stays;
the flag only gates the writes. **Stats are a product feature, not debug** — they must not be gated
by this switch.

## 3.6 Shorten the boot grace (feedback latency)

`_boot_grace()` (`bbox_server.py:97-102`) burns `GRACE_S = 5` (`:40`) in `time.sleep_ms(1000)` steps
*before* `_init_nfc()` and `_send_identity()`. Every connect, every reboot, and every post-send restart
pays it, and it is the single largest component of "the app sits there saying nothing".

**Change:** `GRACE_S = 1`. Do **not** go to 0 — keep a real window. The grace's only job is rescuing
a Box that is crash-looping *before* the main loop starts yielding; with no window at all, a boot-time
exception loop leaves no way in over USB short of reflashing. One second preserves the rescue and
returns four seconds to every boot.

**What must hold for this to be safe** (verify, don't assume):
- The main loop yields, so Ctrl-C lands during normal operation — `time.sleep_ms(1)` (`:596`) and
  `link.pump(idle_ms=20, drain_ms=40)` (`:583`). This looks fine by inspection.
- The blocking stretches are the risk, not the grace: `_serve_client` runs up to
  `SOCK_REPLY_TIMEOUT_S = 30` (`code_server.py:25`), and its `should_abort` hook is a cooperative
  check, **not** a `KeyboardInterrupt` path. Also `time.sleep_ms(1500)` on the SERVE-refused branch
  (`bbox_server.py:203`) and `sleep_ms(1000)` at `:536`. If REPL access during a serve turns out to
  matter, that is a separate change (yield inside the chunk loop) and not a reason to keep a 5 s grace
  at every boot.

Knock-on: `VALIDATE_LIMIT_MS` drops to ~8 s (§3.1), and the `# booting…` line parsing becomes a minor
nicety rather than a 5-second-hole filler — keep it, it still marks a reboot in progress.

## 3.7 Naming (objective 5)

- **Knowledge base** (`ChatBroadcast/knowledge/knowledge.py`) currently states *"The LLM agent may
  ONLY generate or modify ONE file: jumpin.py… Do NOT create new game files"* (`:5-7`). This must be
  rewritten for multi-game, and given a rule to emit one marker line:
  `[GAME_NAME: Jumping Frogs]`.
- **Parsing:** add `parseGameName()` / `stripGameNameMarker()` to `js/chat.js`, copying
  `parseNfcCards`/`stripNfcMarker` exactly (`chat.js:71-79`) — same regex shape, same strip pass.
- **Slugify:** lowercase, spaces→hyphens, drop anything outside `[a-z0-9-]`, collapse repeats, cap
  16 chars (NFC text + filename safety).
- **Reject** if the slug is reserved — the `EXAMPLES` ids (`melody`, `freezedance`, `rainbow`,
  `shakerainbow`, `jump`, `cooking`, `jumpin`, `sound`) plus `getcode`, `DONE`, `payload`, `main`,
  and any `GAME_TAGS` member — or if it already exists on the Box (offer **Replace** explicitly
  rather than silently overwriting).
- **UI:** show the pretty name with an edit field in the send-confirm overlay
  (`index.html` `#send-confirm-overlay`). The teacher never sees the slug.

---

# PART 4 — Staging

**Stage 1 first, and it is app-side, deliberately.** The user asked for Box-then-app, and Stages 2-6
follow that. Stage 1 is the exception because you cannot trust bench evidence from a link whose UI
lies about whether it is connected — it is the instrument you will verify everything else with.

| Stage | Scope | Files |
|---|---|---|
| **1** | Connection state machine + fast/slow liveness (§3.1). No Box change. | `js/device/serialAdapter.js`, `js/device/bboxDeviceLink.js`, `js/device/bboxLink.js`, `js/app.js`, `js/router.js`, `js/upload.js`, `css/app.css`, `index.html` |
| **2** | `mode` event + `{"cmd":"mode"}` (§3.2); **`GRACE_S` 5→1 (§3.6)**; app renders write/serve/idle. | `BBoxFirmware/bbox_server.py`; then `bboxDeviceLink.js`, `app.js`, `router.js` |
| **3** | Library storage + `games.*` commands + `serve(slug)` (§3.3). | `bbox_server.py`, `code_server.py`; then `boxFirmwareInstaller.js` |
| **4** | `/flash/stats.log` + `stats.get`/`stats.reset` + `LOG_ENABLED` (§3.4, §3.5). | `bbox_server.py`, `code_server.py`, `reset_log.py` |
| **5** | App library + stats UI (list/select/delete/clear/reset), advanced-mode gated. | `index.html`, `js/app.js`, `css/app.css` |
| **6** | Naming: knowledge rewrite, marker parse, slugify+validate, send-time edit (§3.7). | `knowledge/knowledge.py`, `js/chat.js`, `js/app.js`, `index.html` |

Reuse, don't rebuild: `reset_log.py`'s persistence idiom; `serialLog.js`'s `logInfo/logWarn/logError`
and `toText()`; `debug.js`'s `dbg/dbgWarn/dbgError`; `parseNfcCards`'s marker pattern;
`BboxDeviceLink.restartFirmware()` and `probe()` (**existing and unreachable** — Stage 1 should wire
`restartFirmware()` to the `stuck` state's "Restart the Box" button rather than write new recovery
code); `_set_mode()` as the single mode choke point; `CodeServer`'s existing
`_emit(on_event,'serving')` hook.

---

# PART 5 — Verification

Hardware, not theory — one Box, one MockWand. State the hypothesis, then falsify it on the device.
Serve ChatBroadcast from `Bag3/Code` (`python3 -m http.server`, open
`/BroadcastBox/ChatBroadcast/`) — it imports `../../Simulator/wand-sim.js`.

**Stage 1 (no Box code change — do these on today's firmware):**
1. *Unplug mid-session.* Expect: badge → "lost the Box", button → **Connect**, within ~1 s, and it
   **stays** lost (today it repaints "connected", I4). Confirm `port` is nulled and the reader lock
   released — reconnect must work without reloading the page.
2. *Connect to a Box mid-boot* (plug in, click Connect within 2 s). Expect "waking up the Box…" then
   `live` once the ≥5 s grace ends — today's 4 s probe cannot survive this (I6).
3. *Click Disconnect.* Expect badge and button to change **together** (today the button stays
   "Disconnect", I3).
4. *`{"cmd":"reboot"}` via the advanced console.* Expect `rebooting` → `live`, never a stuck
   "connecting…" (I8).
5. *Send a game.* Expect `sending` → `rebooting` → `live`, Disconnect disabled throughout (I9).
6. *Wedge test:* keep the port open with the firmware halted at the REPL (Ctrl-C). Expect `stuck`
   plus a working "Restart the Box" button, and the slow watchdog to fire at ~15 s.

**Stage 2:** cycle the Box through IDLE → WRITE → SERVE → WRITE with buttons and confirm the app
badge tracks every transition, **including the exits** that emit nothing today.

**Stage 2, boot grace (§3.6) — this one gates the timing constants, so do it before tuning them:**
1. With `GRACE_S = 1`, measure reset → first `identity` on the wire. Expect ~1 s + NFC init. Then set
   `VALIDATE_LIMIT_MS` from the measurement rather than the estimate.
2. **REPL rescue must still work.** Reset the Box and hold Ctrl-C: you must land at `>>>`. Falsifiable
   claim being tested: "one second is enough of a window in practice." If it is not, raise to 2 s —
   do not go back to 5.
3. **Crash-loop rescue.** Deliberately break `main.py` (e.g. a bad import), reflash, and confirm you
   can still Ctrl-C in before it loops. This is the *only* reason a non-zero grace exists; if it fails,
   the grace is doing nothing useful and the design decision changes.
4. Confirm Ctrl-C still reaches the REPL during normal operation (main loop running), which the
   per-iteration `sleep_ms(1)` should guarantee. Note separately whether it works *during a serve* —
   expected to fail, acceptable, and tracked as its own item rather than a blocker.

**Stage 3:** store 3 games; select each; MockWand `getcode` pull must deliver the **selected** one.
Delete the active game — expect a clean refusal to serve, not a dead AP. `games.clear` then confirm
the Box lands in IDLE.

**Stage 4:** pull twice, write three tags, then **hard-reset the Box** and confirm `stats.get` still
reports 2 and 3 (the whole point — today's counters are session-only, Gap C). Verify
`LOG_ENABLED = False` stops reset-log writes while stats keep accruing.

**Stage 5-6:** name a game "Jumping Frogs!!" → slug `jumping-frogs`, teacher never shown the slug;
retry with `jumpin` → rejected as reserved; retry an existing name → explicit Replace prompt.

**Long-run (hands-off — this is what makes it evidence).** The power fix is merged (§1.4), so leave
the Box tethered and idle for 30 min **without touching the board**, and confirm zero false `lost`
transitions. Because it is hands-off, a reset here *does* count as a finding — read the cause from
`reset_log` on the next boot and apply the attribution rule in §1.4 (`HARD`/`PWRON` vs.
`BROWNOUT`/`WDT`). Repeat once in `SERVE` with a MockWand pulling: that is the state that draws the
most power *and* legitimately stalls heartbeats (§1.1), so it exercises both the power fix and the
45 s watchdog threshold at once.

Conversely, in the hands-on steps above (1-6, and Stages 2-4, where you are pressing Box buttons and
re-plugging cables), **do not log resets as defects** — the reset button is easy to catch by accident.
Note them, check the cause, and only escalate on `BROWNOUT`/`WDT` or if the reset was clearly
unprovoked.

---

## Assumptions the implementer should challenge

- `VALIDATE_LIMIT_MS`, `SILENCE_LIMIT_MS = 15000/45000` and `REBOOT_LIMIT_MS = 20000` are derived from
  `GRACE_S`, `HEARTBEAT_MS = 5000` and `SOCK_REPLY_TIMEOUT_S = 30`. They are **starting points to
  measure on the bench**, not settled values — and `VALIDATE_LIMIT_MS`/`REBOOT_LIMIT_MS` should be set
  from the Stage 2 measurement of reset → first `identity` once `GRACE_S` is reduced (§3.6), not from the
  15 s figure written here for today's 5 s grace.
- `GRACE_S = 1` assumes one second is a usable Ctrl-C window for a human. That is a claim about
  reflexes, not code, and Stage 2 test 2 is what settles it.
- The 16-char slug cap is a guess at NFC-text and filename comfort; confirm against `card_writer.py`'s
  real capacity before Stage 6.
- Only the app-side `armed`-raises-the-threshold trick papers over the un-announced SERVE *exit*.
  Once Stage 2's `mode` event lands, prefer keying the threshold off `mode == SERVE` directly and
  delete the trick.

---

# PART 6 — Execution graph (for parallel subagent assignment)

## The two structural facts that determine everything below

1. **Two independent lanes.** `BBoxFirmware/` (MicroPython) and `ChatBroadcast/` (JS) share **zero
   files**. Lane F and Lane P run fully in parallel start to finish and join only at bench gates.
2. **Two hot files serialize their own lanes.** `js/app.js` (892 lines) and `bbox_server.py`
   (620 lines) are each touched by three or four tasks. **One owner at a time, no exceptions** —
   concurrent edits to these two files are the only real merge hazard in this plan. Every other file
   has exactly one owner.

**Bench verification is a serial resource.** One Box, one MockWand, one human. Coding parallelizes;
testing queues. Do not plan two hardware gates concurrently.

## Task table

`EDIT` = owned exclusively for the task's duration. `CTX` = read-only, safe to share.

**This table supersedes PART 4's stage/file column where the two differ.** PART 4 groups work by
deliverable for a human reader; this table groups it by *file ownership* for concurrent agents. The
one real difference: PART 4's Stage 3 mentions `boxFirmwareInstaller.js`, but that edit (the
`/flash/payload.py` → `/flash/games/<slug>.py` destination) lands in **P4**, because it must agree
with the slug the naming UI produces. Stage → task mapping: Stage 1 → W0-1, W0-2, P1 · Stage 2 → F1,
P2 · Stage 3 → F2 · Stage 4 → W0-3, W0-4, F3 · Stage 5 → P3 · Stage 6 → W0-5, W0-6, P4.

| ID | Task | EDIT (exclusive) | CTX (read-only) | Blocked by | Runs parallel with |
|---|---|---|---|---|---|
| **W0-1** | `onClose(reason)` callback fired from both read-loop exits; null `this.port` (I1, I2) | `js/device/serialAdapter.js` | `js/device/serialLog.js` | — | all W0 |
| **W0-2** | Emit a `booting` event from the `#`-line drop branch (§3.1) | `js/device/bboxLink.js` | `js/device/serialLog.js` | — | all W0 |
| **W0-3** | `LOG_ENABLED` switch gating `record()`/`note_mode()` (§3.5) | `BBoxFirmware/reset_log.py` | — | — | all W0 |
| **W0-4** | New standalone `stats_log.py`: append, aggregate, reset, `_trim()` — **no call sites yet** (§3.4) | `BBoxFirmware/stats_log.py` *(new)* | `BBoxFirmware/reset_log.py` (idiom to copy) | — | all W0 |
| **W0-5** | Knowledge rewrite: drop the one-file `jumpin.py` restriction, add the `[GAME_NAME: …]` rule (§3.7) | `knowledge/knowledge.py` | `js/examples.js` (reserved ids) | — | all W0 |
| **W0-6** | `parseGameName()`/`stripGameNameMarker()` + slugify/validate as pure functions (§3.7) | `js/chat.js`, `js/gameName.js` *(new)* | `js/examples.js`, `js/nfc.js`, `BBoxFirmware/card_writer.py` (capacity) | — | all W0 |
| **F1** | `mode` event from `_set_mode()` + `{"cmd":"mode"}` handler + `GRACE_S` 5→1 (§3.2, §3.6) | `BBoxFirmware/bbox_server.py` | `json_link.py`, `bbox_ui.py`, `reset_log.py` | — | **P1** |
| **F2** | Library: `/flash/games/`, `index.json`, `active.txt`, `games.*` handlers, `serve(slug)`, derived `TAG_LIST` (§3.3) | `bbox_server.py`, `code_server.py` | `card_writer.py`, `bbox_ui.py` | **F1** (same file) | **P2** |
| **F3** | Stats call sites (pull + tag write) and `stats.get`/`stats.reset` handlers (§3.4) | `bbox_server.py`, `code_server.py` | `stats_log.py`, `reset_log.py` | **F2** (same files), **W0-4** | **P4** |
| **P1** | Connection state machine: one store, one renderer owning badge **and** button; fast/slow liveness; `bye`→`rebooting`; wire `restartFirmware()` to the `stuck` button (§3.1, I3-I13) | `js/app.js`, `js/router.js`, `js/upload.js`, `js/device/bboxDeviceLink.js`, `css/app.css`, `index.html` | `js/device/serialAdapter.js`, `js/device/bboxLink.js`, `js/debug.js`, `js/uiMode.js`, `js/device/boxFirmwareInstaller.js`, **`Live_Page/WebApp2/js/main.js` + `js/state/store.js` + `js/components/connection/hubStatusButton.js`** (the reference implementation) | **W0-1**, **W0-2** | **F1** |
| **P2** | Render Box mode sub-states; `"mode"` → `FORWARDED_EVENTS`; retire the `armed`-raises-threshold hack | `js/app.js`, `js/router.js`, `js/device/bboxDeviceLink.js` | — | **P1** (same file), **F1** *(spec only — code against §3.2's JSON, don't wait for firmware)* | **F2** |
| **P3** | Library + stats UI: list/select/delete/clear/reset, advanced-mode gated | `index.html`, `js/app.js`, `css/app.css` | `js/uiMode.js`, `js/library.js` | **P2** (same file), **F2**+**F3** *(spec only for coding; needed for testing)* | **F3** |
| **P4** | Send-flow naming: pretty name + edit field, reserved/duplicate checks, slug→`/flash/games/<slug>.py` | `js/app.js`, `index.html`, `js/device/boxFirmwareInstaller.js` | `js/gameName.js`, `js/chat.js`, `js/nfc.js`, `js/checklist.js` | **P3** (same files), **W0-6**, **F2** | — |

## Waves

```
WAVE 0  — 6 agents, fully parallel, disjoint files, no dependencies
  W0-1 serialAdapter    W0-2 bboxLink    W0-3 reset_log
  W0-4 stats_log(new)   W0-5 knowledge   W0-6 chat/gameName
        │                                      │
        └──────────────┬───────────────────────┘
WAVE 1  — 2 agents, one per lane                      ← BENCH GATE 1 (Stage 1 + grace tests)
  F1 mode+grace  ║  P1 connection state machine
        │        ║        │
WAVE 2  — 2 agents                                    ← BENCH GATE 2 (mode transitions)
  F2 library     ║  P2 mode rendering
        │        ║        │
WAVE 3  — 2 agents                                    ← BENCH GATE 3 (library + stats persistence)
  F3 stats wiring ║ P3 library/stats UI
                 ║        │
WAVE 4  — 1 agent
                    P4 naming send-flow                ← BENCH GATE 4 (naming end-to-end)
```

## Assignment rules for whoever dispatches this

- **Wave 0 is the only place to spend agents freely** — six disjoint files, no coordination cost. Give
  each agent its EDIT file and nothing else writable.
- **W0-1 and W0-2 must publish their contracts before P1 starts**, because P1 codes against them:
  W0-1 → `adapter.onClose = (reason) => {}`, fired once from the `done` break and once from the
  `catch`, with `this.port` nulled before the callback; W0-2 → a `booting` event with
  `{ line }`. Both are one-line contracts; state them in the P1 brief rather than making P1 read the
  other agent's diff.
- **Never run two tasks that both list `js/app.js` or `bbox_server.py` under EDIT.** That rules out
  F1‖F2, F2‖F3, P1‖P2, P2‖P3, P3‖P4. Everything else in the table is safe to overlap.
- **Cross-lane pairs need no handoff** (F1‖P1, F2‖P2, F3‖P4): the JSON shapes in §3.2-3.4 are the
  contract, so the app side can be written and unit-checked before the firmware side exists.
- **Consider merging P1+P2 into one agent.** The renderer is a single function and P2 re-opens it
  immediately; one agent doing both avoids a second pass over the hot file. Recommended unless you
  specifically want the smaller review surface.
- If agents run in separate worktrees (`isolation: "worktree"`), Wave 0 is safe by construction.
  Waves 1-4 should land in the main tree in wave order, since the hot-file tasks are already
  serialized against each other.

## Definition of done per lane

- **Lane F:** every new command replies `ok`/`error` and never raises out of `dispatch()`;
  `_set_mode()` emits on *every* transition including exits; `LOG_ENABLED=False` silences the reset
  log while stats keep accruing; a hard reset preserves stats.
- **Lane P:** badge and button change together in every state, always; no path leaves the UI claiming
  "connected" on a dead port; every raw error reaches `dbgError` + `serialLog` and no traceback
  reaches the teacher.
