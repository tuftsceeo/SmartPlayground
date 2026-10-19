# Hardware test prompts: october19demo

Four bench sessions for local agents, in order. Each prompt is self-contained. Total budget: under 3 hours (H1 ≈ 50 min, H2 ≈ 35 min, H3 ≈ 45 min, H4 ≈ 40 min).

Every session follows `Bag3/Code/HARDWARE_PROTOCOL.md`. Results go in
`Bag3/Code/BroadcastCode/docs_and_design/2026-10-14-integration/RESULTS-integration.md` (one section per session). Splat-pairing Part B results also go in `2026-10-07-splat-pairing/RESULTS-PartB.md`.

---

## H1: gates and scope (≈ 50 min)

```
Branch october19demo. Follow Bag3/Code/HARDWARE_PROTOCOL.md for all device access.
Plan: Bag3/Code/BroadcastCode/docs_and_design/2026-10-14-integration/PLAN.md, Phase 3.
Scripts: Bag3/Code/BroadcastCode/docs_and_design/2026-10-07-splat-pairing/bench_g1_scan.py and bench_g2_fullload.py (usage in their docstrings).
Hardware: wand boards 3101 and 1101, 2 Splats (4 if available), an icon display, a Box (StickS3), a Dial, a goalrace card.

1. G1 (10 min): power-cycle board 3101, run bench_g1_scan.py. Repeat on 1101. Record the G1 JSON lines. PASS = 3101 sees at least one Splat.
2. 3.2 (5 min): from the G1 output compare firmware, unique id and GPIO3/GPIO14 states; hash /lib on both boards. Record differences.
3. G2 (15 min): on the passing board, run bench_g2_fullload.py with G2_N=2 and the default 120 s soak. If it passes, run once with G2_N=3 (G2_N=4 only if 4 Splats are present and N=3 passed). Record each G2 JSON line. PASS = the 32 KB compile succeeds and soak loss < 5 %. The largest passing N sets MAX_SPLATS.
4. 3.4 (10 min): flash the display from this branch; tap a goalrace card and a getcode card. Record whether each read happens and the game starts.
5. 3.5 (10 min): Box wand round trip (stage a game, wand pulls it), then the Dial's BENCH_TEST_PLAN.md core items only (skip anything over 2 min).
Report: gate verdicts (G1, G2, MAX_SPLATS), and anything that blocks Phase 2 or display-card starts. Stop after the report; do not change code.
```

## H2: wave 1 confirmations (≈ 35 min, after H1 passes)

```
Branch october19demo. Follow Bag3/Code/HARDWARE_PROTOCOL.md for all device access.
Plan: Bag3/Code/BroadcastCode/docs_and_design/2026-10-14-integration/PLAN.md ("Hardware needs per task" and Phase 3 rows 3.3b).
Hardware: one MockWand (the H1 passing board), an icon display, the NFC Station, a Box or Dial, 2 Splats, blank cards.

1. idf_largest (10 min): use lib/memprobe.py on the wand and the display. Record pre-ESP-NOW idf_largest on the previous commit of main.py (30bec5c) and on october19demo. Any drop is a finding.
2. 3.3b (5 min): deploy BroadcastCode/MockWand/ (main.py + lib/) to the wand; boot with 2 Splats paired; record idf_largest after Splats connect and that a staged game still pulls and compiles.
3. 1.5/1.6 (5 min): put a game that raises in play() on the display and on the wand. PASS = red X, an error JSON line on serial, device returns to idle and starts another game.
4. 1.9 (2 min): show the elephant icon on the display.
5. 1.1 (5 min): serve Bag3/Code (python3 -m http.server), open BroadcastCode/ChatBroadcast/, install firmware onto a Box or Dial from the app.
6. 1.3/A2.4 (8 min): on the NFC Station write splatecho, soloecho, unpair, and splat-<MAC> cards (MAC from scan_splats on an UNPAIRED wand; it refuses on a paired one). Tap each on the wand and confirm the expected action.
Report PASS/FAIL per item with the evidence the protocol asks for.
```

## H3: Splat games, display-only games, catalog (≈ 45 min, after H2)

```
Branch october19demo. Follow Bag3/Code/HARDWARE_PROTOCOL.md for all device access.
Plan: Bag3/Code/BroadcastCode/docs_and_design/2026-10-07-splat-pairing/PLAN.md Part B (B1–B4), and 2026-10-14-integration/PLAN.md 3.6, 4.1, 4.4.
Hardware: 3 MockWands, 4 Splats, an icon display, a Box and a Dial, the NFC Station.

1. Part B B1–B2 (10 min): boot/store and pairing via splat-<MAC> and unpair cards.
2. Solo games (8 min): soloecho and solotest. Check the start refusal (amber + beep) with no Splat paired, then a Splat power-off mid-game (splat_lost/splat_back).
3. Part B B3–B4 (15 min): partytest with 3 wands (lobby, start, stop on leader and on a follower), then splattag and relaycolor one round each. Note press latency and any follower-to-follower send failures.
4. 4.1 (7 min): from ChatBroadcast send a display-only game to the Box, then to the Dial; the display pulls and runs it; a wand pull of the same slug is refused. Record Box/Dial idf_largest before/after.
5. 4.4 (5 min): in ChatBroadcast Saved games, "Send games to NFC Station"; then write two cards from the pushed catalog and tap them.
Battery: do not run a long drain test. If a USB power meter is available, record Splat current for 60 s with the idle glow on and off; otherwise mark it untested.
Report PASS/FAIL per item.
```

## H4: whole system (≈ 40 min, after the Simulator preview lands)

```
Branch october19demo. Follow Bag3/Code/HARDWARE_PROTOCOL.md for all device access.
Plan: Bag3/Code/BroadcastCode/docs_and_design/2026-10-14-integration/PLAN.md, Verification ("Browser" and H4).
Hardware: 2 MockWands, 2 Splats, an icon display, a Box, the NFC Station.

1. (10 min) In ChatBroadcast generate a solo Splat game; check the preview shows the wand and Splat panel with no peer strip; send to the Box; write its card on the station; the wand pulls and plays it with a paired Splat.
2. (12 min) Generate a party game; preview shows 2 virtual peers; send; play it on 2 wands. Use "Install on another wand" over USB for the second wand.
3. (8 min) Generate a wand+display game (goalrace-like); edit one of its icons in the Icons view; send; the display shows the edited icon.
4. (5 min) Push the catalog to the NFC Station and write one card from it.
Report PASS/FAIL per step and any mismatch between the Simulator preview and the devices.
```
