# lib/

Shared MicroPython modules for Bag2 hub/wand/hardware code. Devices outside
this directory (`../M5Paper Remote/`, `../StickS3 Narrator/`) keep a
bundled copy in sync rather than importing across directories.

## `espnow_manager.py`

`poll(timeout_ms=0)` is non-blocking (the default); a nonzero `timeout_ms`
blocks inside a C call for up to that long, with no Python-level yield
point until it returns. Polling loops should call `poll()` with no
argument and pace themselves with `time.sleep_ms()`, as every
`Wand Module/*.py` game and `M5Paper Remote/main.py` do. `color_quest.py`'s
`poll(50)` is the one exception, inside a loop that also does per-iteration
display work.
