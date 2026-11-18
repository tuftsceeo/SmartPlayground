# game_patterns.md changes

DRAFT. Label each pattern with its row from `game_types.md`, and add the station example.

| Pattern | Row |
|---|---|
| Solo wand game | 1 |
| Solo wand with 1-2 Splats | 2 (`wand_type2.md`) |
| Shared last-write station (melody) | 3 |
| Leader broadcast, class follows (freeze dance) | 4 |
| Every wand broadcasts, with a speaker or display station | 5 |
| Team games, teams by NFC card or teacher command | 6 |
| Group game at a station | 8 |
| Splat host group game | 9 (`splat_host_games.md`) |

Add under row 4 or 5: **Drive a Splat host** (`station_mode.md`): a wand broadcasts
`{"type": "splat", "a": [...]}` and reacts to `{"type": "splat_press", ...}`.
