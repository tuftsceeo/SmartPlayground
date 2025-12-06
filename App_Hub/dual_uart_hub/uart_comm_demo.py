"""
main.py - UART Communication Application
---------------------------------------
Demonstrates reliable two-way UART communication between boards.
Uses the uart_comm library for all communication handling.

CONFIGURATION: Change BOARD_NUMBER below for each board
"""
import asyncio
import time
from machine import I2C, Pin
import ssd1306
from uart_comm import UARTComm

# =============================================================================
# BOARD CONFIGURATION - CHANGE THIS FOR EACH BOARD
# =============================================================================
BOARD_NUMBER = 1  # Change to 1 for first board, 2 for second board

# Configuration
BOARD_NAME = f"BOARD{BOARD_NUMBER}"
DEBUG_PRINTS = False  # Set to True for detailed debugging
BAUD_RATE = 921600   # High speed communication

# Initialize display
DISPLAY_CONNECTED = False
try:
    i2c = I2C(scl=Pin(23), sda=Pin(22))
    display = ssd1306.SSD1306_I2C(128, 64, i2c)
    DISPLAY_CONNECTED = True
except:
    print("No Display")
    DISPLAY_CONNECTED = False
 
    

# Global variables
comm = None
stats = {'pings_received': 0, 'data_received': 0, 'last_message': 'None'}

def handle_incoming_message(msg_type, data, src):
    """Handle incoming messages (not ACKs)"""
    global stats
    
    if msg_type == "PING":
        stats['pings_received'] += 1
        stats['last_message'] = f"PING from {src}"
        print(f"Ping received from {src}: {data.get('message', 'No message')}")
        
    elif msg_type == "DATA":
        stats['data_received'] += 1
        stats['last_message'] = f"DATA: {data.get('sequence', 'N/A')}"
        print(f"Data received from {src}: {data}")
        
    else:
        stats['last_message'] = f"{msg_type} from {src}"
        print(f"Unknown message type '{msg_type}' from {src}: {data}")

async def send_periodic_ping():
    """Send periodic ping messages"""
    await asyncio.sleep_ms(2000)  # Initial delay
    
    while comm and comm.is_running():
        try:
            await comm.send_message("PING", {
                "message": f"Hello from {BOARD_NAME}",
                "uptime": time.time()
            })
            
            await asyncio.sleep_ms(8000)  # Send every 8 seconds
            
        except Exception as e:
            print(f"Ping error: {e}")
            await asyncio.sleep_ms(1000)

async def send_test_data():
    """Send test data messages periodically"""
    await asyncio.sleep_ms(5000)  # Initial delay
    counter = 0
    
    while comm and comm.is_running():
        try:
            counter += 1
            await comm.send_message("DATA", {
                "sensor_reading": counter * 10 + (time.time() % 100),
                "status": "operational",
                "sequence": counter
            })
            
            await asyncio.sleep_ms(300)  # Send every 300ms for speed testing
            
        except Exception as e:
            print(f"Data send error: {e}")
            await asyncio.sleep_ms(1000)

async def update_display():
    """Update OLED display with current status"""
    if DISPLAY_CONNECTED:
        while comm and comm.is_running():
            try:
                comm_stats = comm.get_stats()
                messages = comm_stats['messages']
                
                display.fill(0)
                display.text(f'{BOARD_NAME} - UART', 0, 0, 1)
                display.text(f'ID: {comm_stats["device_id"]}', 0, 8, 1)
                display.text(f'Sent: {messages["sent"]}', 0, 16, 1)
                display.text(f'ACKd: {messages["acknowledged"]}', 0, 24, 1)
                display.text(f'Pend: {comm_stats["pending"]}', 0, 32, 1)
                display.text(f'Pings: {stats["pings_received"]}', 0, 40, 1)
                display.text(f'Mem: {comm_stats["free_memory"]//1000}KB', 0, 48, 1)
                display.show()
                
                await asyncio.sleep_ms(1000)  # Allow REPL interruption
                
            except Exception as e:
                print(f"Display error: {e}")
                await asyncio.sleep_ms(1000)

async def status_reporter():
    """Print periodic status reports"""
    while comm and comm.is_running():
        try:
            await asyncio.sleep_ms(30000)  # Report every 30 seconds
            
            if not DEBUG_PRINTS:
                continue  # Skip detailed reports unless debugging
            
            comm_stats = comm.get_stats()
            messages = comm_stats['messages']
            
            print("\n" + "="*40)
            print(f"{BOARD_NAME} Status Report")
            print("="*40)
            print(f"Messages Sent: {messages['sent']}")
            print(f"Acknowledged: {messages['acknowledged']}")
            print(f"Pending: {comm_stats['pending']}")
            print(f"Failed: {messages['failed']}")
            print(f"Pings Received: {stats['pings_received']}")
            print(f"Data Received: {stats['data_received']}")
            print(f"Last Message: {stats['last_message']}")
            print(f"Free Memory: {comm_stats['free_memory']} bytes")
            print("="*40 + "\n")
            
        except Exception as e:
            print(f"Status report error: {e}")
            await asyncio.sleep_ms(10)

async def main():
    """Main application function"""
    global comm
    
    print(f"Starting {BOARD_NAME} UART Communication Demo")
    print(f"Board: {BOARD_NUMBER}, Baud: {BAUD_RATE}, Debug: {DEBUG_PRINTS}")
    print("Press Ctrl+C to stop")
    
    # Initialize communication
    comm = UARTComm(
        board_name=BOARD_NAME,
        uart_id=1,
        tx_pin=16,
        rx_pin=17,
        baud_rate=BAUD_RATE,
        debug_prints=DEBUG_PRINTS
    )
    
    # Set message handler
    comm.set_message_handler(handle_incoming_message)
    
    # Start communication
    comm.start()
    
    # Send initial message
    await comm.send_message("PING", {
        "message": f"{BOARD_NAME} started successfully",
        "uptime": time.time()
    })
    
    # Start application tasks
    app_tasks = [
        asyncio.create_task(send_periodic_ping()),
        asyncio.create_task(send_test_data()),
        asyncio.create_task(update_display()),
        asyncio.create_task(status_reporter())
    ]
    
    try:
        # Run all tasks concurrently
        await asyncio.gather(*app_tasks)
        
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        print(f"Application error: {e}")
    finally:
        # Clean shutdown
        print("Shutting down...")
        
        # Cancel application tasks
        for task in app_tasks:
            if not task.done():
                task.cancel()
        
        # Stop communication
        if comm:
            comm.stop()
        
        # Final status
        if comm:
            final_stats = comm.get_stats()
            messages = final_stats['messages']
            print(f"Final: {messages['acknowledged']}/{messages['sent']} messages acknowledged")
        
        print(f"{BOARD_NAME} stopped")

# Run the application
if __name__ == "__main__":
    asyncio.run(main())
