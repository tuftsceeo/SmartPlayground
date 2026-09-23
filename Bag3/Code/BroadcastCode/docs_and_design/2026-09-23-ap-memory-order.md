# Radio bring-up needs contiguous memory, claimed early — 2026-09-23

The bench-findings note `docs_and_design/old/TODO-2026-09.md` asked for and
nobody wrote. Three devices have now hit the same constraint; this is
the record.

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

**Earlier, same class, on the clients.** `MockWand/lib/memprobe.py` exists
because of an `OSError: WiFi Out of Memory` at `enow.init()`. Its
`_idf_free()` returns total free *and largest free block* for exactly this
reason. The Icon Display's README records the same constraint as a rule about
build order — "Radio before the panel": `main.py` calls `enow.init()` before
`icon_matrix` is imported, because `Matrix()` takes a 768-byte NeoPixel
buffer, a 512-byte offset table, a 256-byte LUT and a 768-byte frame, and
building the panel first produced the OOM. See
`docs_and_design/old/2026-09-01-wifi-handoff-diagnosis.md` and
`old/REBOOT_PULL_PLAN.md`.

This is not a host-side problem with a client-side echo. It is one constraint
that every device in the tree is subject to, and it has now been hit from
three directions: `enow.init()` on the wand, panel-before-radio on the icon
display, and `arm()` on the Dials.

## The rule

**Nothing may allocate before the radio has claimed its memory.**

Per device, the moment the block is claimed:

| Device | Claims the block at | Imported ahead of it |
|---|---|---|
| Dial, Box | `prewarm_ap()`, then `_start_ap()` in `arm()` | `code_server.py`, at `bdial_server.py`/`bbox_server.py` module scope |
| Wand, Icon Display — normal boot | `ESPNowManager.init()` | everything `main.py` imports at module scope, including every built-in game |
| Wand, Icon Display — pull mode | `sta.active(True)` in `code_puller._reset_sta()` | `code_puller.py`, imported inside `_run_pull_mode()` |

On the wand the first row of that table is the easy one to forget: adding a
built-in game adds a module-scope import, and that costs heap before
`enow.init()` ever runs.

In practice:

1. **No new module-scope content in `code_server.py` or `code_puller.py`.**
   Both are imported ahead of the radio. Docstrings and format strings in
   them are allocated at import whether or not the code runs.
2. **Nothing between `gc.collect()` and `_start_ap()` in `arm()`.** The
   collect is what makes the block findable; anything after it undoes that.
3. **Diagnostics live in `serve_probe.py` / `pull_probe.py`**, which are
   imported lazily and only after the radio is up — `serve_probe` at the end
   of `arm()`, `pull_probe` once `sta.isconnected()` is true. With
   `DEBUG_SERVE` / `DEBUG_PULL` false, neither file is ever parsed. Anything
   logged about the boot itself (`reset_cause()`, battery) prints *after* the
   pull returns, not before it.
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
