#!/bin/bash
# py_compile every Bag3 device/tool .py; the only static check available
# off-device (machine, espnow and neopixel do not exist here).
cd "$(dirname "$0")/../../../../.." || exit 1   # repo root
fail=0
while IFS= read -r -d '' f; do
  python3 -m py_compile "$f" || { echo "FAIL $f"; fail=1; }
done < <(find Bag3/Code -name '*.py' -print0)
find Bag3 -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null
[ $fail -eq 0 ] && echo "ALL COMPILE OK"
exit $fail
