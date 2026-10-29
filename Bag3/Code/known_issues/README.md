---
title: Bag3 known issues index
scope: Bag3/Code
---

# Bag3 known issues

Known-issue notes for Bag3 code. Check here before changing firmware, serving/pull code or
ChatBroadcast. Entries may already be resolved; confirm against the current code.

Each file starts with YAML front matter: `title`, `date`, `status`, `devices`, `components`,
`code` (paths the issues concern), `open` (open items), `keywords`, and `aliases` (former
filenames). Search front matter with `grep -l '<term>' Bag3/Code/known_issues/*.md`.

## Files

| File | Area | Status | Former name |
|---|---|---|---|
| [2026-09-01-bbox-usb-reboots.md](2026-09-01-bbox-usb-reboots.md) | BroadcastBox firmware power/resets | open | `BBoxFirmware/known_issue.md` (restored from `fc25de7^`) |
| [2026-09-04-chatbroadcast.md](2026-09-04-chatbroadcast.md) | ChatBroadcast gallery, simulator, game size | partly outdated | `ChatBroadcast/9-4-known_issues.md` |
| [2026-09-29-chatbroadcast.md](2026-09-29-chatbroadcast.md) | ChatBroadcast roles, remix, Dial load | open | `ChatBroadcast/9-29-known_issues.md` |
| [2026-09-30-known-issues.md](2026-09-30-known-issues.md) | Code pull game size, `stats.log` | open | `docs_and_design/2026-09-30-known-issues.md` |
| [2026-10-23-distribute-code.md](2026-10-23-distribute-code.md) | Status scan, Dial distribute code, per-device differences | open (untested on hardware) | — |
| [2026-10-28-ips096-colour-levels.md](2026-10-28-ips096-colour-levels.md) | IPS096 Display mid-tone colours, panel lookup | workaround | — |
| [2026-10-28-capsule-pn5180.md](2026-10-28-capsule-pn5180.md) | PN5180 on M5Capsule: corrupted replies, Splat tags | open | — |
| [2026-10-28-mockwand-idle-power.md](2026-10-28-mockwand-idle-power.md) | MockWand idle/sleep battery drain, power LED, diffuser | partly fixed | — |
| [2026-10-28-crowpanel5-display.md](2026-10-28-crowpanel5-display.md) | CrowPanel5 Display touch I2C pins, soft-reset lockup, RGB drift | open (workarounds) | — |

## By topic

| Topic | Files |
|---|---|
| Game size / wand `compile()` heap limit | 2026-09-04, 2026-09-30 |
| Heap fragmentation, IDF memory, radio bring-up | 2026-09-01 |
| Resets, brownout, watchdog | 2026-09-01 |
| RGB panels, touch, native USB pins | 2026-10-28 (CrowPanel5) |
| NFC reader (PN532, WS1850S, PN5180) | 2026-09-01, 2026-10-28 (PN5180) |
| Dial / Box code serving, wand pull | 2026-09-30, 2026-09-29, 2026-10-23 |
| ChatBroadcast example gallery and remixing | 2026-09-04, 2026-09-29 |
| Simulator vendored game sources | 2026-09-04 |
| Multi-role games | 2026-09-29, 2026-10-23 |
| Status poll / `kind`, find device, distribute code | 2026-10-23 |
| Display colour response, ST7789 mid-tones | 2026-10-28 (ips096) |
| Battery drain, sleep, power LED, LED brightness | 2026-10-28 (mockwand-idle-power) |

## By device

| Device | Files |
|---|---|
| BroadcastBox | 2026-09-01, 2026-09-29, 2026-09-30 |
| BroadcastDial | 2026-09-29, 2026-09-30, 2026-10-23 |
| Wands / MockWand (XIAO ESP32-C6) | 2026-09-04, 2026-09-29, 2026-09-30, 2026-10-23, 2026-10-28 (mockwand-idle-power) |
| IconDisplay | 2026-09-30, 2026-10-23 |
| M5Paper Remote (Bag3) | 2026-10-23 |
| IPS096 Display (bench) | 2026-10-28 (ips096) |
| M5Capsule + PN5180 (bench) | 2026-10-28 (capsule-pn5180) |

## Firmware comments

`known_issue.md` in BBox and BDial firmware comments (`bbox_server.py`, `bdial_server.py`,
`reset_log.py`) refers to `2026-09-01-bbox-usb-reboots.md`.

## Adding a note

Name new files `YYYY-MM-DD-<topic>.md`, include the front matter fields above, and add a row here.
