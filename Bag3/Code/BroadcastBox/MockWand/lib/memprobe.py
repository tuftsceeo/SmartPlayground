"""memprobe.py -- BENCH-TEST CODE. NOT in the fielded wand baseline.

Deviation from Bag3/Code/Wand Module/. Heap probes for diagnosing the
"OSError: WiFi Out of Memory" failure at enow.init() -- see
Bag3/Code/BroadcastBox/design/2026-09-01-wifi-handoff-diagnosis.md for the
background and REBOOT_PULL_PLAN.md for why enow.init() has to run on a
cold radio. This module exists only so that claim can be checked against
real heap numbers instead of guessed at.

Deliberately stores nothing: no history list, no accumulating buffer -- a
probe that fragments the heap measures itself. Every function returns
immediately (does nothing, allocates nothing) when ENABLED is False.

Output is one line per call, plain ASCII, `key=value` pairs, so a serial
capture can be grepped straight off:

    grep '^MEM '      log.txt   -> point-in-time heap snapshots
    grep '^MEMSPAN '  log.txt   -> timed spans (e.g. one game's import)
    grep '^MEMFRAG '  log.txt   -> micropython.mem_info(1) dumps

Do NOT import this from anything shipped to the fielded wand.
"""

import gc
import time

try:
    import esp32
except ImportError:
    esp32 = None

try:
    import micropython
except ImportError:
    micropython = None

ENABLED = True


def _idf_free():
    """(sum of free bytes, largest single free region) across IDF HEAP_DATA.

    Returns (None, None) if esp32.idf_heap_info is unavailable (e.g. off
    a C6, or on a build without the binding) -- callers print "None" in
    that case rather than raising.
    """
    if esp32 is None:
        return None, None
    try:
        regions = esp32.idf_heap_info(esp32.HEAP_DATA)
    except Exception:
        return None, None
    total_free = 0
    largest = 0
    for r in regions:
        # (total_bytes, free_bytes, largest_free_block, ...) per IDF binding.
        free = r[1]
        biggest = r[2] if len(r) > 2 else 0
        total_free += free
        if biggest > largest:
            largest = biggest
    return total_free, largest


def probe(tag, collect=False):
    """One line of heap state. Returns (gc_total, gc_used, gc_free, idf_free).

    collect=False by default -- a probe that calls gc.collect() perturbs
    the very measurement it is trying to take. Pass collect=True only when
    you deliberately want the post-collection number (e.g. right before
    enow.init(), where main.py collects anyway).
    """
    if not ENABLED:
        return None
    if collect:
        gc.collect()
    used = gc.mem_alloc()
    free = gc.mem_free()
    total = used + free
    idf_free, idf_max = _idf_free()
    print("MEM tag=%s gct=%d gcu=%d gcf=%d idf=%s idfmax=%s"
          % (tag, total, used, free,
             idf_free if idf_free is not None else "None",
             idf_max if idf_max is not None else "None"))
    return total, used, free, idf_free


def mark():
    """Token for a timed span: (ticks_ms, gc.mem_alloc()). One small tuple."""
    if not ENABLED:
        return (0, 0)
    return (time.ticks_ms(), gc.mem_alloc())


def span(tag, token):
    """Elapsed ms + heap delta since mark(). Prints a MEMSPAN line."""
    if not ENABLED:
        return
    t0, used0 = token
    ms = time.ticks_diff(time.ticks_ms(), t0)
    used = gc.mem_alloc()
    free = gc.mem_free()
    idf_free, _idf_max = _idf_free()
    print("MEMSPAN tag=%s ms=%d dgcu=%d gcf=%d idf=%s"
          % (tag, ms, used - used0, free,
             idf_free if idf_free is not None else "None"))


def frag(tag):
    """Bracketed micropython.mem_info(1) dump, for the fragmentation detail
    probe() cannot show (block counts, max contiguous free block).
    """
    if not ENABLED or micropython is None:
        return
    print("MEMFRAG tag=%s" % tag)
    micropython.mem_info(1)
    print("MEMFRAG-END tag=%s" % tag)
