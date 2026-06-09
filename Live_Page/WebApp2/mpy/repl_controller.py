"""
MicroPython REPL Controller

Manages MicroPython REPL (Read-Eval-Print Loop) operations for ESP32 devices.
Handles entering/exiting different REPL modes and executing Python code.

REPL Modes:
- Normal REPL: Interactive prompt (>>>)
- Raw REPL: Programmatic mode for automation (>)
- Paste Mode: Multi-line code entry (Ctrl-E)

Control Sequences:
- Ctrl-C (\\x03): Interrupt/cancel
- Ctrl-A (\\x01): Enter raw REPL
- Ctrl-B (\\x02): Exit raw REPL
- Ctrl-D (\\x04): Execute/reset
- Ctrl-E (\\x05): Enter paste mode
"""

from pyscript import window
import asyncio


class ReplController:
    """Controls MicroPython REPL operations on ESP32"""
    
    def __init__(self, serial_connection):
        """
        Initialize REPL controller.
        
        Args:
            serial_connection: SerialConnection instance for I/O operations
        """
        self.serial = serial_connection
        print("🔧 ReplController initialized")
    
    async def enter_repl_mode(self):
        """
        Stop JSON mode and get to normal REPL (>>> prompt).
        
        Sends Ctrl-C to interrupt running code (typically main.py),
        which brings up the normal REPL prompt (>>>).
        
        Does NOT enter raw REPL mode - that's enter_raw_repl_mode().
        """
        print("🔄 Entering normal REPL mode...")
        
        # Stop JSON read loop (waits for cleanup to complete)
        await self.serial._stop_json_read_loop()
        
        # Send multiple CTRL-C to interrupt any running code (main.py)
        print("🛑 Interrupting running code with Ctrl-C...")
        for i in range(3):
            await self.serial.send_raw('\x03')  # Ctrl-C
            await asyncio.sleep(0.05)
        
        # Wait for interruption to take effect
        await asyncio.sleep(0.2)
        
        # Drain any existing output
        print("🧹 Draining buffer...")
        for i in range(5):
            chunk = await self.serial.read_raw(200)
            if chunk:
                print(f"Drained: {chunk[:100]}")
        
        print("✅ Should now be at normal REPL (>>> prompt)")
    
    async def enter_raw_repl_mode(self):
        """
        Enter raw REPL mode from normal REPL (> prompt).
        
        Sends Ctrl-A to enter raw REPL mode.
        Assumes we're already at normal REPL (>>> prompt).
        
        Raw REPL is like permanent paste mode - no echo, used for uploading files.
        """
        print("🔄 Entering raw REPL mode...")
        
        # Send CTRL-A to enter raw REPL mode
        print("📤 Sending Ctrl-A to enter raw REPL...")
        await self.serial.send_raw('\x01')  # Ctrl-A
        await asyncio.sleep(0.3)
        
        # Wait for "raw REPL; CTRL-B to exit" prompt
        result = await self.serial.adapter.readUntil('raw REPL', 5000)
        
        if result.found:
            print("✅ Entered raw REPL mode (> prompt)")
            # Drain any remaining welcome text
            for i in range(5):
                await self.serial.read_raw(200)
        else:
            # Be lenient - continue anyway
            print("⚠️ May not have entered raw REPL properly")
            print("⚠️ This might work anyway - continuing...")
    
    async def exit_raw_repl_mode(self):
        """
        Exit raw REPL mode and return to normal REPL (>>>) prompt.
        
        Sends CTRL-B to exit raw REPL mode.
        Does NOT return to JSON mode - for that, restart the device.
        """
        print("Exiting raw REPL mode...")
        # Send CTRL-B to exit raw REPL
        await self.serial.send_raw('\x02')
        await asyncio.sleep(0.2)
        
        # Verify we got back to normal REPL
        result = await self.serial.adapter.readUntil('>>>', 1000)
        if result.found:
            print("✓ Exited to normal REPL mode (>>>)")
        else:
            print("⚠️ Exit may not have completed (no >>> prompt), continuing anyway")
    
    async def execute_command(self, code, timeout_ms=5000, chunk_size=None):
        """
        Execute Python code in raw REPL mode.
        
        Protocol:
        1. Write code (not echoed back in raw REPL)
        2. Send CTRL-D (\\x04) to execute
        3. Read response (with timeout to prevent hanging)
        4. Check for errors
        
        Args:
            code: Python code to execute
            timeout_ms: Maximum time to wait for response
            chunk_size: If set, send code in chunks with delays (for older MicroPython)
        
        Returns:
            str: Output from code execution
            
        Raises:
            Exception: If execution errors or timeout
        """
        start_time = window.Date.now()
        
        try:
            # Write the code (chunked if requested for compatibility with older MicroPython)
            if chunk_size:
                # Send in chunks with pacing to avoid buffer overflow on C3/older devices
                print(f"Sending {len(code)} bytes in {chunk_size}-byte chunks...")
                for i in range(0, len(code), chunk_size):
                    chunk = code[i:i+chunk_size]
                    await self.serial.send_raw(chunk)
                    # 10ms delay between chunks (micro-repl's proven approach)
                    await asyncio.sleep(0.01)
                print(f"✓ All chunks sent")
            else:
                # Send all at once (fast path for newer MicroPython)
                await self.serial.send_raw(code)
            
            # Send CTRL-D to execute
            await self.serial.send_raw('\x04')
            await asyncio.sleep(0.2)
            
            # Read response (try multiple times to get all output)
            response = ''
            for i in range(5):
                if (window.Date.now() - start_time) > timeout_ms:
                    raise Exception(f"REPL command timeout after {timeout_ms}ms")
                
                chunk = await self.serial.read_raw(1000)
                response += chunk
                if not chunk:
                    break
            
            # Check for errors
            if 'Traceback' in response or 'Error:' in response:
                error_snippet = response[:200] if response else "Unknown error"
                raise Exception(f"REPL execution error: {error_snippet}")
            
            return response
            
        except Exception as e:
            raise Exception(f"Failed to execute REPL command: {str(e)}")
    
    async def get_board_info(self, timeout_ms=5000):
        """
        Get MicroPython version and board info using PASTE MODE.
        
        Uses paste mode (Ctrl-E) to execute Python code that prints os.uname().version.
        This returns the full version string including board type (e.g., ESP32C6).
        More reliable than parsing boot messages from soft reset.
        
        Approach based on micro-repl's proven implementation.
        
        Returns:
            str: Board info like "MicroPython v1.22.0 on 2024-01-01; ESP32-C6 with ESP32C6"
            
        Raises:
            Exception: If board info cannot be retrieved
        """
        print("🔍 Getting board info via paste mode...")
        start_time = window.Date.now()
        
        try:
            # Step 1: Reset to clean state
            print("🔍 Step 1: Resetting to clean state...")
            await self.serial.send_raw('\x02')  # Ctrl-B (exit raw REPL if in it)
            await asyncio.sleep(0.2)
            await self.serial.send_raw('\x03\x03')  # Double Ctrl-C (interrupt any running code)
            await asyncio.sleep(0.5)
            
            # Step 2: Drain buffer to clear any pending output
            print("🔍 Step 2: Draining buffer...")
            for i in range(5):
                chunk = await self.serial.read_raw(200)
                if chunk:
                    print(f"   Drained: {repr(chunk[:60])}")
            
            # Step 3: Enter paste mode (Ctrl-E)
            print("🔍 Step 3: Entering paste mode (Ctrl-E)...")
            await self.serial.send_raw('\x05')  # Ctrl-E
            await asyncio.sleep(0.3)
            
            # Step 4: Send Python code to get version and machine info
            print("🔍 Step 4: Sending Python code to get version...")
            code = """import os
u = os.uname()
print(f"MicroPython {u.version}; {u.machine}")
"""
            await self.serial.send_raw(code)
            
            # Step 5: Execute the code (Ctrl-D in paste mode)
            print("🔍 Step 5: Executing code (Ctrl-D)...")
            await self.serial.send_raw('\x04')  # Ctrl-D
            await asyncio.sleep(0.8)
            
            # Step 6: Collect response
            response = ''
            print("🔍 Step 6: Collecting response...")
            for i in range(15):
                if (window.Date.now() - start_time) > timeout_ms:
                    print(f"❌ Timeout after {timeout_ms}ms. Received so far: {repr(response[:200])}")
                    raise Exception(f"Timeout waiting for board info ({timeout_ms}ms)")
                
                chunk = await self.serial.read_raw(500)
                if chunk:
                    print(f"   Got chunk ({len(chunk)} bytes): {repr(chunk[:80])}")
                    response += chunk
                
                # Stop if we found MicroPython version
                if 'MicroPython' in response:
                    print(f"✅ Found MicroPython version string!")
                    break
                
                # Stop if no more data
                if not chunk:
                    break
            
            # Step 7: Parse version from response
            print("🔍 Step 7: Parsing version from response...")
            if 'MicroPython' in response:
                lines = response.split('\n')
                for line in lines:
                    # Look for the actual output line (not echoed code)
                    # Valid lines start with "MicroPython " followed by version or git hash
                    # Skip lines that are paste mode echo (contain "===", "print(", etc.)
                    stripped = line.strip()
                    if (stripped.startswith('MicroPython ') and 
                        'on' in line and
                        '===' not in line and
                        'print(' not in line and
                        '{' not in line):  # Skip f-string template
                        board_info = stripped
                        print(f"✅ Board detected: {board_info}")
                        return board_info
            
            # Didn't find MicroPython version in output
            print(f"❌ No MicroPython version found in response")
            print(f"   Full response: {repr(response[:300])}")
            raise Exception(f"MicroPython version not found in response")
                
        except Exception as e:
            print(f"❌ get_board_info failed: {str(e)}")
            raise Exception(f"Failed to get board info: {str(e)}")

