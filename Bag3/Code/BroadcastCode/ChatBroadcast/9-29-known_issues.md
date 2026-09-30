# Known issues — 2026-09-29

Open items recorded on 2026-09-29. Older entries are in `9-4-known_issues.md`.


Multi-role games get one wand file for every wand. Should roles get their own code?

--> Keep one file per device type for now; redesign later in a separate plan.

STILL OPEN. The Box/Dial serves one `<slug>.py` to every wand, so a caller and
its players run the same file and pick their role at runtime by card
(`knowledge/game_patterns.md`). Options for a redesign, each touching the
Dial/Box serving side, the wand pull path and ChatBroadcast:

- Per-role files (`<slug>_caller.py`, `<slug>_player.py`), with the getcode
  card naming the role.
- One file with a `ROLE` value set by the Box when each wand pulls it.
- Role assignment over ESP-NOW by the Dial or display at game start.
