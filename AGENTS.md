# AGENTS.md

Orientation for AI coding agents working in this repository. This file is descriptive, not a
backlog — for known defects and cleanup candidates, see [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md).

Nested `AGENTS.md` files add subtree-specific detail and are read automatically when you're working
there: [Bag1/AGENTS.md](Bag1/AGENTS.md), [Bag2/AGENTS.md](Bag2/AGENTS.md),
[Bag3/AGENTS.md](Bag3/AGENTS.md), and [Live_Page/AGENTS.md](Live_Page/AGENTS.md).

## What this is

SmartPlayground (Tufts CEEO FET Lab) is a **non-production research prototype**: an educational
system for children, used on playground equipment, made of numerous separate, wirelessly
communicating devices. It is a **hardware *and* software design-research project** — just as there
are many software commits, there are many small hardware iterations, and some in-tree code is a
one-off hardware experiment rather than a direction being pursued.

**Cross-generation compatibility is explicitly not a goal.** Prefer deleting a dead path over
preserving it for a prior generation's sake.

## "Bag" = release

A **Bag** is a hardware+software combination that has been brought to a classroom-ready state.
Bag1 and Bag2 have been given to classrooms; Bag3 is the release currently being worked toward.

**Fielded ≠ frozen.** Bag2 is out in the wild with participants right now, and both its hardware and
software still change. A change reaching Bag2 devices carries a real verification burden (see the
gate below) precisely because it's already in children's hands. Bag3 also has active software work —
new/preliminary hardware inherently needs software to test its capabilities (drivers, bring-up
scripts) even before any game or feature work begins on it.

## Ask which Bag

This is a small, nimble team, and **which Bag a piece of work belongs to changes week to week.**
This file does not, and should not, assign work to a Bag. Bag1, Bag2, and Bag3 are iterative and
somewhat parallel stages of a design-based research project — not a strict progression where later
means "current."

**If the target Bag is not already clear from the conversation or the files being edited, ask
before editing.** Each Bag's `AGENTS.md` owns that Bag's hardware facts; never carry a fact from
one Bag's docs into another Bag's code, and never assume a change belongs in more than one Bag
without confirming.

## System components — vocabulary

The project's own language for its components. Not critical for an agent operating purely on code,
but it is what the team, the existing comments, and the existing docs use — so use it in READMEs
and doc prose.

| Term | Meaning |
|---|---|
| **hub** | Generic term for a component in the system. `hubtype.txt` is a config file declaring **what type of hub (playground component)** the code is running on; `hubtype.py` turns that into `HUB_CONFIG`. |
| **module** | A component leaning **smaller and portable** — carried or handled by students. |
| **station** (also called **extension**) | A **larger, more static** component, frequently attached to playground equipment. |

Terminology itself evolves as part of the design research — "station" and "extension" are both in
use for the same idea, and don't expect one fixed name set everywhere.

**⚠ Two meanings of "hub."** The general sense above (any playground component) is what
`hubtype.txt` / `hubtype.py` / `HUB_CONFIG` mean. The **USB hub** in `Live_Page/` is one *specific*
device — the teacher-facing ESP32 that bridges USB serial to ESP-NOW. It is a teacher utility tool,
not something students use on the playground, which is why it took the generic name "hub" instead
of fitting the student-facing module/station split. `Live_Page/AGENTS.md` uses "hub" only in this
narrow sense; the Bag trees use it in the general sense. Don't assume a given "hub" mention means
the USB one.

**Why `hubtype` exists:** it lets components with slightly different hardware share the same shared
library utilities **without drift between them** — a drift-prevention mechanism, not just a pin
table. A component that doesn't use the shared utility libraries (e.g. the obstacle and music
control boards under `old_stuff/`) wouldn't be called a hub at all — just a *system component*.

**The Wand module is one component of the system, not the system.** It is the most numerous hardware
(designed at roughly one per student — design intent, not always the ratio during testing), which is
why its code dominates the repo. Splat modules, button modules, the narrator module, the paper
remote module, the speaker/dial stations, the coding/slide stations, and the USB hub are similar but
distinct hardware that generally interface with Wand modules. The Wand module was called the
**Plushie module** in Bag1 — same component, direct descendant, different name; see
[Bag1/AGENTS.md](Bag1/AGENTS.md).

## The Bag2 verification gate

**Bag2 is fielded — participants are using this hardware right now.** A change that reaches Bag2
devices cannot be merged on code review alone; it requires extensive real-world hardware testing,
which an agent cannot perform. Therefore:

- Open a **pull request** against `May_2026`. **Never merge.**
- State plainly in your summary that hardware verification is outstanding, and name specifically
  what needs testing (which device, which behavior).
- Do not claim a Bag2-affecting change works. You have not observed it work.

This is the highest-consequence rule in this file.

## Wand module edit rule

`Bag2/Code/Wand Module/` and `Bag3/Code/Wand Module/` are near-duplicate codebases (13 of 23 files
differ). **Divergence between them is expected and intended** — Bag3 began as a copy of Bag2's
firmware because that's the natural starting point for an iterative project, not because the two are
meant to stay identical. Bag3 firmware is expected to diverge in ways that are not backwards
compatible, the same way Bag2's ESP-NOW protocol is incompatible with Bag1's.

**Ask which Bag(s) a Wand module change targets before editing** rather than assuming both trees.
When it is clear a change is hardware-agnostic (game logic, ESP-NOW messaging, the tap-coding
grammar, shared `lib/` behavior not tied to pin/geometry specifics), confirm whether it should also
be applied to the other tree — don't do it silently. Hardware-specific changes (LED geometry, NFC
driver, pin maps, `hubtype.py` device configs) belong to one tree only. State in your summary which
tree(s) you touched and which you deliberately left alone.

## Branch and deploy reality

- `origin/HEAD` points at `origin/May_2026` — that's the integration branch. Branch from it, PR into
  it (see the Bag2 gate above). `main` is stale — ignore it.
- `.github/workflows/static.yml` deploys `Live_Page/` to GitHub Pages **only on push to `May_2026`**.
  Changes to `Live_Page/` on any other branch are not deployed, no matter how correct they are.
- `.github/workflows/version_bump.yml` runs on `main`/`beta*` pushes only, so it's currently dormant.

## Directory map

| Path | What it is | Status |
|---|---|---|
| `Bag1/` | Plushie module (Wand module's ancestor) + several other Bag1-era components | Fielded, not under active development — see [Bag1/AGENTS.md](Bag1/AGENTS.md) |
| `Bag2/` | Wand module + fielded stations/modules (coding station, slide station, Splat Companion module, narrator module, paper remote module, speaker/dial stations), plus CAD and battery-test data | Fielded, still actively developed — see [Bag2/AGENTS.md](Bag2/AGENTS.md) |
| `Bag3/` | Wand module only so far; new hardware in progress | Hardware in flux — see [Bag3/AGENTS.md](Bag3/AGENTS.md) |
| `Live_Page/` | Deployed static web apps (see below) | Current |
| `ChatApp/` | 3-file fragment on this branch, cannot run standalone | Broken here — working 22-file version on `origin/chatApp`, unmerged since 2026-06-16 |
| `WebAppDocs/` | Docs for a directory layout (`App_Web/webapp/…`) that no longer exists | Stale |
| `old_stuff/` | Prototypes and explorations from the Bag1 era that never became part of `Bag1/` (not classroom-ready when Bag1 shipped) | Historical — don't mine for patterns; will dominate a naive grep |

## Which of the six web apps is canonical

All under `Live_Page/`, linked from `Live_Page/index.html`:

| App | Role |
|---|---|
| `WebApp2/` | **Canonical** USB hub controller — Bag2/Bag3 Wand module games, teacher-facing |
| `Flasher/` | **Canonical** code uploader — uploads over the REPL as chunked base64, so it can send binary files; the other two upload paths write text only |
| `WebApp/` | Legacy — Bag1 Plushie module controller |
| `Code_Upload/` | Dead predecessor of Flasher, pinned to a stale branch |
| `If_Splats/` | Standalone Web-Bluetooth demo, unrelated to the USB-hub/ESP-NOW stack. Declares its JS↔Python interop via `pyscript.json`'s `js_modules` table, unlike WebApp2's `window.*` globals |
| `wand_icons.html` | Static LED-icon reference (not an app) |

`Live_Page/Flasher/manifests/*.yml` sources are **intentional, not mistakes**:
`wand.yml` → `Bag2/Code/lib` + `Bag2/Code/Wand Module`, `hub.yml` → `Live_Page/WebApp2/hubCode2`,
`m5paper.yml` → `Bag2/Code/M5Paper Remote`. There is currently no manifest for flashing Bag3 Wand
module hardware.

## Cross-cutting invariants — if you touch X, you must consider Y

| If you change… | Then also check/update… |
|---|---|
| A Wand module game or `lib/` module | The Wand module edit rule above — does it belong in Bag2, Bag3, or both? Ask if unclear. |
| The set of game tags | `Bag2/Code/lib/game_tags.py`, `Bag3/Code/lib/game_tags.py`, `Live_Page/WebApp2/hubCode2/game_tags.py`, `Live_Page/WebApp2/js/utils/commands.json`, `Live_Page/wand_icons.html`. Nothing enforces consistency across these four+ places. **Known drift:** `hubCode2/game_tags.py` currently has extra `jumpin1`–`jumpin5` entries and is missing `HIDDEN_TAGS = {"finddevice"}` compared to `Bag3/Code/lib/game_tags.py`. |
| `espnow_manager.py` | It is vendored byte-for-byte identical across `Bag2/Code/lib/`, `Bag2/Code/M5Paper Remote/`, `Bag2/Code/StickS3 Narrator/`, `Bag3/Code/lib/`, and `Live_Page/WebApp2/hubCode2/`. Same bundled-copy pattern for `game_tags.py`, `ssd1306.py`, and `ws1850s.py`. A fix in one needs manual copying to the others. |
| REPL-over-serial upload logic | Implemented three times: `Live_Page/Flasher/js/serial.js` (chunked base64, can send binary files), `Live_Page/WebApp2/mpy/repl_controller.py` + `firmware_manager.py` (triple-quoted text, text only), `Live_Page/Code_Upload/index.html` (inline, text only). A change to upload behavior has to be applied to whichever of the three the affected app actually uses. |
| A JS or Python file under `Live_Page/WebApp2/` | `pyscript.toml`'s `[files]` list — an unlisted module silently 404s in the browser's virtual filesystem. (`main.py` itself is loaded via `<script src>`, not `[files]` — don't add it there.) |

## Building a new component

The integration contract for a new device that talks to a Wand module is the **ESP-NOW message
vocabulary** implemented in `espnow_manager.py`: broadcast-first JSON payloads, no pairing, no
channel negotiation, MAC-slotted status-poll replies to avoid collisions. Copy that file (identical
across every tree) into the new device, and place the component's code inside the Bag whose Wand
module it targets — ask which Bag if it isn't already clear.

## Verification — and its honest limits

There is **no automated test suite, no linter, and no CI** beyond the Pages deploy and the dormant
version-bump workflow. `pyrightconfig.json` sets `typeCheckingMode: "off"` — it exists only to
silence editor noise about unresolved MicroPython imports, not to check anything.
`Bag2/Unit Tests/` and `Bag3/Code/utilities/UnitTest/` are manual, interactive, on-device REPL
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
"fix" them. Wand module games expose a uniform `play(nfc, leds, buz, accel, i2c, enow)` entry point.

**Web code:** vanilla ES modules, no build step, no npm, no bundler — don't introduce
React/Vite/webpack. Tailwind CSS and Lucide icons load from CDN. Components are factory functions
returning detached DOM nodes with `innerHTML` template literals and `.onclick =` handlers.
`Live_Page/WebApp2/js/state/store.js` is a single mutable object with rAF-batched re-render.
`Live_Page/WebApp2/js/utils/pyBridge.js` is the only JS→Python call surface.

## Documentation trust map (non-Bag docs)

Each Bag's `AGENTS.md` carries its own trust map for that Bag's documentation. This table covers
everything else.

| Path | Trust | Notes |
|---|---|---|
| `Live_Page/Flasher/README.md`, `Live_Page/WebApp2/README.md`, `Live_Page/WebApp2/hubCode2/README.md` | Trusted | |
| `WebAppDocs/**` | **Do not trust** | Documents a directory layout removed in an earlier reorganization. |
| `.cursor/plans/*.md` | Historical artifact | Completed local plans, not specs. |
| `old_stuff/**` | Ignore | Bag1-era work that never became part of `Bag1/`. |

## Protocol summary

Three layers; full detail in `Live_Page/AGENTS.md`.

1. **Web app ↔ USB hub** — line-delimited JSON over 115200-baud serial. App sends
   `{"cmd": "<tag>"}` / `{"cmd":"stop"}` / `{"cmd":"poll"}` / `{"cmd":"find","mac":"…"}`; USB hub
   sends `{"type":"ready"|"heartbeat"|"ack"|"poll_started"|"device_report"|"devices"|"error", …}`.
2. **USB hub → Wand modules** — ESP-NOW, JSON payloads, broadcast to `FF:FF:FF:FF:FF:FF`. No
   pairing, no channel negotiation. Status-poll replies are staggered by a slot derived from each
   Wand module's MAC to avoid collisions.
3. **(Bag1/WebApp only) Controller → Plushie modules** — a `{"topic": "/game", "value": <int>}`
   pub-sub scheme, unrelated to the ESP-NOW layer above.
