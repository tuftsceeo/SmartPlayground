import network
import machine
from config import mysecrets, configname
import time
import ubinascii
import urequests
import espnow
import gc
import asyncio
import struct
import json
import random


boottime = time.ticks_ms()

class Networking:       
    def __init__(self, infmsg=True, dbgmsg=False, admin=False):
        self.master = self
        self.infmsg = infmsg
        self.dbgmsg = dbgmsg
        self._admin = admin
            
        self._staif = network.WLAN(network.STA_IF)
        self._apif = network.WLAN(network.AP_IF)
        
        self.sta = self.Sta(self, self._staif)
        self.ap = self.Ap(self, self._apif)
        self.aen = self.Aen(self)
        
        self.id = ubinascii.hexlify(machine.unique_id()).decode()
        self.name = configname
        if self.name == "" or self.name == None:
            self.name = str(self.id)
        
    def _iprint(self, message):
        if self.infmsg:
            try:
                print(f"{int((time.ticks_ms()-boottime))//1/1000} networking Info: {message}")
            except Exception as e:
                print(f"Error printing networking Info: {2}")
        return
            
    def _dprint(self, message):
        if self.dbgmsg:
            try:
                print(f"{int((time.ticks_ms()-boottime))//1/1000} networking Debug: {message}")
            except Exception as e:
                print(f"Error printing networking Debug: {2}")
        return
    
    
    
    class Sta:
        def __init__(self, master, _staif):
            self.master = master
            self._sta = _staif
            self._sta.active(True)
            self.master._iprint("STA initialized and ready")
            
        def scan(self):
            self.master._dprint("sta.scan")
            scan_result = self._sta.scan()
            if self.infmsg:
                for ap in scan_result:
                    self.master._iprint(f"SSID:%s BSSID:%s Channel:%d Strength:%d RSSI:%d Auth:%d " % (ap))
            return scan_result
    
        def connect(self, ssid, key="", timeout=10):
            self.master._dprint("sta.connect")
            self._sta.connect(ssid, key)
            stime = time.time()
            #self._sta.status() returns the current wlan status, update below functions with it
            while time.time() - stime < timeout:
                if self._sta.ifconfig()[0] != '0.0.0.0':
                    self.master._iprint("Connected to WiFi")
                    return
                time.sleep(1)
            self.master._iprint(f"Failed to connect to WiFi: {self._sta.status()}")
        
        def disconnect(self):
            self.master._dprint("sta.disconnect")
            self._sta.disconnect()
            
        def ip(self):
            self.master._dprint("sta.ip")
            return self._sta.ifconfig()
    
        def mac(self):
            self.master._dprint("sta.mac")
            return bytes(self._sta.config('mac'))
        
        def mac_decoded(self):#Necessary?
            self.master._dprint("sta.mac_decoded")
            return ubinascii.hexlify(self._sta.config('mac'), ':').decode()
        
        def channel(self):#Is there an equivalent for AP? How does setting channels work for ESP-Now????????
            self.master._dprint("sta.channel")
            return self._sta.config('channel')
        
        def set_channel(self, number):
            self.master._dprint("sta.set_channel")
            if number > 14 or number < 0:
                number = 0
            self._sta.config(channel=number)
            self.vprint(f"STA channel set to {number}")
            #This will override the channel that was set as part of the add_peer function ???
        
        def get_joke(self):
            self.master._dprint("sta.get_joke")
            try:
                reply = urequests.get('https://v2.jokeapi.dev/joke/Programming')
                if reply.status_code == 200:
                    joke = reply.json()
                    return joke.get('setup', '') + '\n' + joke.get('delivery', joke.get('joke', ''))
            except Exception as e:
                print('Error fetching joke:', str(e))
            return None
  
  
  
    class Ap:
        def __init__(self, master, _apif):
            self.master = master
            self._ap = _apif
            self._ap.active(True)
            self.master._iprint("AP initialized and ready")
        
        def set_ap(self, name="", password="", max_clients=10):
            self.master._dprint("ap.setap")
            if name == "":
                name = self.name
            self._ap.active(True)
            self._ap.config(essid=name)
            if password:
                self._ap.config(authmode=network.AUTH_WPA_WPA2_PSK, password=password)
            self._ap.config(max_clients=max_clients)
            self.master._iprint(f"Access Point {name} set with max clients {max_clients}")
        
        def deactivate(self):
            self.master._dprint("ap.deactivate")
            self._ap.active(False)
            self.master._iprint("Access Point deactivated")
            
        def ip(self):
            self.master._dprint("ap.ip")
            return self._ap.ifconfig()
    
        def mac(self):
            self.master._dprint("ap.mac")
            return bytes(self._ap.config('mac'))
        
        def mac_decoded(self):#Necessary?
            self.master._dprint("ap.mac_decoded")
            return ubinascii.hexlify(self._ap.config('mac'), ':').decode()
        
        def channel(self): #How does setting channels work for ESP-Now????????
            self.master._dprint("ap.channel")
            return self._ap.config('channel')
        
        def set_channel(self, number):
            self.master._dprint("ap.set_channel")
            if number > 14 or number < 0:
                number = 0
            self._ap.config(channel=number)
            self.vprint(f"AP channel set to {number}")
            #This will override the channel that was set as part of the add_peer function ???



    class Aen:
        def __init__(self, master):
            self.master = master
            self._aen = espnow.ESPNow()
            self._aen.active(True)
            
            self._peers = {}
            #self.received_messages = []
            self._saved_messages = []
            self._long_buffer = {}
            self.received_data = {}
            #self._long_sent_buffer = {}
            #self.running = True
            self._irq_function = None
            self.boops = 0
            self.ifidx = 0 #0 sends via sta, 1 via ap
            
            if self.master._admin:
                try:
                    self._aen.irq(self._irq)
                except KeyboardInterrupt:#Trigger should be disabled when ctrl. C-ing
                    self._aen.irq(trigger=0)
                    self._aen.irq(handler=None)
            else:
                self._aen.irq(self._irq)#Processes the messages asap after receiving them, this should not be interrupted by doing ctrl c
            
            self.master._iprint("ESP-NOW initialized and ready")
            
        def update_peer(self, peer_mac, name=None, channel=None, ifidx=None):
            self.master._dprint("aen.update_peer")
            if peer_mac in self._peers:
                try:
                    if name != None:
                        self._peers[peer_mac]['name'] = name
                    if channel  !=  None:
                        self._peers[peer_mac]['channel'] = channel
                    if ifidx  !=  None:
                        self._peers[peer_mac]['ifidx'] = ifidx
                    #self.master._iprint(f"Peer {peer_mac} updated to channel {channel}, ifidx {ifidx} and name {name}")
                except OSError as e:
                    print(f"Error updating peer {peer_mac}: {e}")
                return
            self.master._iprint(f"Peer {peer_mac} not found")

        def add_peer(self, peer_mac, name=None, channel=None, ifidx=None):
            self.master._dprint("aen.add_peer")
            if peer_mac not in self._peers:
                try:
                    self._peers[peer_mac] = {'channel': channel, 'ifidx': ifidx, 'name': name}
                    self.master._dprint(f"Peer {peer_mac} added with channel {channel}, ifidx {ifidx} and name {name}")
                except OSError as e:
                    print(f"Error adding peer {peer_mac}: {e}")
            else:
                self.master._dprint(f"Peer {peer_mac} already exists, updating")
                self.update_peer(peer_mac, name, channel, ifidx)

        def remove_peer(self, peer_mac):
            self.master._dprint("aen.remove_peers")
            if peer_mac in self._peers:
                try:
                    del self._peers[peer_mac]
                    self.master._iprint(f"Peer {peer_mac} removed")
                except OSError as e:
                    print(f"Error removing peer {peer_mac}: {e}")

        def peers(self):
            self.master._dprint("aen.peers")
            return self._peers
        
        def peer_name(self, key):
            self.master._dprint("aen.name")
            if key in self._peers:
                return self._peers[key]['name']
            else:
                return None
        
        def rssi(self):
            self.master._dprint("aen.rssi")
            return self._aen.peers_table
        
        def ping(self, mac):
            self.master._dprint("aen.ping")
            if bool(self.ifidx):
                channel = self.master.ap.channel()#make sure to account for sta send and ap send
            else:
                channel = self.master.sta.channel()#make sure to account for sta send and ap send
            self._compose(mac, [channel,self.ifidx,self.master.name], 0x01, 0x10) #sends channel, ifidx and name
            #self.master._iprint(f"Sent ping to {mac} ({self.peer_name(mac)})")
            gc.collect()
        
        def echo(self, mac, message):
            self.master._dprint("aen.echo")
            try:
                self.master._iprint(f"Sending echo ({message}) to {mac} ({self.peer_name(mac)})")
            except Exception as e:
                self.master._iprint(f"Sending echo to {mac} ({self.peer_name(mac)}), but error printing message content: {e}")
            self._compose(mac, message, 0x01, 0x15)
            gc.collect()
        
        def send(self, mac, message):#make a separate long message function?
            self.master._dprint("aen.message")
            if len(str(message)) > 241:
                try:
                    self.master._iprint(f"Sending message ({str(message)[:50] + '... (truncated)'}) to {mac} ({self.peer_name(mac)})")
                except Exception as e:
                    self.master._iprint(f"Sending message to {mac} ({self.peer_name(mac)}), but error printing message content: {e}")
                    gc.collect()
            else:
                self.master._iprint(f"Sending message ({message}) to {mac} ({self.peer_name(mac)})")
            #self.master._dprint(f"Free memory: {gc.mem_free()}")
            self._compose(mac, message, 0x02, 0x22)
            gc.collect()
            self.master._dprint(f"Free memory: {gc.mem_free()}")
            
        def broadcast(self, message):#needed?
            self.master._dprint("aen.broadcast")
            mac = b'\xff\xff\xff\xff\xff\xff'
            self.send(mac, message)

        def send_sensor(self, mac, message):#message is a dict, key is the sensor type and the value is the sensor value
            self.master._dprint("aen.message")
            try:
                self.master._iprint(f"Sending sensor data ({message}) to {mac} ({self.peer_name(mac)})")
            except Exception as e:
                self.master._iprint(f"Sending sensor data to {mac} ({self.peer_name(mac)}), but error printing message content: {e}")
            self._compose(mac, message, 0x02, 0x21)

        def check_messages(self):
            self.master._dprint("aen.check_message")
            return len(self._saved_messages) > 0
        
        def return_message(self):
            self.master._dprint("aen.return_message")
            if self.check_messages():
                return self._saved_messages.pop()
            return (None, None, None)
        
        def return_messages(self):
            self.master._dprint("aen.return_messages")
            if self.check_messages():
                messages = self._saved_messages[:]
                self._saved_messages.clear()
                gc.collect()
                return messages
            return [(None, None, None)]
            
        def _irq(self, espnow):
            self.master._dprint("aen._irq")
            #self.maste._dprint(f"Free memory: {gc.mem_free()}")
            self._receive()
            if self._irq_function and self.check_messages():
                self._irq_function()
            gc.collect()
            #self.maste._dprint(f"Free memory: {gc.mem_free()}")
            return
        
        def irq(self, func):
            self.master._dprint("aen.irq")
            self._irq_function = func
               
        def _send(self, peers_mac, messages, channel, ifidx):
            self.master._dprint("aen._send")
            
            def __aen_add_peer(peers_mac, channel, ifidx):
                if isinstance(peers_mac, bytes):
                    peers_mac = [peers_mac]
                for peer_mac in peers_mac:
                    try:
                        if channel != None and ifidx != None:
                            self._aen.add_peer(peer_mac, channel=channel, ifidx=ifidx)
                        elif peer_mac in self._peers:
                            self._aen.add_peer(peer_mac, channel=self._peers[peer_mac]['channel'], ifidx=self._peers[peer_mac]['ifidx'])
                        else:
                            self._aen.add_peer(peer_mac, channel=0, ifidx=self.ifidx)
                    except Exception as e:
                        print(f"Error adding {peer_mac} to buffer: {e}")
                    
            def __aen_del_peer(peers_mac):
                if isinstance(peers_mac, bytes):
                    peers_mac = [peers_mac]
                for peer_mac in peers_mac:
                    try:   
                        self._aen.del_peer(peer_mac)
                    except Exception as e:
                        print(f"Error removing {peer_mac} from buffer: {e}")
                        
            __aen_add_peer(peers_mac, channel, ifidx)
            for m in range(len(messages)):
                if isinstance(peers_mac, list):
                    mac = None
                else:
                    mac = peers_mac
                for i in range(3):
                    i += i
                    try:
                        self._aen.send(mac, messages[m])
                        break
                    except Exception as e:
                        print(f"Error sending to {mac}: {e}")
                self.master._dprint(f"Sent {messages[m]} to {mac} ({self.peer_name(mac)})")
                gc.collect()
                #self.master._dprint(f"Free memory: {gc.mem_free()}")
            __aen_del_peer(peers_mac)
            
                    
        def _compose(self, peer_mac, payload=None, msg_type=0x02, subtype=0x22, channel=None, ifidx=None):#rename the function
            self.master._dprint("aen._compose")
            
#             if isinstance(peer_mac, list):
#                 for peer_macs in peer_mac:
#                     if peer_macs not in self._peers:
#                         self.add_peer(peer_macs, None, None, None)#Should automatically add it to the peer regsitry
            if peer_mac not in self._peers:
                self.add_peer(peer_mac, None, None, None)#Should automatically add it to the peer regsitry
            
                
            #self.maste._dprint(f"Free memory: {gc.mem_free()}")
            
            def __encode_payload(payload):
                self.master._dprint("aen.__encode_payload")
                if payload is None: #No payload type
                    return b'\x00', b''
                elif isinstance(payload, bytearray): #bytearray
                    return (b'\x01', bytes(payload))
                elif isinstance(payload, bytes): #bytes
                    return (b'\x01', payload)
                elif isinstance(payload, bool): #bool
                    return (b'\x02', (b'\x01' if payload else b'\x00'))
                elif isinstance(payload, int): #int
                    return (b'\x03', struct.pack('>i', payload))
                elif isinstance(payload, float): #float
                    return (b'\x04', struct.pack('>f', payload))
                elif isinstance(payload, str): #string
                    return (b'\x05', payload.encode('utf-8'))
                elif isinstance(payload, dict) or isinstance(payload, list): #json dict or list
                    json_payload = json.dumps(payload)
                    return (b'\x06', json_payload.encode('utf-8'))
                else:
                    raise ValueError("Unsupported payload type")
            
            payload_type, payload_bytes = __encode_payload(payload)
            messages = []
            identifier = 0x2a
            timestamp = time.ticks_ms()
            header = bytearray(8)
            header[0] = identifier
            header[1] = msg_type
            header[2] = subtype
            header[3:7] = timestamp.to_bytes(4, 'big')
            #self.maste._dprint(f"Free memory: {gc.mem_free()}")
            if len(payload_bytes) < 242: #250-9=241=max_length
                header[7] = payload_type[0]
                total_length = 1 + 1 + 1 + 4 + 1 + len(payload_bytes) + 1
                message = bytearray(total_length)
                message[:8] = header
                message[8:-1] = payload_bytes                
                message[-1:] = (sum(message) % 256).to_bytes(1, 'big') #Checksum
                self.master._dprint(f"Message {1}/{1}; Length: {len(message)}; Free memory: {gc.mem_free()}")
                messages.append(message)

            else:
                self.master._dprint("Long message: Splitting!")
                max_size = 238 #241-3
                total_chunk_number = (-(-len(payload_bytes)//max_size)) #Round up division
                lba = b'\x07'
                header[7] = lba[0] #Long byte array
                if total_chunk_number > 256:
                    raise ValueError("More than 256 chunks, unsupported")
                for chunk_index in range(total_chunk_number):
                    message = bytearray(9 + 3 + min(max_size,len(payload_bytes)-chunk_index*max_size))
                    message[:8] = header
                    message[8:10] = chunk_index.to_bytes(1, 'big') + total_chunk_number.to_bytes(1, 'big')
                    message[10] = payload_type[0]
                    message[11:-1] = payload_bytes[chunk_index * max_size: (chunk_index + 1) * max_size]           
                    message[-1:] = (sum(message) % 256).to_bytes(1, 'big') #Checksum
                    self.master._dprint(message)
                    messages.append(bytes(message))
                    self.master._dprint(f"Message {chunk_index+1}/{total_chunk_number}; length: {len(message)}; Free memory: {gc.mem_free()}")
                    gc.collect()
#                 key = bytearray()
#                 key.extend(header[1:8])
#                 key.extend(total_chunk_number.to_bytes(1, 'big'))
#                 self._long_sent_buffer[bytes(key)] = (messages, (channel,ifidx))
                    
            message = bytearray()
            gc.collect()
            #self.master._dprint(f"Free memory: {gc.mem_free()}")
            self._send(peer_mac, messages, channel, ifidx)


        def _receive(self): #Processes all the messages in the buffer
            self.master._dprint("aen._receive")
            
            def __decode_payload(payload_type, payload_bytes):
                self.master._dprint("aen.__decode_payload")
                if payload_type == b'\x00': #None
                    return None
                elif payload_type == b'\x01': #bytearray or bytes
                    return bytes(payload_bytes)
                elif payload_type == b'\x02': #bool
                    return payload_bytes[0:1] == b'\x01'
                elif payload_type == b'\x03': #int
                    return struct.unpack('>i', payload_bytes)[0]
                elif payload_type == b'\x04': #float
                    return struct.unpack('>f', payload_bytes)[0]
                elif payload_type == b'\x05': #string
                    return payload_bytes.decode('utf-8')
                elif payload_type == b'\x06': #json dict or list
                    return json.loads(payload_bytes.decode('utf-8'))  
                elif payload_type == b'\x07': #Long byte array
                    return bytes(payload_bytes)
                else:
                    raise ValueError(f"Unsupported payload type: {payload_type} Message: {payload_bytes}")
                    #return None
            
            def __process_message(sender_mac, message, rtimestamp):
                self.master._dprint("aen.__process_message")
                if message[0] != 0x2a:  # Uniqe Message Identifier Check
                    self.master._dprint("Invalid message: Message ID Fail")
                    return None
                if len(message) < 9:  # Min size
                    self.master._dprint("Invalid message: too short")
                    return None

                msg_type = bytes(message[1:2])
                subtype = bytes(message[2:3])
                stimestamp = int.from_bytes(message[3:7], 'big')
                payload_type = bytes(message[7:8])
                payload = message[8:-1]
                checksum = message[-1]
                self.master._dprint(f"{type(msg_type)}: {msg_type}, {type(subtype)}: {subtype}, {type(stimestamp)}: {stimestamp}, {type(payload_type)}: {payload_type},  {type(payload)}: {payload},  {type(checksum)}: {checksum}")
                
                #Checksum
                if checksum != sum(message[:-1]) % 256:
                    self.master._dprint("Invalid message: checksum mismatch")
                    return None
                
                if sender_mac not in self._peers:
                    self.add_peer(sender_mac)
                
                if payload_type == b'\x07':
                    self.master._dprint("Long message received, processing...")
                    part_n = int.from_bytes(payload[0:1], 'big')
                    total_n = int.from_bytes(payload[1:2], 'big')
                    payload_type = bytes(payload[2:3])
                    payload = payload[3:]
                    
                    # Create a key as a bytearray: (msg_type, subtype, timestamp, payload_type, total_n)
                    key = bytearray()
                    key.extend(msg_type)
                    key.extend(subtype)
                    key.extend(message[3:7])
                    key.extend(payload_type)
                    key.append(total_n)#does this work? Yes!
                    key = bytes(key)
                    self.master._dprint(f"Key: {key}")
                    
                    # Check if the key already exists in the long buffer
                    if key in self._long_buffer:
                        # If the part is None, add the payload
                        if self._long_buffer[key][part_n] is None:
                            self._long_buffer[key][part_n] = payload
                            self.master._dprint(f"Long message: Key found, message added to entry in long_message_buffer, {sum(1 for item in self._long_buffer[key] if item is not None)} out of {total_n} packages received")
                            # If there are still missing parts, return
                            if any(value is None for value in self._long_buffer[key]):
                                gc.collect()
                                return
                    else:
                        # Initialize the long message buffer for this key
                        payloads = [None] * total_n
                        payloads[part_n] = payload
                        self._long_buffer[key] = payloads
                        self.master._dprint(f"Long message: Key not found and new entry created in long_message_buffer, {sum(1 for item in self._long_buffer[key] if item is not None)} out of {total_n} packages received")
                        gc.collect()
#                        # If there are missing parts, request missing messages, due to buffer constraints this is disabled
#                         if any(value is None for value in self._long_buffer[key]):
#                             none_indexes = [index for index, value in enumerate(self._long_buffer[key]) if value is None]
#                             response = bytearray()
#                             response.extend(msg_type)
#                             response.extend(subtype)
#                             response.extend(message[3:7])#stimestamp.to_bytes(4, 'big')
#                             response.extend(payload_type)
#                             response.extend(payload[1:2])#total_n.to_bytes(1, 'big')
#                             for none_index in none_indexes:
#                                 response.extend(none_index.to_bytes(1, 'big'))
#                             #asyncio.create_task(__request_missing_messages(sender_mac, response, key, total_n))
#                             gc.collect()
                        return
                        
                    # If all parts have been received, reconstruct the message
                    if not any(value is None for value in self._long_buffer[key]):
                        payload = bytearray()
                        for i in range(0, total_n):
                            payload.extend(self._long_buffer[key][i])
                        del self._long_buffer[key]
                        self.master._dprint("Long message: All packages received!")
                    else:
                        self.master._dprint("Long Message: Safeguard triggered, code should not have gotten here")
                        gc.collect()
                        return
                
                #Handle the message based on type
                if msg_type == b'\x01':  # Command Message
                    __handle_cmd(sender_mac, subtype, stimestamp, rtimestamp, payload_type, payload if payload else None)
                elif msg_type == b'\x02':  # Informational Message
                    __handle_inf(sender_mac, subtype, stimestamp, rtimestamp, payload_type, payload if payload else None)
                elif msg_type == b'\x03':  # Acknowledgement Message
                    __handle_ack(sender_mac, subtype, stimestamp, rtimestamp, payload_type, payload if payload else None)
                else:
                    self.master._iprint(f"Unknown message type from {sender_mac} ({self.peer_name(sender_mac)}): {message}")

            async def __request_missing_messages(sender_mac, payload, key, total_n=0, retries=3, waittime=2):
                self.master._dprint("aen.__request_missing_messages")
                for i in range(retries):
                    i += i
                    asyncio.sleep(waittime + total_n*0.1)
                    if key in self._long_buffer:
                        self._compose(sender_mac, payload, 0x01, 0x17)
                    else:
                        return
            
            def __handle_cmd(sender_mac, subtype, stimestamp, rtimestamp, payload_type, payload):
                self.master._dprint("aen.__handle_cmd")
                if subtype == b'\x10': #Ping
                    #self.master._iprint(f"Ping command received from {sender_mac} ({self.peer_name(sender_mac)})")
                    info = __decode_payload(payload_type, payload)
                    self.add_peer(sender_mac, info[2], info[0], info[1])
                    if bool(self.ifidx):
                        channel = self.master.ap.channel()
                    else:
                        channel = self.master.sta.channel()
                    response = [channel, self.ifidx, self.master.name, stimestamp]
                    self._compose(sender_mac, response, 0x03, 0x10)
                elif subtype == b'\x11': #Pair
                    self.master._iprint(f"Pairing command received from {sender_mac} ({self.peer_name(sender_mac)})")
                    # Insert pairing logic here
                elif subtype == b'\x12': #Change Mode to Firmware Update
                    self.master._iprint(f"Update command received from {sender_mac} ({self.peer_name(sender_mac)})")
                    # Insert update logic here
                elif subtype == b'\x13': #RSSI Boop
                    self.boops = self.boops + 1
                    self.master._iprint(f"Boop command received from {sender_mac} ({self.peer_name(sender_mac)}), Received total of {self.boops} boops!")
                    self._compose(sender_mac, self.rssi(), 0x02, 0x20)
                elif subtype == b'\x14': #Reboot
                    self.master._iprint(f"Reboot command received from {sender_mac} ({self.peer_name(sender_mac)})")
                    machine.reset()
                elif subtype == b'\x15': #Echo
                    self.master._iprint(f"Echo command received from {sender_mac} ({self.peer_name(sender_mac)}): {__decode_payload(payload_type, payload)}")#Check i or d
                    self._compose(sender_mac, payload, 0x03, 0x15)
                elif subtype == b'\x16': #Run file
                    filename = __decode_payload(payload_type, payload)
                    self.master._iprint(f"Run command received from {sender_mac} ({self.peer_name(sender_mac)}): {filename}")    
                    #try:    
                    #    task = asyncio.create_task(run_script(filename))
                        #Needs
                        #async def execute_script(script_path):
                        # Load and execute the script
                        #with open(script_path) as f:
                        #    script_code = f.read()
                        #
                        #exec(script_code)  # This executes the script in the current namespace
                        #
                        # Alternatively, if you want to run this in a separate function scope
                        #exec(script_code, {'__name__': '__main__'})
                        #            except Exception as e:
                        #                print(f"Error running {filename}: {e}")
                elif subtype == b'\x17': #Resend lost long messages
                    self.master._iprint("Received resend long message command, long_sent_buffer disabled due to memory constraints")
#                    payload = __decode_payload(payload_type, payload)
#                    self.master._iprint("Received resend long message command, checking buffer for lost message")
#                     key = payload[0:8]
#                     indexes_b = payload[8:]
#                     indexes = []
#                     for i in range(0, len(indexes_b)):
#                         indexes.append(int.from_bytes(indexes_b[i], 'big'))
#                     if key in self._long_sent_buffer:
#                         channel = self._long_sent_buffer[key][1][0]
#                         ifidx = self._long_sent_buffer[key][1][1]
#                         for index in indexes:
#                             message.append(self._long_sent_buffer[key][0][index])
#                         self._send(sender_mac, messages, channel, ifidx)
#                         #resend the message from the message buffer
#                         self.master._iprint("Resent all requested messages")
#                     else:
#                         self.master._iprint("Message not found in the buffer")
                elif subtype == b'\x18': #Connect to WiFi
                    payload = __decode_payload(payload_type, payload) #should return a list of ssid and password
                    self.master._iprint("Received connect to wifi command")
                    self.connect(payload[0], payload[1])
                elif subtype == b'\x19': #Disconnect from WiFi
                    self.master._iprint("Received disconnect from wifi command")
                    self.disconnect()
                elif subtype == b'\x20': #Enable AP
                    payload = __decode_payload(payload_type, payload) #should return a list of desired name, password an max clients
                    self.master._iprint("Received setup AP command")
                    ssid = payload[0]
                    if ssid == "":
                        ssid = self.master.name
                    password = payload[1]
                    self.setap(ssid, password)
                elif subtype == b'\x21': #Disable AP
                    self.master._iprint("Received disable AP command")
                    #disaple ap command
                elif subtype == b'\x22': #Set Admin Bool
                    payload = __decode_payload(payload_type, payload) #should return a bool
                    self.master._iprint(f"Received set admin command: self.admin set to {payload}")
                    self.master._admin = payload
                else:
                    self.vprint(f"Unknown command subtype from {sender_mac} ({self.peer_name(sender_mac)}): {subtype}")

            def __handle_inf(sender_mac, subtype, stimestamp, rtimestamp, payload_type, payload):
                self.master._dprint("aen.__inf")
                if subtype == b'\x21': #Sensor Data
                    payload = __decode_payload(payload_type, payload)
                    payload["time_sent"] = stimestamp
                    payload["time_recv"] = rtimestamp
                    self.master._iprint(f"Sensor data received from {sender_mac} ({self.peer_name(sender_mac)}): {payload}")
                    self.received_data[sender_mac] = payload
                elif subtype == b'\x20': #RSSI
                    payload = __decode_payload(payload_type, payload)
                    self.master._iprint(f"RSSI data received from {sender_mac} ({self.peer_name(sender_mac)}): {payload}")
                    # Process RSSI data
                elif subtype == b'\x22': #Other
                    payload = __decode_payload(payload_type, payload)
                    self.master._iprint(f"Message received from {sender_mac} ({self.peer_name(sender_mac)}): {payload}")
                    self._saved_messages.append((sender_mac, payload, rtimestamp))
                else:
                    payload = __decode_payload(payload_type, payload)
                    self.master._iprint(f"Unknown info subtype from {sender_mac} ({self.peer_name(sender_mac)}): {subtype}")
                    
            def __handle_ack(sender_mac, subtype, stimestamp, rtimestamp, payload_type, payload):
                self.master._dprint("aen.__handle_ack")
                if subtype == b'\x10': #Pong
                    info = __decode_payload(payload_type, payload)
                    self.add_peer(sender_mac, info[2], info[0], info[1])
                    self.master._iprint(f"Pong received from {sender_mac} ({self.peer_name(sender_mac)}), {rtimestamp-info[3]}") #Always print this
                elif subtype == b'\x15': #Echo
                    self.master._iprint(f"Echo received from {sender_mac} ({self.peer_name(sender_mac)}), {__decode_payload(payload_type, payload)}") #Always print this
                else:    
                    self.master._iprint(f"Unknown ack subtype from {sender_mac} ({self.peer_name(sender_mac)}): {subtype}, Payload: {payload}")
                # Insert more acknowledgement logic here add message to acknowledgement buffer

            if self._aen.any(): 
                for sender_mac, data in self._aen:
                    self.master._dprint(f"Received {sender_mac, data}")
                    if sender_mac is None: # mac, msg will equal (None, None) on timeout
                        break
                    if data:
                        rtimestamp = time.ticks_ms()
                        if sender_mac != None and data != None:
                            #self.received_messages.append((sender_mac, data, rtimestamp))#Messages will be saved here, this is only for debugging purposes
                            #print(f"Received from {sender_mac}: {data}")
                            __process_message(sender_mac, data, rtimestamp)
                    if not self._aen.any():#this is necessary as the for loop gets stuck and does not exit properly.
                        break
                    
           
#message structure (what kind of message types do I need?: Command which requires me to do something (ping, pair, change state(update, code, mesh mode, run a certain file), Informational Message (Sharing Sensor Data and RSSI Data)
#| Header (1 byte) | Type (1 byte) | Subtype (1 byte) | Timestamp(ms ticks) (4 bytes) | Payload type (1) | Payload (variable) | Checksum (1 byte) |
