# BLE + ESP-NOW on one controller: platform requirements and options

2026-10-06 · research report, not committed

**Question.** The Splat Companion and the EspnowModem proof of concept both use two controllers: one
runs ESP-NOW, the other runs BLE or WiFi, and they talk over UART. Is there any ESP32 platform, in
any language, that can use BLE and ESP-NOW at the same time? Ideally that would be two radios or
antennas usable concurrently, each with its own buffers. If not, what else could do this kind of
multi-radio work?

## TL;DR

1. **No ESP32 has two radios.** That covers ESP32, S3, C3, C5, C6, C61 and H2. Espressif's
   coexistence guide says: *"Each chip has only one RF path … Different modules cannot use the RF path
   to transmit or receive at the same time."* The C5 is no exception. ESP-NOW can run on 5 GHz there,
   but Espressif states the same RF path is shared on both bands. The XIAO C6's GPIO3/GPIO14 switch,
   and Espressif's antenna-diversity API, only *select* an antenna for that single RF chain.
2. **One chip can do it, but only time-sliced.** Espressif officially supports BLE + ESP-NOW on one
   chip:
   - ESP-NOW **TX** is "stable".
   - ESP-NOW **RX** is "stable in STA mode only". Our firmware uses `STA_IF` everywhere, so that
     condition is met.
   - When BLE is connected, the scheduler gives WiFi/ESP-NOW about **50% of each ~100 ms coex
     period**. ESP-NOW can only receive inside its own slice.
   - Broadcasts have no ACK, so they are lost when they land in the BLE slice. Public reports show
     random multi-second gaps, and in one case roughly ⅓ delivery.
   - ACKed unicast with retries mostly hides the loss.
3. **On the C6 under MicroPython, memory is the practical blocker, not airtime.**
   - MicroPython issue #18859: on C3 and C6, BLE + ESP-NOW fails with `WiFi Out of Memory`. With BLE
     initialised first, the largest free IDF block is about 22 KB. The same code works on ESP32 and S3.
   - This is the same fragmentation failure our AGENTS.md radio-memory-ordering rule describes. A C6
     wand already needs about 78 KB contiguous before ESP-NOW starts, and about 40 KB contiguous to
     `compile()` a game afterwards.
4. **Measured on an M5StickS3, 2026-10-06 (§6): one S3 carried the Splat-hub workload.** The test used
   4 Splats and one MockWand peer. Splat links, acknowledged traffic and buffers held up:
   - **Splat links:** 0 disconnects and 0 failed writes.
   - **ACKed unicast:** 100% delivered.
   - **Bulk transfer:** 32–44 KB/s.
   - **Button handling:** unchanged by ESP-NOW load.
   - **Broadcast receive did not hold up:** 98% → 93% → 85% for 1 → 2 → 4 Splats. Lost broadcasts never
     reached the driver buffer; they were lost on air.
   - **Turning BLE on cost a lot of internal memory:** it cut the largest internal heap block from 115 KB
     to 47 KB.

   The modem exists for other documented reasons: contiguous DRAM, brown-out, and the reset needed to
   switch radios.
5. **Our two-controller design is the industry pattern, not a workaround.**
   - Espressif's own recommendation for simultaneous reception is a dual-SoC design (S3 + H2) with
     separate antennas, optionally coordinated with PTA GPIOs.
   - Espressif's connectivity co-processor framework, esp-hosted, has **no ESP-NOW support yet**
     (feature request open since Nov 2024).
6. **Outside-the-box options that really are concurrent** all mean leaving ESP-NOW for at least one
   link:
   - an nRF24L01+ on SPI (about $2, has a MicroPython driver);
   - a sub-GHz SX1262 (separate band);
   - nRF5340 + nRF7002 (separate radios, C/Zephyr only);
   - a Linux hub speaking ESP-NOW natively through monitor-mode injection (`Linux-ESPNOW`).

   The one cheap option that keeps everything on one chip is to **drop WiFi entirely and use BLE
   advertising as the broadcast bus**. Section 5 covers each option.

**Recommendation.** A single **S3** hub is viable for the Splat Companion on the bench evidence, with
three conditions:
- every wand→hub message that matters is ACKed unicast (broadcasts are lost 2–15% of the time);
- `rxbuf` is at least 16 KB, and below 32768;
- the result is not carried over to the C6. It remains untested there, and the memory numbers make it
  unlikely to fit.

Keep the C6 + C6 modem design until an S3 hub has run real games and a 30-minute soak.

---

## 1. Our platform's requirements

Paths are relative to `Bag3/Code/BroadcastCode/`. "SC" means `SplatCompanion/`.

### 1.1 Which device uses which radio

| Device | Chip | Radios |
|---|---|---|
| MockWand | XIAO ESP32-C6, no PSRAM | ESP-NOW (normal boot); WiFi STA only in a separate pull-mode boot. No BLE (`MockWand/lib/hubtype.py:35`). External u.FL antenna (`espnow_manager.py:39`). |
| Splat Companion hub | XIAO C6 | BLE central, up to 4 Splats. ESP-NOW only via UART to the modem (`SC/Companion/README.md:28-31`). WiFi STA in pull boots. Onboard antenna (`SC/Companion/boot.py:20-22`). |
| Splat modem | XIAO C6 | ESP-NOW only, on `STA_IF`. UART1 at 921600 baud on GPIO16/17 (`SC/ESPNowModem/main.py:37,57-64`). Onboard antenna (`main.py:25`). |
| EspnowModem proof of concept | 2× M5StickS3 (S3 + PSRAM) | ESP-NOW modem plus a UART host at 921600 on GPIO43/44 (`EspnowModem/README.md:3,35`) |
| Broadcast Dial / Box | StampS3A / StickS3 | WiFi SoftAP for code pulls (channel 1), USB serial JSON. No ESP-NOW, no BLE. |

**The Splat Companion is the only device that needs BLE and ESP-NOW at the same time.** The Dial and
Box need WiFi SoftAP plus USB serial. A future Dial that sends over ESP-NOW (`BDialEUM` is named in a
doc but doesn't exist yet) would be a WiFi-AP + ESP-NOW case. That is a different coexistence
problem: same Wi-Fi radio, channel-locked to the AP.

### 1.2 ESP-NOW traffic

| Item | Value | Source |
|---|---|---|
| Payload | ≤ 250 B (v1). Code chunks are 245 B data + 5 B header. | `SC/Companion/lib/eum_proto.py:65`; `EspnowModem/host/code_sender.py:35` |
| Code-transfer windowing | Window of 8 chunks (max 16). Window re-requested after 400 ms. Gives up after 12 windows with no progress. | `EspnowModem/MockWandEUM/lib/espnow_code.py:41-55` |
| Sessions / peers | Up to 6 transfer sessions; peer table about 20; request jitter 0–300 ms; busy retry 2 s | `code_sender.py:42-44`; `EspnowModem/README.md:164-167` |
| Game messages (splatecho) | Unicast, 3 tries; add-request resent every 1 s; wand hello every 1 s; wand loop 20 ms | `SC/Companion/splatecho.py:113-114`; `MockWand/splatecho.py:60-64` |
| Status auto-reply | 16 slots × 180 ms after a 400 ms base, spreading replies over 0.4–3.1 s | `MockWand/lib/espnow_manager.py:26-29` |
| Driver rxbuf | Wand: MicroPython default, 526 B (about 2 frames). EUM wand: 4096 B. Modem: 8192 B. | `MockWand/lib/espnow_manager.py:119-131`; `SC/ESPNowModem/main.py:19` |
| TX-queue-full retry | One retry after 30 ms | `MockWand/lib/espnow_manager.py:32` |
| Channel | Never set (default) | — |

**Measured throughput:**
- Wand to wand, no modem: about 23 KB/s.
- Through the modem, windowed: 5.8–10.7 KB/s.
- Raw broadcast push through the S3 modem: about 22.6 KB/s.
- One game (36–40 KB max) currently takes about 2–4 s on air.

Sources: `docs_and_design/2026-09-30-transfer-comparison-results.md:28-44`,
`2026-09-26-eum-bench-results.md:38-54`.

### 1.3 BLE traffic (Splat hub)

| Item | Value | Source |
|---|---|---|
| Connections | Up to 4 (`CONFIG_BT_NIMBLE_MAX_CONNECTIONS`). 1, 2 and 4 tested. | `SC/Companion/splat_hub.py:32`; README:185-190 |
| Scan | 30 ms / 30 ms (100% duty), only while no Splat is connected; discovery ≤ 8 s | `splat_hub.py:34-35` |
| Connection interval / MTU | Stack defaults. `gap_connect` passes no interval arguments; never measured. | `SC/Companion/lib/ble_splat.py:170` |
| Writes | 2–9 B. Switch read every 150 ms, keepalive every 2.5 s. About 7 writes/s per Splat, about 27/s with 4. | `SC/Companion/splat_api.py:61-62` |
| Write pacing | ≥ 50 ms between commands to one Splat (a Splat drops commands 20–30 ms apart) | `splat_link.py:36-41` |
| Notifications | About 5/s per Splat (measured) | `2026-09-29-splat-hub-logs/10_bench_3c_39209e3.txt` |

The BLE load is **tiny in bandwidth** (well under 1 KB/s) but **sensitive in timing**: 4 connections
must each keep their connection events alive.

### 1.4 UART modem link (the cost of two controllers)

| Item | Value | Source |
|---|---|---|
| Frame | `A5 5A, type, seq, len(2), payload ≤ 1100, crc8`, strict request/reply | `EspnowModem/README.md:72-76` |
| Polling | FETCH every 5 ms, ≤ 4 records per FETCH, ≤ 8 messages handled per hub step | `SC/Companion/companion.py:36-37`; `eum_proto.py:66` |
| Timeouts | Reply 100 ms, sync send 300 ms, link down after 3 timeouts, reconnect every 1 s | `SC/Companion/lib/espnow_manager.py:36-49` |
| Buffers | Host UART RX 1536 B. Modem UART RX 2048 B. Modem ring 64 × 260 B (C6) / 128 slots (S3), drops the oldest when full. | same; `SC/ESPNowModem/main.py:59,65-67` |

### 1.5 Memory (the constraint that matters most on C6)

- C6 wand, largest free IDF block: **77,824 B before ESP-NOW init**, 41,984 B after (4 KB rxbuf),
  40,960 B steady (`eum-bench:30-31,85`).
- A game's `compile()` needs about 40–41 KB contiguous; the per-game limit is 36–40 KB
  (`transfer-comparison:55-60`).
- The WiFi stack costs about 49 KB of heap (224.0 KB free without it, 175.0 KB with it; commit
  `3bd3f27`).
- NimBLE's heap cost per connection has **never been measured** in our tree.

### 1.6 What our own measurements say about interference

- **Splat Echo freeze** (`2026-09-30-splatecho-freeze-results.md`). The link test sent 300 broadcasts
  20 ms apart. Wands missed 6 and 16 with no Splats connected, and 8 and 32 with 4 Splats connected
  and polled. The data could not separate a BLE effect from noise. The real cause was the modem
  transmitting on an external-antenna path with no antenna fitted. On the onboard antenna, 0/300 were
  lost. After the switch to ACKed unicast, 117/119 sends were ACKed first try.
- **Two-Splat flapping** was a software bug: calling `BLE().active(True)` on a running stack restarts
  it. It was not RF interference.
- These results are on **separate** radios. §6 has the single-chip measurements.

### 1.7 Fitting our traffic onto one time-sliced chip

- **ESP-NOW RX** would be available about 50% of the time while Splats are connected.
  - Our protocol has moved to ACKed unicast with retries, and the code transfer re-requests windows.
    Both tolerate this; expect transfer throughput to drop roughly by half or more.
  - Any remaining **broadcast** (status probes, hello) needs repetition faster than the ~100 ms
    coex period, or conversion to unicast.
  - The 526 B rxbuf on wands is irrelevant here, because only the hub would be single-chip.
- **BLE** would lose connection events that fall in the WiFi slice. Writes are already paced at
  ≥ 50 ms, so an extra ≤ 50 ms of latency per command is plausible. Supervision timeouts must comfortably
  exceed the gaps.
- **Memory on C6** is the most likely failure. NimBLE + WiFi + ESP-NOW + a 40 KB contiguous
  `compile()` on a no-PSRAM C6 is the configuration MicroPython #18859 reports failing. The S3 has more
  internal RAM and PSRAM, and #18859 reports it working.

---

## 2. Espressif's documented behaviour

### 2.1 One RF path on every chip

- Coexistence guide (shared across all targets):
  <https://docs.espressif.com/projects/esp-idf/en/latest/esp32c6/api-guides/coexist.html>, source
  <https://raw.githubusercontent.com/espressif/esp-idf/master/docs/en/api-guides/coexist.rst>.
  It says: "Each chip has only one RF path, shared by these two or three modules."
- C5: "This shared RF path is used whether Wi-Fi operates on 2.4 GHz or 5 GHz."
  <https://docs.espressif.com/projects/esp-idf/en/latest/esp32c5/api-guides/coexist.html>
- Antenna diversity (`esp_phy_set_ant_gpio` / `esp_phy_set_ant`, up to 16 antennas behind an
  external switch, e.g. ESP32-WROOM-DA) selects antennas for **one** RF chain. It is not
  concurrency. <https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-guides/phy.html>

### 2.2 The Wi-Fi + BLE support table (identical across C6, S3, C5 and others)

| | BLE scan | BLE advertising | BLE connected |
|---|---|---|---|
| ESP-NOW TX | Y (stable) | Y | Y |
| ESP-NOW RX | S (stable in STA mode only) | S | S |
| SoftAP connected | C1 (unstable) | C1 | C1 |

### 2.3 How the time-slicing works

- A coex period is split into a WiFi slice and a BLE slice. Each module has priority inside its own
  slice.
- With WiFi idle, BLE owns the RF.
- With WiFi CONNECTED and BLE CONNECTED, the split is about 50/50.
- Some BLE events are promoted to high priority and preempt the WiFi slice.
- ESP-NOW is a WiFi "connectionless module": it receives during a `Window` every `Interval`.
  Espressif recommends leaving both at default under coex, because custom values steal BLE time.
  <https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-guides/wifi-driver/wifi-performance-and-power-save.html>
- Under coex, WiFi sleeps outside its slice **even with `WIFI_PS_NONE`**. In MicroPython,
  `PM_NONE` does not buy full-time RX.
- `CONFIG_ESP_COEX_SW_COEXIST_ENABLE` defaults to `y` when both stacks are built, which includes
  MicroPython's BLE builds.
  - Turning it off falls back to hardware "BT priority" mode, which makes WiFi unstable.
  - `esp_coex_preference_set()` is deprecated.
  - Neither setting is reachable from MicroPython without a custom firmware build.

### 2.4 Tuning guidance from Espressif

- **BLE scan:** under software coex, set scan **interval = window**, because coex already truncates
  windows. The older "window < interval" advice is from the hardware-coex era.
  <https://docs.espressif.com/projects/esp-faq/en/latest/software-framework/coexistence.html>
- **BLE connection interval:** an Espressif engineer in esp-idf #15833 advised:
  - Intervals above about 50 ms always request the RF at high priority.
  - Avoid multiples of the 102.4 ms beacon interval; use (n+0.3)×102.4 ms.
  - Keep supervision timeout ≥ 10× the interval.

  <https://github.com/espressif/esp-idf/issues/15833>
- **Two radios:** "we recommend using a dual-SoC solution (e.g., ESP32-S3 + ESP32-H2) with separate
  antennas. This setup enables simultaneous reception." Espressif says this about 802.15.4, but the
  physical limit is the same for BLE.

### 2.5 Published numbers

- ESP-NOW on C6: about 400 kbps close range, under 20 ms latency to 300 m.
  <https://developer.espressif.com/blog/esp-now-for-outdoor-applications/>
- BLE ESP32-to-ESP32: about 700 kbps on 1M PHY, about 1.4 Mbps on 2M PHY.
  <https://docs.espressif.com/projects/esp-faq/en/latest/software-framework/bt/ble.html>
- Espressif publishes **no** Wi-Fi/BLE coexistence throughput table that we could find.

---

## 3. Public reports of one chip doing both

| Report | Setup | Outcome |
|---|---|---|
| [esp-idf #16069](https://github.com/espressif/esp-idf/issues/16069) | ESP32, Bluedroid advertising + ESP-NOW **broadcast** | Random 3–20 s gaps in reception. Espressif explained the 100 ms cycle split 50/50, so a 100 ms broadcast period keeps landing in the BLE slice. A 20 ms period helped; about 8/25 arrived in their log. **Unicast with resend avoided the problem.** The reporter moved to BLE Mesh. |
| [esp-idf #17874](https://github.com/espressif/esp-idf/issues/17874) (open since Nov 2025) | ESP32-WROOM-32E, NimBLE scanning + ESP-NOW | 98–100% ESP-NOW RX loss on the reporter's hardware, even with Espressif's sdkconfig. Espressif could not reproduce it on a WROVER-E ("some packets lost, it works"). Only alternating the two protocols worked for the reporter. |
| [esp-idf #14904](https://github.com/espressif/esp-idf/issues/14904) | ESP32, NimBLE + ESP-NOW RX | BLE message loss appeared after IDF 4.3 → 5.x. Disabling SW coex fixed BLE, at WiFi's expense. |
| [esp-idf #15833](https://github.com/espressif/esp-idf/issues/15833) | ESP32-C3, BLE + WiFi | 16 BLE disconnects in 6 h. Espressif supplied a patched controller lib (not merged); one disconnect remained. |
| [arduino-esp32 #10900](https://github.com/espressif/arduino-esp32/issues/10900) | ESP32-C3 | ESP-NOW RX stopped after BLE init. A community member suggested `WIFI_MODE_APSTA`; the reporter never confirmed it. This contradicts Espressif's table (RX stable in STA only), so treat it as unverified. |
| [micropython #18859](https://github.com/micropython/micropython/issues/18859) | C3/C6, MicroPython 1.27, BLE + WiFi + ESP-NOW | `WiFi Out of Memory`; largest IDF block about 22 KB after BLE init. **Works on ESP32 and S3.** Converted to a discussion, no fix. |
| Bag2 Splat Companion (ours) | One C6, BLE + ESP-NOW, one Splat | Worked; not currently active (`Bag2/Code/Splat Companion/main.py:154-183`). |
| Jan-2026 wand (ours) | One C6 | Time-sliced by hand: ESP-NOW stayed off during BLE and was switched on for a ~5 ms check every 3 s (`Bag2/Code/Splat Companion/legacy_jan26_wand_*`). |

**Pattern:**
- Low-rate, ACKed, retried ESP-NOW alongside a modest BLE load works on chips with enough RAM.
- Broadcast-dependent designs and RAM-tight chips (C3/C6) are where single-chip fails.

---

## 4. Two-chip boards, and esp-hosted

| Platform | What it is | Concurrent? | Relevance |
|---|---|---|---|
| [ESP Thread Border Router board](https://docs.zephyrproject.org/latest/boards/espressif/esp_threadbr/doc/index.html) | S3 (WiFi) + H2 (802.15.4/BLE), each with its own antenna, UART/SPI link plus PTA GPIOs | **Yes** (two RF chains) | Espressif's reference for exactly our pattern |
| [esp-hosted-mcu](https://github.com/espressif/esp-hosted-mcu) | Any ESP as a co-processor over SDIO/SPI/UART for WiFi, BLE HCI, Thread | Same as the co-processor | **No ESP-NOW** ([#19](https://github.com/espressif/esp-hosted-mcu/issues/19), "on our roadmap"). ESPHome has a send-only shim. Has an [external-coex PTA example](https://github.com/espressif/esp-hosted-mcu/blob/main/examples/ext_coex/README.md). |
| ESP32-P4-Function-EV / M5Stack Tab5 | P4 (no radio) + C6 via esp-hosted | No (the C6 is still one radio) | Worse fit than what we have |
| Arduino UNO R4 WiFi / Nano RP2040 Connect | Host MCU + ESP32-S3 / NINA-W102 (an ESP32) | No | The same one-radio limit behind an extra hop |
| ESP32-E22 (announced Jan 2026) | Tri-band Wi-Fi 6E + BLE 5.4 co-processor (PCIe/SDIO) | Unknown | RF architecture and ESP-NOW support unconfirmed; not practical |

**An ESP32-H2 as the BLE side.** MicroPython has `ESP32_GENERIC_H2` / `M5STACK_NANOH2` builds with
BLE enabled and WiFi/ESP-NOW compiled out. An H2 (BLE central) plus a C6 (ESP-NOW) is the
Espressif-sanctioned topology. It is what we already have with C6 + C6, at slightly lower cost and
power. It adds nothing functionally, and moving the hub would be churn.

**The one caveat with any two-chip design.** Two 2.4 GHz transmitters centimetres apart can desensitise
each other. Espressif adds PTA arbitration for this. We haven't seen it on the Splat hub; the 0/300
onboard-antenna result above is evidence against it being a problem at our power levels.

---

## 5. Outside the box

| Option | Truly concurrent? | MicroPython | Cost | Main tradeoff |
|---|---|---|---|---|
| **A. BLE advertising as the broadcast bus**: WiFi off; every device sends non-connectable adverts with a sequence number and scans passively, while the hub keeps its Splat connections | One radio, but one stack schedules everything (no WiFi/BLE arbiter) | Legacy 31 B adverts only. `gap_advertise` has no extended advertising (BLE 5 allows 255 B, chained to 1650 B, in C/IDF). | $0 | Delivery is probabilistic and latency is tens to hundreds of ms. Scan duty drops while connections are active. Code transfer over 31 B adverts is impractical. Breaks ESP-NOW compatibility with every wand. |
| **B. nRF24L01+ on SPI**: the ESP32 does BLE; the nRF24 replaces the ESP-NOW modem MCU | **Yes** (separate front end); both still on 2.4 GHz, so channel planning matters | Driver in the MicroPython repo (`drivers/nrf24l01`) | about $1–3 | 32 B payloads; clone quality varies; every peer needs one, since it can't talk ESP-NOW |
| **C. SX1262 sub-GHz (LoRa or FSK)** | **Yes**, and a different band (868/915 MHz), so no in-band interference | [micropySX126X](https://github.com/ehong-tl/micropySX126X); micropython-lib driver [has issues](https://github.com/micropython/micropython-lib/issues/870) | about $8–15 | LoRa airtime is 30–60 ms per small packet (FSK is much faster); bigger antenna; good for range, not twitchy play |
| **D. Linux hub speaking ESP-NOW natively**: Raspberry Pi + an injection-capable USB WiFi adapter running [Linux-ESPNOW](https://github.com/thomasfla/Linux-ESPNOW) | Yes, if the Pi's onboard BT does BLE and the USB adapter does ESP-NOW | No (C, root, monitor mode) | Pi + about $15 adapter | Could replace the Live_Page teacher-hub ESP32 bridge. ESP-NOW is a documented vendor action frame (OUI 18:fe:34), so wands are unaffected. Expect channel-locking and permissions friction. |
| **E. nRF5340 + nRF7002** | **Yes**: separate radios with a PTA interface | No (Zephyr C) | DK about $60+ | ESP-NOW is plausible via [raw TX](https://nrfconnectdocs.nordicsemi.com/ncs/latest/nrf/samples/wifi/raw_tx_packet/README.html) + [monitor mode](https://nrfconnectdocs.nordicsemi.com/ncs/latest/nrf/samples/wifi/monitor/README.html), but nobody has demonstrated it |
| **F. Pico W / Pico 2 W (CYW43439) + nexmon injection** | No (WiFi+BT combo, shared antenna) | No | about $6 | [nexmon](https://github.com/seemoo-lab/nexmon) supports injection on the 43439, but there's no example; a research spike only |
| **G. ESP32-C5 with ESP-NOW on 5 GHz** | No (one RF path, time-sliced) | Yes (1.27, `SEEED_XIAO_ESP32C5`) | about $7–10 | Removes 2.4 GHz air contention between our own ESP-NOW and BLE, but not the scheduler split. **Every peer must be a C5** to hear 5 GHz. |
| **H. Nordic ESB + BLE on nRF52/53/54** | No (one radio, Nordic's MPSL timeslot scheduler) | Weak: nRF MicroPython BLE central is immature | about $10 | The cleanest single-chip design on paper; C only, drops ESP-NOW |
| **I. Raw 802.15.4 on C6/H2** | No (shares the RF on C6) | No module | — | No better than ESP-NOW; Espressif marks some 802.15.4 + BLE-scan combinations unsupported |

**If a truly concurrent second radio is the goal, B (nRF24L01+) is the cheapest experiment.**
It is a dumb SPI transceiver in place of a second MCU and runs in MicroPython today. The price is
ESP-NOW compatibility with the rest of the playground.

**D (a Linux ESP-NOW hub) is the most interesting way off ESP32 for one node.** The wire format is
documented and stable, so wands don't change.

---

## 6. Bench results: one M5StickS3 as a single-chip Splat hub (2026-10-06)

Scripts and raw logs are in [2026-10-06-coex-bench/](2026-10-06-coex-bench/).

### Setup

**Hub:**
- M5StickS3 (ESP32-S3-PICO-1, 8 MB PSRAM), MicroPython 1.27.0 (`M5STACK_StickS3` build).
- ESP-NOW was brought up first: STA, channel 1, `rxbuf` 8192.
- Then BLE, driven by the shipped `SplatHub` / `SplatGroup` code from `SplatCompanion/Companion/`:
  - stack-default connection interval;
  - 50 ms write pacing, switch read every 150 ms, keepalive every 2.5 s;
  - plus a color write to every connected Splat once a second.

**Peer:** MockWand C6 `A0:F2:62:87:B4:30` on its external antenna, about 1–2 m away, running
`coex_peer.py`, a responder that echoes pings and sends broadcast bursts on request.

**Not run:** the BLE-idle and BLE-off phases. The soak was stopped at 3 minutes and those two phases
were never reached, so this pair has no no-BLE baseline. The closest comparison is splatecho run 07: a
C6 modem on the onboard antenna lost 0/300 broadcasts.

### ESP-NOW with 1, 2 and 4 Splats connected (300 frames, 20 ms apart, per test)

| | 1 Splat | 2 Splats | 4 Splats |
|---|---|---|---|
| Unicast ping, ACKed at S3 | 300/300 | 300/300 | 300/300 |
| Wand's echo received back (wand→S3 ACKed unicast) | 300/300 | 300/300 | 300/300 |
| Ping round trip, ms p50 / p95 / max | 25 / 85 / 151 | 25 / 74 / 92 | 39 / 104 / 145 |
| `send()` blocking, ms p50 / max | 1.9 / 7.8 | 1.9 / 7.0 | 1.9 / 7.8 |
| **Broadcast wand→S3 received** | **98.3%** (longest gap 1) | **93.3%** (2) | **84.7%** (3) |
| Broadcast S3→wand received | 100% | 100% | 100% |
| 36 KB bulk, 245 B ACKed chunks | 43.6 KB/s | 39.4 KB/s | 32.2 KB/s |
| Bulk chunks needing a retry | 0 | 0 | 0 |
| Splat drops / failed writes | 0 / 0 | 0 / 0 | 0 / 0 |
| Driver `rx_dropped` | 0 | 0 | 0 |

- **Soak, 4 Splats, 180 s:** pings every 100 ms, 1801/1801 ACKed, 1800 echoed back (the last was in
  flight at stop). 0 Splat drops, 0 failed writes.
- **Memory, largest free internal (IDF) block:**
  - 155,648 B at start;
  - 114,688 B after ESP-NOW;
  - **47,104 B after `BLE().active(True)`**, unchanged after that through every phase.
- **Memory caveat:** on the S3, the MicroPython heap is in PSRAM, so the C6's 40 KB `compile()` limit
  doesn't apply here. BLE took about 67 KB of the largest internal block. A C6 wand has about 41 KB
  left after ESP-NOW, so the same order is unlikely to fit there, which matches MicroPython #18859.
  The C6 was not tested.

### Receive buffer (4 Splats connected and polled, 250-byte frames)

The wand broadcast 100 frames 20 ms apart. The loop read ESP-NOW for 20 ms, then blocked for the
stall time without reading or polling Splats, and repeated.

| `rxbuf` | stall 0 | 50 | 100 | 200 | 500 | 1000 ms | `rx_dropped` | most frames held | back-to-back burst held |
|---|---|---|---|---|---|---|---|---|---|
| 8192 | 85% | 81% | 92% | 88% | 78% | 65% | +13, at the 1000 ms stall only | 33 | 31 of 150 |
| 16384 | 83% | 96% | 96% | 93% | 82% | 85% | 0 | 46 | 62 of 150 |
| 30000 | 85% | 81% | 79% | 84% | 93% | 97% | 0 | 51 | 114 of 150 |
| 32768 | — | | | | | | | | |

- **32768 does not work.** The first `irecv()` after activating with 32768 raised
  `ValueError: ESPNow.recv(): buffer error`. 30000 worked, so the limit sits between the two.
- **Receive rate is on-air loss, not buffer loss.** It varies between 78% and 97% with no trend
  against `rxbuf` or stall. `rx_dropped` counts the buffer's own losses, and it is non-zero only when
  a stall outran the buffer.
- **Capacity is about `rxbuf` / 264 B per 250-byte frame.** At 20 ms traffic, 8 KB rides out about
  600 ms of not reading, 16 KB over 1 s, and 30 KB about 2 s.

### Splat buttons (4 Splats, a person pressing)

| | Quiet (ESP-NOW up, no traffic) | Loaded (wand broadcasting 250 B every 20 ms) |
|---|---|---|
| Presses detected per Splat | 5, 5, 10, 6 | 5, 5, 3, 7 |
| BLE IRQ → game loop, ms p50 / p95 / max | 2 / 15 / 17 | 3 / 88 / 88 |
| `readSwitches` write → notify, ms (n) p50 / p95 / max | (542) 42 / 143 / 182 | (515) 40 / 144 / 191 |
| ESP-NOW broadcast received during the phase | — | 1470/1500 (98.0%) |
| Splat drops / failed writes | 0 / 0 | 0 / 0 |

- **Press counts are unconfirmed.** They have not yet been checked against the presses the person
  actually made.
- **Press-to-light time** (physical press to Splat colour change) was not measured with a camera.
  It is the BLE notify time plus the IRQ-to-loop time plus a write.
- **The BLE round trip is the same quiet or loaded, about 40 ms typical.** ESP-NOW load did not slow
  the Splat link.
- **The 88 ms IRQ-to-loop maximum under load** is the game loop busy for one iteration: draining
  ESP-NOW, plus 50 ms write pacing after a press's color write. It is not radio time.

### One Splat: BLE alone vs BLE + ESP-NOW (`coex_one.py`, log `one1.log`)

One Splat. The radio was fresh from a reset, so phase A ran with WiFi/ESP-NOW never started. The
person pressed through each 30 s phase, and a press turned the Splat red until release.
`rxbuf` was 16384.

| | A: BLE only | B: ESP-NOW idle | C: ESP-NOW loaded (wand 250 B bcast every 20 ms, S3 pings every 100 ms) |
|---|---|---|---|
| Presses detected | 39 | 35 | 47 |
| BLE IRQ → game loop, ms p50 / p95 / max | 1 / 2 / 9 | 1 / 12 / 23 | 1 / 5 / 7 |
| BLE IRQ → red write returned, ms p50 / max | 2 / 53 | 2 / 72 | 3 / 50 |
| `readSwitches` write → notify, ms (n) p50 / p95 / max | (192) 112 / 147 / 149 | (149) 42 / 129 / 145 | (132) 16 / 94 / 153 |
| ESP-NOW | — | — | bcast 1449/1500 (96.6%); pings ACKed 300/300 |
| Splat drops / failed writes | 0 / 0 | 0 / 0 | 0 / 0 |

- **The S3's own path is fast in every phase.** A press is seen in the loop in about 1 ms, and the
  red write is handed to the stack in 2–3 ms. The maximums of 50–72 ms are `ble_splat`'s 50 ms
  per-Splat write pacing.
- **ESP-NOW did not slow the BLE round trip.** The `readSwitches` round trip got *shorter* as radio
  activity rose, from 112 to 42 to 16 ms typical. That is not explained here. The metric times a
  write to the next notify of any kind, and the connection interval was not logged; no conn-update
  event fired.
- **Color writes are write-without-response** (`ble_splat._write_command` calls `gattc_write` with
  the default mode 0). "0 failed writes" means the local stack accepted every write, not that the
  Splat applied it. Observed misses (a Splat that didn't change color) are not visible in these
  numbers.
- **Possible cause of those misses (not tested):** pacing is applied at hand-off to the stack.
  Commands held by the controller could reach a Splat together, and a Splat drops a command that
  follows another by 20–30 ms.

### Interactive demo: wand button ↔ Splats through one S3 (`demo_hub.py`, `demo_wand.py`)

**Setup:**
- The S3 ran BLE to the Splats and ESP-NOW to the wand at the same time, with `rxbuf` 16384.
- One Splat was lit in its unit colour.
- A wand button press sent an ACKed unicast "next". The hub lit the next connected Splat and told the
  wand, whose LEDs took that colour.
- Pressing the lit Splat sent "hit" to the wand (tone plus success sound). Pressing an unlit Splat sent
  "miss" (low buzz).
- Every message in both directions was ACKed unicast with up to 3 tries.
- 3 Splats connected (Splat 3 never joined). About 3 minutes of play by a person. Logs:
  `demo_hub.log`, `demo_wand.log`.

| | Result |
|---|---|
| Wand button → hub ("next") | 130 presses, all ACKed first try (wand `ACK=False`: 0) |
| Hub → wand ("lit", "hit", "miss") | every send ACKed first try; "lit" sends took ≤ 7 ms |
| Splat presses | 55 hits, 29 misses |
| Splat press IRQ → wand ACK, ms (n=68) p50 / p95 / max | 5 / 18 / 62 |
| Hub handling of "next" (old Splat off, new Splat on, tell wand), ms (n=130) p50 / p95 / max | 21 / 53 / 54 |
| Splat disconnects | 0 |

- **Timing coverage:** 16 of the 84 presses had no IRQ timestamp, because the raw event was consumed
  inside the same `poll()` call that the timer reads before.
- **Not measured:** physical press → BLE notify, and colour write → light change, both on the Splat
  side. Observations of a missed or late Splat light were not recorded for this run.

### Observations and open questions

- **Broadcast loss tracks BLE *write* activity more than connection count.** It was 85% in the
  4-Splat tests, which wrote a color to every Splat each second. It was 98% in the loaded button
  phase, which wrote only on a press. This is a hypothesis from two conditions, not a controlled
  comparison.
- **Against the proposed pass criteria:**
  - zero disconnects: yes, but over 3 minutes plus about 3 minutes of tests, not 30 minutes;
  - ≥ 99% unicast delivery: yes, 100%;
  - code transfer ≥ 8 KB/s: yes, 32 KB/s or more;
  - `idf_largest` ≥ 40 KB: 47 KB. That is a C6 criterion; the S3 compiles from PSRAM.
- **Not tested:**
  - C6 as the single chip;
  - a 30-minute soak;
  - a no-BLE baseline for this pair;
  - more than one wand;
  - real game code (`splatecho`) on the single chip;
  - a non-default BLE connection interval;
  - a WiFi pull boot on the same device;
  - camera-timed press-to-light latency.

---

## Appendix: doc drift found while reading (not fixed)

- `SC/Companion/main.py:4-5` still describes UART on GPIO0/1 with an M5StickS3 modem. The README and
  `hubtype.py` say GPIO16/17 with a C6 modem.
- `docs_and_design/2026-09-30-known-issues.md:56` assumes the Splat Companion uses the external
  antenna. `SC/Companion/boot.py` selects onboard.

## Source notes

- Codebase numbers come from a read of the Bag3 tree on branch `Chat_to_Tap_Doggle`, 2026-10-06.
- Web sources are linked inline.
- esp32.com forum threads were bot-blocked, so points from them (the APSTA workaround, older scan
  advice) come from search snippets only.
- These were not measured: C5 5 GHz ESP-NOW + BLE behaviour (inferred from Espressif's shared-RF
  statement), ESP32-E22 RF architecture, and ESP-NOW over nRF7002 raw TX.
- Prices are approximate.
