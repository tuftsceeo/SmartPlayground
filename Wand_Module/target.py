"""
target.py — ESP-NOW Target Configuration
==========================================
Store the MAC address of the scoreboard/hub that receives
timing results from Color Quest.

To find a device's MAC address, run this on the target device:
    import network
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    print(':'.join('%02X' % b for b in sta.config('mac')))

Format: 6 bytes as a bytes literal
"""

# Replace with your scoreboard/hub MAC address
# Example: SCORE_MAC = b'\xAA\xBB\xCC\xDD\xEE\xFF'
SCORE_MAC = b'\xB4\x3A\x45\x86\x1A\x5C'