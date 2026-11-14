# Icon drafts

Mock-up 16x16 icons that are not in `../icons/` and not in ChatBroadcast's icon list.

- `holiday.json`: Halloween, Día de los Muertos, "eyes in the dark" and text icons
  (`take_one_bold`, scrolling `trick_or_treat` / `please_take_one`).
- `heritage.json`: everyday foods and secular items for Mexican and Salvadoran heritage play.

Each entry has a `key` (character → WS2812 duty) and either `rows` (16 strings of 16 characters,
`.` = off) or `frames` plus `fps`. The icon display shows one frame per icon, so animated entries
need multi-frame support (or a host streaming `frame` commands) before they can play.

`build.py` and `heritage.py` regenerate the JSON, the labelled sheets (`*.jpg`) and the GIFs. Screen
colours use the icon editor's LED model (`ledScreenRgb` in `Simulator/js/panels/display.js`).
Designs target a black background in a dark room: flat or two-tone colours, no outlines.

To make one live, write its map for `IconEditor/hand_author_icons.py`, generate
`../icons/<name>.py`, then run `ChatBroadcast/tools/sync_icons.py`.

## Halloween bench game

`export_halloween.py` packs jack_o_lantern, take_one_bold, bat, ghost and eyes into
`../games/halloween_frames.bin` (21 frames x 768 bytes) for `../games/halloween.py`, which
loops each animation for 10 s with a 10 s TAKE ONE after every second one. It swaps the old neutrals
for the measured white (185,255,150); see "Measured white" in `../README.md`. Start it over
USB with `{"cmd":"start_game","name":"halloween"}`; it is not in `GAME_TAGS`, so no card starts it.
