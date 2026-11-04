# Bag1

The first generation of the SmartPlayground system. Bag1 was given to classrooms and is **not under
active development.**

## What it is

Bag1's student-facing component is the **Plushie module** — a soft-plush-housed handheld with LEDs,
an accelerometer, a battery, and (on some variants) NFC. This is the same component later Bags call
the **Wand module**, a direct design descendant. (`config.py`'s `box` variant is a brief
file-naming label from a rigid-case transitional form; "wand" is what stuck, formalized in the
folder/file names starting in Bag2.)

Bag1 also defines several other component types via `Config` subclasses in
`Plushie_Module/config.py`: a `button` module, a `box` variant (the current default in
`hardware.py`), a `splats` module (talks to a third-party BLE splat toy), and a teacher-side
`controller`, which has four hardware variants of its own.

Communication is ESP-NOW, using a `{'topic': ..., 'value': ...}` pub-sub scheme
(`Plushie_Module/utilities/now.py`) — a different, incompatible protocol from later Bags.

## Where things are

- `Plushie_Module/` — all device code (games, controllers, utilities). See
  [`Plushie_Module/README.md`](Plushie_Module/README.md) for the original architecture write-up.
- `Design Files/CAD Files/Splat Companion/` — STLs for the Bag1 Splat Companion hardware.

## More detail

Bag1 is fielded and not under active development — ask before editing. Read the code directly:
`Plushie_Module/config.py` for the device variants, `Plushie_Module/games/` for the game catalog,
`Plushie_Module/controllers/` and `Plushie_Module/utilities/` for the rest.
