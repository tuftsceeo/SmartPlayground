"""
ble_splat.py — BLE driver for Open Splat devices
==================================================
Write pacing, response capture, WRITE_DONE status tracking, always-on
error logging, button debouncing.

Several OpenSplat instances can share the one ubluetooth.BLE() radio when a
caller routes IRQ events to them (see BroadcastCode/SplatCompanion/Companion/splat_hub.py):

- Disconnect and GATT events are acted on only when their conn_handle is
  this instance's.
- Once mac_address is set -- passed in, or learned from the first device
  advertising as "Splat" -- only that address is connected to; it is never
  replaced by another advertisement.
- Scans are counted (_scans_pending): each started scan delivers exactly
  one SCAN_DONE, so a late SCAN_DONE from a stopped scan does not clear
  the flag of a newer one.
- disconnect() leaves the radio active, and nothing here calls
  active(True) on a radio that is already on (_ensure_active()): that
  restarts the stack and drops every other connection.
- connect_direct() connects to a known address (addr, _addr_type) with no
  scan; a failed attempt (a disconnect event for this address with no
  connection handle yet) clears _connecting.

Button debounce compares each raw state against the last *accepted* one,
so a change rejected inside the debounce window is taken on the next
notification (a readSwitches response, or the next button event) instead
of being lost.
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

# Minimum ms between BLE writes to let Splat process each command
_WRITE_PACE_MS = 20

# Max response notifications to keep in ring buffer
_RESPONSE_BUF_SIZE = 8


class OpenSplat():
    def __init__(self, mac_address=None, verbose=False):
        self._ble = ubluetooth.BLE()
        self._ensure_active()

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
        self._scans_pending = 0     # started scans whose SCAN_DONE is still due

        # Write tracking
        self._last_write_ms = 0
        self._last_write_status = 0
        self._write_count = 0
        self._write_errors = 0

        # Response capture — ring buffer of recent notifications
        self._responses = []
        self._capture_responses = False

    def _ensure_active(self):
        """Turn BLE on only if it is off.

        On MicroPython 1.29 (ESP32-C6), active(True) on an active radio
        restarts the stack: every open connection drops and the peer is
        not notified, so a Splat stays in its connected state.
        """
        if not self._ble.active():
            self._ble.active(True)

    def _irq_handler(self, event, data):
        """Handle BLE IRQ events"""
        if event == 1:  # _IRQ_CENTRAL_CONNECT
            conn_handle, addr_type, addr = data
            self._conn_handle = conn_handle
            self.connected = True
            if self._verbose:
                print("Connected as central")

        elif event == 2:  # _IRQ_CENTRAL_DISCONNECT
            if data[0] != self._conn_handle:
                return
            self._reset_connection_state()
            if self._verbose:
                print("Disconnected")

        elif event == 5:  # _IRQ_SCAN_RESULT
            addr_type, addr, adv_type, rssi, adv_data = data
            addr_str = ':'.join(['%02X' % i for i in addr])
            if self._connecting:
                return
            if self.mac_address is None:
                if self._parse_adv_name(adv_data) != 'Splat':
                    return
                # First Splat seen: remember it and stop; the next scan
                # connects to exactly this address.
                self.mac_address = addr_str
                self._stop_scan()
                return
            if addr_str != self.mac_address:
                return
            self._addr_type, self.addr, self.target_addr = addr_type, bytes(addr), addr_str
            self.device_name = self._parse_adv_name(adv_data)
            self._stop_scan()
            self._connecting = True
            try:
                self._ble.gap_connect(self._addr_type, self.addr)
                if self._verbose:
                    print("Connecting...")
            except OSError as e:
                print("Connection failed: %s" % str(e))
                self._connecting = False

        elif event == 6:  # _IRQ_SCAN_DONE
            if self._scans_pending > 0:
                self._scans_pending -= 1
            if self._scans_pending == 0:
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
            if data[0] != self._conn_handle:
                # A connect attempt to our address that never completed.
                if (self._connecting and not self.connected
                        and ':'.join(['%02X' % i for i in data[2]]) == self.mac_address):
                    self._connecting = False
                    if self._verbose:
                        print("Connect attempt failed")
                return
            self._reset_connection_state()
            if self._verbose:
                print("Peripheral disconnected")

        elif 9 <= event <= 18 and data[0] != self._conn_handle:
            return      # GATT event for another connection

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
            self._last_write_status = status
            if status != 0:
                self._write_errors += 1
                print("  BLE write error: status=%d (errs=%d/%d)" % (
                    status, self._write_errors, self._write_count))

        elif event == 18:  # _IRQ_GATTC_NOTIFY
            conn_handle, value_handle, notify_data = data
            if value_handle == self._rx_char_handle:
                self._process_notification(notify_data)

    def _parse_adv_name(self, adv_data):
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
                except UnicodeError:
                    return None     # not a UTF-8 name, so not a Splat
            i += 1 + length
        return None

    def _reset_connection_state(self):
        self.connected = False
        self._conn_handle = None
        self._connecting = False
        self._tx_char_handle = None
        self._rx_char_handle = None
        self._start_handle = None
        self._end_handle = None

    def _process_notification(self, buffer):
        """Process notifications from the Splat device."""
        raw = bytes(buffer)

        # Capture all responses when enabled
        if self._capture_responses:
            if len(self._responses) >= _RESPONSE_BUF_SIZE:
                self._responses.pop(0)
            self._responses.append(raw)

        if len(buffer) >= 11 and buffer[0] == 0x66 and buffer[11] == 0x99:
            if self._verbose:
                value = ':'.join(['%02X' % i for i in buffer])
                print("Device info: %s" % value)

        elif len(buffer) >= 10 and buffer[0] == 0x13 and buffer[10] == 0x31:
            if self._verbose:
                print("Received date/time")

        else:
            data = [d for d in buffer]
            # Button state notification: [3, X, button_byte]
            if data[0] == 3 and len(data) == 3:
                self._handle_button(data[2])
            elif self._verbose:
                print("Notification: %s" % ' '.join('%02X' % b for b in data))

    def _handle_button(self, value):
        """Runs in the BLE IRQ. Compares against the accepted state, so a
        change rejected inside _DEBOUNCE_MS is taken on a later
        notification rather than dropped."""
        now = time.ticks_ms()
        raw_pressed = bool(value & 0x0F)
        if raw_pressed == self.splat_pressed:
            return
        if time.ticks_diff(now, self._last_button_change_ms) < _DEBOUNCE_MS:
            if self._verbose:
                print("  [BTN debounce rejected raw=%d]" % value)
            return
        self._last_button_change_ms = now

        was_pressed = self.splat_pressed
        if self._verbose:
            print("  [BTN was=%s raw=%s]" % (was_pressed, raw_pressed))

        if raw_pressed and not was_pressed:
            self.splat_pressed = True
            if self.on_splat_pressed:
                try:
                    self.on_splat_pressed()
                except Exception as e:
                    print("  Press callback error: %s" % str(e))

        elif not raw_pressed and was_pressed:
            self.splat_pressed = False
            if self.on_splat_released:
                try:
                    self.on_splat_released()
                except Exception as e:
                    print("  Release callback error: %s" % str(e))

    def decode_button(self, value):
        self._handle_button(value)

    def _subscribe_to_notifications(self):
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
        """Write command with pacing."""
        if not self.connected or self._tx_char_handle is None:
            if self._verbose:
                print("Not connected or TX characteristic not found")
            return False

        now = time.ticks_ms()
        elapsed = time.ticks_diff(now, self._last_write_ms)
        if elapsed < _WRITE_PACE_MS:
            time.sleep_ms(_WRITE_PACE_MS - elapsed)

        try:
            self._ble.gattc_write(self._conn_handle, self._tx_char_handle, data)
            self._last_write_ms = time.ticks_ms()
            self._write_count += 1
            if self._verbose:
                print("Sent: %s" % ' '.join('%02X' % b for b in data))
            return True
        except Exception as e:
            print("Send error: %s" % str(e))
            return False

    # ── Response capture ──

    def start_capture(self):
        """Start capturing all notification responses."""
        self._responses = []
        self._capture_responses = True

    def stop_capture(self):
        """Stop capturing responses."""
        self._capture_responses = False

    def get_responses(self, clear=True):
        """Get captured responses. Returns list of bytes objects."""
        r = list(self._responses)
        if clear:
            self._responses = []
        return r

    def dump_responses(self, label=""):
        """Print all captured responses in hex."""
        resps = self.get_responses()
        if label:
            print("  Responses after [%s]: %d" % (label, len(resps)))
        else:
            print("  Responses: %d" % len(resps))
        for i, r in enumerate(resps):
            print("    [%d] (%d bytes) %s" % (i, len(r), ' '.join('%02X' % b for b in r)))
        return resps

    # ── Send + wait for response ──

    def send_and_wait(self, data, label="", wait_ms=300):
        """
        Send a command and wait for the Splat's response notification.
        Returns list of response bytes objects received.
        """
        self.start_capture()
        ba = bytearray(data)
        ok = self._write_command(ba)
        if label:
            print("    [%s] %s -> %s" % (label, ' '.join('%02X' % b for b in ba), "OK" if ok else "FAIL"))
        time.sleep_ms(wait_ms)
        self.stop_capture()
        return self.dump_responses(label)

    # ── Scanning / Connection ──

    def _start_scan(self, duration_ms=0, interval_us=30000, window_us=30000):
        """Start a scan and count it. Raises OSError as gap_scan does (an
        EALREADY means the radio is still scanning)."""
        self._ble.gap_scan(duration_ms, interval_us, window_us)
        self._scans_pending += 1
        self._scanning = True

    def _stop_scan(self):
        """Stop the running scan, if any. Its SCAN_DONE still arrives and
        is counted off in the IRQ."""
        if self._scanning:
            self._ble.gap_scan(None)
            self._scanning = False

    def connect_direct(self, timeout_ms=10000, interval_us=None):
        """Start a connect to the known address (self.addr, self._addr_type,
        learned from an earlier scan) without scanning. Completion arrives
        as _IRQ_PERIPHERAL_CONNECT. interval_us: None for the stack's
        default connection interval, or (min_us, max_us). Raises OSError as
        gap_connect does."""
        if self.addr is None or self._addr_type is None:
            raise OSError("connect_direct: no known address for %s" % self.mac_address)
        self._connecting = True
        try:
            if interval_us is None:
                self._ble.gap_connect(self._addr_type, self.addr, timeout_ms)
            else:
                self._ble.gap_connect(self._addr_type, self.addr, timeout_ms,
                                      interval_us[0], interval_us[1])
        except OSError:
            self._connecting = False
            raise

    def scanSplat(self, timeout=5):
        print("Scanning for Splat...")
        self._reset_connection_state()
        self._start_scan(0, 1000, 1000)
        start = time.time()
        while self._scanning and self.mac_address is None and (time.time() - start < timeout):
            time.sleep(0.1)
        self._stop_scan()
        return self.mac_address

    def connect(self, timeout=30):
        self._ensure_active()
        if self.connected:
            return True
        self._reset_connection_state()
        self._start_scan()
        start_time = time.time()
        while not self.connected and (time.time() - start_time < timeout):
            if not self._scanning and not self._connecting:
                self._start_scan()
            print(".", end="")
            time.sleep(0.5)
        self._stop_scan()
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
        """Drop this Splat's connection. The radio stays active: other
        OpenSplat instances may be using it."""
        if self._conn_handle is not None:
            self._ble.gap_disconnect(self._conn_handle)
            self._conn_handle = None
            self.connected = False
            if self._verbose:
                print("Disconnected from Splat")

    def is_connected(self):
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

    def write_stats(self):
        return "writes=%d errors=%d" % (self._write_count, self._write_errors)