# Smart Playground Control - Frontend

This is the frontend application for the Smart Playground Control system, built with PyScript and vanilla JavaScript.

## Quick Start

### 1. Start the Development Server

Open a terminal/command prompt and navigate to the frontend directory:

```bash
cd frontend
python -m http.server 8000
```

### 2. Open in Browser

Open your browser and go to: `http://localhost:8000`

### 3. Clear Cache if Needed

If you're seeing old code or errors, clear your browser cache:

-   **Hard Refresh**: Press `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (Mac)
-   **Or**: Press `F12` to open DevTools, then right-click the refresh button and select "Empty Cache and Hard Reload"
-   **Or**: Use Incognito/Private mode to test without any cache

## Development Tips

### Browser Cache Issues

When developing, you might encounter caching issues where changes don't appear. To fix this:

1. **Hard refresh** the page (`Ctrl+Shift+R`)
2. **Clear browser cache** completely
3. **Use Incognito mode** for testing
4. **Check DevTools Console** for any JavaScript errors

### Stopping the Server

To stop the Python server:

-   Press `Ctrl+C` in the terminal
-   If that doesn't work, close the terminal window
-   Or find the Python process and kill it manually

### File Structure

```
frontend/
├── index.html          # Main HTML file
├── main.py            # Python backend (PyScript)
├── pyscript.toml      # PyScript configuration
├── manifest.json      # PWA manifest
├── js/
│   ├── main.js        # Main application logic
│   ├── state/
│   │   └── store.js   # State management
│   ├── utils/
│   │   ├── constants.js
│   │   ├── helpers.js
│   │   └── pyBridge.js
│   └── components/
│       ├── icons.js
│       ├── recipientBar.js
│       ├── messageHistory.js
│       ├── messageInput.js
│       ├── deviceListOverlay.js
│       ├── messageDetailsOverlay.js
│       └── hubConnectionBar.js
└── mpy/
    └── webBluetooth.py # BLE communication module
```

## Features

-   **BLE Hub Connection**: Connect to ESP32 hub via Bluetooth
-   **Device Management**: View and manage connected modules
-   **Command Sending**: Send commands to selected devices
-   **Message History**: Track sent commands and responses
-   **Real-time Updates**: Live device status and connection monitoring

## Troubleshooting

### Common Issues

1. **White Screen**: Check browser console for JavaScript errors
2. **Python Backend Not Loading**: Ensure PyScript is properly configured
3. **BLE Not Working**: Make sure you're using Chrome/Edge with HTTPS or localhost
4. **Caching Issues**: Use hard refresh or incognito mode

### Debug Mode

Open browser DevTools (`F12`) and check the Console tab for detailed logging and error messages.

## Requirements

-   **Browser**: Chrome, Edge, or Firefox (Web Bluetooth API support)
-   **Python**: 3.7+ for development server
-   **HTTPS or localhost**: Required for Web Bluetooth API

## Production Deployment

For production deployment, you'll need to:

1. Serve files over HTTPS (required for Web Bluetooth)
2. Configure proper CORS headers
3. Set up proper caching strategies
4. Test BLE functionality in production environment
