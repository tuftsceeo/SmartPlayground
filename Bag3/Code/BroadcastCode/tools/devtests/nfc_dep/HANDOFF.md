# Hardware test handoff: NFC-DEP bench

Paste the prompt below into a local Claude Code session on the machine that has both Mock Wands on USB.

---

You're running a hardware bench test in the SmartPlayground repo, on branch
`claude/rfid-nfc-controller-emulation-rrvc6n`. Pull that branch first.

**Goal:** measure whether two PN532 NFC readers in NFC-DEP (peer-to-peer) mode can move a game file
between two Mock Wands reliably, and how fast. Everything is in
`Bag3/Code/BroadcastCode/tools/devtests/nfc_dep/`. Read `README.md` there first.

**Rules**
- **Stay in scope:** only edit files inside `tools/devtests/nfc_dep/`. Don't edit Mock Wand firmware
  (`MockWand/main.py`, `MockWand/lib/*`), and don't overwrite `main.py` or `boot.py` on the wands.
  Only copy the bench files onto them.
- **Stop and report instead of working around:**
  - a PN532 that won't answer `GetFirmwareVersion`;
  - a NACK or "bad ACK" that repeats;
  - `TgInitAsTarget` that never returns while the wands are touching;
  - any fix that would need changes outside the directory above.
- **Timeout tuning is the only allowed code change:** if a transfer fails with
  `InDataExchange status 0x01`, raise `TIMEOUT_CODE` in `pn532_dep.py` one step at a time
  (0x0B → 0x0C → 0x0D → 0x0E). Record the value that worked, and commit only that.
- **Report every failure in full:** paste the whole `RESULT FAIL` line, the `#` detail lines
  around it from both wands, and the traceback, if any.
- **Keep full logs:** save both wands' serial output for every step, for example
  `mpremote connect <A> run dep_sender.py | tee logs/A_<step>.log`, and commit the logs under
  `tools/devtests/nfc_dep/logs/`.
- **Trace repeated failures:** if a failure repeats, rerun that step once with `TRACE = True` in both
  scripts. That's a logging switch, not a code change, but set it back to False before committing.

**Setup**
1. **List** the ports with `mpremote connect list`. Pick wand A (sender) and wand B (receiver),
   and label them.
2. **Stop** each wand's `main.py` with Ctrl-C through `mpremote connect <port> repl`, or use
   `mpremote run`, which soft-resets and runs the script without starting `main.py`'s loop.
   If `main.py` still grabs the PN532 first, report that; don't delete it.
3. **Copy** `pn532_dep.py` and `dep_proto.py` to both wands. Copy the payloads to wand A:
   - `Bag3/Code/BroadcastCode/MockWand/jumpin.py` (7 KB);
   - `Bag3/Code/BroadcastCode/MockWand/gestures.py` (28 KB);
   - a 1 KB file made with `head -c 1024 /dev/urandom > kb1.bin`.

**Steps.** Record pass/fail for each before moving on.
1. **Smoke:** run `dep_sender.py` on A and `dep_receiver.py` on B, with `PAYLOAD="kb1.bin"` and
   `RUNS=1`. Both must print `PN532 fw (...)`.
   - Pass: B prints `RESULT OK`, and A prints `link up` then `link done`.
2. **Link time:** 5 runs with `kb1.bin`, bringing the wands together from about 10 cm each time.
   - Pass: `poll_ms` is under 1000 on at least 4 of 5 runs, counting from when you start moving.
3. **Headline:** `jumpin.py`, CHUNK=240, BAUD=106, touching, RUNS=3, at I2C_FREQ 100000 and
   then 400000 (set it on both wands).
4. **Sweep:** for `jumpin.py` at the better I2C speed, CHUNK 64/128/192/240 and BAUD 106/212/424.
   Use 3 runs per cell where time allows.
5. **Size and distance:** `gestures.py` at the best setting, touching; then `jumpin.py` at about
   1 cm and about 2 cm, measured between the wand faces.
6. **Lift test:** start a `gestures.py` transfer and pull the wands apart halfway. Record the
   `RESULT FAIL` line and confirm that A goes back to `waiting as target`.

**Output**
- **Fill in** the Results table in `README.md`, one row per cell, with the median across runs.
  Replace the "Not yet run" line with the date and the wand identifiers.
- **Record findings:** add a short "Findings" section with failure modes, the `TIMEOUT_CODE`
  used, and anything unexpected.
- **Commit** with a message like `nfc_dep: bench results <date>`, then push to the same branch.
- **Report the bottleneck:** say whether `wait_us` or `read_us` dominates, and give the sender's
  `tg_set_us` median.
- **Report back:** the go/no-go verdict against the criteria in `README.md`, plus the headline
  numbers (B/s and xfer_ms for `jumpin.py` at 100 kHz and 400 kHz).
