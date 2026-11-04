# ESP-NOW Remote Commands

## Commands

| Action      | Message         |
|-------------|-----------------|
| Pause       | `FD_FREEZE`     |
| Play        | `FD_GO`         |
| Next Song   | `FD_NEXT`       |
| Prev Song   | `FD_PREV`       |
| Volume Up   | `FD_VOL_UP`     |
| Volume Down | `FD_VOL_DOWN`   |

Volume has 8 levels: 0% → 10% → 25% → 40% → 55% → 70% → 85% → 100%

## Sender Code (for the remote ESP32)

```python
import network
import espnow

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

e = espnow.ESPNow()
e.active(True)

# Broadcast to all devices (or replace with player's MAC)
peer = b'\xff\xff\xff\xff\xff\xff'
e.add_peer(peer)

# Send a command
e.send(peer, "FD_GO")
e.send(peer, "FD_FREEZE")
e.send(peer, "FD_NEXT")
e.send(peer, "FD_PREV")
e.send(peer, "FD_VOL_UP")
e.send(peer, "FD_VOL_DOWN")
```

## Quick Test from REPL

Paste this into the remote ESP32's REPL to test each command:

```python
import network, espnow
w = network.WLAN(network.STA_IF); w.active(True)
e = espnow.ESPNow(); e.active(True)
p = b'\xff\xff\xff\xff\xff\xff'; e.add_peer(p)

# Then run any of these one at a time:
e.send(p, "FD_FREEZE")    # pause
e.send(p, "FD_GO")        # play
e.send(p, "FD_NEXT")      # next song
e.send(p, "FD_PREV")      # previous song
e.send(p, "FD_VOL_UP")    # volume up
e.send(p, "FD_VOL_DOWN")  # volume down
```

## SD Card Song Setup

Name your WAV files on the SD card as:

```
song1.wav
song2.wav
song3.wav
...
```

Export settings: **WAV, Mono, 22050 Hz, Signed 16-bit PCM**

The player auto-discovers and sorts them. The last played song is saved to `lastsong.txt` on the SD card and resumed on reboot.
