# BroadcastBox Prototype (Proof of concept) — wireless .py push, S3 → C6

Prototype for pushing a `.py` file from the Mac to a Xiao ESP32-C6 wirelessly, using a second
ESP32-S3 as the local wireless link. No router, no internet — the S3 runs a SoftAP and the C6
connects directly to it.

**Not firmware OTA.** No `esp32.Partition`, no `.bin`, no A/B partition swap. This writes a file
straight into the C6's existing MicroPython filesystem, the same way you'd `open(path, 'wb')` over
USB — just over WiFi instead.

Background and the failure modes this design accounts for: `esp32_micropython_local_ota.md` (not
committed to this repo).

## Roles

- **`s3_sender.py`** runs on the ESP32-S3. It's a SoftAP + an unthreaded TCP server that accepts
  exactly one connection, sends one file, and closes.
- **`c6_receiver.py`** runs on the ESP32-C6. It joins the S3's AP as a station and is the TCP
  client — it connects out, pulls the file, verifies it, and atomically promotes it into place.

The C6 is the client (not the server) so it always dials a fixed, known address
(`192.168.4.1`) — no IP discovery needed on either side.

## Wire protocol

One connection, one file, sender closes when done:

```
sender → receiver:   4 bytes  size          (big-endian)
                    32 bytes  sha256 digest
                     1 byte   destination filename length
                     N bytes  destination filename (utf-8)
                  size bytes  raw file contents
receiver → sender:   2 bytes  b'OK' or b'NO'
```

No HTTP/chunked framing — this is a private link between two known devices.

## Setup (once per board)

```bash
mpremote connect /dev/cu.usbmodemS3 cp s3_sender.py :s3_sender.py
```

```bash
mpremote connect /dev/cu.usbmodemC6 cp c6_receiver.py :c6_receiver.py
```

(Replace the port paths with whatever `mpremote connect list` shows for your boards.)

## Running a push (two terminals)

**Terminal 1 — S3.** Stage the payload and start the server; it blocks until a receiver connects:

```bash
mpremote connect /dev/cu.usbmodemS3 cp ./payload.py :payload.py + exec "import s3_sender; s3_sender.serve('payload.py', 'pushed.py', verbose=True)"
```

**Terminal 2 — C6.** Once terminal 1 prints that the AP is up:

```bash
mpremote connect /dev/cu.usbmodemC6 exec "import c6_receiver; c6_receiver.pull(verbose=True)"
```

Start with a small file as a sanity check, then try something in the real target range (~30 KB). At
the larger size, a **stall** (not an error) is the signature of the WiFi power-save issue this
design already works around — see below if you see one.

To confirm the file arrived byte-identical, independent of the transfer's own checksum:

```bash
mpremote connect /dev/cu.usbmodemC6 cat :pushed.py | shasum -a 256
shasum -a 256 ./payload.py
```

## Design notes worth knowing before changing this

- **Memory discipline.** Every read/write on both sides goes through one reused
  `bytearray(512)`/`memoryview`, filled with `readinto()`. Nothing ever buffers the whole file, and
  nothing hex/base64-encodes a chunk — that transiently ~triples the memory a chunk needs and is a
  confirmed real-world `MemoryError` cause at this exact file size.
- **Two independent WiFi bottlenecks, both handled.** `sleep_ms(20)` between chunks yields the CPU
  so the WiFi driver's background task gets scheduled. Separately, `wlan.config(pm=0)` on the C6
  disables 802.11 power-save, which a `sleep_ms()` yield *cannot* reach — it's a MAC-layer radio
  sleep state. Fixing only one of the two produces stalls that are miserable to reproduce. If a
  stall still shows up with both in place, the next suspect is ESP-IDF/lwIP TCP stack behavior
  (needs `sdkconfig` tuning) — not more chunk-size fiddling.
- **`.part` + atomic rename.** The receiver never writes directly to the destination path; it writes
  `dest + '.part'`, verifies size and SHA-256, and only then rewrites `dest`. Any previous file at
  `dest` is kept as `dest + '.bak'` (written but not currently consumed by this prototype).
- **C6 antenna GPIO — Wand PCB only, off by default.** `c6_receiver.py` inlines the same
  external-antenna switch used in `Bag3/Code/lib/espnow_manager.py`
  (`_configure_external_antenna`), so it has no dependency on `/lib` and runs standalone. It
  defaults to `external_antenna=False`, though — confirmed against real hardware, toggling those
  GPIOs (3/14) on a bare Xiao ESP32-C6 dev board (no Wand PCB) breaks WiFi entirely
  (`OSError: Wifi Internal Error` on connect). Pass `external_antenna=True` only when running on
  actual Wand Module hardware.
- **`.py` vs `.mpy` import errors are a different bug than transfer errors.** A `MemoryError` at
  `import` time (not during the socket transfer) means the heap was still fragmented from transfer
  machinery when the bytecode compiler ran — `gc.collect()` runs once after the transfer for this
  reason. If you ever push a precompiled `.mpy`, its `mpy-cross` version must match the ABI of the
  firmware actually on the target board.

## Out of scope for this prototype

Deliberate, not overlooked — see the plan this was built from for the full reasoning:

- Import verification / `.bak` rollback on a bad push (the `.bak` file is written, nothing reads it
  back yet).
- Any check that the C6's power-save setting is actually restored (the code restores it; nothing
  asserts that it did).
- A C6 firmware-version check (MicroPython ≥ v1.24 is required for C6 support at all).
- Retry/resume, serving more than one C6, any hook into wand `main.py`, and automating the
  two-terminal dance.
