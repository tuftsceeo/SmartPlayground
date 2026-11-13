# platform.md changes

DRAFT.

- Reserved message types gain `"splat"` and `"splat_press"` (platform.md).
- `[GAME_SETTINGS:]`: drop `wand_splats`. A type 2 game gives `splats` (1-2):
  `{"splats": 2, "wands": 1}`. Keep `splat_host` for type 9: `{"splat_host": 4, "wands": 2}`.
  Any other game: `{"wands": 2}`.
