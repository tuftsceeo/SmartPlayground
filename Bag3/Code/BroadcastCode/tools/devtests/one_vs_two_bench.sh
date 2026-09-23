#!/bin/bash
# one_vs_two_bench.sh -- wand-driven pull cycles against a target Dial/Box,
# for comparing failure rate with only the target armed vs with a second
# Dial/Box also armed nearby. Wand-driven, not laptop-driven: pull_bench.py
# needs the laptop joined to the SoftAP and proves nothing about which
# radio actually fails in normal use.
#
# Run once with only the target armed, then again with both armed (arm/
# disarm the second board yourself, over json_drive.py or its own UI,
# between runs), and diff the two output directories' pass/fail counts and
# each cycle's "N SP-FILEPUSH* visible" line.
#
# Same non-interrupting, auto-recovering design as sticky_state_bench.sh --
# see that file's header for why.
#
# Usage (from BroadcastCode/, wand and both Dials/Boxes already on the bench):
#   tools/devtests/one_vs_two_bench.sh <wand_port> <slug> <host_id> <phase_label> [n_cycles]
#
# Example:
#   tools/devtests/one_vs_two_bench.sh /dev/cu.usbmodem1101 apple_button 5094 A 10
#   # ... arm the second Dial, then:
#   tools/devtests/one_vs_two_bench.sh /dev/cu.usbmodem1101 apple_button 5094 B 10
#
# Writes tools/devtests/out/one_vs_two/phase<label>_cycle_<n>.log.
set -u

if [ "$#" -lt 4 ]; then
  echo "usage: $0 <wand_port> <slug> <host_id> <phase_label> [n_cycles]" >&2
  exit 1
fi

WAND_PORT="$1"
SLUG="$2"
HOST_ID="$3"
PHASE="$4"
N="${5:-10}"
CAP_S="${CAP_S:-60}"
PAUSE_S="${PAUSE_S:-8}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BROADCASTCODE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$BROADCASTCODE_DIR"

OUTDIR="$SCRIPT_DIR/out/one_vs_two"
mkdir -p "$OUTDIR"
PENDING_FILE="$(mktemp -t one_vs_two_pullpending)"

for i in $(seq 1 "$N"); do
  echo "=== phase $PHASE cycle $i: $(date +%H:%M:%S) ==="
  printf '0\n%s\n%s' "$SLUG" "$HOST_ID" > "$PENDING_FILE"
  python3 -m mpremote connect "$WAND_PORT" resume fs cp "$PENDING_FILE" :pullpending 2>&1
  python3 -m mpremote connect "$WAND_PORT" reset 2>&1
  sleep 1
  LOG="$OUTDIR/phase${PHASE}_cycle_${i}.log"
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
  sleep 2
  kill "$MONPID" 2>/dev/null
  wait "$MONPID" 2>/dev/null
  if [ "$SETTLED" -eq 1 ]; then
    echo "=== phase $PHASE cycle $i settled cleanly ==="
  elif [ "$BADACK" -eq 1 ]; then
    echo "=== phase $PHASE cycle $i: NFC Bad ACK -- issuing recovery reset ==="
    python3 -m mpremote connect "$WAND_PORT" reset 2>&1
    sleep 3
  else
    echo "=== phase $PHASE cycle $i: hit the ${CAP_S}s safety cap without a settle marker ==="
  fi
  echo "=== phase $PHASE cycle $i: pausing ${PAUSE_S}s idle before next cycle ==="
  sleep "$PAUSE_S"
done
rm -f "$PENDING_FILE"
echo "PHASE $PHASE DONE"
