# Hardware test handoff: NFC-DEP bench

Paste the prompt below into a local Claude Code session on the machine that has both Mock Wands on USB.

---

You're running a hardware bench test in the SmartPlayground repo. First run:

```sh
git fetch origin claude/rfid-nfc-controller-emulation-rrvc6n
git checkout claude/rfid-nfc-controller-emulation-rrvc6n
git log -1 --format=%H   # must match the commit hash given with this prompt
```

**Read these before touching hardware:**
- `Bag3/Code/HARDWARE_PROTOCOL.md`, which governs everything below. Where this prompt and that
  file disagree, the protocol wins; report the conflict.
- `Bag3/Code/BroadcastCode/tools/devtests/nfc_dep/README.md`.

**Goal:** measure whether two PN532 NFC readers in NFC-DEP (peer-to-peer) mode can move a game file
between two Mock Wands reliably, and how fast. You can't move the wands. The user does every
physical step, and you drive the host side and read the logs.

## Rules
- **Ask which wand is on which port, and wait for the answer.** Never infer it from
  `ls /dev/cu.usbmodem*`. Wand A is the sender (target) and wand B the receiver (initiator).
- **Ask before opening either port, and wait for an explicit answer.** Check that nothing else holds
  it with `lsof <port>`. That includes ChatBroadcast/WebSerial, a serial monitor, or your own
  background job (`pgrep -f mpremote`).
- **Pass `resume` on every `mpremote` call**, as `python3 -m mpremote connect <port> resume ...`.
  The only exception is the plain `reset` at the end that restores the wand.
- **Use absolute paths.** The shell is zsh: print each constructed command and check it before
  running it.
- **Stay in scope:**
  - only edit files inside `Bag3/Code/BroadcastCode/tools/devtests/nfc_dep/`;
  - don't edit Mock Wand firmware;
  - don't overwrite or delete anything already on the wands. The bench files use names that don't
    collide with it: `pn532_dep.py`, `dep_proto.py`, `dep_*.bin`, `dep_rx.bin`.
- **Stop and report instead of working around:**
  - a PN532 that doesn't answer (no `PN532 fw` line, or `0x24` missing from `i2c.scan`);
  - a "bad ACK" that repeats;
  - `waiting as target` with no `link up` while the user confirms the wands are touching;
  - any fix that would need changes outside the directory above.
- **Timeout tuning is the only allowed code change.** If transfers fail with
  `InDataExchange status 0x01 (timeout)`, raise `TIMEOUT_CODE` in `pn532_dep.py` one step at a time
  (0x0B → 0x0C → 0x0D → 0x0E). Re-copy that file to wand B, and record the value that worked.
- **Trace repeated failures:** if a failure repeats, rerun that step once with `TRACE = True` in
  both scripts. Set it back to False before committing, per the protocol's "gate the
  instrumentation" rule.
- **Report what the logs show, citing lines.** Don't claim something "works": the user confirms
  physical behaviour.

## Setup
1. **Ask** the user which port is wand A and which is wand B, and confirm nothing else holds them.
   Wait.
2. **Copy** the bench files in one batched call per wand (`D` = absolute path to
   `Bag3/Code/BroadcastCode`):
   ```sh
   python3 -m mpremote connect $PORT_A resume \
     fs cp $D/tools/devtests/nfc_dep/pn532_dep.py :pn532_dep.py + \
     fs cp $D/tools/devtests/nfc_dep/dep_proto.py :dep_proto.py + \
     fs cp $D/MockWand/jumpin.py :dep_jumpin.bin + \
     fs cp $D/MockWand/gestures.py :dep_gestures.bin + \
     fs cp /tmp/dep_kb1.bin :dep_kb1.bin
   python3 -m mpremote connect $PORT_B resume \
     fs cp $D/tools/devtests/nfc_dep/pn532_dep.py :pn532_dep.py + \
     fs cp $D/tools/devtests/nfc_dep/dep_proto.py :dep_proto.py
   ```
   Create `/tmp/dep_kb1.bin` first with `head -c 1024 /dev/urandom > /tmp/dep_kb1.bin`.
   The Mock Wand writes to its flash root. The `:/flash/` rule in the protocol is for the M5
   boards. If `fs cp` to root fails, stop and report.
3. **Settings go in the local scripts:** `PAYLOAD` in `dep_sender.py`; `BAUD`, `CHUNK` and `RUNS` in
   `dep_receiver.py`; `I2C_FREQ` in both. `resume run` sends the local file, so script edits need
   no re-copy.

## Running one step
1. **Start the sender in the background**, logging to a file:
   `python3 -m mpremote connect $PORT_A resume run $D/tools/devtests/nfc_dep/dep_sender.py > $LOGS/A_<step>.log 2>&1 &`.
   `resume run` interrupts the wand's `main.py` with Ctrl-C and runs the script without rebooting.
2. **Start the receiver** the same way, into `$LOGS/B_<step>.log`.
3. **Confirm both are ready:** both logs show `PN532 fw`, A shows `waiting as target`, and B shows
   `run 1/N`.
4. **Give the user numbered physical steps**, for example "1. Hold the wands 10 cm apart, with the
   PN532 faces toward each other. 2. Bring them together until the faces touch. 3. Hold until B's
   log shows `RESULT` (I'll tell you), then separate." Say you're waiting, then stop until the user
   says go.
5. **Watch B's log for each `RESULT` line** and tell the user when to separate and when to bring the
   wands back together. Keep capture windows long, around 15 minutes.
6. **Finish the step:** once B prints `SUMMARY`, stop the sender process (the kill takes it by
   PID). Confirm with `pgrep -f mpremote` that nothing still holds the ports before the next step.

`$LOGS` is `Bag3/Code/BroadcastCode/tools/devtests/nfc_dep/logs/` (absolute path; create it).

## Steps
Record pass/fail for each step, citing the log lines, before moving on.
1. **Smoke:** `PAYLOAD="dep_kb1.bin"`, `RUNS=1`.
   - Pass: B prints `RESULT OK`, and A prints `link 1 up` then `link 1 done`.
2. **Link time:** `dep_kb1.bin`, `RUNS=5`. The user starts each approach from about 10 cm.
   - Pass: `poll_ms` is under 1000 on at least 4 of 5 runs. `poll_ms` counts from when B starts
     polling, so ask the user to start moving right after you say "go".
3. **Headline:** `dep_jumpin.bin`, CHUNK=240, BAUD=BAUD_106, touching, RUNS=3, at I2C_FREQ 100_000
   and then 400_000 (set on both wands).
4. **Sweep:** `dep_jumpin.bin` at the better I2C speed, CHUNK 64/128/192/240 and BAUD 106/212/424.
   Use 3 runs per cell where the user has time; ask before starting a long sweep.
5. **Size and distance:** `dep_gestures.bin` at the best setting, touching; then `dep_jumpin.bin`
   with the user holding about 1 cm and about 2 cm between the wand faces.
6. **Lift test:** `dep_gestures.bin`. The user separates the wands partway through the transfer
   when you say so.
   - Record: B's `RESULT FAIL` line, and whether A logs `link N FAILED` and returns to
     `waiting as target`.

## Wrap up
1. **Restore both wands** with a plain reset, no `resume`:
   `python3 -m mpremote connect $PORT reset`. Ask the user to confirm each wand is back in its
   normal idle state.
2. **Fill in** the Results table in `README.md`, one row per cell, with the median across runs.
   Replace "Not yet run on hardware." with the date and the wand identifiers.
3. **Add a "Findings" section** to `README.md`. For each claim, say how it was verified, by log
   file and line. Cover:
   - failure modes, with the full `RESULT FAIL` line and the `#` detail lines from both wands;
   - the `TIMEOUT_CODE` used;
   - whether `wait_us` or `read_us` dominates, and the sender's `tg_set_us` median;
   - anything unexpected.
4. **Commit** the README and `logs/` with a message like `nfc_dep: bench results <date>`. Push to
   `claude/rfid-nfc-controller-emulation-rrvc6n`.
5. **Report back:** the go/no-go verdict against the criteria in `README.md`, plus the headline
   numbers (B/s and xfer_ms for `dep_jumpin.bin` at 100 kHz and 400 kHz).
