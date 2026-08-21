# AGENTS.md

Orientation for AI coding agents working in this repository. This file is descriptive, not a
backlog — for known defects and cleanup candidates, see [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md).

Nested `AGENTS.md` files add subtree-specific detail and are read automatically when you're working
there: [Bag3/AGENTS.md](Bag3/AGENTS.md) (wand firmware — also covers Bag2's wand code, see below)
and [Live_Page/AGENTS.md](Live_Page/AGENTS.md) (web apps).

## What this is

SmartPlayground (Tufts CEEO FET Lab) is a **non-production research prototype**: an educational
system for children, used on playground equipment, made of numerous separate, wirelessly
communicating devices. It is a **hardware *and* software design-research project** — just as there
are many software commits, there are many small hardware iterations, and some in-tree code is a
one-off hardware experiment rather than a direction being pursued.

**Cross-generation compatibility is explicitly not a goal.** Prefer deleting a dead path over
preserving it for a prior generation's sake.

## "Bag" = release

A **Bag** is a hardware+software combination that has been brought to a classroom-ready state, and
it contains **the wand plus its compatible extensions** (complementary hardware for that
generation's wand). Bag1 and Bag2 have been given to classrooms; Bag3 is the upcoming release being
worked toward.

**Fielded ≠ frozen.** Bag2 is out in the wild with participants right now. It still changes — but a
change reaching Bag2 devices carries a real verification burden (see the gate below), because it's
already in children's hands.

## Which Bag are you working on?

Three developer populations use this repo, and figuring out which one you're serving is the first
thing to resolve on any task:

| Population | Hardware | Tree |
|---|---|---|
| **The majority** | Bag2 wands — there are simply more of these in circulation | `Bag2/Code/` |
| Some | New Bag3 hardware iterations, ahead of a larger production batch | `Bag3/Code/` |
| Some | Complementary/extension prototypes interfacing with a Bag2 or Bag3 wand (TBD which) | the Bag they're compatible with |

**`Bag2/` is not legacy — it is the most widely used target.** `Live_Page/Flasher/manifests/wand.yml`
sourcing `Bag2/Code/lib` + `Bag2/Code/Wand Module` is deliberate, not a mistake to fix.

**Extensions live in the Bag they're compatible with.** Bag2's are already in-tree:
`Bag2/Code/Stations/Programming Station/`, `Bag2/Code/Stations/Slide Score Station/`,
`Bag2/Code/Splat Companion/`, `Bag2/Code/M5Paper Remote/`, `Bag2/Code/Speaker/`,
`Bag2/Code/DialSpeaker/`. A new extension goes in its compatible Bag, not a new top-level directory.

`old_stuff/` is **the Bag1 cycle's unshipped work** — control boards, Splats, Big Buttons, IR/light/
movement extensions and similar prototypes investigated during Bag1 that weren't classroom-ready
when Bag1 went out, so they never became part of `Bag1/`. It and `Bag1/` are large, tracked, and
will dominate a naive grep — don't mine them for current patterns.

## The Bag2 verification gate

**Bag2 is fielded — participants are using this hardware right now.** A change that reaches Bag2
devices cannot be merged on code review alone; it requires extensive real-world hardware testing,
which an agent cannot perform. Therefore:

- Open a **pull request** against `May_2026`. **Never merge.**
- State plainly in your summary that hardware verification is outstanding, and name specifically
  what needs testing (which device, which behavior).
- Do not claim a Bag2-affecting change works. You have not observed it work.

This is the highest-consequence rule in this file.

## Hardware state — dated 2026-08-10

Three separate decisions, at three different levels of settledness for the wand:

| Aspect | State | Where the code is |
|---|---|---|
| LED matrix **5×5, 25 pixels** | **Next major hardware round** — 10+ prototypes in production | `Bag2/Code/lib/leds.py` (current); `origin/claude/pn532-5x5` commit `8e567ca` (Bag3 port) |
| NFC reader **real PN532** | **Next major hardware round** | same |
| Card storage: **4-byte opcode @ page/block 5** vs today's NDEF text | **Still being explored** — neither accepted nor rejected | `origin/claude/pn532-5x5` commits `71e7c08`, `9ccd917` (`lib/opcodes.py`, `utilities/migrate_cards.py`) |
| LED matrix 6×10, 60 pixels + WS1850S NFC @ I2C 0x28 | **One-off hardware exploration; not going forward** — the pixels were too small | committed on `May_2026` in `Bag3/Code/` |

`origin/claude/pn532-5x5` and `origin/opcodeexperiment` are the *same three commits* and bundle the
5×5 revert, the PN532 revert, and the opcode-card experiment together. Treat them as separate
decisions at separate confidence levels, not one verdict: the matrix and reader choices are settled;
the card format is not.

### Governance protocol

Hardware iterates faster than this document, and several variants circulate at once.

> **If the user's instructions or statements about hardware differ from what's written here, trust
> the user.** Do not correct the user from the docs.
>
> But **flag the discrepancy** and ask which kind of change it is:
> - **Minor iteration** (a one-off or short-run exploration) → make the change; leave documentation alone.
> - **Major iteration** (the next hardware round) → add a **dated** entry to the hardware tables in
>   this file, `README.md`, and `Bag3/AGENTS.md`, superseding rather than overwriting the prior row.

The 6×10-vs-5×5 episode is the worked example of a minor iteration that was tried and correctly
abandoned — that's why it's a row in the table above rather than the current description of the wand.

## Wand edit rule

`Bag2/Code/Wand Module/` and `Bag3/Code/Wand Module/` are near-duplicate codebases (13 of 23 files
differ), and both are actively used. The discriminator:

- **Hardware-agnostic changes** — game logic, ESP-NOW messaging, the tap-coding grammar, shared
  `lib/` behavior → **both trees**.
- **Hardware-specific changes** — LED geometry, NFC driver, pin maps, `hubtype.py` device configs →
  **that tree only**.

State in your summary which tree(s) you touched and which you deliberately left alone.

## Branch and deploy reality

- `origin/HEAD` points at `origin/May_2026` — that's the integration branch. Branch from it, PR into
  it (see the Bag2 gate above). `main` is stale — ignore it.
- `.github/workflows/static.yml` deploys `Live_Page/` to GitHub Pages **only on push to `May_2026`**.
  Changes to `Live_Page/` on any other branch are not deployed, no matter how correct they are.
- `.github/workflows/version_bump.yml` runs on `main`/`beta*` pushes only, so it's currently dormant.

## Directory map

| Path | What it is | Status |
|---|---|---|
| `Bag2/` | Wand + fielded extensions (Stations, Splat Companion, M5Paper Remote, Speaker, DialSpeaker), plus CAD and battery-test data | **Active, most-used** |
| `Bag3/` | Wand only, next release | **Active, upcoming** |
| `Bag1/` | Plushie-generation wand + games, given to classrooms | Fielded, historical |
| `Live_Page/` | Deployed static web apps (see below) | **Current** |
| `ChatApp/` | 3-file fragment on this branch, cannot run standalone | **Broken here** — working 22-file version on `origin/chatApp`, unmerged since 2026-06-16 |
| `WebAppDocs/` | Docs for a directory layout (`App_Web/webapp/…`) that no longer exists | **Stale** |
| `old_stuff/` | Bag1-cycle prototypes that never shipped | Historical — don't mine for patterns |

## Which of the six web apps is canonical

All under `Live_Page/`, linked from `Live_Page/index.html`:

| App | Role |
|---|---|
| `WebApp2/` | **Canonical** hub controller — Bag2/Bag3 wand games, teacher-facing |
| `Flasher/` | **Canonical** code uploader — best REPL implementation (chunked base64, binary-safe) |
| `WebApp/` | Legacy — Bag1 plushie controller |
| `Code_Upload/` | Dead predecessor of Flasher, pinned to a stale branch |
| `If_Splats/` | Standalone Web-Bluetooth demo, unrelated to the hub/ESP-NOW stack — but uses a cleaner PyScript interop pattern than WebApp2, worth copying for new work |
| `wand_icons.html` | Static LED-icon reference (not an app) |

`Live_Page/Flasher/manifests/*.yml` sources are **intentional, not mistakes**:
`wand.yml` → `Bag2/Code/lib` + `Bag2/Code/Wand Module` (the majority hardware),
`hub.yml` → `Live_Page/WebApp2/hubCode2`, `m5paper.yml` → `Bag2/Code/M5Paper Remote`.
There is currently no manifest for flashing Bag3 wand hardware.

## Cross-cutting invariants — if you touch X, you must consider Y

| If you change… | Then also check/update… |
|---|---|
| A wand game or `lib/` module | The wand edit rule above — does it belong in Bag2, Bag3, or both? |
| The set of game tags | `Bag2/Code/lib/game_tags.py`, `Bag3/Code/lib/game_tags.py`, `Live_Page/WebApp2/hubCode2/game_tags.py`, `Live_Page/WebApp2/js/utils/commands.json`, `Live_Page/wand_icons.html`. Nothing enforces consistency across these four+ places. **Known drift:** `hubCode2/game_tags.py` currently has extra `jumpin1`–`jumpin5` entries and is missing `HIDDEN_TAGS = {"finddevice"}` compared to `Bag3/Code/lib/game_tags.py`. |
| `espnow_manager.py` | It is vendored byte-for-byte identical in `Bag2/Code/lib/`, `Bag3/Code/lib/`, and `Live_Page/WebApp2/hubCode2/`. Same pattern for `ssd1306.py` and `ws1850s.py`. A fix in one needs manual copying to the others. |
| REPL-over-serial upload logic | It's implemented three times: `Live_Page/Flasher/js/serial.js` (authoritative — chunked base64, binary-safe), `Live_Page/WebApp2/mpy/repl_controller.py` + `firmware_manager.py` (triple-quoted text, text-only), `Live_Page/Code_Upload/index.html` (inline, oldest). Prefer porting callers to Flasher's approach over improving the other two. |
| A JS or Python file under `Live_Page/WebApp2/` | `pyscript.toml`'s `[files]` list — an unlisted module silently 404s in the browser's virtual filesystem. (`main.py` itself is loaded via `<script src>`, not `[files]` — don't add it there.) |

## Building an extension

The integration contract for a new device that talks to a wand is the **ESP-NOW message
vocabulary** implemented in `espnow_manager.py`: broadcast-first JSON payloads, no pairing, no
channel negotiation, MAC-slotted status-poll replies to avoid collisions. Copy that file (identical
across every tree) into the new device, and place the extension's code inside the Bag whose wand it
targets.

## Verification — and its honest limits

There is **no automated test suite, no linter, and no CI** beyond the Pages deploy and the dormant
version-bump workflow. `pyrightconfig.json` sets `typeCheckingMode: "off"` — it exists only to
silence editor noise about unresolved MicroPython imports, not to check anything.
`Bag3/Code/utilities/UnitTest/` (and Bag2's equivalent) are manual, interactive, on-device REPL
bring-up scripts with no assertions — never describe running them as "running the tests."

What *is* available without hardware:

- `python -m py_compile <file>` to catch syntax errors in device code. **Compile only, never
  import** — `machine`, `espnow`, `neopixel`, and `ubluetooth` don't exist off-device.
- `.claude/launch.json`'s `flasher` config (`npx serve Live_Page/Flasher --no-clipboard`, port 8766)
  plus browser tooling, for real verification of web-app changes.
- Grep-based consistency checks for the duplicated-vocabulary invariants above.

If a change can only be validated on real hardware, say so plainly in your summary rather than
claiming it works.

## Conventions actually in use

**Device code (MicroPython):** no type annotations, no `typing`/`dataclasses`/`pathlib`/`logging`
imports, module-level config dicts (e.g. `HUB_CONFIG`). F-strings *are* used in shipped code — don't
"fix" them. Games expose a uniform `play(nfc, leds, buz, accel, i2c, enow)` entry point.

**Web code:** vanilla ES modules, no build step, no npm, no bundler — don't introduce
React/Vite/webpack. Tailwind CSS and Lucide icons load from CDN. Components are factory functions
returning detached DOM nodes with `innerHTML` template literals and `.onclick =` handlers.
`Live_Page/WebApp2/js/state/store.js` is a single mutable object with rAF-batched re-render.
`Live_Page/WebApp2/js/utils/pyBridge.js` is the only JS→Python call surface.

## Documentation trust map

| Path | Trust | Notes |
|---|---|---|
| `Bag3/Code/Wand Module/GAME_AUTHORING_GUIDE.md` | Trusted | |
| `Bag3/Code/Wand Module/readme.md` | Partial | Its "5×5 / PN532" hardware sections are correct for the *next* round, not stale as they might appear against the committed 6×10 code. Its brightness table, its 6-of-16 games list, and its "Adding a New Game" steps (describes an `if cmd == …` branch; `main.py` uses `GAME_DISPATCH`) are genuinely stale. See `Bag3/AGENTS.md`. |
| `Bag2/**/*.md` | Trusted | Accurate for Bag2 devices, which is the majority-hardware target — among the most useful docs in the repo. |
| `Live_Page/Flasher/README.md`, `Live_Page/WebApp2/hubCode2/README.md` | Trusted | |
| `Live_Page/WebApp2/README.md` | **Do not trust** | Byte-identical copy of `Live_Page/WebApp/README.md` — describes the wrong app, hub, games, and protocol. |
| `WebAppDocs/**` | **Do not trust** | Documents a directory layout removed in an earlier reorganization. |
| `.cursor/plans/*.md` | Historical artifact | Completed local plans, not specs. |
| `old_stuff/**` | Ignore | Bag1-cycle work that never shipped. |

## Protocol summary

Three layers; full detail in `Live_Page/AGENTS.md`.

1. **Web app ↔ hub** — line-delimited JSON over 115200-baud serial. App sends `{"cmd": "<tag>"}` /
   `{"cmd":"stop"}` / `{"cmd":"poll"}` / `{"cmd":"find","mac":"…"}`; hub sends
   `{"type":"ready"|"heartbeat"|"ack"|"poll_started"|"device_report"|"devices"|"error", …}`.
2. **Hub → wands** — ESP-NOW, JSON payloads, broadcast to `FF:FF:FF:FF:FF:FF`. No pairing, no
   channel negotiation. Status-poll replies are staggered by a slot derived from each wand's MAC to
   avoid collisions.
3. **(Bag1/WebApp only) Hub → plushies** — a `{"topic": "/game", "value": <int>}` pub-sub scheme,
   unrelated to the ESP-NOW layer above.
