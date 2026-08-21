# SmartPlayground

An interactive playground system developed by the Tufts University Center for Engineering
Education and Outreach (CEEO) FET Lab: NFC-programmable wands, an ESP32 hub, and browser-based
control apps, combined with physical playground equipment for engaging, wirelessly connected play.

This is a **research prototype**, not a finished product — a hardware-and-software design project
that is actively changing. Working on the code or pointing an AI agent at it? Start with
[AGENTS.md](AGENTS.md) instead of this file.

## The Bag model

Each generation of hardware+software that's been brought to a classroom-ready state is called a
**Bag** — a Bag bundles a wand with its compatible extensions (companion devices that interface
with that wand). **Bag1** and **Bag2** have gone out to classrooms; **Bag3** is the release
currently being developed. Being "in classrooms" doesn't mean frozen — Bag2 in particular still
receives changes, they just require real hardware testing before they reach devices already in
children's hands.

**Most wand hardware in circulation today is Bag2.** Bag3 hardware exists in smaller numbers while
a larger batch is produced.

**Hardware status (dated 2026-08-10):** the wand's next major hardware round settles on a **5×5 LED
matrix** and a **PN532 NFC reader** (matching Bag2); how programming cards are stored on the NFC
tag — today's plain-text format vs. a more compact opcode format — is still being explored and not
yet decided.

## What's in the system

- **Wand** — a handheld NFC-programmable device. Kids tap NFC cards against it to build simple
  programs ("tap coding": trigger card → one or more action cards) or launch built-in games
  (Color Quest, Freeze Dance, Melody Builder, and others).
- **Hub** — an ESP32 bridging a browser (over USB Serial) to wands (over ESP-NOW wireless).
- **Bag2 extensions** — companion hardware that pairs with Bag2 wands: a 4-reader Programming
  Station, an LED Slide Score Station, a Splat Companion (bridges to third-party BLE "Splat" toys),
  an e-ink Teacher Remote (M5Paper), and speaker modules.

## Try it — no hardware required

The live site is **<https://tuftsceeo.github.io/SmartPlayground/>**, deployed from the `May_2026`
branch. You can open it and look around, but sending commands or uploading firmware needs a USB-
connected device.

## Use it — with hardware

1. **Flash a device.** Open the [Flasher](https://tuftsceeo.github.io/SmartPlayground/Flasher/)
   page, pick a device type (Wand, Hub, or M5Paper Remote) and a source branch, connect over USB,
   and upload. The Wand option currently flashes Bag2 firmware — that's deliberate, since most
   wands in circulation are Bag2.
2. **Connect the hub and play.** Open [WebApp2](https://tuftsceeo.github.io/SmartPlayground/WebApp2/),
   connect to the hub over USB, and tap a game in the message box to broadcast it to nearby wands.
3. **Program NFC cards.** Card writing is a REPL tool, not a web app: run
   `Bag2/Utilities/writetoNFCcards.py` (or `Bag3/Code/utilities/writetoNFCcards.py` for Bag3
   hardware) from a device connected to your computer, and follow its prompts.

(There is no `config.py`, `games/` folder, or `Plushie_Module/` setup step in the current system —
if you've seen those mentioned elsewhere in this repo's history, they describe an earlier layout.)

## Repository map

| Path | What it is |
|---|---|
| `Bag2/` | Bag2 wand firmware, shared libraries, and its extensions (Stations, Splat Companion, M5Paper Remote, Speaker) — the most widely used hardware target today |
| `Bag3/` | Bag3 wand firmware — the upcoming release |
| `Bag1/` | The original plushie-based generation, given to classrooms |
| `Live_Page/` | The deployed web apps: WebApp2 (hub controller), Flasher (uploader), and a few smaller/legacy tools |
| `ChatApp/` | An in-progress AI-assisted wand programming tool (work in progress on another branch) |
| `old_stuff/` | Earlier prototypes and explorations that predate or sit alongside Bag1, never brought to classroom readiness |

See [AGENTS.md](AGENTS.md) for a status/trust verdict on every entry above, plus the parts of this
map that are still evolving.

## Developing

No build step, no package manager, no automated test suite. Device code is MicroPython, edited and
uploaded with the [MicroPico](https://marketplace.visualstudio.com/items?itemName=paulober.pico-w-go)
VS Code extension (manual connect — it won't grab your serial port on startup). Web code is plain
ES modules with Tailwind CSS loaded from a CDN.

- **Deep technical reference for contributors and AI agents:** [AGENTS.md](AGENTS.md),
  [Bag3/AGENTS.md](Bag3/AGENTS.md), [Live_Page/AGENTS.md](Live_Page/AGENTS.md).
- **Game-writing guide:** [Bag3/Code/Wand Module/GAME_AUTHORING_GUIDE.md](Bag3/Code/Wand%20Module/GAME_AUTHORING_GUIDE.md).
- **Known issues and cleanup backlog:** [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md).
- **Branches:** `May_2026` is the current integration and deploy branch (not `main`). Changes
  affecting devices already in classrooms (Bag2) go through a pull request with real hardware
  testing before merge — see `AGENTS.md` for the specifics.

## Project status

Active development. Check the [Issues](https://github.com/tuftsceeo/SmartPlayground/issues) tab for
known bugs and planned features.

## Contact

For questions or collaboration inquiries, please contact the Tufts CEEO team.

## Acknowledgments

Developed by the Future Education Technology (FET) Lab at Tufts University Center for Engineering
Education and Outreach. Funded in part by NSF Award #2301249.
