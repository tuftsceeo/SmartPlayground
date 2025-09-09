import network
import time
import ubinascii
import espnow
import gc
import struct
import json
import machine


class Networking:
    def __init__(self, infmsg=False, dbgmsg=False, errmsg=False, admin=False, inittime=0):
        gc.collect()
        self.inittime = inittime
        if infmsg:
            print(f"{(time.ticks_ms() - self.inittime) / 1000:.3f} Initialising Networking")
        self.master = self
        self.infmsg = infmsg
        self.dbgmsg = dbgmsg
        self.errmsg = errmsg
        self.admin = admin
        self.config = {"Name": None,
                       "Configuration": None,
                       "id": None,
                       "Version": None,
        } #Just as an example, can include more information here, but for interoperability purposes please keep the basic four attributes

        self._staif = network.WLAN(network.STA_IF)
        self._apif = network.WLAN(network.AP_IF)

        self.sta = self.Sta(self, self._staif)
        self.ap = self.Ap(self, self._apif)
        self.aen = self.Aen(self)

        if infmsg:
            print(f"{(time.ticks_ms() - self.inittime) / 1000:.3f} Networking initialised and ready")

    def cleanup(self):
        self.dprint(".cleanup")
        self.aen.cleanup()
        self._staif.active(False)
        self._apif.active(False)

    def log(self, text):
        if self.admin:
            with open("log.txt", "a") as f:
                f.write(f"{text}\n")

    def iprint(self, message):
        if self.infmsg:
            try:
                text = f"{(time.ticks_ms() - self.inittime) / 1000:.3f} Networking Info: {message}"
                print(text)
                self.log(text)
            except Exception as e:
                print(f"Error printing Networking Info: {e}")
        return

    def dprint(self, message):
        if self.dbgmsg:
            try:
                text = f"{(time.ticks_ms() - self.inittime) / 1000:.3f} Networking Debug: {message}"
                print(text)
                self.log(text)
            except Exception as e:
                print(f"Error printing Networking Debug: {e}")
        return

    def eprint(self, message):
        if self.errmsg:
            try:
                text = f"{(time.ticks_ms() - self.inittime) / 1000:.3f} Networking Error: {message}"
                print(text)
                self.log(text)
            except Exception as e:
                print(f"Error printing Networking Error: {e}")
        return
    
    class Sta:
        def __init__(self, master, _staif):
            self.master = master
            self._sta = _staif
            self._sta.active(True)
            self.master.iprint("STA initialised and ready")

        def scan(self):
            self.master.dprint("sta.scan")
            scan_result = self._sta.scan()
            if self.master.infmsg:
                for ap in scan_result:
                    self.master.iprint(f"SSID:%s BSSID:%s Channel:%d Strength:%d RSSI:%d Auth:%d " % ap)
            return scan_result

        def connect(self, ssid, key="", timeout=10):
            self.master.dprint("sta.connect")
            self._sta.connect(ssid, key)
            stime = time.time()
            while time.time() - stime < timeout:
                if self._sta.ifconfig()[0] != '0.0.0.0':
                    self.master.iprint("Connected to WiFi")
                    return
                time.sleep(0.1)
            self.master.iprint(f"Failed to connect to WiFi: {self._sta.status()}")

        def disconnect(self):
            self.master.dprint("sta.disconnect")
            self._sta.disconnect()

        def ip(self):
            self.master.dprint("sta.ip")
            return self._sta.ifconfig()

        def mac(self):
            self.master.dprint("sta.mac")
            return bytes(self._sta.config('mac'))

        def mac_decoded(self):  # Necessary?
            self.master.dprint("sta.mac_decoded")
            return ubinascii.hexlify(self._sta.config('mac'), ':').decode()

        def channel(self):
            self.master.dprint("sta.channel")
            return self._sta.config('channel')

        def set_channel(self, number):
            self.master.dprint("sta.set_channel")
            if number > 14 or number < 0:
                number = 0
            self._sta.config(channel=number)
            self.master.iprint(f"STA channel set to {number}")

    class Ap:
        def __init__(self, master, _apif):
            self.master = master
            self._ap = _apif
            self._ap.active(True)
            self.master.iprint("AP initialised and ready")

        def set_ap(self, name="", password="", max_clients=10):
            self.master.dprint("ap.set_ap")
            if name == "":
                name = self.master.config["name"]
            self._ap.active(True)
            self._ap.config(essid=name)
            if password:
                self._ap.config(authmode=network.AUTH_WPA_WPA2_PSK, password=password)
            self._ap.config(max_clients=max_clients)
            self.master.iprint(f"Access Point {name} set with max clients {max_clients}")

        def deactivate(self):
            self.master.dprint("ap.deactivate")
            self._ap.active(False)
            self.master.iprint("Access Point deactivated")

        def ip(self):
            self.master.dprint("ap.ip")
            return self._ap.ifconfig()

        def mac(self):
            self.master.dprint("ap.mac")
            return bytes(self._ap.config('mac'))

        def mac_decoded(self):
            self.master.dprint("ap.mac_decoded")
            return ubinascii.hexlify(self._ap.config('mac'), ':').decode()

        def channel(self):
            self.master.dprint("ap.channel")
            return self._ap.config('channel')

        def set_channel(self, number):
            self.master.dprint("ap.set_channel")
            if number > 14 or number < 0:
                number = 0
            self._ap.config(channel=number)
            self.master.iprint(f"AP channel set to {number}")

    class Aen:
        def __init__(self, master):
            self.master = master
            self._aen = espnow.ESPNow()
            self._aen.active(True)

            self._peers = {}
            self._received_messages = []
            self._received_messages_size = []
            self._long_buffer = {}
            self._long_buffer_size = {}
            self.received_sensor_data = {}
            self.received_rssi_data = {}
            self._irq_function = None
            self.boop_irq = None
            self.data_irq = None
            self.msg_irq = None
            self.ack_irq = None
            self.custom_cmd = None
            self.custom_inf = None
            self.custom_ack = None
            self.boops = 0
            self.ifidx = 0  # 0 sends via sta, 1 via ap
            # self.channel = 0

            self._aen.irq(self._irq)

            self.master.iprint("ESP-NOW initialised and ready")

        def cleanup(self):
            self.master.iprint("aen.cleanup")
            self.irq(None)
            self._aen.active(False)
            # add delete buffers and stuff

        def update_peer(self, peer_mac, peer_config=None, channel=None, ifidx=None):
            self.master.dprint("aen.update_peer")
            if peer_mac == b'\xff\xff\xff\xff\xff\xff':
                return
            if peer_mac in self._peers:
                try:
                    if peer_config is not None:
                        self._peers[peer_mac].update(peer_config)
                    if channel is not None:
                        self._peers[peer_mac].update({'channel': channel})
                    if ifidx is not None:
                        self._peers[peer_mac].update({'ifidx': ifidx})
                    self.master.dprint(f"Peer {peer_mac} updated to channel {channel}, ifidx {ifidx} and name {self.peer_name(peer_mac)}")
                except OSError as e:
                    self.master.eprint(f"Error updating peer {peer_mac}: {e}")
                return
            self.master.iprint(f"Peer {peer_mac} not found")

        def add_peer(self, peer_mac, peer_config=None, channel=None, ifidx=None):
            self.master.dprint("aen.add_peer")
            if peer_mac == b'\xff\xff\xff\xff\xff\xff':
                return
            if peer_mac not in self._peers:
                try:
                    self._peers[peer_mac] = {}
                    if channel is not None:
                        self._peers[peer_mac].update({'channel': channel})
                    if ifidx is not None:
                        self._peers[peer_mac].update({'ifidx': ifidx})
                    if peer_config is not None:
                        self._peers[peer_mac].update(peer_config)
                    self._peers[peer_mac].update({'rssi': None, 'time': None, 'last_ping': 0})
                    self.master.dprint(f"Peer {peer_mac} added with channel {channel}, ifidx {ifidx} and name {self.peer_name(peer_mac)}")
                except OSError as e:
                    self.master.eprint(f"Error adding peer {peer_mac}: {e}")
            else:
                self.master.dprint(f"Peer {peer_mac} already exists, updating")
                self.update_peer(peer_mac, peer_config, channel, ifidx)

        def remove_peer(self, peer_mac):
            self.master.dprint("aen.remove_peers")
            if peer_mac in self._peers:
                try:
                    del self._peers[peer_mac]
                    self.master.iprint(f"Peer {peer_mac} removed")
                except OSError as e:
                    self.master.eprint(f"Error removing peer {peer_mac}: {e}")

        def peers(self):
            self.master.dprint("aen.peers")
            rssi_table = self._aen.peers_table
            for key in self._peers:
                self._peers[key].update({'rssi': rssi_table[key][0]})
                self._peers[key].update({'time': rssi_table[key][1]-self.master.inittime})
            return self._peers

        def peer_name(self, key):
            self.master.dprint("aen.name")
            if isinstance(key, list):
                return "..."
            if key in self._peers:
                if 'name' in self._peers[key]:
                    return self._peers[key]['name']
                else:
                    return None
            else:
                return None

        def rssi(self):
            self.master.dprint("aen.rssi")
            return self._aen.peers_table

        # Send cmds
        def send_custom(self, msg_code, msg_subcode, mac, payload=None, channel=None, ifidx=None):
            self.master.dprint("aen.send_custom")
            self._compose(mac, payload, msg_code, msg_subcode, channel, ifidx)
            gc.collect()

        def ping(self, mac, channel=None, ifidx=None): #Ping
            self.master.dprint("aen.ping")
            if bool(self.ifidx):
                send_channel = self.master.ap.channel()
            else:
                send_channel = self.master.sta.channel()
            self.send_custom(0x01, 0x10, mac, [send_channel, self.ifidx, self.master.config], channel, ifidx)  # sends channel, ifidx and name
            if isinstance(mac, list):
                for key in mac:
                    self._peers[key].update({'last_ping': time.ticks_ms()})
            elif mac == b'\xff\xff\xff\xff\xff\xff':
                for key in self._peers:
                    self._peers[key].update({'last_ping': time.ticks_ms()})
            else:
                self._peers[mac].update({'last_ping': time.ticks_ms()})

        def boop(self, mac, channel=None, ifidx=None): #"RSSI/Status/Config-Boop"
            self.master.dprint("aen.boop")
            self.send_custom(0x01, 0x15, mac, None, channel, ifidx)

        def echo(self, mac, message, channel=None, ifidx=None):
            self.master.dprint("aen.echo")
            if len(str(message)) > 241:
                try:
                    self.master.iprint(f"Sending echo ({message}) to {mac} ({self.peer_name(mac)})")
                except Exception as e:
                    self.master.eprint(f"Sending echo to {mac}, but error printing message content: {e}")
            else:
                self.master.iprint(f"Sending echo ({message}) to {mac} ({self.peer_name(mac)})")
            self.send_custom(0x01, 0x15, mac, message, channel, ifidx)
            gc.collect()

        def send_message(self, mac, message, channel=None, ifidx=None):
            self.send(mac, message, channel, ifidx)
            
        def send(self, mac, message, channel=None, ifidx=None):
            self.master.dprint("aen.send_message")
            if len(str(message)) > 241:
                try:
                    self.master.iprint(
                        f"Sending message ({str(message)[:50] + '... (truncated)'}) to {mac} ({self.peer_name(mac)})")
                except Exception as e:
                    self.master.eprint(f"Sending message to {mac} ({self.peer_name(mac)}), but error printing message content: {e}")
                    gc.collect()
            else:
                self.master.iprint(f"Sending message ({message}) to {mac} ({self.peer_name(mac)})")
            self._compose(mac, message, 0x02, 0x22, channel, ifidx)
            gc.collect()

        def send_data(self, mac, message, channel=None,ifidx=None):  # message is a dict, key is the sensor type and the value is the sensor value, fix name!!!!!!!
            self.master.dprint("aen.message")
            try:
                self.master.iprint(f"Sending sensor data ({message}) to {mac} ({self.peer_name(mac)})")
            except Exception as e:
                self.master.eprint(f"Sending sensor data to {mac} ({self.peer_name(mac)}), but error printing message content: {e}")
            self._compose(mac, message, 0x02, 0x21, channel, ifidx)

        def check_messages(self):
            self.master.dprint("aen.check_message")
            return len(self._received_messages) > 0

        def return_message(self):
            self.master.dprint("aen.return_message")
            if self.check_messages():
                self._received_messages_size.pop()
                return self._received_messages.pop()
            return None, None, None

        def return_messages(self):
            self.master.dprint("aen.return_messages")
            if self.check_messages():
                messages = self._received_messages[:]
                self._received_messages.clear()
                self._received_messages_size.clear()
                gc.collect()
                return messages
            return [(None, None, None)]

        def return_data(self):
            self.master.dprint("aen.return_data")
            return self.received_sensor_data
        
        def _irq(self, espnow):
            self.master.dprint("aen._irq")
            if self.master.admin:
                try:
                    self._receive()
                    if self._irq_function and self.check_messages():
                        self._irq_function()
                    gc.collect()
                    return
                except KeyboardInterrupt:
                    self.master.eprint("aen._irq except KeyboardInterrupt")
                    self.master.cleanup() #network cleanup
                    raise SystemExit("Stopping networking execution. ctrl-c or ctrl-d again to stop main code")  # in thonny stops library code but main code keeps running, same in terminal
            else:
                self._receive()
                if self._irq_function and self.check_messages():
                    self._irq_function()
                gc.collect()
                return

        def irq(self, func):
            self.master.dprint("aen.irq")
            self._irq_function = func

        def cmd(self, func):
            self.master.dprint("aen.cmd")
            self.custom_cmd = func

        def inf(self, func):
            self.master.dprint("aen.inf")
            self.custom_inf = func

        def ack(self, func):
            self.master.dprint("aen.ack")
            self.custom_ack = func
 
        def _send(self, peers_mac, messages, channel, ifidx, long_msg=False):
            self.master.dprint("aen._send")
            if isinstance(peers_mac, bytes):
                peers_mac = [peers_mac]
            for peer_mac in peers_mac:
                try:
                    if channel is None:
                        if peer_mac in self._peers:
                            if 'channel' in self._peers[peer_mac]:
                                channel=self._peers[peer_mac]['channel']
                        else:
                            channel = 0
                    elif ifidx is None:
                        if peer_mac in self._peers:
                            if 'ifidx' in self._peers[peer_mac]:
                                ifidx=self._peers[peer_mac]['ifidx']
                        else:
                            ifidx=self.ifidx
                    self._aen.add_peer(peer_mac, channel=channel, ifidx=ifidx)
                    self.master.dprint(f"Added {peer_mac} to espnow buffer with channel {channel} and ifidx {ifidx}")
                except Exception as e:
                    self.master.eprint(f"Error adding {peer_mac} to espnow buffer: {e}")
                for m in range(len(messages)):
                    i = 0
                    while i in range(3):
                        i += i
                        ack = False
                        try:
                            ack = self._aen.send(peer_mac, messages[m], True)
                            self.master.dprint(f"Receipt confirm: {ack}")
                            if ack:
                                break
                        except Exception as e:
                            self.master.eprint(f"Error sending to {peer_mac}: {e}")
                    self.master.dprint(f"Sent {messages[m]} to {peer_mac} ({self.peer_name(peer_mac)}) with {ack}")
                    gc.collect()
                try:
                    self._aen.del_peer(peer_mac)
                    self.master.dprint(f"Removed {peer_mac} from espnow buffer")
                except Exception as e:
                    self.master.eprint(f"Error removing {peer_mac} from espnow buffer: {e}")

        def __send_confirmation(self, msg_type, recipient_mac, msg_subkey_type, payload=None, error=None):
            if msg_type == "Success":
                self._compose(recipient_mac, [msg_subkey_type, payload], 0x03, 0x11)
            elif msg_type == "Fail":
                self._compose(recipient_mac, [msg_subkey_type, error, payload], 0x03, 0x12)
            else:
                self._compose(recipient_mac, [msg_subkey_type, payload], 0x03, 0x13)

        def _compose(self, peer_mac, payload=None, msg_type=0x02, subtype=0x22, channel=None, ifidx=None):
            self.master.dprint("aen._compose")

            if isinstance(peer_mac, list):
                for peer_macs in peer_mac:
                    if peer_macs not in self._peers:
                        self.add_peer(peer_macs, None, channel, ifidx)
            elif peer_mac not in self._peers:
                self.add_peer(peer_mac, None, channel, ifidx)
                
            payload_type, payload_bytes = None, None
            self.master.dprint("aen.__encode_payload")
            if payload is None:  # No payload type
                payload_type, payload_bytes = b'\x00', b''
            elif isinstance(payload, bytearray):  # bytearray
                payload_type, payload_bytes = b'\x01', bytes(payload)
            elif isinstance(payload, bytes):  # bytes
                payload_type, payload_bytes = b'\x01', payload
            elif isinstance(payload, bool):  # bool
                payload_type, payload_bytes = b'\x02', (b'\x01' if payload else b'\x00')
            elif isinstance(payload, int):  # int
                payload_type, payload_bytes = b'\x03', str(payload).encode('utf-8')
            elif isinstance(payload, float):  # float
                payload_type, payload_bytes = b'\x04', str(payload).encode('utf-8')
            elif isinstance(payload, str):  # string
                payload_type, payload_bytes = b'\x05', payload.encode('utf-8')
            elif isinstance(payload, dict) or isinstance(payload, list):  # json dict or list
                json_payload = json.dumps(payload)
                payload_type, payload_bytes = b'\x06', json_payload.encode('utf-8')
            else:
                raise ValueError("Unsupported payload type")
            
            messages = []
            identifier = 0x2a
            timestamp = time.ticks_ms()
            header = bytearray(8)
            header[0] = identifier
            header[1] = msg_type
            header[2] = subtype
            header[3:7] = timestamp.to_bytes(4, 'big')
            long_msg = False
            if len(payload_bytes) < 242:  # 250-9=241=max_length
                header[7] = payload_type[0]
                total_length = 1 + 1 + 1 + 4 + 1 + len(payload_bytes) + 1
                message = bytearray(total_length)
                message[:8] = header
                message[8:-1] = payload_bytes
                message[-1:] = (sum(message) % 256).to_bytes(1, 'big')  # Checksum
                self.master.dprint(f"Message {1}/{1}; Length: {len(message)}; Free memory: {gc.mem_free()}")
                messages.append(message)
            else:
                self.master.dprint("Long message: Splitting!")
                max_size = 238  # 241-3
                total_chunk_number = (-(-len(payload_bytes) // max_size))  # Round up division
                lba = b'\x07'
                header[7] = lba[0]  # Long byte array
                if total_chunk_number > 256:
                    raise ValueError("More than 256 chunks, unsupported")
                for chunk_index in range(total_chunk_number):
                    message = bytearray(9 + 3 + min(max_size, len(payload_bytes) - chunk_index * max_size))
                    message[:8] = header
                    message[8:10] = chunk_index.to_bytes(1, 'big') + total_chunk_number.to_bytes(1, 'big')
                    message[10] = payload_type[0]
                    message[11:-1] = payload_bytes[chunk_index * max_size: (chunk_index + 1) * max_size]
                    message[-1:] = (sum(message) % 256).to_bytes(1, 'big')  # Checksum
                    self.master.dprint(message)
                    messages.append(bytes(message))
                    self.master.dprint(
                        f"Message {chunk_index + 1}/{total_chunk_number}; length: {len(message)}; Free memory: {gc.mem_free()}")
                    gc.collect()
                    long_msg = True
            gc.collect()
            self._send(peer_mac, messages, channel, ifidx, long_msg)
            
            
        def __remove_long_message_from_buffer(self, timer, key):
            self.master.dprint("aen.__remove_long_message_from_buffer")
            if key in self._long_buffer:
                del self._long_buffer[key]
            if key in self._long_buffer_size:
                self._long_buffer_size[key]
            gc.collect()
            
        def _receive(self):
            self.master.dprint("aen._receive")
            


            def __process_message(self, sender_mac, message, receive_timestamp):
                self.master.dprint("aen.__process_message")
                if message[0] != 0x2a:  # Unique Message Identifier Check
                    self.master.dprint("Invalid message: Message ID Fail")
                    return None
                if len(message) < 9:  # Min size
                    self.master.dprint("Invalid message: too short")
                    return None

                msg_type = int.from_bytes(message[1:2], 'big')
                subtype = subtype = int.from_bytes(message[2:3], 'big')
                send_timestamp = int.from_bytes(message[3:7], 'big')
                payload_type = bytes(message[7:8])
                payload_bytes = message[8:-1]
                checksum = message[-1]
                self.master.dprint(f"{type(msg_type)}: {msg_type}, {type(subtype)}: {subtype}, {type(send_timestamp)}: {send_timestamp}, {type(payload_type)}: {payload_type},  {type(payload_bytes)}: {payload_bytes},  {type(checksum)}: {checksum}")

                # Checksum
                if checksum != sum(message[:-1]) % 256:
                    self.master.dprint("Invalid message: checksum mismatch")
                    return None

                if sender_mac not in self._peers:
                    self.add_peer(sender_mac)
                    
                payload = None

                if payload_type == b'\x07':
                    self.master.dprint("Long message received, processing...")
                    part_n = int.from_bytes(payload_bytes[0:1], 'big')
                    total_n = int.from_bytes(payload_bytes[1:2], 'big')
                    payload_type = bytes(payload_bytes[2:3])

                    # Create a key as a bytearray: (msg_type, subtype, timestamp, payload_type, total_n)
                    key = bytearray()
                    key.extend(message[1:2])
                    key.extend(message[2:3])
                    key.extend(message[3:7])
                    key.extend(payload_type)
                    key.extend(payload_bytes[1:2])
                    key = bytes(key)
                    self.master.dprint(f"Key: {key}")
                    
                    payload_bytes = payload_bytes[3:]

                    # Check if the key already exists in the long buffer
                    if key in self._long_buffer:
                        # If the part is None, add the payload
                        if self._long_buffer[key][part_n] is None:
                            self._long_buffer[key][part_n] = payload_bytes
                            self._long_buffer_size[key] = self._long_buffer_size[key] + len(payload_bytes)
                            self.master.dprint(
                                f"Long message: Key found, message added to entry in long_message_buffer, {sum(1 for item in self._long_buffer[key] if item is not None)} out of {total_n} packages received")
                            # If there are still missing parts, return
                            if any(value is None for value in self._long_buffer[key]):
                                gc.collect()
                                return
                        else:
                            return
                    else:
                        # Initialize the long message buffer for this key
                        payloads = [None] * total_n
                        payloads[part_n] = payload_bytes
                        self._long_buffer[key] = payloads
                        self._long_buffer_size[key] = len(payload_bytes)
                        self.master.dprint(
                            f"Long message: Key not found and new entry created in long_message_buffer, {sum(1 for item in self._long_buffer[key] if item is not None)} out of {total_n} packages received")

                        while len(self._long_buffer) > 8 or sum(self._long_buffer_size.values()) > 75000:
                            self.master.dprint(
                                f"Maximum buffer size reached: {len(self._long_buffer)}, {sum(self._long_buffer_size.values())} bytes; Reducing!")
                            oldest_key = next(iter(self._long_buffer))
                            del self._long_buffer[oldest_key]
                            del self._long_buffer_size[oldest_key]
                        gc.collect()
                        timer = machine.Timer(0)
                        timer.init(period=10000, mode=machine.Timer.ONE_SHOT, callback=lambda t: self.__remove_long_message_from_buffer(t, key))
                        return

                    # If all parts have been received, reconstruct the message
                    if not any(value is None for value in self._long_buffer[key]):
                        payload_bytes = bytearray()
                        for i in range(0, total_n):
                            payload_bytes.extend(self._long_buffer[key][i])
                        del self._long_buffer[key]
                        del self._long_buffer_size[key]
                        self.master.dprint("Long message: All packages received!")
                    else:
                        self.master.dprint("Long Message: Safeguard triggered, code should not have gotten here")
                        gc.collect()
                        return
                
                payload_size = len(payload_bytes)
                    
                self.master.dprint("aen.__decode_payload")
                if payload_type == b'\x00':  # None
                    payload = None
                elif payload_type == b'\x01':  # bytearray or bytes
                    payload = bytes(payload_bytes)
                elif payload_type == b'\x02':  # bool
                    payload = payload_bytes[0:1] == b'\x01'
                elif payload_type == b'\x03':  # int
                    payload = int(payload_bytes.decode('utf-8'))
                elif payload_type == b'\x04':  # float
                    payload = float(payload_bytes.decode('utf-8'))
                elif payload_type == b'\x05':  # string
                    payload = payload_bytes.decode('utf-8')
                elif payload_type == b'\x06':  # json dict or list
                    payload = json.loads(payload_bytes.decode('utf-8')) #use eval instead? #FIX
                elif payload_type == b'\x07':  # Long byte array
                    payload = bytes(payload_bytes)
                else:
                    raise ValueError(f"Unsupported payload type: {payload_type} Message: {payload_bytes}")

                # Handle the message based on type
                if msg_type == 0x01:  # Command Message
                    msg_key = "cmd"
                    __handle_cmd(self, sender_mac, subtype, send_timestamp, receive_timestamp, payload, payload_size, msg_key)
                elif msg_type == 0x02:  # Informational Message
                    msg_key = "inf"
                    __handle_inf(self, sender_mac, subtype, send_timestamp, receive_timestamp, payload, payload_size, msg_key)
                elif msg_type == 0x03:  # Acknowledgement Message
                    msg_key = "ack"
                    __handle_ack(self, sender_mac, subtype, send_timestamp, receive_timestamp, payload, payload_size, msg_key)
                else:
                    self.master.iprint(f"Unknown message type from {sender_mac} ({self.peer_name(sender_mac)}): {message}")

            def __handle_cmd(self, sender_mac, subtype, send_timestamp, receive_timestamp, payload, payload_size, msg_key):
                self.master.dprint(f"aen.__handle_cmd")
                if (msg_subkey := "Ping") and subtype == 0x01 or subtype == 0x10:  # Ping
                    self.master.iprint(f"{msg_subkey} ({subtype}) command received from {sender_mac} ({self.peer_name(sender_mac)})")
                    self.add_peer(sender_mac, payload[2], payload[0], payload[1])
                    if bool(self.ifidx):
                        channel = self.master.ap.channel()
                    else:
                        channel = self.master.sta.channel()
                    response = [channel, self.ifidx, self.master.config, send_timestamp]
                    self._compose(sender_mac, response, 0x03, 0x10)
                elif (msg_subkey := "RSSI/Status/Config-Boop") and subtype == 0x03 or subtype == 0x13:  # RSSI/Status/Config Boop
                    self.boops = self.boops + 1
                    self.master.iprint(f"{msg_subkey} ({subtype}) command received from {sender_mac} ({self.peer_name(sender_mac)}), Received total of {self.boops} boops!")
                    try:
                        self._compose(sender_mac, [self.master.config, self.master.version, self.master.sta.mac, self.master.ap.mac, self.rssi()], 0x02, 0x20)  # [ID, Name, Config, Version, sta mac, ap mac, rssi]
                    except Exception as e:
                        self.master.aen.__send_confirmation(self, "Fail", sender_mac, f"{msg_subkey} ({subtype})", payload, e)
                elif (msg_subkey := "Echo") and subtype == subtype == 0x02 or subtype == 0x15:  # Echo
                    self.master.iprint(f"{msg_subkey} ({subtype}) command received from {sender_mac} ({self.peer_name(sender_mac)}): {payload}")  # Check i or d
                    self._compose(sender_mac, payload, 0x03, 0x15)
                else:
                    if self.custom_cmd:
                        self.master.iprint(f"Checking custom cmd handler library")
                        self.custom_cmd([sender_mac, subtype, send_timestamp, receive_timestamp, payload, msg_key])
                    self.master.iprint(f"Unknown command subtype from {sender_mac} ({self.peer_name(sender_mac)}): {subtype}")

            def __handle_inf(self, sender_mac, subtype, send_timestamp, receive_timestamp, payload, payload_size, msg_key):
                self.master.dprint("aen.__handle_inf")
                if (msg_subkey := "RSSI/Status/Config-Boop") and subtype == 0x00 or subtype == 0x20:  # RSSI/Status/Config-Boop
                    self.master.iprint(f"{msg_subkey} ({subtype}) data received from {sender_mac} ({self.peer_name(sender_mac)}): {payload}")
                    self.received_rssi_data[sender_mac] = payload
                    # self.master.aen.__send_confirmation(self, "Confirm", sender_mac, f"{msg_subkey} ({subtype})", payload) #confirm message recv
                    if self.boop_irq:
                        self.boop_irq()
                elif (msg_subkey := "Data") and subtype == 0x01 or subtype == 0x21:  # Sensor Data
                    payload["time_sent"] = send_timestamp
                    payload["time_recv"] = receive_timestamp
                    self.master.iprint(f"{msg_subkey} ({subtype}) data received from {sender_mac} ({self.peer_name(sender_mac)}): {payload}")
                    if sender_mac in self.received_sensor_data:
                        self.received_sensor_data[b'prev_' + sender_mac] = self.received_sensor_data[sender_mac]
                    self.received_sensor_data[sender_mac] = payload
                    # self.master.aen.__send_confirmation(self, "Confirm", sender_mac, f"{msg_subkey} ({subtype})", payload) #confirm message recv
                    if self.data_irq:
                        self.data_irq()
                elif (msg_subkey := "Message") and subtype == 0x02 or subtype == 0x22:  # Message / Other
                    self.master.iprint(f"{msg_subkey} ({subtype}) received from {sender_mac} ({self.peer_name(sender_mac)}): {payload}")
                    self._received_messages.append((sender_mac, payload, receive_timestamp))
                    self._received_messages_size.append(payload_size)
                    while len(self._received_messages) > 2048 or sum(self._received_messages_size) > 20000:
                        self.master.dprint(f"Maximum buffer size reached: {len(self._received_messages)}, {sum(self._received_messages_size)} bytes; Reducing!")
                        self._received_messages.pop(0)
                        self._received_messages_size.pop(0)
                    # self.master.aen.__send_confirmation(self, "Confirm", sender_mac, f"{msg_subkey} ({subtype})", payload) #confirm message recv
                    if self.msg_irq:
                        self.msg_irq()
                else:
                    if self.custom_inf:
                        self.master.iprint(f"Checking custom inf handler library")
                        self.custom_inf([sender_mac, subtype, send_timestamp, receive_timestamp, payload, msg_key])
                    self.master.iprint(f"Unknown info subtype from {sender_mac} ({self.peer_name(sender_mac)}): {subtype}")

            def __handle_ack(self, sender_mac, subtype, send_timestamp, receive_timestamp, payload, payload_size, msg_key):
                self.master.dprint("aen.__handle_ack")
                if (msg_subkey := "Pong") and subtype == 0x10:  # Pong
                    self.add_peer(sender_mac, payload[2], payload[0], payload[1])
                    self.master.iprint(f"{msg_subkey} ({subtype})  received from {sender_mac} ({self.peer_name(sender_mac)}), {receive_timestamp - payload[3]}")
                elif (msg_subkey := "Echo") and subtype == 0x15:  # Echo
                    self.master.iprint(f"{msg_subkey} ({subtype})  received from {sender_mac} ({self.peer_name(sender_mac)}), {payload}")
                    self.last_echo = payload
                elif (msg_subkey := "Success") and subtype == 0x11:  # Success
                    # payload should return a list with a cmd type and payload
                    self.master.iprint(f"{msg_subkey} ({subtype}) received from {sender_mac} ({self.peer_name(sender_mac)}) for type {payload[0]} with payload {payload[1]}")
                    # add to ack buffer
                elif (msg_subkey := "Fail") and subtype == 0x12:  # Fail
                    # payload should return a list with a cmd type, error and payload
                    self.master.iprint(f"{msg_subkey} ({subtype}) received from {sender_mac} ({self.peer_name(sender_mac)}) for type {payload[0]} with error {payload[1]} and payload {payload[2]}")
                    # add to ack buffer
                elif (msg_subkey := "Confirm") and subtype == 0x13:  # Confirmation
                    # payload should return a list with message type and payload
                    self.master.iprint(f"{msg_subkey} ({subtype}) received from {sender_mac} ({self.peer_name(sender_mac)}) for type {payload[0]} with payload {payload[1]}")
                    # add to ack buffer
                else:
                    if self.custom_ack:
                        self.master.iprint(f"Checking custom ack handler library")
                        self.custom_ack([sender_mac, subtype, send_timestamp, receive_timestamp, payload, msg_key])
                        self.master.iprint(f"Unknown ack subtype from {sender_mac} ({self.peer_name(sender_mac)}): {subtype}, Payload: {payload}")
                        # Insert more acknowledgement logic here and/or add message to acknowledgement buffer
                if self.ack_irq:
                    self.ack_irq()

            if self._aen.any():
                timestamp = time.ticks_ms()
                for mac, data in self._aen:
                    self.master.dprint(f"Received {mac, data}")
                    if mac is None:  # mac, msg will equal (None, None) on timeout
                        break
                    if data:
                        if mac and data is not None:
                            # self._received_messages.append((sender_mac, data, receive_timestamp))#Messages will be saved here, this is only for debugging purposes
                            __process_message(self, mac, data, timestamp)
                    if not self._aen.any():  # this is necessary as the for loop gets stuck and does not exit properly.
                        break

# message structure (what kind of message types do I need?: Command which requires me to do something (ping, pair, change state(update, code, mesh mode, run a certain file), Informational Message (Sharing Sensor Data and RSSI Data)
# | Header (1 byte) | Type (1 byte) | Subtype (1 byte) | Timestamp (ms ticks) (4 bytes) | Payload type (1) | Payload (variable) | Checksum (1 byte) |




