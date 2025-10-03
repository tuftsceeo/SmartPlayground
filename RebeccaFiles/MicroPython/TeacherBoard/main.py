
# ESP32C6 BLE UART Firmware
# This code runs ON the ESP32, uploaded via RS232 terminal

from BLE_CEEO import Yell
from machine import Pin
import time

# LED on PIN 1
led = Pin(1, Pin.OUT)

# Global buffer for line-buffered commands
_rxbuf = b""

def _apply_cmd(cmd_str: str):
    """Execute a command received via BLE"""
    s = cmd_str.strip().upper()
    if not s:
        return
    
    # Normalize "LED1" -> "LED 1", "LED0" -> "LED 0"
    if s.startswith("LED") and len(s) >= 4 and s[3].isdigit() and s[2] != ' ':
        s = s[:3] + ' ' + s[3:]
    
    print("BLE RX:", repr(s))
    
    try:
        if s in ("LED 1", "ON", "LIGHT ON"):
            led.value(1)
            print("LED ON")
            try: 
                p.send(b"ACK LED ON")
            except Exception as e: 
                print("BLE send error (LED ON):", e)
        
        elif s in ("LED 0", "OFF", "LIGHT OFF"):
            led.value(0)
            print("LED OFF")
            try: 
                p.send(b"ACK LED OFF")
            except Exception as e: 
                print("BLE send error (LED OFF):", e)
        
        elif s.startswith("SEND"):
            payload_text = s[4:].strip()
            print(f"Received message: {payload_text}")
            try:
                p.send(b"ACK MESSAGE RECEIVED: " + payload_text.encode())
            except Exception as e:
                print("BLE send error (SEND):", e)
        
        else:
            print("Unknown cmd:", s)
            
    except Exception as e:
        print("Command processing error:", e)

def handle_cmd(chunk: bytes):
    """Line-buffered BLE command handler"""
    global _rxbuf
    if not chunk:
        return
    
    # Immediate path: if chunk looks like standalone command (no newline),
    # try to execute it right away
    quick = chunk.strip()
    if b"\n" not in chunk and 0 < len(quick) <= 16:
        try:
            _apply_cmd(quick.decode())
            return
        except Exception as ex:
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

# Main BLE peripheral setup
def run_ble_peripheral(name='Fred'):
    global p
    try:
        # Create BLE UART peripheral
        p = Yell(name, interval_us=30000, verbose=True)
        
        if p.connect_up():
            p.callback = handle_cmd
            print(f'BLE connected as "{name}"; ready for commands (SEND / LED 1 / LED 0)')
            
            # Keep running while connected
            while p.is_connected:
                time.sleep(0.1)
            
            print('Lost connection')
        else:
            print('Failed to connect')
            
    except Exception as e:
        print('Error:', e)
    finally:
        try:
            p.disconnect()
        except:
            pass
        print('BLE closed')

# Auto-run when uploaded as main.py
if __name__ == '__main__':
    run_ble_peripheral('Fred')  # Change name if desired
