"""
Firmware Upload Manager

Manages firmware upload operations to ESP32 devices via Serial.
Handles file upload, directory creation, and device reset operations.

Upload Process:
1. Enter REPL mode (interrupt running code)
2. Enter raw REPL mode (for file operations)
3. Create directories as needed
4. Upload files with progress tracking
5. Exit REPL and restart with new firmware
"""

import asyncio


class FirmwareManager:
    """Manages firmware upload and device operations"""
    
    def __init__(self, repl_controller):
        """
        Initialize firmware manager.
        
        Args:
            repl_controller: ReplController instance for REPL operations
        """
        self.repl = repl_controller
        print("📦 FirmwareManager initialized")
    
    async def ensure_directory(self, dir_path):
        """
        Create directory on device if it doesn't exist.
        
        Args:
            dir_path: Directory path to create (e.g., "lib", "config")
        """
        if not dir_path or dir_path in ['/', '.']:
            return
        
        print(f"Creating directory: {dir_path}")
        
        code = f"""
import os
try:
    os.mkdir('{dir_path}')
except OSError:
    pass  # Already exists
"""
        await self.repl.execute_command(code, timeout_ms=3000)
    
    async def upload_single_file(self, file_path, content):
        """
        Upload single file to device using triple-quoted string.
        
        Args:
            file_path: Path on device (e.g., "main.py", "lib/module.py")
            content: File content as string
        """
        print(f"Uploading {file_path} ({len(content)} bytes)")
        
        # Escape content for triple-quoted Python string
        content_escaped = content.replace('\\', '\\\\').replace("'''", "\\'\\'\\'")
        
        # Build Python code to write the file
        upload_code = f"""
with open('{file_path}', 'w') as f:
    f.write('''{content_escaped}''')
print('OK')
"""
        
        try:
            # Use chunked upload for large files (> 2KB) to support older MicroPython
            # Helps ESP32-C3 with limited RAM and older firmware versions
            # Doesn't hurt newer devices (C6) - just slightly slower
            timeout_ms = max(5000, len(content) // 100)  # ~10KB/sec minimum
            chunk_size = 256 if len(upload_code) > 2048 else None
            
            if chunk_size:
                print(f"Using chunked upload ({chunk_size} bytes/chunk) for compatibility")
            
            response = await self.repl.execute_command(
                upload_code, 
                timeout_ms=timeout_ms,
                chunk_size=chunk_size
            )
            
            # Check for OK response
            if 'OK' in response or not response:
                print(f"✓ Uploaded {file_path}")
            else:
                print(f"⚠️ Upload completed but unexpected response: {response[:100]}")
            
        except Exception as e:
            raise Exception(f"Upload failed for {file_path}: {str(e)}")
    
    async def execute_file(self, file_path, timeout_ms=10000):
        """
        Execute/run a specific Python file on the device.
        
        Args:
            file_path: Path to file on device (e.g., "main.py")
            timeout_ms: Execution timeout
            
        Returns:
            str: Output from file execution
        """
        print(f"Executing {file_path}...")
        
        code = f"exec(open('{file_path}').read())"
        response = await self.repl.execute_command(code, timeout_ms=timeout_ms)
        
        print(f"✓ Executed {file_path}")
        return response
    
    async def soft_reset(self, wait_time_ms=1500):
        """
        Soft reset device (Ctrl-D).
        
        Re-initializes MicroPython without hardware reboot.
        Device will be at REPL prompt after reset.
        
        Args:
            wait_time_ms: Time to wait for reset to complete
        """
        print("Soft resetting device...")
        await self.repl.serial.send_raw('\x04')
        await asyncio.sleep(wait_time_ms / 1000.0)
        print(f"✓ Soft reset complete (waited {wait_time_ms}ms)")
    
    async def hard_reset(self, wait_time_ms=2000):
        """
        Hard reset device (machine.reset()).
        
        Full hardware reboot - device will run main.py on startup.
        
        Args:
            wait_time_ms: Time to wait for reboot to complete
        """
        print("Hard resetting device (hardware reboot)...")
        
        # Execute reset command in raw REPL
        reset_code = """
import machine
machine.reset()
"""
        try:
            await self.repl.serial.send_raw(reset_code)
            await self.repl.serial.send_raw('\x04')  # CTRL-D to execute
            
            # Wait for device to reset
            await asyncio.sleep(wait_time_ms / 1000.0)
            print(f"✓ Hard reset initiated (waited {wait_time_ms}ms for reboot)")
        except Exception as e:
            # Reset command may not return a response since device reboots
            print(f"Hard reset command sent (device is rebooting...)")

