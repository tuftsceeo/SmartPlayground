# ESP32C6 Xiao BLE Nordic UART Service
# Compatible with LightBlue and other Nordic UART apps
# MicroPython v1.25.0 on ESP32C6
"""
Use Thonny to install "Manage Packages" > aioble first
"""

from micropython import const
import asyncio
import aioble
import bluetooth
import json
import struct
from machine import Pin, SoftI2C
import time

# Try to import display - adjust based on your Xiao expansion board setup
try:
    from ssd1306 import SSD1306_I2C
    # Adjust pins based on your Xiao expansion board
    i2c = SoftI2C(scl=Pin(7), sda=Pin(6))  # Common Xiao expansion pins
    display = SSD1306_I2C(128, 64, i2c)
    HAS_DISPLAY = True
    print("Display initialized successfully")
except Exception as e:
    HAS_DISPLAY = False
    print(f"Display not available: {e}")

# Nordic UART Service UUIDs
_SERVICE_UUID = bluetooth.UUID('6E400001-B5A3-F393-E0A9-E50E24DCCA9E')
_RX_CHAR_UUID = bluetooth.UUID('6E400002-B5A3-F393-E0A9-E50E24DCCA9E')  # Receive from phone
_TX_CHAR_UUID = bluetooth.UUID('6E400003-B5A3-F393-E0A9-E50E24DCCA9E')  # Send to phone

# Advertising interval (milliseconds)
_ADV_INTERVAL_MS = const(250)

# Global variables
rx_characteristic = None
tx_characteristic = None
connection_handle = None
received_data_queue = []

def display_text(text_lines, clear=True):
    """Display text on OLED screen if available"""
    if not HAS_DISPLAY:
        return
    
    try:
        if clear:
            display.fill(0)
        
        # Use exact same pattern as working UART demo
        if len(text_lines) > 0:
            display.text(str(text_lines[0]), 0, 0, 1)
        if len(text_lines) > 1:
            display.text(str(text_lines[1]), 0, 8, 1)
        if len(text_lines) > 2:
            display.text(str(text_lines[2]), 0, 16, 1)
        if len(text_lines) > 3:
            display.text(str(text_lines[3]), 0, 24, 1)
        if len(text_lines) > 4:
            display.text(str(text_lines[4]), 0, 32, 1)
        if len(text_lines) > 5:
            display.text(str(text_lines[5]), 0, 40, 1)
        if len(text_lines) > 6:
            display.text(str(text_lines[6]), 0, 48, 1)
        if len(text_lines) > 7:
            display.text(str(text_lines[7]), 0, 56, 1)
        
        display.show()
    except Exception as e:
        print(f"Display error: {e}")

def parse_received_data(data):
    """Parse received data - handles integers, JSON, and plain strings"""
    try:
        # Convert bytes to string
        data_str = data.decode('utf-8').strip()
        print(f"Received string: '{data_str}'")
        
        # Try parsing as JSON first (for complex structures)
        try:
            parsed_json = json.loads(data_str)
            return {"type": "json", "data": parsed_json}
        except:
            pass
        
        # Try parsing as integer
        try:
            parsed_int = int(data_str)
            return {"type": "integer", "data": parsed_int}
        except:
            pass
        
        # Try parsing as float
        try:
            parsed_float = float(data_str)
            return {"type": "float", "data": parsed_float}
        except:
            pass
        
        # Default to string
        return {"type": "string", "data": data_str}
        
    except Exception as e:
        print(f"Data parsing error: {e}")
        return {"type": "error", "data": str(e)}

async def peripheral_task():
    """Handle BLE advertising and connections"""
    global connection_handle
    
    print("Starting BLE peripheral...")
    
    while True:
        try:
            # Start advertising
            print("Advertising as 'ESP32C6-Playground'...")
            display_text([
                "BLE Status:",
                "Advertising...",
                "",
                "Connect with:",
                "LightBlue or",
                "nRF Connect"
            ])
            
            async with await aioble.advertise(
                _ADV_INTERVAL_MS,
                name="ESP32C6-Playground",
                services=[_SERVICE_UUID],
            ) as connection:
                connection_handle = connection
                print(f"Connected to: {connection.device}")
                
                display_text([
                    "BLE Status:",
                    "CONNECTED!",
                    "",
                    f"Device:",
                    f"{str(connection.device)[:16]}",
                    "",
                    "Ready for data..."
                ])
                
                # Wait for disconnection
                await connection.disconnected()
                print("Disconnected")
                connection_handle = None
                
        except asyncio.CancelledError:
            print("Peripheral task cancelled")
            break
        except Exception as e:
            print(f"Error in peripheral_task: {e}")
            await asyncio.sleep_ms(1000)

async def data_handler():
    """Handle incoming data from BLE"""
    global received_data_queue
    
    while True:
        try:
            if rx_characteristic:
                # Wait for data to be written to RX characteristic
                connection, data = await rx_characteristic.written()
                
                print(f"Raw data received: {data}")
                
                # Parse the received data
                parsed = parse_received_data(data)
                received_data_queue.append(parsed)
                
                print(f"Parsed data: {parsed}")
                
                # Update display with received data
                display_lines = [
                    "Data Received:",
                    f"Type: {parsed['type']}",
                    f"Data: {str(parsed['data'])[:20]}",
                    "",
                    f"Queue size: {len(received_data_queue)}",
                    "",
                    f"Time: {time.ticks_ms()}"
                ]
                display_text(display_lines)
                
                # Send acknowledgment back to phone
                if tx_characteristic and connection_handle:
                    ack_message = json.dumps({
                        "status": "received",
                        "type": parsed['type'],
                        "timestamp": time.ticks_ms()
                    })
                    await tx_characteristic.notify(connection_handle, ack_message.encode())
                    print(f"Sent acknowledgment: {ack_message}")
                
        except asyncio.CancelledError:
            print("Data handler cancelled")
            break
        except Exception as e:
            print(f"Error in data_handler: {e}")
            await asyncio.sleep_ms(100)

async def status_sender():
    """Periodically send status updates to phone"""
    counter = 0
    
    while True:
        try:
            await asyncio.sleep(5)  # Send status every 5 seconds
            
            if tx_characteristic and connection_handle:
                counter += 1
                status_data = {
                    "device": "ESP32C6-Playground",
                    "counter": counter,
                    "queue_size": len(received_data_queue),
                    "free_memory": "N/A",  # Could add gc.mem_free() if needed
                    "timestamp": time.ticks_ms()
                }
                
                status_message = json.dumps(status_data)
                await tx_characteristic.notify(connection_handle, status_message.encode())
                print(f"Status sent: {status_message}")
                
        except asyncio.CancelledError:
            print("Status sender cancelled")
            break
        except Exception as e:
            print(f"Error in status_sender: {e}")
            await asyncio.sleep_ms(1000)

def setup_service():
    """Set up the Nordic UART Service"""
    global rx_characteristic, tx_characteristic
    
    print("Setting up Nordic UART Service...")
    
    # Register the Nordic UART Service
    service = aioble.Service(_SERVICE_UUID)
    
    # RX Characteristic (receives data from phone)
    rx_characteristic = aioble.Characteristic(
        service, _RX_CHAR_UUID, 
        write=True, 
        capture=True
    )
    
    # TX Characteristic (sends data to phone)  
    tx_characteristic = aioble.Characteristic(
        service, _TX_CHAR_UUID, 
        notify=True
    )
    
    # Register the service
    aioble.register_services(service)
    print("Nordic UART Service registered successfully")

async def main():
    """Main application loop"""
    print("=== ESP32C6 BLE Nordic UART Service ===")
    print("MicroPython version:", end=" ")
    
    try:
        import sys
        print(sys.version)
    except:
        print("Unknown")
    
    # Initialize display
    display_text([
        "ESP32C6 BLE",
        "Nordic UART",
        "Service",
        "",
        "Initializing..."
    ])
    
    # Set up BLE service
    setup_service()
    
    print("Starting main tasks...")
    
    # Create tasks
    tasks = [
        asyncio.create_task(peripheral_task()),
        asyncio.create_task(data_handler()),
        asyncio.create_task(status_sender())
    ]
    
    try:
        # Run all tasks concurrently
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("Application stopped by user")
    except Exception as e:
        print(f"Application error: {e}")
    finally:
        # Clean up
        for task in tasks:
            task.cancel()
        print("Application ended")

if __name__ == "__main__":
    # Run the main application
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Failed to start application: {e}")
        # Show error on display
        try:
            display_text([
                "ERROR:",
                str(e)[:20],
                "",
                "Check console",
                "for details"
            ])
        except:
            pass