import struct
import time
import machine
from micropython import const

# Constants
_PREAMBLE = const(0x00)
_STARTCODE1 = const(0x00)
_STARTCODE2 = const(0xFF)
_POSTAMBLE = const(0x00)

_HOSTTOPN532 = const(0xD4)
_PN532TOHOST = const(0xD5)

# PN532 Commands
_COMMAND_DIAGNOSE = const(0x00)
_COMMAND_GETFIRMWAREVERSION = const(0x02)
_COMMAND_GETGENERALSTATUS = const(0x04)
_COMMAND_SAMCONFIGURATION = const(0x14)
_COMMAND_INLISTPASSIVETARGET = const(0x4A)
_COMMAND_INDATAEXCHANGE = const(0x40)
_COMMAND_INRELEASE = const(0x52)

_MIFARE_ISO14443A = const(0x00)

# Mifare Commands
MIFARE_CMD_AUTH_A = const(0x60)
MIFARE_CMD_AUTH_B = const(0x61)
MIFARE_CMD_READ = const(0x30)
MIFARE_CMD_WRITE = const(0xA0)
MIFARE_ULTRALIGHT_CMD_WRITE = const(0xA2)

_ACK = b"\x00\x00\xff\x00\xff\x00"
_WAKEUP = const(0x55)
_PN532_I2C_ADDRESS = const(0x24)


class PN532_I2C:
    """PN532 NFC reader via I2C interface for MicroPython"""
    
    def __init__(self, i2c, address=_PN532_I2C_ADDRESS, debug=False):
        """Initialize the PN532 I2C driver
        
        Args:
            i2c: machine.I2C object configured for the desired pins
            address: I2C address of the PN532 (default 0x24)
            debug: Enable debug output
        """
        self.i2c = i2c
        self.address = address
        self.debug = debug
        self.low_power = True
        
        # Initialize the device
        self._wakeup()
        time.sleep(0.5)
        
        # Verify firmware
        try:
            fw = self.get_firmware_version()
            if self.debug:
                print(f"PN532 firmware version: {fw[1]}.{fw[2]}")
        except Exception as e:
            print(f"Warning: Could not verify firmware: {e}")
    
    def _wakeup(self):
        """Wake up the PN532"""
        try:
            self.i2c.writeto(self.address, bytes([_WAKEUP]))
            time.sleep(0.1)
        except Exception as e:
            if self.debug:
                print(f"Wakeup error: {e}")
    
    def _write_data(self, framebytes):
        """Write frame data to the PN532 via I2C"""
        try:
            self.i2c.writeto(self.address, framebytes)
            if self.debug:
                print("Write frame:", [hex(i) for i in framebytes])
        except Exception as e:
            print(f"I2C write error: {e}")
            raise
    
    def _read_data(self, count):
        """Read data from the PN532 via I2C
        
        I2C protocol: First byte is status (0x01 = ready), rest is frame data
        """
        try:
            # Read status byte + frame data
            data = self.i2c.readfrom(self.address, count + 1)
            
            # Check status byte
            status = data[0]
            if status != 0x01:
                # Not ready or error - return empty or retry
                return bytes()
            
            # Return data without status byte
            frame_data = data[1:count + 1]
            if self.debug:
                print("Read frame:", [hex(i) for i in frame_data])
            return frame_data
        except Exception as e:
            print(f"I2C read error: {e}")
            raise
    
    def _wait_ready(self, timeout=1.0):
        """Wait for the PN532 to be ready to respond"""
        start = time.time()
        while (time.time() - start) < timeout:
            try:
                # Read status byte - 0x01 means ready
                status = self.i2c.readfrom(self.address, 1)
                if len(status) > 0 and status[0] == 0x01:
                    return True
            except OSError:
                pass
            time.sleep(0.02)
        return False
    
    def _write_frame(self, data):
        """Write a frame to the PN532"""
        assert data is not None and 1 < len(data) < 255, "Data must be 1-255 bytes"
        
        length = len(data)
        frame = bytearray(length + 8)
        frame[0] = _PREAMBLE
        frame[1] = _STARTCODE1
        frame[2] = _STARTCODE2
        frame[3] = length & 0xFF
        frame[4] = (~length + 1) & 0xFF
        frame[5:-2] = data
        
        # Calculate checksum
        checksum = sum(frame[0:3]) + sum(data)
        frame[-2] = ~checksum & 0xFF
        frame[-1] = _POSTAMBLE
        
        self._write_data(bytes(frame))
    
    def _read_frame(self, length):
        """Read a response frame from the PN532"""
        response = self._read_data(length + 7)
        
        if len(response) == 0:
            raise RuntimeError("No response data")
        
        # Find the start of the frame (0x00 0xFF)
        offset = 0
        while offset < len(response) - 1 and response[offset] == 0x00:
            offset += 1
        
        if offset >= len(response) or response[offset] != 0xFF:
            raise RuntimeError(f"Response frame preamble invalid at offset {offset}: {[hex(b) for b in response[offset:offset+3]]}")
        
        offset += 1
        if offset >= len(response):
            raise RuntimeError("Response contains no data")
        
        # Check length and length checksum
        frame_len = response[offset]
        if offset + 1 >= len(response):
            raise RuntimeError("Frame too short to read length checksum")
        
        if (frame_len + response[offset + 1]) & 0xFF != 0:
            raise RuntimeError(f"Response length checksum mismatch: len={frame_len} checksum={response[offset+1]}")
        
        # Check frame checksum
        if offset + 2 + frame_len + 1 > len(response):
            raise RuntimeError(f"Frame data incomplete: expected {offset + 2 + frame_len + 1} bytes, got {len(response)}")
        
        checksum = sum(response[offset + 2 : offset + 2 + frame_len + 1]) & 0xFF
        if checksum != 0:
            raise RuntimeError(f"Response checksum mismatch: {checksum}")
        
        return response[offset + 2 : offset + 2 + frame_len]
    
    def _send_command(self, command, params=b"", timeout=1.0):
        """Send a command and wait for ACK"""
        if self.low_power:
            self._wakeup()
        
        # Build command frame
        data = bytearray(2 + len(params))
        data[0] = _HOSTTOPN532
        data[1] = command & 0xFF
        for i, val in enumerate(params):
            data[2 + i] = val
        
        self._write_frame(data)
        
        # Small delay to let device process
        time.sleep(0.05)
        
        # Try to read ACK with retry logic
        start = time.time()
        while (time.time() - start) < timeout:
            try:
                if self._wait_ready(0.1):
                    ack = self._read_data(len(_ACK))
                    if ack == _ACK:
                        return True
            except Exception:
                pass
            time.sleep(0.02)
        
        if self.debug:
            print(f"Warning: No ACK for command {command}")
        return False
    
    def _process_response(self, command, response_length=0, timeout=1.0):
        """Read and process a response from the PN532"""
        if not self._wait_ready(timeout):
            return None
        
        response = self._read_frame(response_length + 2)
        
        # Verify response command
        if response[0] != _PN532TOHOST or response[1] != (command + 1):
            raise RuntimeError(f"Unexpected response: {response[0]:02x} {response[1]:02x}")
        
        return response[2:]
    
    def _call_function(self, command, response_length=0, params=b"", timeout=1.0):
        """Send command and get response"""
        if not self._send_command(command, params=params, timeout=timeout):
            return None
        return self._process_response(command, response_length=response_length, timeout=timeout)
    
    def get_firmware_version(self):
        """Get the firmware version tuple (ic, ver, rev, support)"""
        response = self._call_function(_COMMAND_GETFIRMWAREVERSION, response_length=4, timeout=0.5)
        if response is None:
            raise RuntimeError("Failed to detect PN532")
        return tuple(response)
    
    def SAM_configuration(self):
        """Configure the PN532 for MiFare card reading"""
        self._call_function(_COMMAND_SAMCONFIGURATION, params=[0x01, 0x14, 0x01])
    
    def listen_for_passive_target(self, card_baud=_MIFARE_ISO14443A, timeout=1.0):
        """Start listening for a card"""
        try:
            response = self._send_command(
                _COMMAND_INLISTPASSIVETARGET,
                params=[0x01, card_baud],
                timeout=timeout
            )
            return response
        except Exception:
            return False
    
    def get_passive_target(self, timeout=1.0):
        """Get the UID of a card (must call listen_for_passive_target first)"""
        response = self._process_response(
            _COMMAND_INLISTPASSIVETARGET,
            response_length=30,
            timeout=timeout
        )
        
        if response is None:
            return None
        
        if response[0] != 0x01:
            raise RuntimeError("More than one card detected!")
        
        if response[5] > 7:
            raise RuntimeError("UID longer than expected")
        
        return response[6 : 6 + response[5]]
    
    def read_passive_target(self, card_baud=_MIFARE_ISO14443A, timeout=1.0):
        """Wait for a card and return its UID"""
        if not self.listen_for_passive_target(card_baud=card_baud, timeout=timeout):
            return None
        return self.get_passive_target(timeout=timeout)
    
    def release_targets(self):
        """Release detection of targets"""
        try:
            self._call_function(_COMMAND_INRELEASE, params=[0x00])
        except Exception:
            pass
    
    def mifare_classic_authenticate_block(self, uid, block_number, key_number, key):
        """Authenticate a block with a key (key_number should be MIFARE_CMD_AUTH_A or _B)"""
        uidlen = len(uid)
        keylen = len(key)
        params = bytearray(3 + uidlen + keylen)
        params[0] = 0x01
        params[1] = key_number & 0xFF
        params[2] = block_number & 0xFF
        params[3 : 3 + keylen] = key
        params[3 + keylen :] = uid
        
        response = self._call_function(_COMMAND_INDATAEXCHANGE, params=params, response_length=1)
        return response is not None and response[0] == 0x00
    
    def mifare_classic_read_block(self, block_number):
        """Read a 16-byte block from a MiFare card"""
        response = self._call_function(
            _COMMAND_INDATAEXCHANGE,
            params=[0x01, MIFARE_CMD_READ, block_number & 0xFF],
            response_length=17
        )
        
        if response is None or response[0] != 0x00:
            return None
        
        return response[1:]
    
    def mifare_classic_write_block(self, block_number, data):
        """Write a 16-byte block to a MiFare card"""
        assert data is not None and len(data) == 16, "Data must be 16 bytes"
        
        params = bytearray(19)
        params[0] = 0x01
        params[1] = MIFARE_CMD_WRITE
        params[2] = block_number & 0xFF
        params[3:] = data
        
        response = self._call_function(_COMMAND_INDATAEXCHANGE, params=params, response_length=1)
        return response is not None and response[0] == 0x00
    
    def ntag2xx_read_block(self, block_number):
        """Read a 4-byte block from an NTAG card"""
        block = self.mifare_classic_read_block(block_number)
        if block is not None:
            return block[0:4]
        return None
    
    def ntag2xx_write_block(self, block_number, data):
        """Write a 4-byte block to an NTAG card"""
        assert data is not None and len(data) == 4, "Data must be 4 bytes"
        
        params = bytearray(3 + len(data))
        params[0] = 0x01
        params[1] = MIFARE_ULTRALIGHT_CMD_WRITE
        params[2] = block_number & 0xFF
        params[3:] = data
        
        response = self._call_function(_COMMAND_INDATAEXCHANGE, params=params, response_length=1)
        return response is not None and response[0] == 0x00
