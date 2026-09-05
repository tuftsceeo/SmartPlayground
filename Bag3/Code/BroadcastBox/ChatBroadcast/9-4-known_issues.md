The gallery's Python currently comes from hand-written payloads in examples.js, not the real games. Where should the real Wand Module .py be used?

--> Everywhere

Simulator/tools/sync_sources.py copies vendor/ from Bag2/Code, not Bag3. That is why the vendored melody/jumpin/nfc_sound are stale. Repoint it?

--> Keep Bag2

The Freeze Dance example has no vendored counterpart — Bag3 has freeze_dance.py, but it is not in the sync list, so Pyodide cannot load it. What should happen to it?

--> Drop the example

Which games should the example gallery show once it is backed by real files?

--> Expose all vendored games