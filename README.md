# SmartPlayground

A playground system developed by the Tufts University Center for Engineering Education and
Outreach (CEEO) FET Lab: NFC-programmable wands, an ESP32 hub, and browser-based control apps that
communicate wirelessly, used with physical playground equipment.

This is a **research prototype**, not a finished product — a hardware-and-software design project
that is actively changing. Working on the code or pointing an AI agent at it? Start with
[AGENTS.md](AGENTS.md) instead of this file.

## The Bag model

Each generation of hardware+software that's been brought to a classroom-ready state is called a
**Bag**. **Bag1** and **Bag2** have gone out to classrooms; **Bag3** is the release currently being
developed. Being "in classrooms" doesn't mean frozen — Bag2 in particular still receives changes,
they just require real hardware testing before they reach devices already in children's hands. Bag3
similarly has active software work: new hardware needs software to test its capabilities before any
game work begins on it.

"Current" bag isn't a single fixed answer — there's **more Bag2 hardware in circulation** than Bag3,
since Bag3 boards are still being produced in smaller numbers.

Each Bag owns its own hardware details (dated, and Bag3's especially so, since it's actively
changing): see [Bag1/AGENTS.md](Bag1/AGENTS.md), [Bag2/AGENTS.md](Bag2/AGENTS.md), and
[Bag3/AGENTS.md](Bag3/AGENTS.md).

## What's in the system

The playground is built from several **components** that talk to each other wirelessly, not one
device. The project uses two words for them: a **module** is small and portable — carried or handled
by students; a **station** (also called an **extension**) is larger and more static, usually mounted
on playground equipment.

- **Wand module** — a handheld NFC-programmable device: RGB LED matrix, NFC reader, buzzer,
  vibration motor, accelerometer, button, and battery gauge. Kids tap NFC cards against it to build
  simple programs ("tap coding": trigger card → one or more action cards) or launch one of several
  built-in games (Color Quest, Freeze Dance, Melody Builder, and others). It's the **most numerous
  hardware in the system** — designed at roughly one per student — which is why its code dominates
  this repository. It was called the **Plushie module** in Bag1, for its soft plush housing; same
  component, direct descendant, different name.
- **USB hub** — an ESP32 bridging a browser (over USB Serial) to Wand modules (over ESP-NOW
  wireless); relays game commands to wands and reports each wand's battery level and signal strength
  back to the browser. It's a **teacher tool**, not something students use on the playground — that's
  why it's called a "hub" rather than a module or station.
- **Splat modules, button modules** — built on third-party hardware, similar but distinct from the
  Wand module.
- **Stations and other modules** (Bag2 and later) — a coding station (reads NFC color tags, starts a
  round), a slide station (an LED panel on a playground slide), a Splat Companion module (bridges to
  a third-party BLE splat toy), a narrator module (speaks the current game aloud), a paper remote
  module (e-ink teacher remote), and speaker/dial stations (music playback).

See each Bag's `AGENTS.md` for exactly which of these exist in that Bag.

## Try it — no hardware required

The live site is **<https://tuftsceeo.github.io/SmartPlayground/>**, deployed from the `May_2026`
branch. You can open it and look around, but sending commands or uploading firmware needs a USB-
connected device.

## Use it — with hardware

1. **Flash a device.** Open the [Flasher](https://tuftsceeo.github.io/SmartPlayground/Flasher/)
   page, pick a device type (Wand, Hub, or M5Paper Remote) and a source branch, connect over USB,
   and upload. The Wand option currently flashes Bag2 firmware — that's deliberate, since there's
   more Bag2 Wand-module hardware in circulation.
2. **Connect the USB hub and play.** Open [WebApp2](https://tuftsceeo.github.io/SmartPlayground/WebApp2/),
   connect to the hub over USB, and tap a game in the message box to broadcast it to nearby wands.
3. **Program NFC cards.** Card writing is a REPL tool, not a web app: run
   `Bag2/Utilities/writetoNFCcards.py` (or `Bag3/Code/utilities/writetoNFCcards.py` for Bag3
   hardware) from a device connected to your computer, and follow its prompts.

(There is no `config.py`, `games/` folder, or `Plushie_Module/` setup step in the current system —
if you've seen those mentioned elsewhere in this repo's history, they describe an earlier layout.)

## Repository map

| Path         | What it is                                                                                                                                                                                                             |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Bag2/`      | Wand module firmware, shared libraries, and its stations/modules (coding station, slide station, Splat Companion, narrator, paper remote, speaker/dial stations) — more of this hardware is in circulation than Bag3's |
| `Bag3/`      | Wand module firmware — the release being developed now; new hardware in progress                                                                                                                                       |
| `Bag1/`      | The original Plushie-module generation, given to classrooms — the Wand module's direct ancestor                                                                                                                        |
| `Live_Page/` | The deployed web apps: WebApp2 (USB hub controller), Flasher (uploader), and a few smaller/legacy tools                                                                                                                |
| `ChatApp/`   | An in-progress AI-assisted wand programming tool (work in progress on another branch)                                                                                                                                  |
| `old_stuff/` | Earlier prototypes and explorations that predate or sit alongside Bag1, never brought to classroom readiness                                                                                                           |

See [AGENTS.md](AGENTS.md) for a status/trust verdict on every entry above, plus the parts of this
map that are still evolving.

## Developing

No build step, no package manager, no automated test suite. Device code is MicroPython, edited and
uploaded with the [MicroPico](https://marketplace.visualstudio.com/items?itemName=paulober.pico-w-go)
VS Code extension (manual connect — it won't grab your serial port on startup). Web code is plain
ES modules with Tailwind CSS loaded from a CDN.

- **Deep technical reference for contributors and AI agents:** [AGENTS.md](AGENTS.md),
  [Bag1/AGENTS.md](Bag1/AGENTS.md), [Bag2/AGENTS.md](Bag2/AGENTS.md),
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
