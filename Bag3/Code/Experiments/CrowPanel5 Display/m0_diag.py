"""M0 diagnostics. Import only after the radio is up."""

import gc
import time

import esp32

_INT_MAX = 2 * 1024 * 1024   # regions above this are PSRAM


def heap():
    """(internal largest free block, internal free total, PSRAM largest free block)."""
    big = free = psram = 0
    for size, f, largest, _ in esp32.idf_heap_info(esp32.HEAP_DATA):
        if size > _INT_MAX:
            psram = max(psram, largest)
        else:
            big = max(big, largest)
            free += f
    return big, free, psram


def line(tag, extra=""):
    gc.collect()
    big, free, psram = heap()
    t = time.ticks_ms() // 1000
    print(f"M0 {t:5d}s {tag:<10} mem_free={gc.mem_free()} int_largest={big} int_free={free} psram_largest={psram} {extra}")
    return big
