# Smart Playground Control - Demo Mode

This is the **demo version** of the Smart Playground Control application. It provides a complete demonstration of the app's functionality without requiring any Bluetooth hardware.

## 🎮 Demo Mode Features

- **No Bluetooth Required**: Works entirely with simulated data
- **Full Functionality**: All features work exactly like the real app
- **Realistic Simulation**: Mock devices with varying signal strengths and battery levels
- **Visual Indicators**: Clear "Demonstration" status instead of "Connected"
- **Demo Banner**: Blue banner at top clearly indicates demo mode

## 🚀 How to Use

1. **Open the App**: Simply open `index.html` in any modern web browser
2. **No Setup Required**: No Bluetooth pairing or hardware needed
3. **Full Experience**: 
   - View simulated playground modules
   - Adjust range slider to filter devices
   - Send commands to simulated devices
   - See realistic responses and animations

## 🔧 Technical Details

### What's Different from Production Version

- **Python Backend**: Uses `main.py` with demo mode simulation instead of BLE connections
- **JavaScript State**: Always shows as "connected" with "Demo Hub"
- **Device Data**: Uses pre-configured mock devices with realistic properties
- **Command Simulation**: All commands are simulated with realistic delays
- **No BLE Dependencies**: Completely removes Web Bluetooth API requirements

### Mock Devices Included

- **M-A3F821**: Module with strong signal (3 bars)
- **M-B4C932**: Module with good signal (3 bars) 
- **M-C5D043**: Module with medium signal (2 bars)
- **E-D6E154**: Extension with good signal (2 bars)
- **E-E7F265**: Extension with weak signal (1 bar)
- **B-F8G376**: Button with weak signal (1 bar)

### Simulated Features

- **Signal Strength**: Varies realistically based on RSSI values
- **Battery Levels**: Different battery states (full, high, medium, low)
- **Command Responses**: Simulated delays and status updates
- **Device Discovery**: Realistic device scanning simulation

## 🎯 Use Cases

- **Demonstrations**: Perfect for showing the app to stakeholders
- **Testing**: UI/UX testing without hardware dependencies
- **Development**: Frontend development without BLE setup
- **Training**: User training without risk of real device interference
- **Presentations**: Clean demo environment for presentations

## 🔄 Switching to Production

To use the real app with actual Bluetooth hardware:

1. Use the files in the main `app/` directory (not `app_mock_data/`)
2. Ensure you have Bluetooth-enabled devices
3. Follow the production setup instructions in the main README

## 📱 Browser Compatibility

- **Chrome/Edge**: Full compatibility
- **Firefox**: Full compatibility  
- **Safari**: Full compatibility
- **Mobile Browsers**: Full compatibility

No special browser features or permissions required for demo mode.

## 🎨 Visual Indicators

- **Blue Banner**: "🎮 DEMO MODE - No Bluetooth Required" at top of screen
- **Status Text**: Shows "Demonstration" instead of "Connected"
- **Hub Name**: Displays as "Demo: Demo Hub"
- **Page Title**: "Smart Playground Control - Demo Mode"

This ensures users always know they're in demo mode and won't be confused about connection status.
