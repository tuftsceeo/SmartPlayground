"""
uart_comm.py - Generic UART Communication Library
------------------------------------------------
Provides reliable message-based UART communication with automatic 
acknowledgments, retries, and memory management.

Features:
- Automatic acknowledgment and retry handling
- Memory-optimized with garbage collection
- Simple send/receive interface
- Connection health monitoring
- Pre-allocated buffers for performance

Usage:
    from uart_comm import UARTComm
    
    def on_message(msg_type, data, src):
        print(f"Received {msg_type}: {data}")
    
    comm = UARTComm(board_name="BOARD1", uart_id=1, baud_rate=921600)
    comm.set_message_handler(on_message)
    comm.start()
    comm.send_message("PING", {"hello": "world"})
"""
import machine
import time
import ujson
import binascii
import asyncio
import gc
import micropython

class BufferPool:
    """Pre-allocated buffers to prevent memory fragmentation"""
    def __init__(self):
        self.rx_buffer = bytearray(2048)
        self.tx_temp = bytearray(512)
        self.message_buffer = ""
        self.stats = {'buffer_reuses': 0, 'gc_triggers': 0}
    
    def get_tx_buffer(self, size_needed):
        """Get a reusable transmit buffer"""
        if size_needed > len(self.tx_temp):
            self.tx_temp = bytearray(size_needed + 100)
        self.stats['buffer_reuses'] += 1
        return self.tx_temp
    
    def trigger_gc(self):
        """Force garbage collection"""
        free_before = gc.mem_free()
        gc.collect()
        free_after = gc.mem_free()
        self.stats['gc_triggers'] += 1
        return free_after - free_before

class MessageTracker:
    """Manages outgoing message tracking with acknowledgments"""
    
    def __init__(self, ack_timeout_ms=3000, max_retries=3):
        self.pending_messages = {}
        self.ack_timeout_ms = ack_timeout_ms
        self.max_retries = max_retries
        self.stats = {
            'sent': 0, 'acknowledged': 0, 'retries': 0, 
            'failed': 0, 'cleaned_up': 0
        }
    
    def add_message(self, msg_id, message_data, needs_ack=True):
        """Add a message to tracking"""
        if needs_ack:
            self.pending_messages[msg_id] = {
                'message': message_data,
                'sent_time': time.ticks_ms(),
                'retry_count': 0
            }
        self.stats['sent'] += 1
    
    def acknowledge_message(self, msg_id):
        """Mark a message as acknowledged"""
        if msg_id in self.pending_messages:
            del self.pending_messages[msg_id]
            self.stats['acknowledged'] += 1
            return True
        return False
    
    def get_expired_messages(self):
        """Get messages that need to be retried"""
        current_time = time.ticks_ms()
        expired = []
        
        for msg_id, info in self.pending_messages.items():
            time_elapsed = time.ticks_diff(current_time, info['sent_time'])
            if (time_elapsed >= self.ack_timeout_ms and 
                info['retry_count'] < self.max_retries):
                expired.append((msg_id, info))
        
        # Clean up failed messages
        failed_ids = [msg_id for msg_id, info in self.pending_messages.items() 
                     if info['retry_count'] >= self.max_retries]
        for msg_id in failed_ids:
            del self.pending_messages[msg_id]
            self.stats['failed'] += 1
        
        return expired
    
    def retry_message(self, msg_id):
        """Mark a message for retry"""
        if msg_id in self.pending_messages:
            self.pending_messages[msg_id]['sent_time'] = time.ticks_ms()
            self.pending_messages[msg_id]['retry_count'] += 1
            self.stats['retries'] += 1
    
    def cleanup_old_messages(self, max_age_ms=30000):
        """Remove old messages that have timed out"""
        current_time = time.ticks_ms()
        old_ids = [msg_id for msg_id, info in self.pending_messages.items()
                   if time.ticks_diff(current_time, info['sent_time']) > max_age_ms]
        for msg_id in old_ids:
            del self.pending_messages[msg_id]
            self.stats['cleaned_up'] += 1
    
    def get_status(self):
        """Get tracking statistics"""
        return {
            'pending': len(self.pending_messages),
            'stats': self.stats.copy()
        }

class UARTComm:
    """Generic UART Communication Manager"""
    
    def __init__(self, board_name, uart_id=1, tx_pin=16, rx_pin=17, 
                 baud_rate=921600, debug_prints=False):
        self.board_name = board_name
        self.uart_id = uart_id
        self.tx_pin = tx_pin
        self.rx_pin = rx_pin
        self.baud_rate = baud_rate
        self.debug_prints = debug_prints
        
        # Initialize components
        self.uart = None
        self.device_id = self._get_device_id()
        self.buffer_pool = BufferPool()
        self.message_tracker = MessageTracker()
        self.message_handler = None
        self.msg_counter = 0
        self.running = False
        self.tasks = []
        
        # Initialize emergency exception buffer
        micropython.alloc_emergency_exception_buf(100)
    
    def _get_device_id(self):
        """Generate unique device ID from MAC address"""
        import network
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        mac = wlan.config('mac')
        return binascii.hexlify(mac).decode('utf-8')[-4:]
    
    def _debug_print(self, *args):
        """Conditional debug printing"""
        if self.debug_prints:
            print(*args)
    
    def _status_print(self, *args):
        """Always print important status"""
        print(*args)
    
    def set_message_handler(self, handler):
        """Set callback for incoming messages: handler(msg_type, data, src)"""
        self.message_handler = handler
    
    def start(self):
        """Initialize and start UART communication"""
        if self.running:
            return
        
        self._status_print(f"Starting UART communication for {self.board_name}")
        self._status_print(f"Baud: {self.baud_rate}, Debug: {self.debug_prints}")
        
        # Initialize UART
        self.uart = machine.UART(
            self.uart_id, baudrate=self.baud_rate,
            tx=self.tx_pin, rx=self.rx_pin, timeout=100,
            rxbuf=4096, txbuf=2048
        )
        
        self._status_print(f"UART initialized on pins TX:{self.tx_pin}, RX:{self.rx_pin}")
        self.running = True
        
        # Start background tasks
        self.tasks = [
            asyncio.create_task(self._receive_messages()),
            asyncio.create_task(self._retry_handler()),
            asyncio.create_task(self._memory_manager())
        ]
    
    def stop(self):
        """Stop UART communication"""
        self.running = False
        for task in self.tasks:
            if not task.done():
                task.cancel()
        self.tasks.clear()
        self._status_print("UART communication stopped")
    
    async def send_message(self, msg_type, data, needs_ack=True):
        """Send a message with automatic acknowledgment handling"""
        if not self.running:
            raise RuntimeError("UART communication not started")
        
        message = {
            "src": f"{self.board_name}_{self.device_id}",
            "type": msg_type,
            "id": self.msg_counter,
            "data": data,
            "timestamp": time.time(),
            "needs_ack": needs_ack
        }
        
        if msg_type != "ACK":
            self.msg_counter += 1
        
        # Add to tracker
        self.message_tracker.add_message(message["id"], message, needs_ack)
        
        # Send message
        await self._send_raw_message(message)
        
        self._debug_print(f"Sent {msg_type} message {message['id']}")
        return message["id"]
    
    async def _send_raw_message(self, message):
        """Send raw message using pre-allocated buffer"""
        json_str = ujson.dumps(message) + "\n"
        json_bytes = json_str.encode('utf-8')
        
        tx_buffer = self.buffer_pool.get_tx_buffer(len(json_bytes))
        tx_buffer[:len(json_bytes)] = json_bytes
        
        self.uart.write(tx_buffer[:len(json_bytes)])
        await asyncio.sleep_ms(10)  # Allow REPL interruption
    
    async def _send_ack(self, ref_id, target):
        """Send acknowledgment message"""
        await self.send_message("ACK", {
            "ref_id": ref_id,
            "status": "OK",
            "target": target
        }, needs_ack=False)
    
    async def _receive_messages(self):
        """Continuously receive and process messages"""
        while self.running:
            try:
                if self.uart and self.uart.any():
                    bytes_read = self.uart.readinto(self.buffer_pool.rx_buffer)
                    if bytes_read:
                        new_data = self.buffer_pool.rx_buffer[:bytes_read].decode('utf-8')
                        self.buffer_pool.message_buffer += new_data
                        
                        # Process complete messages
                        while '\n' in self.buffer_pool.message_buffer:
                            line, self.buffer_pool.message_buffer = \
                                self.buffer_pool.message_buffer.split('\n', 1)
                            line = line.strip()
                            
                            if line:
                                try:
                                    message = ujson.loads(line)
                                    asyncio.create_task(self._process_message(message))
                                except Exception as e:
                                    self._debug_print(f"Parse error: {e}")
                
                await asyncio.sleep_ms(50)  # Allow REPL interruption
                
            except Exception as e:
                self._status_print(f"Receive error: {e}")
                await asyncio.sleep_ms(100)
    
    async def _process_message(self, message):
        """Process received message"""
        try:
            msg_type = message.get("type")
            msg_data = message.get("data")
            msg_src = message.get("src")
            
            if msg_type == "ACK":
                # Handle acknowledgment
                ref_id = msg_data.get("ref_id")
                if self.message_tracker.acknowledge_message(ref_id):
                    self._debug_print(f"ACK received for message {ref_id}")
            else:
                # Handle user message
                self._debug_print(f"Received {msg_type} from {msg_src}")
                
                # Send ACK if requested
                if message.get("needs_ack", True):
                    await self._send_ack(message.get("id"), msg_src)
                
                # Call user handler
                if self.message_handler:
                    try:
                        self.message_handler(msg_type, msg_data, msg_src)
                    except Exception as e:
                        self._debug_print(f"Handler error: {e}")
        
        except Exception as e:
            self._debug_print(f"Process error: {e}")
    
    async def _retry_handler(self):
        """Handle message retransmissions"""
        while self.running:
            try:
                expired_messages = self.message_tracker.get_expired_messages()
                
                for msg_id, msg_info in expired_messages:
                    self._debug_print(f"Retrying message {msg_id}")
                    await self._send_raw_message(msg_info['message'])
                    self.message_tracker.retry_message(msg_id)
                
                await asyncio.sleep_ms(1000)  # Allow REPL interruption
                
            except Exception as e:
                self._status_print(f"Retry error: {e}")
                await asyncio.sleep_ms(1000)
    
    async def _memory_manager(self):
        """Manage memory and garbage collection"""
        while self.running:
            try:
                free_memory = gc.mem_free()
                
                if free_memory < 5000:
                    self._status_print(f"Critical memory: {free_memory} bytes")
                    self.message_tracker.cleanup_old_messages()
                    self.buffer_pool.trigger_gc()
                elif free_memory < 10000:
                    self._debug_print(f"Low memory: {free_memory} bytes")
                    self.buffer_pool.trigger_gc()
                else:
                    # Proactive garbage collection
                    gc.collect()
                
                # Regular cleanup
                self.message_tracker.cleanup_old_messages()
                
                await asyncio.sleep_ms(2000)  # Allow REPL interruption
                
            except Exception as e:
                self._status_print(f"Memory manager error: {e}")
                await asyncio.sleep_ms(10)
    
    def get_stats(self):
        """Get communication statistics"""
        tracker_stats = self.message_tracker.get_status()
        return {
            'board_name': self.board_name,
            'device_id': self.device_id,
            'free_memory': gc.mem_free(),
            'messages': tracker_stats['stats'],
            'pending': tracker_stats['pending'],
            'buffer_stats': self.buffer_pool.stats.copy()
        }
    
    def is_running(self):
        """Check if communication is active"""
        return self.running