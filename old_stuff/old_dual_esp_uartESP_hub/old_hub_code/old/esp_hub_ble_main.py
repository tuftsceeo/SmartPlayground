# sender_main.py (Teacher board)
import network, espnow, time
from ble_uart import Yell
from machine import Pin

# === CONFIG ===
# Paste the Student's MAC here
PEER_MAC = b'\xE4\xB3\x23\xB5\x67\x6C'   # <-- CHANGE THIS to Student's MAC
WIFI_CHANNEL = 1

# Optional LED on this sender board for local feedback
led = Pin(1, Pin.OUT)

# --- ESP-NOW setup ---
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.config(channel=WIFI_CHANNEL)
try:
    wlan.disconnect()
except:
    pass

e = espnow.ESPNow()
e.active(True)
e.add_peer(PEER_MAC)
print("ESP-NOW initialized, peer added")

# --- BLE UART setup ---
p = Yell('Fred', verbose=False, type='uart')
_rxbuf = b""

def _apply_cmd(cmd_str: str):
    # Robust parse: normalize spaces, accept LED1/LED 1 variants
    s = cmd_str.strip().upper()
    if not s:
        return
    
    # Normalize "LED1" -> "LED 1", "LED0" -> "LED 0"
    if s.startswith("LED") and len(s) >= 4 and s[3].isdigit() and s[2] != ' ':
        s = s[:3] + ' ' + s[3:]
    
    print("BLE RX:", repr(s))
    
    if s in ("LED 1", "ON", "LIGHT ON"):
        led.value(1)
        print("LED ON")
        try: 
            p.send(b"ACK LED ON")
        except: 
            pass
            
    elif s in ("LED 0", "OFF", "LIGHT OFF"):
        led.value(0)
        print("LED OFF")
        try: 
            p.send(b"ACK LED OFF")
        except: 
            pass
            
    elif s.startswith("SEND "):
        # Extract the message after "SEND "
        # Use original case-preserved version
        original = cmd_str.strip()
        if len(original) > 5:
            payload_text = original[5:]  # Everything after "SEND "
        else:
            payload_text = "PING"
        
        payload = payload_text.encode()
        ok = e.send(PEER_MAC, payload, True)
        print("ESP-NOW sent:", payload, "ok:", ok)
        
        try:
            p.send(b"ESPNOW:%s:%s" % (b"OK" if ok else b"FAIL", payload))
        except:
            pass
    else:
        print("Unknown cmd:", s)

def handle_cmd(chunk: bytes):
    """Line-buffered BLE command handler with immediate single-command fallback."""
    global _rxbuf
    if not chunk:
        return
    
    # Immediate path: if the chunk looks like a standalone command (no newline),
    # try to execute it right away so buttons that send plain 'LED 1' work.
    quick = chunk.strip()
    if b"\n" not in chunk and 0 < len(quick) <= 16:
        try:
            _apply_cmd(quick.decode())
            return
        except Exception as ex:
            # Fall back to buffered path if something went wrong
            print("quick-parse failed:", ex)
    
    # Buffered path (supports multi-line or streaming text)
    _rxbuf += chunk.replace(b"\r", b"\n")
    while b"\n" in _rxbuf:
        line, _, rest = _rxbuf.partition(b"\n")
        _rxbuf = rest
        try:
            _apply_cmd(line.decode())
        except Exception as ex:
            print("parse error:", ex)

# hook the BLE write callback so browser commands arrive here
p._write_callback = handle_cmd

# advertise + wait for BLE connect
if p.connect_up():
    print("BLE connected; ready for commands (SEND <message> / LED 1 / LED 0)")
else:
    print("BLE not connected (timeout)")