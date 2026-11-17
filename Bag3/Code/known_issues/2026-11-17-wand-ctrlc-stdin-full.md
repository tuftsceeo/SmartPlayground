---
title: Wand ignores Ctrl-C once stdin fills
date: 2026-11-17
status: open (confirmed on hardware 2026-11-17; drain fix built into flash_bundle, not yet on hardware)
devices: [Wand (Mock Wand), ESP32-C6]
components: [MicroPython v1.28.0 USB-Serial-JTAG stdin, main.py main loop, main.py _boot_grace, Splat host loop, game loops]
code:
  - Bag3/Code/Wand Module/main.py
  - Bag3/Code/Wand Module/lib/splat_host.py
  - Bag3/Code/Wand Module/lib/stdin_drain.py
  - Bag3/Code/tools/wand_breakin.py
open:
  - Run the drain fix (lib/stdin_drain.py) on hardware - 300 bytes then Ctrl-C, awake, asleep and in the Splat host role.
  - Check whether the drain in the countdown frees a wand that is already locked out, after a port-reopen reset, without a power-off.
  - Running games have their own loops and do not drain stdin; Ctrl-C there can still be locked out.
keywords: [Ctrl-C, KeyboardInterrupt, stdin, ring buffer, USB-Serial-JTAG, REPL, Thonny, mpremote, raw repl, break in, lockout, sleep, unresponsive]
---

# Wand ignores Ctrl-C once stdin fills

## Symptom

A running wand stops answering Ctrl-C over USB. Thonny and `mpremote` cannot reach the REPL;
Thonny only worked after a power cycle and catching the wand early in boot. It looked like a sleep
problem but is not: it happens awake too.

Field case, spare wand A0:F2:62:85:D6:14, MicroPython v1.28.0, 2026-11-17. The log shows Ctrl-C
ignored while asleep (11:25:46) and while awake (11:26:01), with no traceback and no "Exiting.".
Text typed into the port before that got no response, and no `[ERR] Main loop` lines appear.

## Cause (MicroPython v1.28.0 source)

- The stdin ring buffer is 260 bytes, so it holds 259 (`ports/esp32/mphalport.c:57`,
  `static uint8_t stdin_ringbuf_array[260];`; `py/ringbuf.h` keeps one slot empty).
- The USB-Serial-JTAG RX interrupt reads from the USB hardware FIFO only as many bytes as the ring
  buffer has room for, and checks for Ctrl-C only on the bytes it reads
  (`ports/esp32/usb_serial_jtag.c`, `usb_serial_jtag_handle_rx()`):
  ```c
  size_t req_len = ringbuf_free(&stdin_ringbuf);   // capped at 64
  size_t len = usb_serial_jtag_ll_read_rxfifo(rx_buf, req_len);
  for (...) if (rx_buf[i] == mp_interrupt_char) mp_sched_keyboard_interrupt(); else ringbuf_put(...)
  ```
  With the buffer full, `req_len` is 0, nothing is read, and a 0x03 waiting in the FIFO is never
  seen.
- The only other path that reads the FIFO, `usb_serial_jtag_poll_rx()`, is called only from
  stdin reads and polls (`mphalport.c:111`, `:132`). `time.sleep_ms()` (`mp_hal_delay_ms`) does
  not call it. MicroPython commit f7413113 (2023) records that a full buffer gets no further
  interrupt.
- `main.py` never read stdin, so anything the host sent that was not 0x03 (Thonny's connect
  probes, raw-REPL attempts, typed text) stayed in the buffer. After about 259 bytes, Ctrl-C was
  dead.
- WiFi, ESP-NOW, BLE and power management: no source path found that blocks this interrupt. The
  interrupt is level 1 and not in IRAM (`usb_serial_jtag.c:97`), which can delay it but not lose
  bytes. The receive path did not change between v1.24 and v1.28.
- No matching report found on the MicroPython tracker (search partly rate-limited).

## Bench result (2026-11-17, wand on port 3101)

The port-testing agent reported:

| Test | Result |
|---|---|
| 300 bytes, then Ctrl-C | Locked out |
| 200 bytes, then Ctrl-C (after a power-off) | Ctrl-C works |
| Plain Ctrl-C (after a power-off) | Ctrl-C works |
| 3 resets by reopening the port (rst:0x15) | Lockout stays |
| Unplug and replug (power-off) | Lockout cleared |

So the lockout is confirmed between 200 and 300 bytes, matching the 259-byte buffer. It survives
a port-reopen reset and is cleared by a power-off.

Why it survives a reset is not confirmed. Likely (inference): the reset does not clear the
USB-Serial-JTAG peripheral's FIFO or the host's queued data, and the USB link stays up through it
(the port reappears without re-enumerating as a new device). The leftover bytes are delivered
again during boot, the new program never reads them, and the buffer fills before anyone sends
Ctrl-C. A power-off clears both ends.

## Fix (2026-11-17, compiled and bundled, not yet on hardware)

`lib/stdin_drain.py` reads and discards stdin. `Drainer.drain()` reads one byte at a time with
`sys.stdin.buffer.readinto()` into a 1-byte bytearray while `poll.ipoll(0)` reports input; after
the first call it allocates nothing per byte. `Drainer.tick()` runs `drain()` at most every
250 ms. Reading calls `usb_serial_jtag_poll_rx()` -> `usb_serial_jtag_handle_rx()`, which checks
every byte for 0x03, so a waiting Ctrl-C raises KeyboardInterrupt as normal.

It runs in three places, each importing the module after the radio is up:

- `main.py` `_boot_grace()`: every 250 ms through the countdown, so bytes left over from before a
  reset cannot hide the countdown's Ctrl-C.
- `main.py` main loop: `tick()` at the top of the `try`, so both the awake and sleep paths run it
  and a Ctrl-C reaches `except KeyboardInterrupt`.
- `lib/splat_host.py` `_loop()`: `tick()` every pass; a Ctrl-C reaches `run()`'s
  `except KeyboardInterrupt`.

`manifest.js` lists the new module, and `flash_bundle/` was rebuilt
(`tools/build_wand_bundle.py`).

Not covered: running games.

## Related

[2026-11-17-wand-ctrlc-boot-crash.md](2026-11-17-wand-ctrlc-boot-crash.md): a Ctrl-C that landed
during boot crashed the wand.
[2026-11-12-wand-mpremote-copy-fails.md](2026-11-12-wand-mpremote-copy-fails.md): mpremote could not
break into the Splat host; likely the same lockout (not re-tested).
