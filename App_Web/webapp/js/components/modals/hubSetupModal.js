/**
 * Hub Setup Modal Component
 * 
 * Modal overlay for uploading hub firmware to ESP32 via serial.
 * Queries device info, shows confirmation, then uploads with progress tracking.
 * 
 * States:
 * - loading: Connecting and querying device information
 * - initial: Confirmation screen with device info
 * - uploading: Progress bar and file list
 * - success: Success message with reset button
 * - resetting: Device is performing hard reset to boot into new firmware
 * - error: Error message with retry option
 */

import { loadHubFiles } from '../../../hubCode/manifest.js';
import { PyBridge } from '../../utils/pyBridge.js';

export class HubSetupModal {
    constructor() {
        this.modal = null;
        this.state = 'loading'; // loading, initial, uploading, success, error
        this.hasExternalAntenna = false; // Track antenna configuration
        this.deviceInfo = null; // Device information from query
        this.deviceType = null; // Parsed device type (e.g., 'C6', 'C3', 'S3')
        this.uploadProgress = {
            current: 0,
            total: 0,
            currentFile: '',
            files: []
        };
    }

    /**
     * Show the modal and query device info
     */
    async show(serialPort) {
        this.serialPort = serialPort;
        
        this.createModal();
        this.render();
        document.body.appendChild(this.modal);
        
        // Initialize Lucide icons
        if (window.lucide) {
            window.lucide.createIcons();
        }
        
        // Query device info
        await this.queryDeviceInfo();
    }

    /**
     * Hide and destroy the modal
     */
    hide() {
        if (this.modal && this.modal.parentNode) {
            this.modal.parentNode.removeChild(this.modal);
        }
        this.modal = null;
    }

    /**
     * Create the modal DOM structure
     */
    createModal() {
        this.modal = document.createElement('div');
        this.modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
        this.modal.onclick = (e) => {
            if (e.target === this.modal && this.state !== 'uploading') {
                this.hide();
            }
        };
    }

    /**
     * Query device information via serial
     * Uses thin JavaScript async layer with Python business logic
     */
    async queryDeviceInfo() {
        try {
            console.log('🔍 Querying device info...');
            
            // Check if already connected
            const connectionStatus = await PyBridge.getConnectionStatus();
            
            if (!connectionStatus.connected || connectionStatus.mode !== 'serial') {
                // Need to connect first
                console.log('🔌 Connecting to serial port...');
                const connectResult = await PyBridge.connectHubSerial();
                
                if (connectResult.status !== 'success') {
                    throw new Error('Failed to connect: ' + (connectResult.error || 'Unknown error'));
                }
                
                // Wait for connection to stabilize (JavaScript handles timing)
                console.log('⏸️ Waiting for connection to stabilize...');
                await new Promise(resolve => setTimeout(resolve, 500));
            }
            
            // Step 1: Stop JSON read loop (Python logic)
            console.log('🛑 Stopping JSON read loop...');
            const stopResult = await PyBridge.queryDeviceInfoForSetup();
            
            if (stopResult.status === 'error') {
                throw new Error(stopResult.error || 'Failed to stop read loop');
            }
            
            // Step 2: Wait for loop to fully stop (JavaScript handles timing)
            console.log('⏸️ Waiting for read loop to stop...');
            await new Promise(resolve => setTimeout(resolve, 300));
            
            // Step 3: Get board info (Python logic)
            console.log('📡 Getting device information...');
            const infoResult = await PyBridge.getDeviceBoardInfo();
            
            if (infoResult.status === 'success') {
                this.deviceInfo = infoResult.info;
                this.deviceType = this.parseDeviceType(infoResult.info);
                console.log(`✅ Device detected: ${this.deviceType}`);
                
                // Move to initial confirmation state
                this.state = 'initial';
                this.render();
            } else {
                throw new Error(infoResult.error || 'Failed to get device info');
            }
            
        } catch (error) {
            console.error('❌ Device query error:', error);
            this.errorMessage = error.message || 'Failed to query device information';
            this.state = 'error';
            this.render();
        }
    }
    
    /**
     * Parse device type from info string
     * Example: "MicroPython v1.22.0 on 2024-01-01; ESP32-C6 with ESP32C6"
     */
    parseDeviceType(info) {
        if (!info) return null;
        
        const infoUpper = info.toUpperCase();
        if (infoUpper.includes('ESP32-C6') || infoUpper.includes('ESP32C6')) {
            return 'C6';
        } else if (infoUpper.includes('ESP32-C3') || infoUpper.includes('ESP32C3')) {
            return 'C3';
        } else if (infoUpper.includes('ESP32-S3') || infoUpper.includes('ESP32S3')) {
            return 'S3';
        } else if (infoUpper.includes('ESP32-S2') || infoUpper.includes('ESP32S2')) {
            return 'S2';
        } else if (infoUpper.includes('ESP32')) {
            return 'ESP32';
        }
        return 'Unknown';
    }

    /**
     * Render the modal content based on current state
     */
    render() {
        if (!this.modal) return;

        let content = '';
        switch (this.state) {
            case 'loading':
                content = this.renderLoading();
                break;
            case 'initial':
                content = this.renderInitial();
                break;
            case 'uploading':
                content = this.renderUploading();
                break;
            case 'success':
                content = this.renderSuccess();
                break;
            case 'resetting':
                content = this.renderResetting();
                break;
            case 'error':
                content = this.renderError();
                break;
        }

        this.modal.innerHTML = `
            <div class="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
                ${content}
            </div>
        `;

        // Re-attach event listeners
        this.attachEventListeners();
        
        // Initialize Lucide icons
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    /**
     * Render loading state while querying device
     */
    renderLoading() {
        return `
            <div class="p-6">
                <div class="flex items-center gap-3 mb-4">
                    <div class="animate-spin">
                        <i data-lucide="loader" class="w-6 h-6 text-blue-500"></i>
                    </div>
                    <h2 class="text-xl font-bold text-gray-800">Connecting to Device...</h2>
                </div>
                
                <div class="text-gray-600 text-sm">
                    <p>Please wait while we connect and identify your ESP32 device.</p>
                </div>
            </div>
        `;
    }

    /**
     * Render initial confirmation state
     */
    renderInitial() {
        const showAntennaOption = this.deviceType === 'C6';
        
        // For C3 devices, note that external antenna is always on (can't be configured)
        const isC3 = this.deviceType === 'C3';
        
        return `
            <div class="p-6">
                <div class="flex items-center gap-3 mb-4">
                    <i data-lucide="upload-cloud" class="w-6 h-6 text-blue-500"></i>
                    <h2 class="text-xl font-bold text-gray-800">Setup ESP32 as Hub</h2>
                </div>
                
                <div class="space-y-4">
                    ${this.deviceInfo ? `
                        <div class="bg-green-50 border border-green-200 rounded-lg p-4">
                        <div class="flex items-start gap-3">
                                <i data-lucide="check-circle" class="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5"></i>
                            <div class="text-sm">
                                    <p class="font-medium text-green-900 mb-1">Device Detected</p>
                                    <p class="text-green-800 font-mono text-xs">${this.deviceInfo}</p>
                                </div>
                            </div>
                        </div>
                    ` : ''}
                    
                    <div class="text-gray-700 text-sm">
                        <p class="mb-2">Ready to upload hub firmware to your ${this.deviceType || 'ESP32'} device.</p>
                        <p>This takes about 30 seconds and will enable communication with playground modules.</p>
                    </div>
                    
                    <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                        <div class="flex items-start gap-2">
                            <i data-lucide="alert-triangle" class="w-4 h-4 text-yellow-600 flex-shrink-0 mt-0.5"></i>
                            <p class="text-xs text-yellow-800">
                                This will overwrite existing code on your device.
                            </p>
                        </div>
                    </div>
                    
                    ${showAntennaOption ? `
                        <div class="bg-blue-50 border border-blue-200 rounded-lg p-3">
                            <div class="flex items-start gap-2">
                                <input type="checkbox" id="externalAntennaCheckbox" class="mt-0.5 w-4 h-4 text-blue-600 rounded">
                                <div class="flex-1">
                                    <label for="externalAntennaCheckbox" class="text-sm font-medium text-blue-900 cursor-pointer">
                                        Use external antenna
                                    </label>
                                    <p class="text-xs text-blue-700 mt-0.5">
                                        Check if your C6 has an external antenna connected.
                                    </p>
                                </div>
                            </div>
                        </div>
                    ` : ''}
                    
                    ${isC3 ? `
                        <div class="bg-gray-50 border border-gray-200 rounded-lg p-3">
                            <p class="text-xs text-gray-600">
                                <i data-lucide="info" class="w-3 h-3 inline mr-1"></i>
                                C3 devices use external antenna by default (not configurable).
                                </p>
                        </div>
                    ` : ''}
                </div>
                
                <div class="flex gap-3 mt-6">
                    <button id="cancel-btn" class="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 font-medium transition-colors">
                        Cancel
                    </button>
                    <button id="start-upload-btn" class="flex-1 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2">
                        <i data-lucide="play" class="w-4 h-4"></i>
                        <span>Start Upload</span>
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Render uploading progress state
     */
    renderUploading() {
        const progress = this.uploadProgress;
        const percentComplete = progress.total > 0 ? Math.floor((progress.current / progress.total) * 100) : 0;
        
        return `
            <div class="p-6">
                <div class="flex items-center gap-3 mb-4">
                    <div class="animate-spin">
                        <i data-lucide="loader" class="w-6 h-6 text-blue-500"></i>
                    </div>
                    <h2 class="text-xl font-bold text-gray-800">Uploading Hub Firmware...</h2>
                </div>
                
                <div class="mb-6">
                    <div class="flex justify-between text-sm text-gray-600 mb-2">
                        <span>Progress: ${progress.current} / ${progress.total} files</span>
                        <span>${percentComplete}%</span>
                    </div>
                    <div class="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                        <div class="bg-blue-500 h-full transition-all duration-300 rounded-full" style="width: ${percentComplete}%"></div>
                    </div>
                    <p class="text-xs text-gray-500 mt-2">Current: ${progress.currentFile || 'Preparing...'}</p>
                </div>
                
                <div class="bg-gray-50 border border-gray-200 rounded-lg p-4 max-h-64 overflow-y-auto">
                    <div class="space-y-2 text-sm">
                        ${progress.files.map(file => `
                            <div class="flex items-center gap-2">
                                ${file.status === 'uploaded' ? 
                                    '<i data-lucide="check-circle" class="w-4 h-4 text-green-500"></i>' :
                                    file.status === 'uploading' ?
                                    '<i data-lucide="loader" class="w-4 h-4 text-blue-500 animate-spin"></i>' :
                                    file.status === 'error' ?
                                    '<i data-lucide="x-circle" class="w-4 h-4 text-red-500"></i>' :
                                    '<i data-lucide="circle" class="w-4 h-4 text-gray-300"></i>'
                                }
                                <span class="${file.status === 'uploaded' ? 'text-green-700' : file.status === 'error' ? 'text-red-700' : 'text-gray-600'}">${file.path}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
                
                <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mt-4">
                    <div class="flex items-start gap-3">
                        <i data-lucide="info" class="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5"></i>
                        <div class="text-sm text-blue-800">
                            <p>Please keep this window open and do not disconnect your ESP32...</p>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render success state
     */
    renderSuccess() {
        return `
            <div class="p-6">
                <div class="flex items-center gap-3 mb-4">
                    <i data-lucide="check-circle" class="w-6 h-6 text-green-500"></i>
                    <h2 class="text-xl font-bold text-gray-800">Hub Firmware Uploaded Successfully!</h2>
                </div>
                
                <div class="space-y-4">
                    <div class="bg-green-50 border border-green-200 rounded-lg p-4">
                        <div class="flex items-start gap-3">
                            <i data-lucide="thumbs-up" class="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5"></i>
                            <div class="text-sm text-green-800">
                                <p class="font-medium mb-2">All files uploaded successfully!</p>
                                <p>Your ESP32 is now configured as a Simple Hub.</p>
                            </div>
                        </div>
                    </div>
                    
                    <div class="bg-gray-50 border border-gray-200 rounded-lg p-4">
                        <p class="font-medium text-gray-900 mb-3">Ready to activate:</p>
                        <p class="text-sm text-gray-700">Click "Done & Reset" to reboot the device and start the hub firmware.</p>
                    </div>
                    
                    <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
                        <div class="flex items-start gap-3">
                            <i data-lucide="info" class="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5"></i>
                            <div class="text-sm text-blue-800">
                                <p>The hub will respond to commands and communicate with playground modules via ESP-NOW.</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="flex gap-3 mt-6">
                    <button id="done-btn" class="flex-1 px-4 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2">
                        <i data-lucide="zap" class="w-4 h-4"></i>
                        <span>Done & Reset</span>
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Render resetting state while device reboots
     */
    renderResetting() {
        return `
            <div class="p-6">
                <div class="flex items-center gap-3 mb-4">
                    <div class="animate-spin">
                        <i data-lucide="refresh-cw" class="w-6 h-6 text-blue-500"></i>
                    </div>
                    <h2 class="text-xl font-bold text-gray-800">Resetting Device...</h2>
                </div>
                
                <div class="space-y-4">
                    <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
                        <div class="flex items-start gap-3">
                            <i data-lucide="zap" class="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5"></i>
                            <div class="text-sm text-blue-800">
                                <p class="font-medium mb-1">Performing hard reset...</p>
                                <p>The device is rebooting into the new firmware.</p>
                            </div>
                        </div>
                    </div>
                    
                    <div class="text-gray-600 text-sm">
                        <p>This will take just a moment. The hub will automatically start running.</p>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render error state
     */
    renderError() {
        return `
            <div class="p-6">
                <div class="flex items-center gap-3 mb-4">
                    <i data-lucide="alert-circle" class="w-6 h-6 text-red-500"></i>
                    <h2 class="text-xl font-bold text-gray-800">Upload Failed</h2>
                </div>
                
                <div class="space-y-4">
                    <div class="bg-red-50 border border-red-200 rounded-lg p-4">
                        <div class="text-sm text-red-800">
                            <p class="font-medium mb-1">An error occurred during upload:</p>
                            <p class="font-mono text-xs mt-2 bg-red-100 p-2 rounded">${this.errorMessage || 'Unknown error'}</p>
                        </div>
                    </div>
                    
                    <div class="bg-gray-50 border border-gray-200 rounded-lg p-4">
                        <p class="font-medium text-gray-900 mb-2">Common solutions:</p>
                        <ul class="list-disc list-inside space-y-1 text-sm text-gray-700">
                            <li>Check USB cable connection</li>
                            <li>Make sure ESP32 is powered on</li>
                            <li>Try pressing the reset button on your ESP32</li>
                            <li>Close other applications using the serial port (Thonny, Arduino IDE)</li>
                            <li>Try disconnecting and reconnecting</li>
                        </ul>
                    </div>
                </div>
                
                <div class="flex gap-3 mt-6">
                    <button id="cancel-btn" class="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 font-medium transition-colors">
                        Cancel
                    </button>
                    <button id="retry-btn" class="flex-1 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2">
                        <i data-lucide="refresh-cw" class="w-4 h-4"></i>
                        <span>Retry Upload</span>
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Attach event listeners to buttons
     */
    attachEventListeners() {
        const cancelBtn = this.modal.querySelector('#cancel-btn');
        const startBtn = this.modal.querySelector('#start-upload-btn');
        const retryBtn = this.modal.querySelector('#retry-btn');
        const doneBtn = this.modal.querySelector('#done-btn');
        const antennaCheckbox = this.modal.querySelector('#externalAntennaCheckbox');

        if (cancelBtn) {
            cancelBtn.onclick = () => this.hide();
        }

        if (startBtn) {
            startBtn.onclick = () => {
                // Capture antenna checkbox state before starting upload
                // C3 devices: antenna flag causes crashes, so always set to false
                // C6 devices: use checkbox value
                // Other devices: default to false
                if (this.deviceType === 'C3') {
                    this.hasExternalAntenna = false;
                    console.log('C3 device: external antenna disabled (causes crashes)');
                } else if (antennaCheckbox) {
                    this.hasExternalAntenna = antennaCheckbox.checked;
                    console.log(`External antenna: ${this.hasExternalAntenna}`);
                } else {
                    this.hasExternalAntenna = false;
                }
                this.startUpload();
            };
        }

        if (retryBtn) {
            retryBtn.onclick = async () => {
                // Reset state and query device again
                this.state = 'loading';
                this.deviceInfo = null;
                this.deviceType = null;
                this.render();
                await this.queryDeviceInfo();
            };
        }

        if (doneBtn) {
            doneBtn.onclick = async () => {
                try {
                    console.log('🔄 Performing hard reset to boot into new firmware...');
                    
                    // Show resetting state
                    this.state = 'resetting';
                    this.render();
                    
                    // Perform hard reset (executes machine.reset() on device)
                    const result = await PyBridge.hardResetDevice();
                    
                    if (result.status === 'success') {
                        console.log('✅ Device reset successful, now running main.py');
                    } else {
                        console.warn('⚠️ Reset completed but with warning:', result.error);
                    }
                    
                    // Close modal after brief delay
                    setTimeout(() => this.hide(), 500);
                    
                } catch (error) {
                    console.error('❌ Reset error:', error);
                    // Close anyway - device may have reset despite error
                    setTimeout(() => this.hide(), 500);
                }
            };
        }
    }

    /**
     * Start the upload process
     */
    async startUpload() {
        try {
            // Change to uploading state
            this.state = 'uploading';
            this.render();

            // Check if Python serial is connected
            // Python's WebSerial needs an active connection for upload
            console.log('Checking Python serial connection status...');
            const connectionStatus = await PyBridge.getConnectionStatus();
            
            if (!connectionStatus.connected || connectionStatus.mode !== 'serial') {
                // Not connected via serial - need to connect first
                console.log('Python serial not connected - connecting now...');
                
                // Connect via Python (this will prompt user for port selection)
                const connectResult = await PyBridge.connectHubSerial();
                
                if (connectResult.status !== 'success') {
                    throw new Error('Failed to connect to serial port: ' + (connectResult.error || 'Unknown error'));
                }
                
                console.log('Connected to serial port via Python');
                
                // Give it a moment to stabilize
                await new Promise(resolve => setTimeout(resolve, 500));
            } else {
                console.log('Python serial already connected, using existing connection');
            }

            // Load all hub files
            console.log('Loading hub files...');
            const files = await loadHubFiles();
            
            // Modify main.py based on antenna and display configuration
            const mainPyFile = files.find(f => f.path === 'main.py');
            if (mainPyFile) {
                // Antenna configuration
                console.log(`Configuring antenna: external=${this.hasExternalAntenna}`);
                if (!this.hasExternalAntenna) {
                    // Remove the antenna configuration line
                    mainPyFile.content = mainPyFile.content.replace(
                        /\s*# Add C6 external antenna configuration\s*\n\s*self\.n\.antenna\(\)\s*\n/,
                        '\n'
                    );
                    console.log('Removed external antenna configuration from main.py');
                } else {
                    console.log('Keeping external antenna configuration in main.py');
                }
                
                // Display I2C pin configuration
                console.log(`Configuring display for device type: ${this.deviceType}`);
                const beforeReplace = mainPyFile.content.includes('__DISPLAY_CONFIG_C6__');
                console.log(`Before replace: contains display config markers: ${beforeReplace}`);
                
                if (this.deviceType === 'C3') {
                    // Use C3 pins: SoftI2C on pins 7 (SCL), 6 (SDA)
                    const newContent = mainPyFile.content.replace(
                        /i2c = I2C\(scl=Pin\(23\), sda=Pin\(22\)\)  # __DISPLAY_CONFIG_C6__\s*\n\s*# i2c = SoftI2C\(scl=Pin\(7\), sda=Pin\(6\)\)  # __DISPLAY_CONFIG_C3__/,
                        '# i2c = I2C(scl=Pin(23), sda=Pin(22))  # __DISPLAY_CONFIG_C6__\n            i2c = SoftI2C(scl=Pin(7), sda=Pin(6))  # __DISPLAY_CONFIG_C3__'
                    );
                    const didReplace = newContent !== mainPyFile.content;
                    console.log(`Display config replacement ${didReplace ? 'SUCCEEDED' : 'FAILED'}`);
                    mainPyFile.content = newContent;
                    console.log('Configured display for C3: SoftI2C on pins 7 (SCL), 6 (SDA)');
                } else {
                    // Use C6/default pins: I2C on pins 23 (SCL), 22 (SDA)
                    console.log('Configured display for C6: I2C on pins 23 (SCL), 22 (SDA)');
                }
            }
            
            // Initialize progress tracking
            this.uploadProgress = {
                current: 0,
                total: files.length,
                currentFile: '',
                files: files.map(f => ({ path: f.path, status: 'pending' }))
            };
            this.render();

            // Set up progress callback for Python to call
            window.onUploadProgress = (progress) => {
                    this.uploadProgress.current = progress.current;
                this.uploadProgress.currentFile = progress.file;
                
                // Update file status
                    const fileIndex = this.uploadProgress.files.findIndex(f => f.path === progress.file);
                    if (fileIndex >= 0) {
                        this.uploadProgress.files[fileIndex].status = progress.status;
                    }
                
                this.render();
            };

            // Call Python upload function (handles REPL mode internally)
            console.log('Starting Python upload...');
            const result = await PyBridge.uploadFirmware(files);

            // Clean up progress callback
            delete window.onUploadProgress;

            // Check result
            if (result.status === 'success') {
                console.log(`✅ Upload successful: ${result.files_uploaded} files`);
            this.state = 'success';
            this.render();
            } else {
                throw new Error(result.error || 'Upload failed');
            }

        } catch (error) {
            console.error('Upload error:', error);
            this.errorMessage = error.message || 'Unknown error occurred';
            this.state = 'error';
            this.render();

            // Clean up progress callback
            if (window.onUploadProgress) {
                delete window.onUploadProgress;
            }
        }
    }
}

export default HubSetupModal;

