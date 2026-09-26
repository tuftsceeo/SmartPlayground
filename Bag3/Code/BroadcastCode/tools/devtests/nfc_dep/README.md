# NFC-DEP (PN532 peer-to-peer) bench

Proof of concept and speed test for sending game files wand-to-wand over NFC-DEP. It runs on two
stock Mock Wands and doesn't touch Mock Wand firmware (`main.py`, `lib/pn532.py`, `lib/nfc_reader.py`).

| File | Runs on | Purpose |
|---|---|---|
| `pn532_dep.py` | both wands | PN532 I2C driver: InJumpForDEP, InDataExchange, InRelease, TgInitAsTarget, TgGetData, TgSetData |
| `dep_proto.py` | both wands | Request/response file protocol (`H` header, `C` chunk, `D` done), with sha256 verification |
| `dep_sender.py` | wand A | Target ("broadcast device"): serves `PAYLOAD` until Ctrl-C |
| `dep_receiver.py` | wand B | Initiator: pulls `RUNS` times and prints `RESULT` lines |
| `dep_loopback.py` | host (CPython) | Checks `dep_proto.py` in memory; the driver isn't exercised |
| `HANDOFF.md` | — | Prompt for the local agent that runs the hardware tests |

## Assumptions
- **Wiring:** Mock Wand, with the PN532 at I2C `0x24` on SDA 22 / SCL 23, as in `MockWand/lib/hubtype.py` `"wand"`.
- **Bus:** SoftI2C at 100 kHz, the shipped value. `I2C_FREQ` in both scripts sets it.
- **Roles:** wand A is the target and wand B the initiator. The PN532 antennas face each other.

## Run
```sh
mpremote connect <A> cp pn532_dep.py dep_proto.py :
mpremote connect <A> cp ../../../MockWand/jumpin.py :
mpremote connect <A> run dep_sender.py

mpremote connect <B> cp pn532_dep.py dep_proto.py :
mpremote connect <B> run dep_receiver.py
```
The settings are constants at the top of each script:
- **Receiver:** `BAUD`, `CHUNK`, `RUNS`.
- **Sender:** `PAYLOAD`.
- **Both:** `I2C_FREQ`.
- **Initiator reply timeout:** `pn532_dep.TIMEOUT_CODE`.

## Output
The receiver prints one line per run:
```
RESULT OK name=jumpin.py bytes=7048 i2c=100000 baud=106 chunk=240 timeout_code=0x0B poll_ms=.. xfer_ms=.. Bps=.. rtt_us_min=.. med=.. max=..
RESULT FAIL err='...' after_ms=.. bytes_received=..
```
- `xfer_ms` runs from link up to the verified end, including the header and the sha256 check.
- `rtt_us` is the per-chunk round trip, from InDataExchange command to reply.

Each `RESULT OK` line is followed by detail lines:
- `wait_us`: ready-bit wait before each chunk reply (RF time plus the target's reply).
- `read_us`: the I2C read of the reply on the receiver (bus time).
- `ready_polls`, `header_us`.

If `read_us` dominates, the I2C bus is the bottleneck. If `wait_us` dominates, the air link or the
target host is.

On each link the sender prints:
- ATR_REQ bytes and per-op request counts;
- `tg_get_us`: the TgGetData wait;
- `tg_set_us`: the target host's reply latency, which is what counts against the receiver's
  `TIMEOUT_CODE`.

The receiver also prints ATR_RES, including the target's TO value.

Failures print:
- the PN532 status code with its UM0701 name;
- the phase timing of the failing command;
- the last op or offset reached.

Set `TRACE = True` in either script for one line per PN532 command.

## Results

Not yet run on hardware.

| i2c | baud | chunk | payload | spacing | runs ok | xfer_ms (median) | B/s | rtt med (µs) | notes |
|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | |

## Go / no-go
- **Trigger only:** the link comes up in under 1 s, and a 1 KB transfer verifies.
- **WiFi replacement:** a 7 KB game verifies in under about 5 s, hand-held, on 3 of 3 runs.
- **No-go:** target-side timeouts that raising `TIMEOUT_CODE` doesn't fix, or less than 1 KB/s.
