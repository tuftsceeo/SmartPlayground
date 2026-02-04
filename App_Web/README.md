# App_Web - Smart Playground Web Application

This directory contains the web application interface for controlling Smart Playground modules via ESP32 hub.

## Contents

```
App_Web/
├── webapp/              # Main web application
│   ├── index.html       # Entry point
│   ├── main.py          # PyScript backend
│   ├── js/              # JavaScript components and utilities
│   ├── mpy/             # Python modules for hub communication
│   ├── hubCode/         # ESP32 hub firmware files
│   └── README.md        # Detailed documentation
└── visual_design/       # Design specifications and prototypes
```

## Live Demo

The **main branch** webapp is automatically deployed to GitHub Pages via GitHub Actions:

🌐 **https://tuftsceeo.github.io/SmartPlayground/**

The deployment workflow (`.github/workflows/static.yml`) automatically publishes the `webapp/` directory whenever changes are pushed to the main branch.

## Local Development & Testing

For development branches or local testing, you can run the application locally:

### Prerequisites

- Python 3.x installed
- Chrome or Edge browser (Web Serial API support required)
- ESP32-C6 or ESP32-C3 to flash as hub


### Running Locally

1. **Navigate to the webapp directory:**
   ```bash
   cd App_Web/webapp
   ```

2. **Start a local HTTP server:**
   ```bash
   python3 -m http.server 8000
   ```

   Or on some systems:
   ```bash
   python -m http.server 8000
   ```

3. **Open in browser:**
   ```
   http://localhost:8000
   ```

4. **Test the application:**
   - UI components will load without hardware
   - Connect ESP32 hub via USB to test full functionality
   - Check browser console for any errors

### Alternative: Using Node.js

If you prefer Node.js, you can use `http-server`:

```bash
# Install globally (once)
npm install -g http-server

# Run server
cd App_Web/webapp
http-server -p 8000
```

## Browser Requirements

**Supported Browsers:**
- Chrome 89+ ✅
- Edge 89+ ✅
- Opera 75+ ✅

**Not Supported:**
- Safari ❌ (no Web Serial API)
- Firefox ❌ (no Web Serial API)
- Mobile browsers ❌ (Web Serial API not available)

## Key Features

- **USB Serial Connection** to ESP32-C6 hub
- **Command Broadcasting** to playground modules via ESP-NOW
- **Firmware Upload** capability from browser
- **Mobile-First Design** with PWA support
- **PyScript Backend** (Python running in browser)

## Documentation

For detailed documentation, including:
- Architecture overview
- API references
- Development guides
- Troubleshooting

See: **[webapp/README.md](webapp/README.md)**

## Design Resources

The `visual_design/` directory contains:
- Color palette guides
- Bluetooth feature specifications
- UI/UX design prototypes

## Project Info

**Team:** Smart Playground Project at Tufts CEEO  
**Funding:** NSF Award #2301249  
**Contributors:** J. Cross (front-end/backend), C. Rogers & M. Dahal (hub utilities)

## Quick Start

1. **Test the live demo:** Visit https://tuftsceeo.github.io/SmartPlayground/
2. **For development:** Clone repo → `cd App_Web/webapp` → `python3 -m http.server 8000` → Open `http://localhost:8000`
3. **Connect hardware:** Click "Connect USB Hub" and select your ESP32 device
4. **Send commands:** Use the chat interface to control playground modules

## Support

For issues or questions:
1. Check the detailed [webapp README](webapp/README.md)
2. Review browser console for errors
3. Verify hardware connections and firmware versions
