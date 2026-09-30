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

---

The example gallery is hard to remix. What should replace it?

--> Separate plan.

STILL OPEN. The gallery examples are the full built-in games (up to ~22 KB
for Color Quest), with complex structure that differs game to game. Test
users who asked to "remix the rainbow example" quickly hit memory failures.
A rework would add short, kindergarten-first starter games written to be
remixed, and keep the full built-ins out of the remix path.

---

Remixed games fail on the Dial before reaching the wand. Why?

--> Log it; reproduce with serial capture first.

STILL OPEN. Suspected cause, not yet confirmed on hardware:
`js/device/replController.js` `writeFile()` sends each file as one base64
string literal inside one raw-REPL script, so the Box/Dial must hold and
compile the whole script (about 1.33x the file) in one allocation before
writing. A multi-device game adds a display file and its icon files, each
sent the same way. The Rainbow remix failed "at load, before it could
transmit from the dial to the wand". Next steps: reproduce with the Dial's
serial log captured; if confirmed, write each file in small appended chunks.

---

Should recent serial errors be sent to the model?

--> Future consideration.

STILL OPEN. When a device is connected by USB, the serial log
(`js/device/serialLog.js`) holds `[FAIL]` / `[ERR]` / traceback lines that
name the real cause of a load failure. Wands and stations are usually not
connected to the computer, so this helps only in that case. Revisit if test
sessions show relevant serial errors the assistant could have used.

---

Advanced mode is the only switch for technical replies.

--> Recorded for review.

The assistant also switches to technical detail when a user says they are on
the team or writes Python (knowledge/policy.md). Advanced mode additionally
sends knowledge/advanced.md. There is no separate "technical assistant"
toggle while the UI stays simple.
