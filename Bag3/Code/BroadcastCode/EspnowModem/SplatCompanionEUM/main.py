# Splat Companion (EUM) boot shim.
# BLE claims its controller memory before anything else allocates (AGENTS.md,
# memory order). Keep this file free of strings, docstrings and extra imports:
# everything in it is compiled and allocated before BLE comes up.
import ubluetooth
ubluetooth.BLE().active(True)
import splat_companion
splat_companion.main()
