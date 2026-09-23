# AP bring-up needs contiguous memory, claimed early — 2026-09-23

The bench-findings note `docs_and_design/old/TODO-2026-09.md` asked for and
nobody wrote. Two incidents have now been paid for; this is the record.

## The constraint

The WiFi driver needs **one large contiguous block of IDF DRAM** to bring up
the SoftAP (or ESP-NOW). It must be claimed **first thing on boot**, because
nothing later can un-fragment the heap enough to find it again.

MicroPython's GC heap is carved out of that same DRAM. Two consequences that
are easy to get backwards:

- `gc.mem_free()` does **not** measure what the radio needs. A large idle
  Python heap is DRAM the driver cannot have.
- The failure is **fragmentation, not exhaustion**. Total free can be
  comfortable while the largest single free block is far too small.

Every Python object allocated before the AP claims its block — a docstring, a
format string, a function object, a list — makes the largest free block
smaller. Instrumentation is not exempt. **A probe that allocates consumes the
thing it is trying to measure.**

## Evidence

**2026-09-23, both Dials, after `95f684c`.** Diagnostic prints were added to
`code_server.py`. `bdial_server.py` imports that module at module scope, so
its new docstrings and format strings were allocated before `prewarm_ap()` and
long before `arm()`. Both Dials then refused to arm:

```
# CodeServer.arm: AP start failed: WiFi Out of Memory
  (gc_free=81344 idf_free=12456 idf_largest=7680)
```

81 KB of free Python heap and 12 KB of total free IDF heap, of which the
largest single block was 7680 bytes. Not short of memory — short of
*contiguous* memory. A soft reset did not clear it; only a power cycle did.

`b9f49ca` then made it worse by probing the heap between `arm()`'s
`gc.collect()` and `_start_ap()` — the one place a diagnostic cannot go.

Reverting the instrumentation (`41f78dc`) restored arming.

**Earlier, same class.** `MockWand/lib/memprobe.py` exists because of an
`OSError: WiFi Out of Memory` at `enow.init()`. Its `_idf_free()` returns
total free *and largest free block* for exactly this reason. See
`docs_and_design/old/2026-09-01-wifi-handoff-diagnosis.md` and
`old/REBOOT_PULL_PLAN.md`.

## The rule

**Nothing may allocate before the radio has claimed its memory.**

On the Dial and Box that means before `prewarm_ap()` and `_start_ap()`. On
the wand and icon display it means before `sta.active(True)` in
`code_puller._reset_sta()`, and before `ESPNowManager.init()`.

In practice:

1. **No new module-scope content in `code_server.py` or `code_puller.py`.**
   Both are imported ahead of the radio. Docstrings and format strings in
   them are allocated at import whether or not the code runs.
2. **Nothing between `gc.collect()` and `_start_ap()` in `arm()`.** The
   collect is what makes the block findable; anything after it undoes that.
3. **Diagnostics live in `serve_probe.py` / `pull_probe.py`**, which are
   imported lazily and only after the radio is up — `serve_probe` at the end
   of `arm()`, `pull_probe` once `sta.isconnected()` is true. With
   `DEBUG_SERVE` / `DEBUG_PULL` false, neither file is ever parsed.
4. **`prewarm_ap()` is required, not experimental.** Its own docstring is
   more tentative than the evidence warrants. Turning it off should be
   expected to make `arm()` fail more often. `PREWARM_AP` exists only to run
   that A/B deliberately.

## Measuring it

`esp32.idf_heap_info(esp32.HEAP_DATA)` gives per-region
`(total, free, largest_free_block, ...)`. Largest free block is the number
that matters; total free alone will mislead you. `serve_probe.idf_heap()` and
`memprobe._idf_free()` both wrap it.

Read a failure as: **large total + small largest = fragmented**, and the fix
is ordering, not freeing.
