"""
⚠️ DEPRECATED - NOT USED ⚠️

This file is no longer used. The hub only supports USB Serial connection.
Bluetooth/BLE was never successfully implemented.

This file is kept for historical reference only.

For actual hub communication, see:
- mpy/hub_serial.py (USB Serial communication)
- js/adapters/serialAdapter.js (JavaScript WebSerial API wrapper)
"""

print("⚠️ hub_bluetooth.py is deprecated and should not be imported")


class BluetoothConnection:
    """Deprecated - Bluetooth was never implemented for this hub"""
    
    def __init__(self):
        raise NotImplementedError(
            "Bluetooth connection is not supported. Use SerialConnection instead."
        )
