/**
 * ⚠️ DEPRECATED - NOT USED ⚠️
 * 
 * This file is no longer used. The hub only supports USB Serial connection.
 * Bluetooth/BLE was never successfully implemented.
 * 
 * This file is kept for historical reference only.
 * 
 * For actual hub communication, see:
 * - js/adapters/serialAdapter.js (USB Serial communication)
 * - mpy/hub_serial.py (Python serial wrapper)
 */

console.warn('⚠️ bluetoothAdapter.js is deprecated and should not be loaded');

// Empty exports to prevent import errors
export const BluetoothAdapter = {};
