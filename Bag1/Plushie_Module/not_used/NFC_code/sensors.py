import machine
from machine import Pin, SoftI2C, ADC
from pn532_i2c import PN532_I2C, MIFARE_CMD_AUTH_A, MIFARE_CMD_AUTH_B
from icons import SSD1306_SMART
import utime

SDA = 6
SCL = 7
#nav switches
switch_down = Pin(8, Pin.IN)
switch_select = Pin(9, Pin.IN)
switch_up= Pin(10, Pin.IN)

# Potentiometer on pin 3
pot = ADC(Pin(3))
pot.atten(ADC.ATTN_11DB)  # Full range 0-3.3V

i2c = SoftI2C(scl = Pin(7), sda = Pin(6))
display = SSD1306_SMART(128, 64, i2c)

# Animal names
ANIMALS = ["Lion", "Zebra", "Otter"]

class NFC:
    def __init__(self, detect_callback = None, removed_calback = None):
        self.on_detect = detect_callback
        self.on_remove = removed_calback
        self.error_count = 0
        self.last_read_failed = False
        self.detected_cards = set()
        self.current_uid = None
        
        self.rf = PN532_I2C(i2c, debug=False)
        self.rf.SAM_configuration()
        
    def version(self):
        try:
            ic, ver, rev, support = self.rf.get_firmware_version()
            return 'Firmware: {0}.{1}'.format(ver, rev)
        except Exception as e:
            self.rf = None
            return f'No NFC detected: {e}'
            
    def read(self, timeout = 1.0):
        uid = self.rf.read_passive_target(timeout=timeout)
        self.error_count = 0
        if uid:
            uid_tuple = tuple(uid)
            self.current_uid = uid
            if uid_tuple not in self.detected_cards:
                self.detected_cards.add(uid_tuple)
                if self.on_detect: self.on_detect(list(uid))
            self.last_read_failed = False
        else:
            if self.detected_cards and not self.last_read_failed:
                for card in self.detected_cards:
                    if self.on_remove: self.on_remove(list(card))
                self.detected_cards.clear()
                self.current_uid = None
            self.last_read_failed = False
    
    def write_mifare_block(self, block_number, data, key=b'\xFF\xFF\xFF\xFF\xFF\xFF', key_type=MIFARE_CMD_AUTH_A):
        """Write to MiFare Classic card (16 bytes)"""
        if not self.current_uid:
            return False, "No card detected"
        
        if len(data) != 16:
            # Pad data to 16 bytes
            data = data + b'\x00' * (16 - len(data))
        
        try:
            if not self.rf.mifare_classic_authenticate_block(self.current_uid, block_number, key_type, key):
                return False, "Auth failed"
            
            if self.rf.mifare_classic_write_block(block_number, data):
                return True, "Write successful"
            else:
                return False, "Write cmd failed"
        except Exception as e:
            return False, f"Error: {str(e)[:20]}"
    
    def write_ntag_block(self, block_number, data):
        """Write to NTAG card (4 bytes)"""
        if not self.current_uid:
            return False, "No card detected"
        
        if len(data) != 4:
            # Pad or truncate to 4 bytes
            data = (data + b'\x00\x00\x00\x00')[:4]
        
        try:
            if self.rf.ntag2xx_write_block(block_number, data):
                return True, "Write successful"
            else:
                return False, "Write cmd failed"
        except Exception as e:
            return False, f"Error: {str(e)[:20]}"
    
    def write_animal_name(self, name):
        """Write animal name to card - tries both MiFare and NTAG"""
        name_bytes = name.encode('ascii')
        
        # Try MiFare first (16 bytes on block 4)
        success, msg = self.write_mifare_block(4, name_bytes)
        if success:
            return True, "MiFare write OK"
        
        # Try NTAG (4 bytes on block 4)
        success, msg = self.write_ntag_block(4, name_bytes)
        if success:
            return True, "NTAG write OK"
        
        return False, "Write failed"
    
    def read_mifare_block(self, block_number, key=b'\xFF\xFF\xFF\xFF\xFF\xFF', key_type=MIFARE_CMD_AUTH_A):
        """Read from MiFare Classic card (returns 16 bytes)"""
        if not self.current_uid:
            return None, "No card detected"
        
        try:
            if not self.rf.mifare_classic_authenticate_block(self.current_uid, block_number, key_type, key):
                return None, "Auth failed"
            
            data = self.rf.mifare_classic_read_block(block_number)
            if data:
                return data, "Read successful"
            else:
                return None, "Read failed"
        except Exception as e:
            return None, f"Error: {str(e)[:20]}"
    
    def read_ntag_block(self, block_number):
        """Read from NTAG card (returns 4 bytes)"""
        if not self.current_uid:
            return None, "No card detected"
        
        try:
            data = self.rf.ntag2xx_read_block(block_number)
            if data:
                return data, "Read successful"
            else:
                return None, "Read failed"
        except Exception as e:
            return None, f"Error: {str(e)[:20]}"
    
    def read_animal_name(self):
        """Read animal name from card - tries both MiFare and NTAG"""
        # Try MiFare first
        data, msg = self.read_mifare_block(4)
        if data:
            try:
                # Remove null bytes and decode
                name = data.split(b'\x00')[0].decode('ascii')
                return name, "MiFare"
            except:
                pass
        
        # Try NTAG
        data, msg = self.read_ntag_block(4)
        if data:
            try:
                name = data.split(b'\x00')[0].decode('ascii')
                return name, "NTAG"
            except:
                pass
        
        return None, None
        
    def reset(self):
        self.error_count += 1
        self.last_read_failed = True
        if self.error_count > 5:
            try:
                self.rf.SAM_configuration()
                self.error_count = 0
            except Exception:
                pass

class AnimalSelector:
    def __init__(self, animals):
        self.animals = animals
        self.selected_index = 0
        self.last_pot_value = 0
        
    def update(self, pot_value):
        """Update selected animal based on potentiometer value (0-4095)"""
        # Divide range into sections for each animal
        section_size = 4096 // len(self.animals)
        new_index = min(pot_value // section_size, len(self.animals) - 1)
        
        # Add hysteresis to prevent flickering
        if abs(pot_value - self.last_pot_value) > 50:
            self.selected_index = new_index
            self.last_pot_value = pot_value
            return True  # Changed
        return False  # No change
    
    def get_selected(self):
        return self.animals[self.selected_index]
    
    def get_index(self):
        return self.selected_index

# Global state
card_present = False
card_uid = None
selector = AnimalSelector(ANIMALS)

def draw_main_screen():
    """Draw the main animal selection screen"""
    display.clear()
    
    # Title
    display.text("Select Animal:", 10, 0, 1)
    
    # Draw all animals with arrow pointing to selected
    y_pos = 18
    for i, animal in enumerate(ANIMALS):
        if i == selector.get_index():
            display.text(">", 5, y_pos, 1)
            display.text(animal, 20, y_pos, 1)
        else:
            display.text(animal, 20, y_pos, 1)
        y_pos += 12
    
    # Instructions at bottom
    if card_present:
        display.text("UP=Write DOWN=Read", 0, 54, 1)
    else:
        display.text("Place card...", 20, 54, 1)
    
    display.show()

def on_detect(uid):
    global card_present, card_uid
    card_present = True
    card_uid = uid
    print(f'Card detected: {uid}')
    draw_main_screen()
    
def on_remove(uid):
    global card_present, card_uid
    card_present = False
    card_uid = None
    print(f'Card removed: {uid}')
    draw_main_screen()

# Initialize NFC
nfc = NFC(on_detect, on_remove)

# Startup screen
display.clear()
display.text('Animal Card', 20, 10, 1)
display.text('Writer', 35, 22, 1)
display.text(nfc.version(), 5, 40, 1)
display.show()
utime.sleep(2)

draw_main_screen()

last_update = utime.ticks_ms()

while nfc.rf is not None:
    try:
        # Read NFC cards
        nfc.read(timeout=0.5)
        
        # Update potentiometer selection (every 100ms to avoid flicker)
        if utime.ticks_diff(utime.ticks_ms(), last_update) > 100:
            pot_value = pot.read()
            if selector.update(pot_value):
                draw_main_screen()
            last_update = utime.ticks_ms()
        
        # WRITE - UP button
        if switch_up.value() == 0 and card_present:
            selected_animal = selector.get_selected()
            
            display.clear()
            display.text("Writing...", 30, 20, 1)
            display.text(selected_animal, 35, 35, 1)
            display.show()
            
            success, msg = nfc.write_animal_name(selected_animal)
            
            print(f"Write {selected_animal}: {msg}")
            
            display.clear()
            if success:
                display.text("Write Success!", 15, 15, 1)
                display.text(selected_animal, 35, 30, 1)
                display.text("written to card", 15, 45, 1)
            else:
                display.text("Write Failed!", 20, 20, 1)
                display.text(msg, 10, 35, 1)
            display.show()
            
            utime.sleep(2)
            draw_main_screen()
            utime.sleep(0.3)  # Debounce
        
        # READ - DOWN button
        if switch_down.value() == 0 and card_present:
            display.clear()
            display.text("Reading...", 30, 25, 1)
            display.show()
            
            name, card_type = nfc.read_animal_name()
            
            print(f"Read result: {name} ({card_type})")
            
            display.clear()
            if name:
                display.text("Card contains:", 15, 10, 1)
                display.text(name, 40, 28, 1)
                display.text(f"({card_type})", 35, 45, 1)
            else:
                display.text("No data found", 20, 20, 1)
                display.text("or read failed", 15, 35, 1)
            display.show()
            
            utime.sleep(2)
            draw_main_screen()
            utime.sleep(0.3)  # Debounce
        
        # SELECT button - could be used for other functions
        if switch_select.value() == 0:
            utime.sleep(0.3)  # Debounce
            
    except Exception as e:
        print(f"Exception: {e}")
        nfc.reset()