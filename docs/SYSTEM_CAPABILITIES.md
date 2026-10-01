# Smart Playground — System Capabilities Overview

**Audience:** internal non-technical audiences
**Covers:** Bag 1, Bag 2, and the in-progress Bag 3
**Reflects:** the code as written on 2026-10-01

Smart Playground is a research prototype from the Tufts University Center for Engineering Education
and Outreach (CEEO), FET Lab, funded in part by NSF Award #2301249. It adds small electronic
devices to ordinary playground play. Children program the devices by tapping cards, and teachers
start games from a laptop, a tablet-style remote, or an AI-assisted web app.

This is a prototype, not a commercial product. Everything below describes what the system can do
in its current form. Features marked *in testing* or *prototype* exist in code but are not ready
to promise to customers.

---

## Contents

1. [Key terms](#1-key-terms)
2. [The "Bag" model at a glance](#2-the-bag-model-at-a-glance)
3. [How the system works (all Bags)](#3-how-the-system-works-all-bags)
4. [Bag 1 — Early prototypes](#4-bag-1--early-prototypes)
5. [Bag 2 — In classrooms with partners](#5-bag-2--in-classrooms-with-partners)
6. [Bag 3 — New hardware, prototypes and beta](#6-bag-3--new-hardware-prototypes-and-beta)
7. [Side-by-side comparison](#7-side-by-side-comparison)
8. [Messaging guidance](#8-messaging-guidance)

---

## 1. Key terms

| Term | Plain-language meaning |
|---|---|
| **Bag** | One generation of hardware and software, sent out together as a kit. Bag 1 → Bag 2 → Bag 3. Bags are not compatible with each other. |
| **Module** | A small, portable device that children hold or carry (for example, the Wand). |
| **Station** | A larger device that stays in one place, often mounted on playground equipment (for example, a scoreboard on a slide). |
| **Wand** | The main handheld device. There is roughly one per child. In Bag 1 it was a soft plush toy called the **Plushie**. |
| **NFC card** | A small card or sticker with a chip inside, like a contactless transit card. When a child taps it on a Wand, the Wand reads a word stored on the card, such as "red", "cooking", or "start". |
| **Tap coding** | Building a simple program by tapping cards in order: "when I shake → turn red and play a cow sound". |
| **Hub** | A small device plugged into the teacher's computer by USB. It relays the teacher's commands to every Wand over the radio. |
| **ESP-NOW** | The radio the devices use to talk to each other. It needs no Wi-Fi network, router, or internet, and no pairing. |
| **Bluetooth (BLE)** | Used only to talk to the third-party "Splat" toys. |
| **Unruly Splat** | A commerically available light-up floor pad educational toy that children press or stomp. It plays sounds and lights up. Smart Playground controls it without modifying it. |
| **LED matrix** | A small grid of colored lights that shows simple pictures. The Wand's grid is 5 × 5. The Bag 3 Icon Display is 16 × 16. |
| **Accelerometer** | A motion sensor. It lets a device detect shaking, jumping, tilting, and flipping. |

---

## 2. The "Bag" model at a glance

| | **Bag 1** | **Bag 2** | **Bag 3** |
|---|---|---|---|
| **Status** | Early prototypes | In classrooms with partners | New hardware, still being developed |
| **In classrooms?** | Fielded but not in current use | Yes, this is the main fielded system | Small sets usability testing only |
| **Hardware changing?** | No | No | Yes, new boards are still on order |
| **Software changing?** | No, not under active development | Minor fixes and new games from developed by team and partners | Changing weekly |
| **Main child device** | Plushie (soft toy) | Wand | Wand (updated) |
| **How games are made** | Built in by the team | Built in, plus AI-assisted custom games | In Development. AI-assisted core. Planned compatible with Bag 2 games as well.|

---

## 3. How the system works (all Bags)

Current Bags follow the same basic pattern:

1. **Children hold small devices** (Plushies or Wands) with lights, sounds, vibration, a button,
   and a motion sensor.
2. **A teacher picks a game** using a controller, a remote, or a web page, and broadcasts it to
   every device at once.
3. **Devices talk to each other by radio.** No Wi-Fi network or internet connection is needed on
   the playground.
4. **Children play physically** by shaking, jumping, tapping cards, pressing buttons, and moving
   around. The devices respond with lights, sounds, and buzzes.
5. **Optional stations and add-ons** such as scoreboards, speakers, displays, and Splat pads make
   the game larger than a single handheld.

---

## 4. Bag 1 — Early prototypes

> **Status:** early prototypes. Not in use with classroom partners. Not under active development.
> Bag 1 does not work with Bag 2 or Bag 3 devices.

### 4.1 Devices

- **Plushie module.** A handheld device inside a soft plush toy. It has:
  - a ring of 12 color lights
  - a motion sensor
  - a button, a vibration motor, and a buzzer that plays simple musical notes
  - a rechargeable battery, and a sleep mode
  - an NFC card reader on some units
- **Box variant.** A rigid-case version of the Plushie with 25 lights.
- **Button module.** A standalone colored button.
- **Splats module.** Connects by Bluetooth to a store-bought Splat floor pad.
- **Teacher controllers.** Four hand-built versions with a small screen, buttons, and a knob. One
  version has a touchscreen. A web page could also act as the controller through a USB-connected
  board.

### 4.2 Games

1. **Notes / Bell Choir.** Each Plushie gets a note. Children press to play and perform together.
2. **Shake.** Shake hard to fill the light ring.
3. **Shake Rainbow.** Shake harder to climb through the rainbow colors.
4. **Hot/Cold.** Hide-and-seek. The lights show how close a child is to the hidden controller.
5. **Jump.** Count jumps on the lights.
6. **Clap.** A physical demonstration of radio range: devices close enough to the teacher buzz.
7. **Rainbow.** Shows the battery level, then a rainbow.
8. **Pattern.** Pressing colored button modules builds a shared color pattern across all Plushies.
9. **Color Press / Ice Cream Shop.** Press to pick a flavor, then flip the toy to "scoop". There
   is also a three-scoop version.
10. **Splat Notes.** Stepping on a Splat pad plays a note.
11. **Hibernate.** Turns every device off at once.

### 4.3 Why it matters

Bag 1 established the core ideas that later Bags kept and developed: a child-held device,
whole-class games started by the teacher, radio with no network, motion-based play, and Splat
integration.

---

## 5. Bag 2 — In classrooms with partners

> **Status:** this hardware is with partner classrooms now, and more of it is in circulation than
> Bag 3. The hardware is stable. The software still receives minor changes, and we and our partners
> are adding new games.

### 5.1 Devices

#### Wand module (one per child)

The Wand is a handheld device built on a small ESP32-C6 circuit board. It has:

- a **5 × 5 grid of color lights** for showing simple pictures and colors
- an **NFC card reader** for tap coding and for starting games
- a **buzzer** for notes, melodies, and animal sounds, plus a **vibration motor**
- a **motion sensor** that detects shake, jump, tilt, and flip
- **one button**
- a **rechargeable battery** that charges over USB-C, with a battery gauge
- a **light sensor** that dims or brightens the lights to suit the room

The Wand needs no screen or keyboard. Everything is done with cards, the button, and movement.

#### Stations and add-on modules

| Device | What it is | What children or teachers experience |
|---|---|---|
| **Coding Station** | A board with four NFC card slots, a light strip, and a button | Lay up to 4 color cards in the slots and press the button. The color sequence is sent to every Wand to start a Color Quest round. Special cards check every device's battery or stop all games. |
| **Slide Score Station** | A 40-light panel mounted on a playground slide | Shows the last four Color Quest finish times as a live bar graph, with a celebration animation for each new score. |
| **Speaker Station** | A small speaker box with songs on a memory card, no screen | Plays Freeze Dance music. Responds to play, pause, next, and volume commands sent by radio. |
| **Dial Station** | A round touchscreen with a turning knob, plus a speaker | Turn the knob to pick a song, tap to play or pause, and turn during play for volume. Plays and pauses along with Freeze Dance. |
| **Paper Remote** | A handheld e-ink touchscreen, similar to an e-reader | A teacher remote that needs no laptop. It has a grid of game buttons, a large STOP button, a battery check, a "Now Playing" banner, a screen for choosing which games appear, and a device status list showing each Wand's battery and signal strength. |
| **Narrator** *(prototype)* | A small device with a screen and speaker | An accessibility helper for children with low vision. It speaks the game name aloud with a recorded voice when a game starts or stops, shows it on screen, and calls out "Go / Freeze / Dance". |
| **Splat Companion** *(not currently active)* | A small board that connects to a store-bought Splat pad by Bluetooth | Built to let a Splat pad light up and play sounds programmed from a Wand. The Wand side of this link is not part of the current Bag 2 software. |

### 5.2 Tap coding

Children build programs by tapping NFC cards in order:

1. **A trigger card:** *button down*, *button up*, or *shake*.
2. **One or more action cards:**
   - **Colors:** red, green, blue, purple, yellow, white, off
   - **Musical notes:** C through high C, or a short melody
   - **Animal sounds:** cat, chicken, cow, dog, pig, duck, elephant, horse, goat
3. **Joining cards:** **AND** makes actions happen together, and **THEN** makes them happen one
   after another.
4. **A START card** runs the program, and a **STOP card** ends it.

The Wand confirms each card with a buzz and a chirp, and gives a different chirp when it rejects a
card.

### 5.3 Built-in games (14 games, plus 6 custom-game slots)

Children start a game by tapping its card, or a teacher starts it for the whole class at once.

| Game | What children do |
|---|---|
| **Color Quest** | A scavenger hunt. The Coding Station sends a color sequence, and children find and tap the matching color cards in order. Their time appears on the Slide Score Station. |
| **Freeze Dance** | One Wand is the "caller" and signals GO, FREEZE, or DANCE. A player caught moving during FREEZE sees a sad face and taps a card to rejoin. The Speaker or Dial plays music in sync. |
| **Cooking** | Tap ingredient cards (tomato, milk, cheese, flour, egg, butter, sugar), then hold the button to "cook" a recipe: egg, pancakes, pizza, pasta, or cupcake. |
| **Melody Builder** | Tap note cards to compose a tune, then press the button to hear it. |
| **Bell Choir** | Each Wand gets a random note. Children hold the button to ring it and play together. |
| **NFC Bell Choir** | The same, but each child taps a card to choose their own note. |
| **Shake Fill** | Shake harder to light more lights. The Wand remembers the best shake. |
| **Shake Rainbow** | Shake to climb through the rainbow colors. |
| **Jump Counter** | Each jump lights one more light. |
| **Rainbow Show** | Shows the battery level, then a rainbow. |
| **Simple Ice Cream** | Press to count scoops, then flip the Wand to reveal the flavor color. |
| **Multi Ice Cream** | Build a three-scoop cone by flipping the Wand after each scoop. |
| **Gestures** | Teach the Wand three motions, then perform one. The Wand guesses which motion it was and shows how confident it is. This is an introduction to machine learning. |
| **Jump In** | A simple starter game: press the button to blink green. |
| **Custom slots (Jump In 1–5)** | Five open slots for games written with the AI-assisted Wand Programmer (see 5.5). |

A printable **Game Icon Guide** for teachers explains what each light picture means in the games.

### 5.4 Teacher tools

- **WebApp2.** A teacher web page that runs in Chrome or Edge and connects to the USB Hub. It
  offers:
  - a chat-style list of games: tap one to start it on every Wand, or tap Stop
  - a description card for each game
  - **Device Status:** every Wand reports its battery level and signal strength
  - **Find my Wand:** click a Wand in the list to make it flash and beep
  - a setting to show or hide beta games
  - installation as an app on a computer
- **Paper Remote.** The same core controls on a handheld e-ink screen, with no laptop (see 5.1).
- **Flasher.** A web page for loading software onto a Wand, Hub, or Paper Remote over USB.
- **Card-writing tool.** A developer tool for programming blank NFC cards with game or action words.

### 5.5 AI-assisted game creation (Wand Programmer, in testing)

- A teacher describes a game in plain English, for example "show a heart when I shake".
- Claude, Anthropic's AI model, writes the Wand code. It works from a reference guide that
  describes what the Wand can do.
- The teacher can review the code, keep earlier versions, and upload the game over USB into one of
  the Wand's five custom slots.
- The tool also produces the list of NFC cards the game needs, and can write them.
- This is how partners and our team add new Bag 2 games without writing code by hand.

### 5.6 Wand Simulator

A browser page that shows an on-screen Wand. It runs real game code with a live light grid, sound,
a button, and tilt controls, so a game can be tried without any hardware. It supports 13 of the
built-in games; Color Quest is not included.

---

## 6. Bag 3 — New hardware, prototypes and beta

> **Status:** new hardware that is still changing, with new boards on order. The software changes
> weekly. All Bag 3 devices are prototypes. Small beta batches go to classrooms for usability
> testing only. **Treat every detail in this section as subject to change.**

### 6.1 The big idea

Bag 3 changes how games get onto the playground. A teacher **describes a game in plain language**.
The AI writes code for **several kinds of devices at once**: Wands, a large picture display, and
Splat pads. A teacher-side "Broadcast" device then writes the cards and hands the game to the
children's devices **wirelessly**. A child taps a "get code" card, the Wand downloads the new game,
and play begins.

### 6.2 Devices

| Device | What it is | Role | Status |
|---|---|---|---|
| **Wand** | Updated handheld. The current design has a 5 × 5 light grid, card reader, motion sensor, buzzer, vibration, button, battery gauge, and auto-dimming light sensor | Plays games. Can **download new games wirelessly** after a card tap | Prototype; hardware design still changing |
| **Broadcast Box** | A small handheld with a screen and two buttons (M5Stack StickS3), plus an NFC card writer | The teacher's "transmitter". It receives games from the web app, writes the NFC cards each game needs, and shares the game wirelessly with up to 4 Wands at a time | Prototype |
| **Broadcast Dial** | A round touchscreen with a turning knob (M5 Dial) | Does the same job as the Box with a different set of controls. The same web app drives both | Prototype; hardware checks still open |
| **Icon Display** | A 16 × 16 grid of color lights (256 pixels), large enough to see across a room | Shows pictures (icons) as part of a game, for example the winning team's icon or a team scoreboard. Downloads its game and icons from the Box or Dial | Prototype |
| **Icon Display Station** | The same display, paired with an **Icon Maker** web app | Turns any photo into a 16 × 16 icon and previews it live. Comes with a library of about 63 icons: animals, food, weather, jobs, vehicles, and faces | Prototype |
| **Splat Companion** | A two-board station that connects to 1–4 store-bought Splat pads by Bluetooth and to the rest of the playground by radio | Runs Splat games. Pads light up and play animal sounds, and presses are shared with the Wands | First hardware tests 2026-09-29 to 2026-09-30 |
| **Radar Station** | A small radar sensor | Senses where children are, how fast they move, which direction, and how many there are. Results appear in a browser viewer | Internal exploratory demo only |

### 6.3 ChatBroadcast: the AI game designer

ChatBroadcast is a browser web app (Chrome or Edge) and the center of the Bag 3 teacher experience.

**Teacher workflow:**

1. **Start.** Browse example games, open a saved game, or start from scratch.
2. **Describe the game.** Chat with the AI in plain language, for example "Flash the lights blue
   five times when the button is pressed".
3. **Preview.** A live on-screen Wand shows how the game will behave, and the Icon Display has its
   own picture preview.
4. **Refine.** Ask for changes. The app keeps earlier versions, with undo, rename, and save. Code
   stays hidden unless the teacher opens it, and the app offers Simple and Advanced modes.
5. **Check the hardware.** A plain-language checklist lists what the game needs, for example "at
   least 1 Wand" and "8 NFC cards".
6. **Send.** Connect the Broadcast Box or Dial by USB and send the game to it. The app refuses to
   send a game that names an icon or Splat action the devices don't have.
7. **Write cards and share.** On the Box or Dial, write the NFC cards, then switch to Share mode.
8. **Play.** Children tap a "get code" card. Their Wand downloads the game, restarts, and the game
   begins.

**Other features:**

- A built-in **Icon Maker** for drawing or importing 16 × 16 icons into a game
- An **example gallery** of 7 starter games: Melody, Freeze Dance, Rainbow, Shake Rainbow, Jump,
  Cooking, and Jump In
- **Box management:** list the games on the Box, check its battery and health, remove games, and
  install Box software
- Games are saved in the teacher's own browser

### 6.4 Games

**Wand games.** Bag 3 carries over the Bag 2 game set (Color Quest, Freeze Dance, Cooking, Melody,
Bell Choir, Shake, Jump, Ice Cream, Gestures, and the others) and adds:

- **Team Goal Race.** Children join the green or blue team and race to tap the goal card. The Icon
  Display shows the winning team's icon.
- **Splat Echo.** A two-player Simon game: the Splat pads play a pattern, the player repeats it,
  then adds a step using their Wand. Players take turns.

**Icon Display games:**

- **Goal Race (display half).** Shows a tree or whale icon for the winning team.
- **Team Scoreboard.** A running goal tally visible across the room.

**Splat games:**

- **Jump In.** Each pad gets a color and an animal sound, and presses echo between pads and Wands.
- **Splat Whack.** A color prompt appears and the first press scores.
- **Splat Echo.** See above.

**AI-generated games.** Any game a teacher creates in ChatBroadcast can use Wands, the Icon
Display, and Splats together.

### 6.5 Being explored (not features yet)

- Sending games over the playground radio instead of Wi-Fi
- Copying a game from one Wand to another by touching them together
- Radar-based games that respond to where children are on the playground

### 6.6 Current limitations

Bag 3 is a prototype, so these items are expected at this stage:

- **Wireless game download** sometimes fails, especially with several Broadcast devices in one room.
- **Very large AI-generated games** can be too big to load on a Wand, and the app does not yet warn
  about this.
- **Splat Companion:** tested with 1 and 2 pads only. Downloading Splat games wirelessly and using
  3–4 pads have not been tested on hardware yet.
- **Splat Echo:** a fix for Wands freezing mid-game was written but has not run on hardware yet.
- **Icon Display:** only the Goal Race game has been proven end to end. It does not yet respond to
  a "stop" command, and its own card reader has not been tested on hardware.
- **Broadcast Box:** writing an NFC card replaces what was on it without asking first.
- **Broadcast Dial:** several hardware checks are still open.

---

## 7. Side-by-side comparison

| Capability | Bag 1 | Bag 2 | Bag 3 |
|---|---|---|---|
| Child handheld device | Plushie (12 lights) | Wand (5 × 5 light grid) | Wand (5 × 5 light grid; design changing) |
| Motion play (shake, jump, flip) | ✓ | ✓ | ✓ |
| Sounds and vibration | ✓ | ✓ | ✓ |
| NFC card tap coding | Some units | ✓ | ✓ |
| Built-in games | ~11 | 14 + 5 custom slots | Bag 2 set + new multi-device games |
| Teacher starts games for whole class | Hand-built controllers | Web app, Paper Remote | Broadcast Box or Dial |
| Device battery and status check | Battery reports | ✓ (battery and signal) | ✓ |
| AI-assisted game creation | — | Wand Programmer (in testing) | ChatBroadcast (core workflow) |
| Games for several device types at once | — | — | ✓ |
| Wireless game download to Wands | — | — (USB only) | ✓ (prototype) |
| Large picture display | — | — | Icon Display (16 × 16) |
| Splat pad integration | ✓ | Not currently active | ✓ (in testing) |
| Scoreboard on equipment | — | Slide Score Station | Icon Display scoreboard |
| Music stations | — | Speaker, Dial | — |
| Accessibility (spoken game names) | — | Narrator (prototype) | — |
| Browser simulator, no hardware needed | — | ✓ | ✓ (built into ChatBroadcast) |
| Works without internet on the playground | ✓ | ✓ | ✓ |

---

## 8. Messaging guidance

**Safe to say:**

- Children program devices by **tapping cards**, with no screens or keyboards.
- Games are **physical and active**: shaking, jumping, dancing, racing, and stomping.
- A teacher can **start a game on every device at once** and check every device's battery.
- Devices talk to each other **without Wi-Fi or internet**.
- Bag 2 is **in classrooms with partner schools**, and new games are being added by our team and
  by partners.
- Teachers can **describe a game in plain English** and AI helps create it. This is in testing for
  Bag 2 and is the core design of Bag 3.

**Avoid or qualify:**

- Do not describe Bag 3 features as available or finished. Use "prototype", "in development", or
  "in beta testing".
- Do not cite Bag 1 as current classroom use.
- Do not claim Splat integration for Bag 2. It is not currently active.
- Do not promise wireless updates for Bag 2. They exist only as early research.
- The Narrator, Radar Station, and wand-to-wand sharing are prototypes or explorations. Describe
  them as research directions.
- Bags are **not compatible** with each other. Do not imply that Bag 2 and Bag 3 devices can be
  mixed.

---

*For technical detail, see the README and AGENTS.md files in each Bag folder.*
