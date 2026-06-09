/**
 * Hub Setup Modal
 *
 * Upload hub firmware to ESP32 via serial. Queries device info, confirmation, then upload with progress.
 */

import { loadHubFiles } from '../../../hubCode2/manifest.js';
import { PyBridge } from '../../utils/pyBridge.js';
import { setState, state } from '../../state/store.js';

export class HubSetupModal {
    constructor() {
        this.modal = null;
        this.state = 'loading';
        this.hasExternalAntenna = false;
        this.deviceInfo = null;
        this.deviceType = null;
        this.uploadProgress = {
            current: 0,
            total: 0,
            currentFile: '',
            files: []
        };
    }

    async show(serialPort) {
        this.serialPort = serialPort;
        
        setState({ hubValidationEnabled: false });
        if (window.clearHubValidationTimeout) {
            window.clearHubValidationTimeout();
        }
        
        this.createModal();
        this.render();
        document.body.appendChild(this.modal);
        
        if (window.lucide) {
            window.lucide.createIcons();
        }
        
        await this.queryDeviceInfo();
    }

    async hide(keepConnection = false) {
        console.log('✅ Re-enabling hub validation');
        
        if (keepConnection) {
            console.log('✅ Marking device as validated hub (just uploaded firmware)');
            setState({ 
                hubValidationEnabled: true,
                hubValidated: true
            });
        } else {
            setState({ hubValidationEnabled: true });
        }
        
        if (!keepConnection && (this.state === 'error' || this.state === 'loading' || this.state === 'initial')) {
            console.log('🔌 Disconnecting serial connection (upload did not complete successfully)...');
            try {
                await PyBridge.disconnectHubSerial();
                console.log('✅ Disconnected serial connection');
            } catch (error) {
                console.warn('⚠️ Error during disconnect:', error);
            }
        }
        
        if (this.modal && this.modal.parentNode) {
            this.modal.parentNode.removeChild(this.modal);
        }
        this.modal = null;
    }

    createModal() {
        this.modal = document.createElement('div');
        this.modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
        this.modal.onclick = (e) => {
            if (e.target === this.modal && this.state !== 'uploading') {
                this.hide();
            }
        };
    }

    async queryDeviceInfo() {
        try {
            console.log('🔍 Querying device info...');
            
            const connectionStatus = await PyBridge.getConnectionStatus();
            
            if (!connectionStatus.connected || connectionStatus.mode !== 'serial') {
                console.log('🔌 Connecting to serial port...');
                const connectResult = await PyBridge.connectHubSerial();
                
                if (connectResult.status !== 'success') {
                    throw new Error('Failed to connect: ' + (connectResult.error || 'Unknown error'));
                }
                
                console.log('⏸️ Waiting for connection to stabilize...');
                await new Promise(resolve => setTimeout(resolve, 500));
            }
            
            console.log('🛑 Stopping JSON read loop...');
            const stopResult = await PyBridge.queryDeviceInfoForSetup();
            
            if (stopResult.status === 'error') {
                throw new Error(stopResult.error || 'Failed to stop read loop');
            }
            
            console.log('⏸️ Waiting for read loop to stop...');
            await new Promise(resolve => setTimeout(resolve, 300));
            
            console.log('📡 Getting device information...');
            const infoResult = await PyBridge.getDeviceBoardInfo();
            
            if (infoResult.status === 'success') {
                this.deviceInfo = infoResult.info;
                this.deviceType = this.parseDeviceType(infoResult.info);
                console.log(`✅ Device detected: ${this.deviceType}`);
                
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

        this.attachEventListeners();
        
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

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

    renderInitial() {
        const showAntennaOption = this.deviceType === 'C6';
        
        // C3: external antenna always on
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
                            <li>Close other applications using the serial port (Thonny, Arduino IDE)</li>
                            <li>Try disconnecting and reconnecting USB</li>
                        </ul>
                    </div>
                </div>
                
                <div class="flex gap-3 mt-6">
                    <button id="cancel-btn" class="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 font-medium transition-colors">
                        Cancel
                    </button>
                    <button id="reset-retry-btn" class="flex-1 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2">
                        <i data-lucide="refresh-cw" class="w-4 h-4"></i>
                        <span>Retry</span>
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
        const resetRetryBtn = this.modal.querySelector('#reset-retry-btn');
        const doneBtn = this.modal.querySelector('#done-btn');
        const antennaCheckbox = this.modal.querySelector('#externalAntennaCheckbox');

        if (cancelBtn) {
            cancelBtn.onclick = () => this.hide();
        }

        if (startBtn) {
            startBtn.onclick = () => {
                // C3: antenna=false to avoid crashes; C6: use checkbox
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

        if (resetRetryBtn) {
            resetRetryBtn.onclick = async () => {
                try {
                    console.log('🔄 Performing hard reset before retry...');
                    
                    // Show loading state
                    this.state = 'loading';
                    this.deviceInfo = null;
                    this.deviceType = null;
                    this.render();
                    
                    // Perform hard reset (like the one that works well in error modal)
                    const resetResult = await PyBridge.hardResetDevice();
                    
                    if (resetResult.status === 'success') {
                        console.log('✅ Device reset successful');
                    } else {
                        console.warn('⚠️ Reset completed with warning:', resetResult.error);
                    }
                    
                    // Wait for device to reboot
                    console.log('⏸️ Waiting for device to boot...');
                    await new Promise(resolve => setTimeout(resolve, 2000));
                    
                    // Now retry query
                    console.log('🔍 Retrying device query after reset...');
                    await this.queryDeviceInfo();
                    
                } catch (error) {
                    console.error('❌ Reset & retry error:', error);
                    this.errorMessage = 'Reset failed: ' + (error.message || 'Unknown error');
                    this.state = 'error';
                    this.render();
                }
            };
        }

        if (doneBtn) {
            doneBtn.onclick = async () => {
                try {
                    console.log('🔄 Performing hard reset to boot into new firmware...');
                    
                    this.state = 'resetting';
                    this.render();
                    
                    const result = await PyBridge.hardResetDevice();
                    
                    if (result.status === 'success') {
                        console.log('✅ Device reset successful, now running main.py');
                    } else {
                        console.warn('⚠️ Reset completed but with warning:', result.error);
                    }
                    
                    setTimeout(() => this.hide(true), 500);
                    
                } catch (error) {
                    console.error('❌ Reset error:', error);
                    setTimeout(() => this.hide(true), 500);
                }
            };
        }
    }

    /**
     * Start the upload process
     */
    async startUpload() {
        try {
            this.state = 'uploading';
            this.render();

            console.log('Checking Python serial connection status...');
            const connectionStatus = await PyBridge.getConnectionStatus();
            
            if (!connectionStatus.connected || connectionStatus.mode !== 'serial') {
                console.log('Python serial not connected - connecting now...');
                
                const connectResult = await PyBridge.connectHubSerial();
                
                if (connectResult.status !== 'success') {
                    throw new Error('Failed to connect to serial port: ' + (connectResult.error || 'Unknown error'));
                }
                
                console.log('Connected to serial port via Python');
                
                await new Promise(resolve => setTimeout(resolve, 500));
            } else {
                console.log('Python serial already connected, using existing connection');
            }

            console.log('Loading hub files...');
            const files = await loadHubFiles();
            
            const mainPyFile = files.find(f => f.path === 'main.py');
            if (mainPyFile) {
                console.log(`Configuring antenna: external=${this.hasExternalAntenna}`);
                if (!this.hasExternalAntenna) {
                    mainPyFile.content = mainPyFile.content.replace(
                        /(# __ANTENNA_CONFIG_START__\s*\n\s*antenna_enabled = )True(\s*# C6 external antenna \(set to False for internal\)\s*\n\s*# __ANTENNA_CONFIG_END__)/,
                        '$1False$2'
                    );
                    console.log('Configured for internal antenna (antenna_enabled = False)');
                } else {
                    console.log('Configured for external antenna (antenna_enabled = True)');
                }
                
                console.log(`Configuring display for device type: ${this.deviceType}`);
                const beforeReplace = mainPyFile.content.includes('__DISPLAY_CONFIG_C6__');
                console.log(`Before replace: contains display config markers: ${beforeReplace}`);
                
                if (this.deviceType === 'C3') {
                    const newContent = mainPyFile.content.replace(
                        /i2c = I2C\(scl=Pin\(23\), sda=Pin\(22\)\)  # __DISPLAY_CONFIG_C6__\s*\n\s*# i2c = SoftI2C\(scl=Pin\(7\), sda=Pin\(6\)\)  # __DISPLAY_CONFIG_C3__/,
                        '# i2c = I2C(scl=Pin(23), sda=Pin(22))  # __DISPLAY_CONFIG_C6__\n            i2c = SoftI2C(scl=Pin(7), sda=Pin(6))  # __DISPLAY_CONFIG_C3__'
                    );
                    const didReplace = newContent !== mainPyFile.content;
                    console.log(`Display config replacement ${didReplace ? 'SUCCEEDED' : 'FAILED'}`);
                    mainPyFile.content = newContent;
                    console.log('Configured display for C3: SoftI2C on pins 7 (SCL), 6 (SDA)');
                } else {
                    console.log('Configured display for C6: I2C on pins 23 (SCL), 22 (SDA)');
                }
            }
            
            this.uploadProgress = {
                current: 0,
                total: files.length,
                currentFile: '',
                files: files.map(f => ({ path: f.path, status: 'pending' }))
            };
            this.render();

            window.onUploadProgress = (progress) => {
                    this.uploadProgress.current = progress.current;
                this.uploadProgress.currentFile = progress.file;
                
                    const fileIndex = this.uploadProgress.files.findIndex(f => f.path === progress.file);
                    if (fileIndex >= 0) {
                        this.uploadProgress.files[fileIndex].status = progress.status;
                    }
                
                this.render();
            };

            console.log('Starting Python upload...');
            const result = await PyBridge.uploadFirmware(files);

            delete window.onUploadProgress;

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

            if (window.onUploadProgress) {
                delete window.onUploadProgress;
            }
        }
    }
}

export default HubSetupModal;

