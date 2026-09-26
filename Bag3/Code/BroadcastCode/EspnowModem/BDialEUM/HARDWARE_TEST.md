# BDialEUM hardware test: prompt for a local agent

Paste the prompt below into a local agent session on the machine with the boards attached. Branch: `claude/esp-now-dial`.

---

You are testing `Bag3/Code/BroadcastCode/EspnowModem/BDialEUM`: a Broadcast Dial build that serves game code to a MockWandEUM wand over ESP-NOW, through an ESP-NOW UART modem (EUM). The Dial uses no WiFi.

**Read first:**
- `Bag3/Code/HARDWARE_PROTOCOL.md`
- `EspnowModem/BDialEUM/README.md`
- `EspnowModem/README.md` (Wiring, Flashing)
- `EspnowModem/MockWandEUM/README.md`

**Rules:**
- Pass `resume` on every `mpremote` call, and write only under `/flash/` on the UIFlow boards.
- Ask which port is the Dial, the modem and the wand. Ask that nothing else holds them (ChatBroadcast closed).
- The user does every physical step. Give numbered steps, say you are waiting, and stop until they say go.
- Report what the logs show, and say which evidence is a log line and which is the user's eyes.
- Do not edit firmware to make a step pass. Report the failure, with the log excerpt.

**Hardware:**
- **Dial:** M5 Dial 2 (StampS3A), external NFC reader on Port A.
- **Modem:** M5StickS3 running `EspnowModem/modem/main.py`, on its own USB power.
- **Wand:** a MockWandEUM wand (XIAO ESP32-C6).
- **Wiring:** Dial Port B GPIO2 (TX) → modem GPIO44, Dial GPIO1 (RX) ← modem GPIO43, GND to GND. The Grove colour-to-pin mapping is unconfirmed; check the silkscreen.

## Steps

1. **Offline checks.**
   - Run `python tests/test_bdial_eum.py`, `python tests/test_code_xfer.py` and `python BDialEUM/tools/dial_menu_check.py` from `EspnowModem/`.
   - Report the pass counts.
2. **Flash.**
   - **Modem:** flash `modem/` per `EspnowModem/README.md` if it is not already running EUM firmware from this branch.
   - **Dial:** `python3 BDialEUM/tools/deploy_dial.py $DIAL`, then a plain `reset`.
   - **Wand:** flash `MockWandEUM/main.py` and `MockWandEUM/lib/espnow_code.py`. This branch changes both so that the card's `@<id>` reaches the Dial.
3. **Boot option.**
   - Read the Dial's UIFlow `boot_option` with the command in the BDialEUM README. It must be `0`; report the value.
   - If the command raises, report the error and ask the user whether the Dial shows the UIFlow startup or network screen at boot.
4. **Boot with the modem.**
   - Start `tools/serial_monitor.py $DIAL 900 > dial.log` in the background, then ask the user to reset the Dial.
   - Expect in the log: `# [eum] modem up`, an `identity` line with `"variant": "eum"` and a `host_id`, `mode` `WRITE`, and heartbeats.
   - Ask the user what the top breadcrumb says. Expected: `Sharing <host_id>`.
   - Report the host id, and the `mem[...]` lines.
5. **Card and pull.**
   - The user picks a game of 28 KB or less already on the Dial (for example `tilt_tones`), opens its group, selects the `getcode:<slug>` row, presses WRITE and holds a card on the reader.
   - Expect `card_written` in the log, with label `getcode:<slug>`.
   - The user taps that card on the wand. Expected: the wand turns blue, shows a check and launches the game.
   - Report the Dial's `pull` event (`ok`, `bytes`, `ms`), and the wand's `enx_result` if you can capture the wand's port. Ask the user whether the game launched.
6. **Pull while the reader is busy.**
   - The user stops the game (a `stop` card or a reset), starts a WRITE scan of any tag on the Dial and leaves it scanning, then taps the getcode card on the wand.
   - Expect a `pull` event with `ok: true` while the scan screen is up.
   - Report whether the scan screen stayed responsive (BACK works).
7. **Modem lost and restored.**
   - With the Dial on the top-level menu, the user unplugs the modem's USB power for about 5 s, then plugs it back in.
   - Expect in the log: `modem link down`, then `modem link restored`, and `modem` events.
   - Expected on screen: the crumb reads `Modem Lost`, then `Sharing <id>`.
   - Repeat step 5's tap and report the `pull` result.
8. **Boot without the modem.**
   - With the modem unpowered, the user resets the Dial.
   - Expect a `modem DOWN: EUM: no modem ...` line and the `No Modem` crumb. Card writing should still work; ask the user to write one card.
   - The user then powers the modem. Expect `modem up` within about 5 s of the modem finishing its boot.
Host pinning (a card from this Dial ignored by other hosts) is covered only in simulation. `host/code_host.py` has no host id and answers every request, so it cannot serve as the second host for this test.

## Report

For each step, give:
- the result: pass, fail or skipped
- the log lines that show it
- what the user saw

Then give the `info` reply fields `modem`, `served`, `failed` and `busy_replies`, and the modem `link_stats` counters if you read them. List anything unexpected, especially:
- a Dial reset (a dropped port)
- a `fatal` line
- a crumb that did not change
- CRC or timeout counters above 0
