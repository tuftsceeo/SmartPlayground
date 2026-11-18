# Bench checklist (hardware session)

Nothing here has run on hardware. Follow `Bag3/Code/HARDWARE_PROTOCOL.md` and load the
`bag3-hardware-protocol` skill first.

## Setup

- **Ask** which wand is on which port; wait for an explicit answer. Check nothing holds the port (`lsof`).
- **Use** MicroPython v1.28.0 wands (`known_issues/2026-11-12-splat-host-v129-firmware.md`: v1.29.0 hosts 2 Splats, not 4).
- **Stage** with `python3 deploy.py --out <empty dir> --host-games --colorpads`; it opens no port.
- **Copy** with `python3 -m mpremote connect <port> resume fs cp ...`: reset, copy all changed files in one invocation, reset.
- **Avoid** copying to a running Splat host (`known_issues/2026-11-12-wand-mpremote-copy-fails.md`, open); reset it first.
- **Do not** use `tools/deploy.py`.

## Tests (report PASS/FAIL plus the noted observation for each)

| # | Setup | Do | Expect | Report |
|---|---|---|---|---|
| 1 | One wand, 2 Splats, `colorpads` | tap the Color Pads card (slug `color_pads`) | Splats glow red and blue, wand shows one of them; the matching Splat press scores, a wrong press beeps; an exit card ends the game | Splat colors, wand color, scoring, whether the Splats go dark at the end |
| 2 | Same wand, 1 Splat | tap the card | game refused at load, with the load-failure feedback | what the wand shows |
| 3 | Same wand, no Splat | tap the card | same refusal | what the wand shows |
| 4 | Splat host, 4 Splats, 2+ player wands, `host_splattag` | teacher taps card on host, each child taps on a wand, press host button | a Splat glows in a player's color; that player's press scores | whether all 4 Splats join; scoring |
| 5 | During 4 | switch one Splat off or carry it away | the round skips it; it resumes on `splat_back` | what happened, within how many seconds |
| 6 | During 4 | switch one player wand off | the host skips that player; it resumes on return | same |
| 7 | Two Splat hosts idle, a wand broadcasting `{"type":"splat","a":["turnred"]}` | send once | both hosts turn their Splats red; a press broadcasts `splat_press` | which Splats changed; the rate-limit behavior on rapid presses (250 ms) |
| 8 | A host running a type 9 game | broadcast the same `splat` message | ignored | whether any Splat changed |
| 9 | Any wand after the game imports | read `idf largest` | at least 163840 (`9d1a8b8d` bench figure) | the number |

Also run `host_relaycolor` and `host_lobbytest` once each if time allows.

## Report back

The user cannot be watched, so for each test report what the wands and Splats showed, any serial error text, and the `idf largest` value.
