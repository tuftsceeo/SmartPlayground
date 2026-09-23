#!/bin/bash
# sticky_state_bench.sh -- repeated wand pulls against one armed Dial/Box,
# with no power cycles and no intervening fixes, to see whether repeated
# pull attempts leave state behind that later attempts inherit.
#
# Host-side tool, no dependencies beyond mpremote and this tree's
# serial_monitor.py. Drives the wand the same zero-hands way as
# pull_flag.py's own docstring describes: write /pullpending, reset, let the
# wand's own boot-time pull loop run to whatever it runs to.
#
# Never interrupts a pull in progress: each cycle's capture runs until the
# wand itself prints a settle marker (pull OK, attempt budget spent, or back
# to idle at "Tap a TRIGGER tag"), with a generous safety-cap duration used
# only as a last resort, never as the normal stopping point -- resetting the
# board before its own retry/give-up sequence finishes is an external
# interrupt, not a natural retry, and produces misleading data. A short idle
# pause follows every settle before the next cycle touches the board again.
#
# Also recovers automatically from the wand's own unrelated NFC (PN532)
# "Bad ACK" boot glitch (an intermittent I2C hiccup, not part of the pull
# protocol) by issuing one reset rather than idling out the full safety cap.
#
# Usage (from BroadcastCode/, wand and target Dial/Box already on the bench):
#   tools/devtests/sticky_state_bench.sh <wand_port> <slug> <host_id> [n_cycles]
#
# Example:
#   tools/devtests/sticky_state_bench.sh /dev/cu.usbmodem1101 tilt_tones 004c 10
#
# Writes tools/devtests/out/sticky_state/cycle_<n>.log, one full serial
# capture per cycle. Watch the target Dial/Box's own port separately (a
# plain serial_monitor.py invocation, left running for the whole session --
# see HARDWARE_PROTOCOL.md on not touching an armed board's port mid-test,
# which is exactly the mistake this tool exists to avoid on the wand side).
set -u

if [ "$#" -lt 3 ]; then
  echo "usage: $0 <wand_port> <slug> <host_id> [n_cycles]" >&2
  exit 1
fi

WAND_PORT="$1"
SLUG="$2"
HOST_ID="$3"
N="${4:-10}"
CAP_S="${CAP_S:-60}"
PAUSE_S="${PAUSE_S:-8}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BROADCASTCODE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$BROADCASTCODE_DIR"

OUTDIR="$SCRIPT_DIR/out/sticky_state"
mkdir -p "$OUTDIR"
PENDING_FILE="$(mktemp -t sticky_state_pullpending)"

for i in $(seq 1 "$N"); do
  echo "=== cycle $i: $(date +%H:%M:%S) ==="
  printf '0\n%s\n%s' "$SLUG" "$HOST_ID" > "$PENDING_FILE"
  python3 -m mpremote connect "$WAND_PORT" resume fs cp "$PENDING_FILE" :pullpending 2>&1
  python3 -m mpremote connect "$WAND_PORT" reset 2>&1
  sleep 1
  LOG="$OUTDIR/cycle_${i}.log"
  : > "$LOG"
  python3 tools/serial_monitor.py "$WAND_PORT" "$CAP_S" >> "$LOG" 2>&1 &
  MONPID=$!
  START=$(date +%s)
  SETTLED=0
  BADACK=0
  while true; do
    if grep -q "pull OK\|attempt budget spent\|Tap a TRIGGER" "$LOG" 2>/dev/null; then
      SETTLED=1
      break
    fi
    if grep -q "RuntimeError: Bad ACK" "$LOG" 2>/dev/null; then
      BADACK=1
      break
    fi
    NOW=$(date +%s)
    if [ $((NOW - START)) -ge "$CAP_S" ]; then
      break
    fi
    if ! kill -0 "$MONPID" 2>/dev/null; then
      break
    fi
    sleep 2
  done
  # Give the settle marker's (or the Bad ACK crash's) own trailing prints a moment.
  sleep 2
  kill "$MONPID" 2>/dev/null
  wait "$MONPID" 2>/dev/null
  if [ "$SETTLED" -eq 1 ]; then
    echo "=== cycle $i settled cleanly ==="
  elif [ "$BADACK" -eq 1 ]; then
    echo "=== cycle $i: NFC Bad ACK -- dropped to raw REPL, issuing recovery reset ==="
    python3 -m mpremote connect "$WAND_PORT" reset 2>&1
    sleep 3
  else
    echo "=== cycle $i: hit the ${CAP_S}s safety cap without a settle marker ==="
  fi
  echo "=== cycle $i: pausing ${PAUSE_S}s idle before next cycle ==="
  sleep "$PAUSE_S"
done
rm -f "$PENDING_FILE"
echo "ALL CYCLES DONE"
