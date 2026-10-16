# Code-free pairing: concept and brainstorm

Status: **concept, pre-implementation.** Covers usability, interaction design and task analysis
only. Nothing here is built. The hardware facts come from the Bag3 trees as of this date. Each
one is marked where it constrains a design.

A child links an input to an output without writing code. They do it with a wand alone, then a
wand with a Splat, Icon Display or another wand. A **Pairing Station** then shows more of the
relationship and lets them change it (progressive disclosure). These are "pregame"
explorations: the child is in charge of the customization, not a game author.

Related: [2026-10-07-splat-pairing/SPEC.md](../2026-10-07-splat-pairing/SPEC.md) (wand↔Splat BLE
pairing by Splat card), `tools/devtests/nfc_dep/` (PN532 wand-to-wand NFC-DEP), `ProgrammableTag/`
(NT3H2111 tag the device rewrites itself).

---

## 1. Precedents and what each contributes

| Precedent | Input → output model | Child's controls | Pattern to keep |
|---|---|---|---|
| **LEGO Spike Prime "heart program"** | Ports placed opposite each other are paired. Default is proportional. | Hub buttons change the gain and sign. On-screen buttons drive a lone output. | **Position is the pairing.** No menu; the physical arrangement declares the link. A lone output has a manual control. |
| **Smart Motor** | Nearest-neighbor over recorded (input, output) pairs. | Dial picks the accelerometer axis or an external sensor. A button records a pair. | **Teach by example.** The child sets the output, holds the input, presses record. Changing the input source is a separate, single control. |
| **Smart LED ring prototype** | Same trainer, three output dimensions: color, count, brightness. | Same as Smart Motor. | **One output device can have several output dimensions.** Choosing which one is a small decision of its own. |
| **Flutter** | Proportional by default. The app sets endpoints and a relationship type: cumulative (averaging window), change (derivative), threshold (if/else), and others. | App with endpoints and a relationship picker. | **A small, named catalog of relationships.** Endpoints are the main proportional setting. |

What all four share:

- **It works at power-on.** Something meaningful happens before the child changes anything.
- **There are few kinds of setting:** which input, which output, what relationship (shape), how
  much (gain or endpoints) and which way (sign).
- **Changing one thing is one action.** Nobody navigates a menu tree to flip a direction.

---

## 2. Resources

### Wand (Bag3 / MockWand)

| Kind | Part | Notes for this concept |
|---|---|---|
| Input | One push button (GPIO0) | Press, hold, double-press and press count are all available from one button. |
| Input | LIS2DW12 accelerometer | Tilt (3 axes), shake energy, free fall. The chip has hardware single/double tap and 6D orientation detection; `lib/lis2dw12.py` does not expose them yet. |
| Input | OPT3002 ambient light | Currently used only for LED auto-brightness. A child can use it as a **"shadow" input**: cover it with a hand, point it at the sky. |
| Input | NFC reader | Cards, Splat cards, and NFC-DEP to another wand (bench only). |
| Output | 5×5 RGB matrix | Hue, brightness, fill count (0–25 = a bar), simple shapes. |
| Output | Buzzer | Pitch, beep rate, short melodies. |
| Link | ESP-NOW, plus BLE when paired with Splats | BLE comes up only for a paired wand (SPEC §4). |

### Partner devices

| Device | Inputs | Outputs | How the wand reaches it today |
|---|---|---|---|
| **Splat** (stock toy) | Button press/release | Color (named set in `splat_api.COLOR_RGB`), note, animal sound | BLE from a paired wand, or the Splat Companion |
| **Icon Display** | None today | 16×16 icon, color, animation | Station firmware; radio path to wands not defined yet |
| **Another wand** | Everything in the wand table above | Everything in the wand table above | ESP-NOW; NFC-DEP when touching |
| **Radar Station** (LD2450) | Person position/distance | None to speak of | ESP-NOW events |
| **NFC Station** (M5 Dial) | Dial, touch, button, card reader | Round color screen, card writer | USB serial only; no radio |

**Constraint:** Splat color is a named palette, not continuous RGB, in the current API.
A proportional input → Splat color mapping is therefore **stepped** (7 colors) unless the BLE
layer can write arbitrary RGB. This needs checking before relying on smooth fades.

---

## 3. Design principles

1. **Something happens by default.** Every pairing has a sensible behavior with zero setup.
2. **Screenless and non-reader.** Meaning comes from color, light count, sound, the position of
   things and the pictures on cards. Nothing requires reading.
3. **One button, shallow state.** At most one level of "mode" on a wand alone. The child can
   always get back to the default in one known action (**long hold = reset to default**).
4. **The physical act is the instruction.** Touching, placing, holding up and showing do the
   work menus would do.
5. **Show the relationship while it runs.** The input's current value is visible or audible so
   the child can see cause and effect.
6. **The child owns it.** Settings belong to the child's wand for the session (power-off clears
   them, matching SPEC §2), and can be **saved to a card** they keep.
7. **Progressive disclosure.** Wand alone: default plus one or two controls. Paired: plus
   direction and teach. Pairing Station: the whole relationship catalog, endpoints, and saving.

---

## 4. A wand-only control grammar

This vocabulary is shared by every scenario so a child learns it once.

| Action | Meaning | Feedback |
|---|---|---|
| **Press** | Do the "next" thing: next input source, or next output value while teaching. | One click. The matrix shows the new choice for ~1 s. |
| **Double-press** | **Flip** the direction (invert the sign). | Rising or falling two-tone. An arrow on the matrix points up or down. |
| **Hold (~1 s) while posed** | **Record** this input → current output pair (teach). | A fill animation during the hold; a chime on capture. |
| **Long hold (~3 s)** | **Reset** to the default relationship. | Rainbow wipe; "start" sound. |
| **Hardware tap on the wand body** (optional) | A second "button" if one is not enough. Candidate meaning: freeze/unfreeze the output. | Matrix blinks. |
| **Tap a card** | Change something by picture: a relationship card, an input card, an output card, a Splat card to pair. | Card picture on the matrix. |

**Recommendation:** start with press, double-press and the two holds only. Add body taps only if
testing shows the button grammar runs out. Body taps compete with shaking as an input, so they
can fire by accident.

**Input source icons on the 5×5:** tilt = a dot that slides, shake = scattered pixels,
light = a sun, button = a filled square. The icon is shown for about 1 s after each change, then
the live output returns.

---

## 5. Five scenarios

Each scenario lists the setup, the default, how the child changes it with existing interfaces,
what it exercises, and open questions.

### Scenario 1. "Feel it": wand alone

**Setup.** Wand on, nothing else. A "feel" card (or idle after boot) starts the mode.

**Default.** Tilt → hue on the whole matrix (proportional, Flutter-style), with brightness
following shake energy. Tipping the wand forward sweeps red → violet. Holding it still keeps
the color.

**Child controls.**
- **Press** cycles the input source: tilt → light (shadow) → shake → back to tilt.
- **Double-press** flips the direction: tilting forward now goes violet → red; covering the light
  sensor now makes it brighter instead of darker.
- **Long hold** resets.
- Optional output cycle (an output card or a body tap): hue → fill count (a 0–25 light "level
  meter") → buzzer pitch. Smart LED ring precedent: one device, several output dimensions.

**Exercises.** Input/output, proportionality, sign. The level-meter output makes "more input,
more output" countable.

**Open questions.** Is three inputs × three outputs too many for a wand alone? A first test
could fix the output at hue and only cycle inputs.

### Scenario 2. "Magic remote": wand → Splat (Spike heart)

**Setup.** The child taps a Splat card (existing SPEC pairing flow). The wand and Splat share an
identity color.

**Default.** Both directions work right away, like an input and an output placed opposite each
other on a Spike hub:
- **Wand tilt → Splat color**, stepped across the Splat color set.
- **Splat press → wand sound and flash**, so the Splat works as a remote button for the wand.

**Child controls.**
- **Double-press** on the wand flips the tilt direction.
- **Press** cycles the wand input (tilt, light, shake), as in Scenario 1, with the Splat as the
  output.
- **Pressing the Splat** while the wand is in "hold" (frozen) mode steps the Splat to the next
  color manually. This is the Spike "lone output has buttons" pattern.
- **Two Splats paired:** the default could split one input across both (tilt left lights Splat
  A, tilt right lights Splat B). That is a two-endpoint threshold children can see.

**Exercises.** Remote cause and effect, mapping one input to a device across the room, and
direction.

**Open questions.** BLE write rate and latency for live tilt → color (needs a bench number). Does
the Splat → wand direction confuse things when the child is focused on wand → Splat? It could be
off until a second card turns it on.

### Scenario 3. "Teach the Splat": Smart Motor training

**Setup.** A paired wand and Splat, plus a "teach" card, or a hold on the wand at the start of
Scenario 2.

**Default after "teach".** The relationship is empty. The Splat shows white, and the wand shows
an empty 5×5 with one pixel per recorded example (max 5–8).

**Child controls (the Smart Motor loop on existing hardware):**
1. **Press the Splat** to choose an output color. Each press steps the color.
2. **Hold the wand in a pose** (tipped left, upside down, in shadow).
3. **Hold the wand button** to record the pair. The wand shows a new pixel in that color; the
   Splat flashes.
4. Repeat for 2–5 poses. Then press the wand button once to **play**: moving the wand drives the
   Splat to the nearest recorded color.
5. **Long hold** clears the examples.

**Exercises.** Classification by example and the idea that the device "learned" from
demonstration. It is a first contact with ML ideas, with no numbers anywhere.

**Variation.** The output is a Splat **sound** (animal or note) instead of a color: "tip the wand
toward the cow and it moos." Sound is easier for some children to tell apart than 7 colors.

**Open questions.** Which input features does the nearest-neighbor use? Raw 3-axis tilt is the
Smart Motor default and the simplest. Shake and light can be features later. Do children need to
see *which* example is closest while it runs? The matching pixel on the wand could pulse.

### Scenario 4. "Buddy link": wand ↔ wand by touching

**Setup.** Two children touch wand heads together. NFC-DEP (bench-proven) or a short ESP-NOW
handshake triggered by the touch links them. Each wand shows the other's identity color in a
corner.

**Default.** **My input drives your output.** Tilting my wand changes your colors, and yours
changes mine. It is symmetric, so both children feel in control immediately. Only cross-links
are made by default; my own wand keeps showing my own output.

**Child controls.**
- **Double-press** flips how *my input* affects *your wand*. Each child owns their own side of
  the link.
- **Press** changes *my* input source, as in Scenario 1.
- **Touch again** unlinks. Touching a third wand adds it to a chain (A → B → C), which is a
  "telephone" game with no rules beyond the default.
- **A relationship card** (Section 6) tapped on one wand changes how that wand transforms
  incoming values. One child can make the partner's tilt "echo" with a delay, or work only past a
  threshold.

**Exercises.** Shared control, networks and chains. It also makes "who controls what" a social
negotiation, which is the point in a playground.

**Open questions.** ESP-NOW broadcast vs. unicast after the NFC handshake. Range and fade-out:
should the link drop when the partners walk apart? NFC-DEP needs both PN532s in DEP modes. Check
that this is reachable from the idle loop without breaking card reads.

### Scenario 5. "Puppet show": wand → Icon Display (threshold and change)

**Setup.** A wand linked to an Icon Display. The method is open (Section 7); the simplest is
tapping an NFC tag on the display's frame.

**Default.** **Tilt picks the picture.** The tilt range is split into as many bins as the display
has icons in its current set (e.g. 3–5): tip left for the cat, center for the dog, right for the
duck. This is a stepped/threshold relationship the child can see without numbers. A shake
triggers the icon's animation if it has one.

**Child controls.**
- **Press** steps the display to the next icon *set* (animals, faces, weather). The icon set
  names come from the existing icon library.
- **Double-press** reverses the order.
- **Hold while posed** records a pose for the icon currently shown. This is teach, as in
  Scenario 3, and replaces the even bins with the child's own poses.
- **A "change" card:** the display shows a picture only when the wand *moves* (derivative). It
  returns to a "sleeping" icon when still, which makes stillness a game.
- **A "count" card:** each shake advances one icon (cumulative). The display becomes a flipbook
  or story driven by the child's rhythm.

**Exercises.** Thresholds, sequence and storytelling. The display gives the child a large,
readable output that a 5×5 matrix cannot.

**Open questions.** The Icon Display has no radio protocol to wands yet. Latency for live
switching. What the display shows when nothing is linked.

### Compositions to test after the five

- **Splat → Icon Display:** each Splat press advances the picture (cumulative). It needs no wand
  input, only the wand as the "connector" that set it up.
- **Radar → wand:** a "warmer/colder" game: distance to the radar station → wand beep rate.
- **Chain:** wand tilt → Splat color → (Splat press) → Icon Display. This tests whether children
  can build a two-step causal chain.

---

## 6. Relationship catalog

The catalog behind the cards and the Pairing Station. Each needs a **picture** (card art and a
5×5 glyph) and a **sound**, never a word.

| Kid name (working) | Behavior | Parameters | Precedent | 5×5 glyph idea |
|---|---|---|---|---|
| **Follow** | Proportional; output tracks input linearly between endpoints. | low end, high end, sign | Spike, Flutter default | Diagonal line |
| **Opposite** | Follow with the sign flipped. Also reachable by double-press. | — | Spike sign | Diagonal the other way |
| **Switch** | Threshold: output A below a level, output B above. | threshold, A, B | Flutter threshold | Step shape |
| **Steps** | Quantized: input range split into N bins. | N, outputs per bin | Smart Motor (discrete) | Staircase |
| **Wiggle** | Change/derivative: output responds to movement, rests when still. | sensitivity | Flutter change | Zigzag |
| **Count** | Cumulative: each event adds one; wraps or resets. | step size, wrap | Flutter cumulative (sum form) | Stacking dots |
| **Smooth** | Averaging window; output follows slowly. | window length | Flutter cumulative (average form) | Gentle curve |
| **Echo** | Delay: output repeats input after a pause. | delay | — | Two offset dots |
| **Toggle** | Each event flips the output on/off. | — | — | Half-filled square |
| **Taught** | Nearest neighbor over recorded examples. | the examples | Smart Motor | Scattered colored dots |
| **Surprise** | Random output on each event. | — | — | Sparkle |

**Recommendation:** ship the first test with **Follow, Opposite, Switch and Taught**. Add
**Wiggle** and **Count** once children have the first four. **Smooth** and **Echo** are hard to
tell apart from "it's broken" without the Pairing Station's live display, so hold them for the
station.

### Relationship cards (existing interface)

Cards are the code-free control that already exists. Each card is a picture card the wand reads
in its idle loop. Tapping one changes the relationship on the currently active link. This adds
no hardware, but it does add tags. Per `AGENTS.md`, game tags are consumed in four places with
nothing enforcing consistency; a new card family adds entries to all four.

---

## 7. The Pairing Station

### Role

The station is where the child **sees and changes the relationship** that the wand already runs.
The wand stays the place where the relationship lives and executes. The station is an editor and
a window, not a host. Lifting a wand off the station keeps the edited behavior.

### How devices are recognized

| Method | Wand | Splat | Icon Display | Notes |
|---|---|---|---|---|
| **Read the device's tag** | NFC-DEP or PN532 card emulation | The existing Splat card | A tag on its frame | The station only needs a reader. A static tag gives identity but not live state. |
| **Station tag emulation** (`ProgrammableTag`-style NT3H) | Wand reads the station like a card | — | — | Fits the wand's existing "tap a card" habit. The station rewrites its tag to say "you are on the input pad". |
| **ID by tag, then a radio session** | ESP-NOW after the tap | BLE via the wand | ESP-NOW | Live values flow over the radio; the tap only establishes identity and pad position. |

**Recommendation:** identity by NFC (it is already the playground's "touch to connect" gesture)
and live data over ESP-NOW. Each device type answers with a small **capability manifest**:
inputs, outputs, output dimensions and their ranges. The station builds its options from the
manifests, so the choices change depending on what is placed.

### Directions

1. **The two-pad plate (Spike heart, physical).** Two marked pads: left is "makes it happen"
   (input), right is "what happens" (output). Placing a wand on the left and a Splat on the
   right pairs wand input → Splat output. Swapping them reverses the direction. The pads carry a
   picture (hand vs. lightning bolt), not words. This is the most tangible option, and position
   alone carries the meaning.
2. **Dial editor (NFC Station hardware).** An M5 Dial-style knob and round screen between the
   pads. Turning the dial picks the relationship from the catalog's pictures. Pressing selects.
   A second "page" sets the endpoints. The firmware pattern (icon rings, dial input with
   hold/tap guard) already exists in `Stations/NFC Station/`.
3. **Live graph ring.** An LED ring or strip around the dial shows the input's current value as a
   moving dot and the output as a second dot. The relationship's shape is drawn as the path
   between them. It makes Smooth and Echo legible.
4. **Demonstrate endpoints.** No numbers: "move your wand to the low end, press; to the high end,
   press." The station captures the input range the child actually uses, then shows the output at
   each end. This is Flutter's endpoints, set by showing instead of by slider.
5. **Save to a card.** The station writes the relationship to a blank card with the existing card
   writer. The child takes it home or to another wand. Tapping the card restores the
   relationship. This makes customization a physical, tradeable object.
6. **Three-slot station (stretch).** Input pad, relationship slot, output pad. The child drops a
   relationship card in the middle slot, like a tile in a sentence: *wand → Switch → Splat*.
   It is fully screenless and readable left to right.

### Affordances

- **Pad shapes and pictures** that say input vs. output without words.
- **A device-shaped outline** on each pad (wand cradle, Splat ring) so placement is obvious.
- **A dial** for "choose" and a **press** for "set", the same grammar as the wand button.
- **A big "undo/reset" area**, e.g. a lift-and-replace or a dedicated back button.
- **Card slot or reader zone** for relationship cards and saving.

### What the station must display

| Information | Why the child needs it | Non-reader form |
|---|---|---|
| Which devices are placed and in which role | Confirms the pairing | Device picture in each pad zone, in the device's identity color |
| What the input can be (from the manifest) | Choose the input source | Icon ring (tilt, shake, light, button, Splat press) |
| What the output can be | Choose the output dimension (color, sound, count, picture) | Icon ring |
| Current relationship | Know what will happen | Catalog glyph, large |
| **Live input value** | See cause | Moving dot / bar |
| **Live output value** | See effect | The output itself (Splat lights), mirrored on screen |
| Endpoints / threshold position | Adjust "how much" | Markers on the live bar |
| Direction | Adjust "which way" | Arrow |
| Recorded examples (Taught) | Know what the device learned | Colored dots at their recorded positions; nearest one pulses |
| Saved / not saved | Trust that it will last | Card icon, filled when written |

### Progressive disclosure levels

| Level | Where | What the child controls |
|---|---|---|
| 0 | Wand alone, at power-on | Nothing; the default plays |
| 1 | Wand alone | Input source (press), direction (double-press), reset (long hold) |
| 2 | Wand + partner device | The same, plus teach (hold while posed) |
| 3 | Wand + relationship cards | Choose from the first relationship set |
| 4 | Pairing Station | Full catalog, endpoints by demonstration, live view, output dimension |
| 5 | Pairing Station + card writer | Save, carry and share relationships; chains |

---

## 8. Task analysis (core tasks)

### T1. "Make the Splat change color when I tip my wand" (Levels 0–2)

1. **Pair:** tap the Splat card with the wand. *Feedback:* shared identity color, rising tone.
2. **Observe the default:** tip the wand. *Feedback:* the Splat steps through colors.
3. **Adjust direction (optional):** double-press. *Feedback:* two-tone; the order reverses.

Risks: the child expects the Splat to follow *their* color choice, not a sweep, which leads to
Scenario 3. They tip around an axis the default does not use. **Mitigation:** the default uses
the axis with the most range for a natural wrist motion; test which one that is.

### T2. "Teach the Splat my three poses" (Level 2)

1. Start teaching (card or long hold, depending on the decision in Section 9).
2. For each pose: press the Splat to pick a color → hold the pose → hold the wand button →
   *chime, pixel added*.
3. Press once to play. Move between poses. *Feedback:* the Splat changes to the matching color.
4. Clear with a long hold if unhappy.

Risks: step 2 needs two hands on two devices while holding a pose. Test with Splat-on-floor
plus wand-in-hand. The child forgets which state they are in; **mitigation:** the teach state has
a distinctive matrix look (empty grid with example pixels) and a quiet tick.

### T3. "Make my friend's wand only light up when I tip a lot" (Level 3)

1. Touch wands (link). 2. Tap the **Switch** card on *my* wand. 3. Tip a little: nothing
happens. Tip a lot: the friend's wand lights.

Risks: the threshold position is invisible on a wand alone. This is where the Pairing Station's
live bar earns its place.

### T4. "Change the relationship at the Pairing Station and keep it" (Levels 4–5)

1. Place the wand on the input pad, the Splat on the output pad. *Feedback:* both pictures
   appear; the live link starts.
2. Turn the dial to a relationship glyph; press.
3. Demonstrate the endpoints: move to low, press; move to high, press.
4. Watch the live view; adjust.
5. Put a blank card on the reader zone; press save.
6. Lift the wand. The behavior persists. Tapping the card on any wand restores it later.

---

## 9. Open questions and technical risks

### Interaction

- **Starting a mode:** does each scenario need a card to start it (clear, uses existing
  practice), or does the wand infer it from what it is paired with (less to carry, more
  magic)?
- **Teach entry:** a card or a gesture? A long hold is already "reset" in this grammar.
- **Who sees state:** with two children on one link, whose wand shows the relationship?
- **Visible "off":** how a child tells "nothing is linked" from "linked, input at zero".

### Technical

- **Splat color resolution:** named palette only in `splat_api`. Check whether arbitrary RGB is
  writable over BLE before designing smooth fades.
- **BLE update rate:** live proportional control needs a bench measurement of write rate and
  latency with ESP-NOW active (see `2026-10-07-coex-benchc6/`).
- **Radio memory order (`AGENTS.md`):** any relationship engine and new card parsing loads after
  the radio. Relationship code must not land at `main.py` module scope ahead of `enow.init()`.
- **Accelerometer features:** hardware tap and 6D detection need adding to `lib/lis2dw12.py` if
  body taps or orientation bins are used.
- **NFC-DEP from the idle loop:** proven on a bench, not integrated with card reading.
- **Icon Display radio path:** no wand-facing protocol yet.
- **Tag sprawl:** relationship cards add to four unsynchronized tag lists.
- **Where relationship state lives:** proposed on the wand, session-scoped like `/pairing.json`,
  with the saved card as the durable copy.

---

## 10. Suggested next steps (research, not implementation)

1. **Paper/Wizard-of-Oz test of Scenarios 1–3** with the button grammar: an adult drives a
   Splat by hand from the child's wand motions to test comprehension before any firmware.
2. **Draw the relationship glyphs** on a 5×5 grid and test whether children can match glyph to
   behavior.
3. **Bench numbers:** BLE color write rate with ESP-NOW active; tilt axis range for natural wrist
   motions.
4. **Pairing Station paper prototype:** two pads plus dial, with the screen as cards swapped by
   hand.
5. **Decide** which relationships ship first (recommended: Follow, Opposite, Switch, Taught).
