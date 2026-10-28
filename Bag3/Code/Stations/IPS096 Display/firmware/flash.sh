#!/usr/bin/env bash
# Flash an IPS096 Display board: erase, write the LVGL firmware, copy the demo, hard reset.
# Usage: firmware/flash.sh <firmware.bin> [port]
#   --files-only <port-or-empty>  skip erase/flash, only copy the demo files
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
FILES=(board.py display_lvgl.py main.py)

FILES_ONLY=0
if [[ "${1:-}" == "--files-only" ]]; then
    FILES_ONLY=1
    shift
else
    BIN="${1:?usage: flash.sh <firmware.bin> [port]  |  flash.sh --files-only [port]}"
    shift
    [[ -f "$BIN" ]] || { echo "firmware not found: $BIN" >&2; exit 1; }
fi

PORT="${1:-}"
if [[ -z "$PORT" ]]; then
    PORTS=( $(ls /dev/cu.usbmodem* /dev/ttyACM* 2>/dev/null || true) )
    if [[ ${#PORTS[@]} -ne 1 ]]; then
        echo "found ${#PORTS[@]} serial ports (${PORTS[*]:-none}); pass one as an argument" >&2
        exit 1
    fi
    PORT="${PORTS[0]}"
fi
echo "port: $PORT"

ESPTOOL="$(command -v esptool.py || command -v esptool || true)"
MPREMOTE="$(command -v mpremote || true)"
[[ -n "$MPREMOTE" ]] || { echo "mpremote not found: pip install mpremote" >&2; exit 1; }

if [[ $FILES_ONLY -eq 0 ]]; then
    [[ -n "$ESPTOOL" ]] || { echo "esptool not found: pip install esptool" >&2; exit 1; }
    # One call: a separate erase_flash resets the board and the USB port drops out.
    "$ESPTOOL" --chip esp32s3 --port "$PORT" -b 460800 write_flash --erase-all 0x0 "$BIN"
    # The board re-enumerates after reset; wait for the port to come back.
    for _ in $(seq 1 30); do [[ -e "$PORT" ]] && break; sleep 0.5; done
    sleep 2
fi

cd "$HERE"
"$MPREMOTE" connect "$PORT" exec \
    "import gc, lvgl; gc.collect(); print('mem_free', gc.mem_free(), 'lvgl', lvgl.version_major(), lvgl.version_minor())"
"$MPREMOTE" connect "$PORT" cp "${FILES[@]}" :
# Hard reset: main.py fails to re-create the SPI bus after a soft reboot.
"$MPREMOTE" connect "$PORT" exec "import machine; machine.reset()" >/dev/null 2>&1 || true
echo "done: the test pattern should appear; USR1 counts, USR2 resets"
