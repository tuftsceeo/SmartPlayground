import RS232
myRS232 = RS232.CEEO_RS232(divName = 'all_things_rs232', suffix = '1', myCSS = False, default_code='sd')

import channel
myChannel = channel.CEEO_Channel("hackathon", "@chrisrogers", "talking-on-a-channel", divName = 'all_things_channels', suffix='_test')

# Import our Web Bluetooth module
from pyscript import document, when, window
import asyncio

# Import and create the BLE instance
import webBluetooth
# Create the WebBLE instance from the imported module's code
exec(webBluetooth.code)  # This executes the code and creates the WebBLE class
ble = WebBLE()  # Now create an instance

# Status display elements for BLE
status_div = document.getElementById('ble_status')
messages_div = document.getElementById('ble_messages')

# Status display for RS232
rs232_status_div = document.getElementById('rs232_status')

def update_status(message):
    """Update the BLE status display"""
    status_div.innerHTML = f"Status: {message}"

def add_message(message):
    """Add a message to the BLE messages display"""
    messages_div.innerHTML += f"{message}<br>"
    # Auto-scroll to bottom
    messages_div.scrollTop = messages_div.scrollHeight

def update_rs232_status(message):
    """Update the RS232 status display"""
    rs232_status_div.innerHTML = f"Status: {message}"

def on_ble_data(data):
    """Callback for when BLE data is received"""
    add_message(f"📩 Received: {data}")

# Set the callback
ble.on_data_callback = on_ble_data

# ========== BLE Control Buttons ==========

@when("click", "#ble_connect_esp")
async def connect_esp_handler(event):
    """Handle BLE connect button - searches by service UUID (any ESP32 with Nordic UART)"""
    update_status("Connecting...")
    add_message("Looking for devices with Nordic UART service...")
    
    # Connect to any device with the Nordic UART service UUID
    success = await ble.connect_by_service()  
    
    if success:
        update_status("Connected!")
        add_message(f"Connected to {ble.device.name}")
    else:
        update_status("Connection failed")
        add_message("Failed to connect")

@when("click", "#ble_connect_any")
async def connect_any_handler(event):
    """Handle BLE connect to ANY device (for testing)"""
    update_status("Connecting to any device...")
    add_message("🔍 Requesting ANY BLE device...")
    
    try:
        print("Requesting ANY Bluetooth device...")
        
        # Create options object properly
        options = window.Object.new()
        options.acceptAllDevices = True
        options.optionalServices = [ble.service_uuid]
        
        ble.device = await window.navigator.bluetooth.requestDevice(options)
        
        if not ble.device:
            update_status("❌ No device selected")
            add_message("❌ No device selected")
            return
            
        add_message(f"Selected: {ble.device.name}")
        
        # Continue with normal connection
        print("Connecting to GATT server...")
        ble.server = await ble.device.gatt.connect()
        
        print("Getting service...")
        ble.service = await ble.server.getPrimaryService(ble.service_uuid)
        
        print("Getting characteristics...")
        ble.tx_char = await ble.service.getCharacteristic(ble.tx_uuid)
        ble.rx_char = await ble.service.getCharacteristic(ble.rx_uuid)
        
        print("Starting notifications...")
        await ble.tx_char.startNotifications()
        ble.tx_char.addEventListener('characteristicvaluechanged', ble._on_notification)
        
        update_status("✅ Connected!")
        add_message("✅ Connected!")
        
    except Exception as e:
        update_status("❌ Connection failed")
        add_message(f"❌ Error: {e}")
        print(f"Connection error: {e}")

@when("click", "#ble_disconnect")
async def disconnect_handler(event):
    """Handle BLE disconnect button"""
    await ble.disconnect()
    update_status("Disconnected")
    add_message("👋 Disconnected from device")

@when("click", "#led_on")
async def led_on_handler(event):
    """Turn LED on"""
    if ble.is_connected():
        await ble.send("LED 1")
        add_message("💡 Sent: LED ON")
    else:
        add_message("⚠️ Not connected!")

@when("click", "#led_off")
async def led_off_handler(event):
    """Turn LED off"""
    if ble.is_connected():
        await ble.send("LED 0")
        add_message("🌑 Sent: LED OFF")
    else:
        add_message("⚠️ Not connected!")

@when("click", "#send_hi")
async def send_hi_handler(event):
    """Send Hi message"""
    if ble.is_connected():
        await ble.send("SEND Hi")
        add_message("👋 Sent: Hi")
    else:
        add_message("⚠️ Not connected!")

@when("click", "#send_custom")
async def send_custom_handler(event):
    """Send custom message to display"""
    if ble.is_connected():
        # Get the message from the input box
        message_input = document.getElementById("messageInput")
        message = message_input.value
        
        if message:
            # Send "SEND <message>" to Teacher
            await ble.send(f"SEND {message}")
            add_message(f"📤 Sent to display: {message}")
            
            # Clear the input box after sending
            message_input.value = ""
        else:
            add_message("⚠️ Please enter a message first!")
    else:
        add_message("⚠️ Not connected!")

# ========== RS232 Upload Buttons ==========

@when("click", "#rs232_load_ble")
async def rs232_load_ble_handler(event):
    """Complete BLE setup - uploads library AND firmware"""
    if myRS232.uboard.connected:
        update_rs232_status("⏳ Step 1/2: Uploading BLE_CEEO library...")
        try:
            # Step 1: Upload the library
            import ble_ceeo_lib
            success1 = await myRS232.uboard.board.upload('BLE_CEEO.py', ble_ceeo_lib.code)
            
            if not success1:
                update_rs232_status("❌ Library upload failed")
                return
            
            update_rs232_status("⏳ Step 2/2: Uploading BLE firmware...")
            await asyncio.sleep(0.5)
            
            # Step 2: Upload the main firmware
            import espConnectToPage
            success2 = await myRS232.uboard.board.upload('main.py', espConnectToPage.code)
            
            if success2:
                update_rs232_status("✅ Complete! Resetting board...")
                await myRS232.uboard.board.reset()
                await asyncio.sleep(1)
                update_rs232_status("✅ Board ready! Use BLE Control section above to connect wirelessly.")
            else:
                update_rs232_status("❌ Firmware upload failed")
        except Exception as e:
            update_rs232_status(f"❌ Error: {e}")
    else:
        update_rs232_status("⚠️ Not connected via RS232! Use the terminal below to connect.")

@when("click", "#rs232_sample_code")
async def rs232_sample_code_handler(event):
    """Load sample BLE code into editor"""
    try:
        import bleexample
        myRS232.python.code = bleexample.code
        update_rs232_status("✅ Sample BLE code loaded into editor. You can now edit and upload it.")
    except Exception as e:
        update_rs232_status(f"❌ Error loading sample: {e}")

@when("click", "#rs232_reset")
async def rs232_reset_handler(event):
    """Reset the board"""
    if myRS232.uboard.connected:
        update_rs232_status("🔄 Resetting board...")
        await myRS232.uboard.board.reset()
        await asyncio.sleep(1)
        update_rs232_status("✅ Board reset complete")
    else:
        update_rs232_status("⚠️ Not connected via RS232! Use the terminal below to connect.")

# Keep your existing RS232 code
myRS232.python.code = '''
# Default code - will be replaced when you load BLE code
print("Hello from ESP32C6!")
'''