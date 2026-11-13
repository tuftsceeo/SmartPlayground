# Pattern: drive an idle Splat host (station mode)

DRAFT, for game_patterns.md. Any wand game (types 1, 3-6) can drive a Splat host that is
**idle** (not running a group game). It is open and last-write-wins, like the icon display;
every host in range obeys.

Send actions:

```python
enow.broadcast({"type": "splat", "s": 0, "a": ["turnred", "note_c"]})
```

`"s"` is the Splat index; omit it for every Splat. `"a"` is a list of action names from the
SPLAT ACTION NAMES list.

The host answers a press with:

```python
enow.broadcast({"type": "splat_press", "s": i, "c": "turnred"})   # c = host color name
```

React to it in the ordinary loop: `msg_type, data, _mac = enow.poll()`, then
`if msg_type == "splat_press": ...`. A device does not hear its own broadcast.

## Example: freeze dance cue (type 4)

The leader wand lights the class Splats red on freeze and green on go.

```python
# leader wand, inside the loop
if frozen_changed:
    if frozen:
        enow.broadcast({"type": "splat", "a": ["turnred"]})
    else:
        enow.broadcast({"type": "splat", "a": ["turngreen", "note_c"]})
```

Repeat the current state about once a second so a Splat that missed it catches up.

## Platform changes

- Reserved message types gain `"splat"` and `"splat_press"` (platform.md).
- `[GAME_SETTINGS:]`: drop `wand_splats`. A type 2 game gives `splats` (1-2):
  `{"splats": 2, "wands": 1}`. Keep `splat_host` for type 9: `{"splat_host": 4, "wands": 2}`.
  Any other game: `{"wands": 2}`.

Open question: when several hosts are in range, should a broadcast target one (host color in
the message) or all?
