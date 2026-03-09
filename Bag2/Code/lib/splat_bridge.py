"""
splat_bridge.py — ESP-NOW bridge for sending configs to Splat Companions
=========================================================================
Goes in /lib/ on the wand.

Handles ESP-NOW initialization and sending action configurations
to Splat Companion devices identified by SC:MAC tags.

Usage:
    from splat_bridge import SplatBridge

    bridge = SplatBridge()
    bridge.add_companion("AA:BB:CC:DD:EE:FF")
    bridge.send_config("AA:BB:CC:DD:EE:FF", [["turnblue", "notec"]])
    bridge.send_stop("AA:BB:CC:DD:EE:FF")
    bridge.shutdown()
"""

import network
import espnow
import json
import time


def _mac_str_to_bytes(mac_str):
    """Convert 'AA:BB:CC:DD:EE:FF' to b'\\xAA\\xBB...'"""
    parts = mac_str.split(':')
    return bytes([int(p, 16) for p in parts])


def _mac_bytes_to_str(mac_bytes):
    """Convert b'\\xAA\\xBB...' to 'AA:BB:CC:DD:EE:FF'"""
    return ':'.join('%02X' % b for b in mac_bytes)


class SplatBridge:
    """
    Manages ESP-NOW connections to one or more Splat Companion devices.
    Sends action configurations and stop commands.
    """

    def __init__(self):
        self.enow = None
        self.companions = {}  # mac_str -> mac_bytes
        self._active = False

    def init(self):
        """Activate WiFi and ESP-NOW."""
        if self._active:
            return

        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        sta.disconnect()

        self.enow = espnow.ESPNow()
        self.enow.active(True)
        self._active = True
        print("  SplatBridge: ESP-NOW active")

    def add_companion(self, mac_str):
        """
        Register a Splat Companion by MAC address string.
        Initializes ESP-NOW if not already active.

        Args:
            mac_str: MAC address like 'AA:BB:CC:DD:EE:FF'
        """
        if not self._active:
            self.init()

        mac_bytes = _mac_str_to_bytes(mac_str)
        if mac_str not in self.companions:
            try:
                self.enow.add_peer(mac_bytes)
            except Exception:
                pass  # peer may already exist
            self.companions[mac_str] = mac_bytes
            print("  SplatBridge: added companion %s" % mac_str)

    def remove_companion(self, mac_str):
        """Remove a Splat Companion."""
        if mac_str in self.companions:
            try:
                self.enow.del_peer(self.companions[mac_str])
            except Exception:
                pass
            del self.companions[mac_str]

    def send_config(self, mac_str, action_chain):
        """
        Send action configuration to a Splat Companion.

        Args:
            mac_str: Target companion MAC
            action_chain: List of action groups, e.g. [["turnblue", "notec"]]
        """
        if not self._active:
            print("  SplatBridge: not active")
            return False

        mac_bytes = self.companions.get(mac_str)
        if mac_bytes is None:
            print("  SplatBridge: unknown companion %s" % mac_str)
            return False

        msg = json.dumps({
            "type": "splat_config",
            "actions": action_chain,
        })

        try:
            self.enow.send(mac_bytes, msg)
            print("  SplatBridge: config sent to %s" % mac_str)
            return True
        except Exception as e:
            print("  SplatBridge: send error: %s" % str(e))
            return False

    def send_stop(self, mac_str):
        """Send stop command to a Splat Companion."""
        if not self._active:
            return False

        mac_bytes = self.companions.get(mac_str)
        if mac_bytes is None:
            return False

        msg = json.dumps({"type": "stop"})
        try:
            self.enow.send(mac_bytes, msg)
            print("  SplatBridge: stop sent to %s" % mac_str)
            return True
        except Exception as e:
            print("  SplatBridge: stop error: %s" % str(e))
            return False

    def send_stop_all(self):
        """Send stop to all registered companions."""
        for mac_str in list(self.companions.keys()):
            self.send_stop(mac_str)

    def has_companions(self):
        """Check if any companions are registered."""
        return len(self.companions) > 0

    def get_companion_macs(self):
        """Return list of registered companion MAC strings."""
        return list(self.companions.keys())

    def clear_companions(self):
        """Remove all companions."""
        for mac_str in list(self.companions.keys()):
            self.remove_companion(mac_str)


    def shutdown(self):
        """Deactivate ESP-NOW."""
        if self._active:
            self.send_stop_all()
            try:
                self.enow.active(False)
            except Exception:
                pass
            self._active = False
            self.companions.clear()
            print("  SplatBridge: shutdown")