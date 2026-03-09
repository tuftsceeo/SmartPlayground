"""
ble_splat.py — BLE driver for Open Splat devices
==================================================
Fixed: button debouncing, false trigger prevention,
removed auto-playSound on button press.
"""

import ubluetooth
import time
import struct
import binascii
import micropython


UUID_SERVICE = ubluetooth.UUID(0xfff0)
UUID_CHARACTERISTIC_RECV = ubluetooth.UUID(0xfff4)
UUID_CHARACTERISTIC_WRITE = ubluetooth.UUID(0xfff3)


# Command constants
KEEP_ALIVE = 0x01, 0x00
SOUND_OFF = 0x02, 0x00
ALL_LEDS_OFF = 0x03, 0x00
ALL_TASKS_OFF = 0x04, 0x00
READ_SWITCHES = 0x05, 0x00
READ_BATTERY = 0x06, 0x00
IDENTIFY_SPLAT = 0x00, 0x10
SET_VOLUME = 0x01, 0x10
PLAY_SOUND = 0x00, 0x20
PLAY_RECORDED_SOUND = 0x01, 0x20
LEDS_OFF = 0x04, 0x20
SET_LEDS = 0x01, 0x50
PLAY_LED_SEQUENCE = 0x01, 0x60
FLASH_LEDS = 0x01, 0x70
NOTE_ON = 0x00, 0x40
NOTE_OFF = 0x01, 0x40

# Button debounce
_DEBOUNCE_MS = 80


class OpenSplat():
    def __init__(self, mac_address=None, verbose=False):
        self._ble = ubluetooth.BLE()
        self._ble.active(True)

        self.mac_address = mac_address

        self._connection = None
        self._conn_handle = None
        self._tx_char_handle = None
        self._rx_char_handle = None

        self._device_info = {}
        self._date_time = None
        self._time_schedule = []

        self.on_splat_pressed = None
        self.on_splat_released = None

        self.sound = 1
        self.volume = 255

        # Set up IRQ handler
        self._ble.irq(self._irq_handler)

        # Connection state
        self.connected = False
        self._addr_type = None
        self.addr = None
        self.target_addr = None
        self.device_name = None
        self._value_handle = None
        self._start_handle = None
        self._end_handle = None
        self._verbose = verbose
        self._connecting = None
        self._scanning = False

        # Button state with debounce
        self.splat_pressed = False
        self._last_button_change_ms = 0
        self._last_raw_state = False

    def _irq_handler(self, event, data):
        """Handle BLE IRQ events"""
        if event == 1:  # _IRQ_CENTRAL_CONNECT
            conn_handle, addr_type, addr = data
            self._conn_handle = conn_handle
            self.connected = True
            if self._verbose:
                print("Connected as central")

        elif event == 2:  # _IRQ_CENTRAL_DISCONNECT
            self._reset_connection_state()
            if self._verbose:
                print("Disconnected")

        elif event == 5:  # _IRQ_SCAN_RESULT
            self._addr_type, self.addr, adv_type, rssi, adv_data = data
            self.device_name = self._parse_adv_name(adv_data)
            self.target_addr = ':'.join(['%02X' % i for i in self.addr])

            if self.target_addr == self.mac_address and not self._connecting:
                self._ble.gap_scan(None)
                self._scanning = False
                self._connecting = True
                try:
                    self._ble.gap_connect(self._addr_type, self.addr)
                    if self._verbose:
                        print("Connecting...")
                except Exception as e:
                    print("Connection failed: %s" % str(e))
                    self._connecting = False

            elif self.device_name == 'Splat' and not self._connecting:
                self.mac_address = self.target_addr
                self._ble.gap_scan(None)
                self._scanning = False

        elif event == 6:  # _IRQ_SCAN_DONE
            self._scanning = False
            if self._verbose:
                print("Scan complete")

        elif event == 7:  # _IRQ_PERIPHERAL_CONNECT
            conn_handle, addr_type, addr = data
            addr_str = ':'.join(['%02X' % i for i in addr])

            if addr_str == self.mac_address:
                self._conn_handle = conn_handle
                self.connected = True
                self._connecting = False
                if self._verbose:
                    print("Connected! Discovering services...")
                self._ble.gattc_discover_services(self._conn_handle)

        elif event == 8:  # _IRQ_PERIPHERAL_DISCONNECT
            self._reset_connection_state()
            if self._verbose:
                print("Peripheral disconnected")

        elif event == 9:  # _IRQ_GATTC_SERVICE_RESULT
            conn_handle, start_handle, end_handle, uuid = data
            if uuid == UUID_SERVICE:
                self._start_handle = start_handle
                self._end_handle = end_handle
                if self._verbose:
                    print("Service found: %d-%d" % (start_handle, end_handle))

        elif event == 10:  # _IRQ_GATTC_SERVICE_DONE
            if self._start_handle and self._end_handle:
                self._ble.gattc_discover_characteristics(
                    self._conn_handle, self._start_handle, self._end_handle
                )
            else:
                print("Required service not found")

        elif event == 11:  # _IRQ_GATTC_CHARACTERISTIC_RESULT
            conn_handle, def_handle, value_handle, properties, uuid = data
            if uuid == UUID_CHARACTERISTIC_WRITE:
                self._tx_char_handle = value_handle
            elif uuid == UUID_CHARACTERISTIC_RECV:
                self._rx_char_handle = value_handle

        elif event == 12:  # _IRQ_GATTC_CHARACTERISTIC_DONE
            if self._rx_char_handle:
                self._subscribe_to_notifications()
            if self._verbose:
                print("Setup complete!")

        elif event == 17:  # _IRQ_GATTC_WRITE_DONE
            conn_handle, value_handle, status = data
            if self._verbose and status != 0:
                print("Write error: %d" % status)

        elif event == 18:  # _IRQ_GATTC_NOTIFY
            conn_handle, value_handle, notify_data = data
            if value_handle == self._rx_char_handle:
                self._process_notification(notify_data)

    def _parse_adv_name(self, adv_data):
        """Parse device name from advertising data"""
        i = 0
        while i < len(adv_data):
            length = adv_data[i]
            if length == 0:
                break
            ad_type = adv_data[i + 1]
            if ad_type == 0x09 or ad_type == 0x08:
                name_bytes = adv_data[i + 2:i + 1 + length]
                try:
                    return bytes(name_bytes).decode('utf-8')
                except:
                    return None
            i += 1 + length
        return None

    def _reset_connection_state(self):
        """Reset all connection-related state"""
        self.connected = False
        self._conn_handle = None
        self._connecting = False
        self._tx_char_handle = None
        self._rx_char_handle = None
        self._start_handle = None
        self._end_handle = None

    def _process_notification(self, buffer):
        """Process notifications from the Splat device"""
        if len(buffer) >= 11 and buffer[0] == 0x66 and buffer[11] == 0x99:
            # Device info packet
            if self._verbose:
                value = ':'.join(['%02X' % i for i in buffer])
                print("Device info: %s" % value)

        elif len(buffer) >= 10 and buffer[0] == 0x13 and buffer[10] == 0x31:
            # Date/time packet
            if self._verbose:
                print("Received date/time")

        else:
            data = [d for d in buffer]
            # Button state notification: [3, X, button_byte]
            if data[0] == 3 and len(data) == 3:
                self._handle_button(data[2])
            elif self._verbose:
                print("Unknown notification: %s" % str(data))

    def _handle_button(self, value):
        """
        Process button state with debouncing.
        Prevents false triggers from noisy BLE notifications.

        value: bitmask of pressed buttons (any bit set = pressed)
        """
        now = time.ticks_ms()

        # Determine current raw state
        raw_pressed = bool(value & 0x0F)  # any of the 4 button bits

        # Ignore if same as last raw state (no change)
        if raw_pressed == self._last_raw_state:
            return
        self._last_raw_state = raw_pressed

        # Debounce: ignore if too soon after last change
        if time.ticks_diff(now, self._last_button_change_ms) < _DEBOUNCE_MS:
            return
        self._last_button_change_ms = now

        was_pressed = self.splat_pressed

        if raw_pressed and not was_pressed:
            # Button just pressed
            self.splat_pressed = True
            if self.on_splat_pressed:
                try:
                    self.on_splat_pressed()
                except Exception as e:
                    print("  Press callback error: %s" % str(e))

        elif not raw_pressed and was_pressed:
            # Button just released
            self.splat_pressed = False
            if self.on_splat_released:
                try:
                    self.on_splat_released()
                except Exception as e:
                    print("  Release callback error: %s" % str(e))

    def _subscribe_to_notifications(self):
        """Subscribe to device notifications"""
        if self._rx_char_handle:
            try:
                self._ble.gattc_write(
                    self._conn_handle, self._rx_char_handle + 1, b'\x01\x00'
                )
                if self._verbose:
                    print("Subscribed to notifications")
            except Exception as e:
                print("Subscription failed: %s" % str(e))

    def _write_command(self, data):
        """Write command to Splat device"""
        if not self.connected or self._tx_char_handle is None:
            if self._verbose:
                print("Not connected or TX characteristic not found")
            return False

        try:
            self._ble.gattc_write(self._conn_handle, self._tx_char_handle, data)
            if self._verbose:
                print("Sent: %s" % str([hex(b) for b in data]))
            return True
        except Exception as e:
            print("Send error: %s" % str(e))
            return False

    def decode_button(self, value):
        """Legacy method — now handled by _handle_button"""
        self._handle_button(value)

    def scanSplat(self, timeout=5):
        """Scan for nearby Splat device"""
        print("Scanning for Splat...")
        self._reset_connection_state()

        self._scanning = True
        self._ble.gap_scan(0, 1000, 1000)

        start = time.time()
        while self._scanning and (time.time() - start < timeout):
            time.sleep(0.1)

        if self._scanning:
            self._ble.gap_scan(None)
            self._scanning = False

        return self.mac_address

    def connect(self, timeout=30):
        """Connect to the Splat device"""
        self._ble.active(True)

        if self.connected:
            return True

        self._reset_connection_state()

        self._scanning = True
        self._ble.gap_scan(0, 30000, 30000)

        start_time = time.time()
        while not self.connected and (time.time() - start_time < timeout):
            if not self._scanning and not self._connecting:
                self._scanning = True
                self._ble.gap_scan(0, 30000, 30000)
            print(".", end="")
            time.sleep(0.5)

        if self._scanning:
            self._ble.gap_scan(None)
            self._scanning = False

        if not self.connected:
            print("\nConnection timeout after %ds" % timeout)
            return False

        start_time = time.time()
        while (not self._tx_char_handle or not self._rx_char_handle) and (time.time() - start_time < 10):
            time.sleep(0.5)

        if not self._tx_char_handle or not self._rx_char_handle:
            print("\nService setup failed")
            self.disconnect()
            return False

        print("\nConnected successfully!")
        return True

    def disconnect(self):
        """Disconnect from device"""
        if self._conn_handle is not None:
            self._ble.gap_disconnect(self._conn_handle)
            self._conn_handle = None
            self.connected = False
            if self._verbose:
                print("Disconnected from Splat")
            self._ble.active(False)

    def is_connected(self):
        """Check if connected to device"""
        return self.connected

    # ── Command implementations ──

    def keepAlive(self):
        return self._write_command(bytearray(KEEP_ALIVE))

    def soundOff(self):
        return self._write_command(bytearray(SOUND_OFF))

    def allLEDsOff(self):
        return self._write_command(bytearray(ALL_LEDS_OFF))

    def allTasksOff(self):
        return self._write_command(bytearray(ALL_TASKS_OFF))

    def readSwitches(self):
        return self._write_command(bytearray(READ_SWITCHES))

    def readBattery(self):
        return self._write_command(bytearray(READ_BATTERY))

    def identifySplat(self):
        return self._write_command(bytearray(IDENTIFY_SPLAT))

    def setVolume(self, vol):
        return self._write_command(bytearray(SET_VOLUME + (vol,)))

    def playSound(self, soundIndex, vol):
        return self._write_command(bytearray(PLAY_SOUND + (soundIndex, vol)))

    def playRecordedSound(self, soundIndex, vol):
        return self._write_command(bytearray(PLAY_RECORDED_SOUND + (soundIndex, vol)))

    def LEDsOff(self, lowByte, highByte):
        return self._write_command(bytearray(LEDS_OFF + (lowByte, highByte)))

    def setLEDsON(self, color):
        return self._write_command(bytearray(
            SET_LEDS + (0xFF, 0x3F, color[0], color[1], color[2])
        ))

    def setLEDs(self, leds, red, green, blue):
        value = 0
        for led in leds:
            value = value | 1 << led
        return self._write_command(bytearray(
            SET_LEDS + (value & 0xFF, value >> 8 & 0xFF, red, green, blue)
        ))

    def playLEDSequence(self, seqIndex, red, green, blue, duration, loops):
        return self._write_command(bytearray(
            PLAY_LED_SEQUENCE + (seqIndex, red, green, blue, duration, loops)
        ))

    def flashLEDs(self, lowByte, highByte, red, green, blue, duration, flashes):
        return self._write_command(bytearray(
            FLASH_LEDS + (lowByte, highByte, red, green, blue, duration, flashes)
        ))

    def noteOn(self, note, velocity, octave, instrument):
        return self._write_command(bytearray(
            NOTE_ON + (note, octave, velocity, instrument)
        ))

    def noteOff(self, note, velocity, octave, instrument):
        return self._write_command(bytearray(
            NOTE_OFF + (note, octave, velocity, instrument)
        ))