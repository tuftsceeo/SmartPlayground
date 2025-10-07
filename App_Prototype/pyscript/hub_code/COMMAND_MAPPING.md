# Command Mapping Reference

**Updated:** October 7, 2025  
**Status:** Production Ready

## Overview

This document maps the complete command flow from the web app UI buttons through to the ESP-NOW messages sent to playground modules.

## Command Flow Chain

```
User clicks button in web app
    ↓
JavaScript sends command.label
    ↓
BLE transmission: "CommandLabel":"rssiThreshold"
    ↓
ESP32 Hub receives and parses
    ↓
Maps to ESP-NOW protocol command
    ↓
Broadcasts to modules: {"espnowCmd": {"RSSI": -60, "value": 0}}
```

## Complete Command Mapping Table

| Web App Button | Command Label | ESP-NOW Command | Game Value | Module Action |
|---------------|---------------|-----------------|------------|---------------|
| 🎮 Play | `"Play"` | `updateGame` | 0 | Start generic game |
| ⏸️ Pause | `"Pause"` | `lightOff` | 0 | Turn off/pause display |
| 🏆 Win | `"Win"` | `rainbow` | 0 | Show winning animation |
| 🎨 Color Game | `"Color Game"` | `updateGame` | 1 | Start color-based grouping |
| #️⃣ Number Game | `"Number Game"` | `updateGame` | 2 | Start number-based grouping |
| 🔴 Off | `"Off"` | `deepSleep` | 0 | Enter deep sleep mode |

## Web App Command Definitions

From `app/js/utils/constants.js`:

```javascript
export const COMMANDS = [
    { id: "play", label: "Play", bgColor: "#7eb09b", icon: "play" },
    { id: "pause", label: "Pause", bgColor: "#d4a574", icon: "pause" },
    { id: "win", label: "Win", bgColor: "#b084cc", icon: "trophy" },
    { id: "color_game", label: "Color Game", bgColor: "#658ea9", icon: "palette" },
    { id: "number_game", label: "Number Game", bgColor: "#d7a449", icon: "hash" },
    { id: "off", label: "Off", bgColor: "#e98973", icon: "poweroff" },
];
```

**Important:** The web app sends **`command.label`** (e.g., "Win"), not `command.id` (e.g., "win")!

## BLE Transmission Format

When user clicks a button, the web app sends via BLE:

```
Format: "CommandLabel":"rssiThreshold"

Examples:
  "Win":"all"           → Send to all devices
  "Pause":"-60"         → Send to devices >= -60 dBm
  "Color Game":"-40"    → Send color game to close devices
```

## ESP32 Hub Command Mapping

From `hub_code/esp_hub_new_main.py`:

```python
COMMAND_MAP = {
    # Main commands from web app
    "Play": "updateGame",           # Start game
    "Pause": "lightOff",             # Pause modules
    "Win": "rainbow",                # Winning animation
    "Color Game": "updateGame",      # Color game (value: 1)
    "Number Game": "updateGame",     # Number game (value: 2)
    "Off": "deepSleep",              # Deep sleep
    
    # Legacy commands (backwards compatibility)
    "BATTERY CHECK": "batteryCheck",
    "RAINBOW": "rainbow",
    "TURN OFF": "lightOff",
}

GAME_VALUES = {
    "Play": 0,              # Generic play
    "Color Game": 1,        # Color-based grouping
    "Number Game": 2,       # Number-based grouping
}
```

## ESP-NOW Protocol Messages

After mapping, hub sends to modules:

### Win Command
```python
# User clicks "Win" with range slider at "Close" (-60)
# BLE receives: "Win":"-60"
# Hub sends ESP-NOW:
{
    "rainbow": {
        "RSSI": -60,
        "value": 0
    }
}
```

### Pause Command
```python
# User clicks "Pause" with range slider at "All"
# BLE receives: "Pause":"all"
# Hub sends ESP-NOW:
{
    "lightOff": {
        "RSSI": -90,
        "value": 0
    }
}
```

### Color Game Command
```python
# User clicks "Color Game" with range slider at "Near"
# BLE receives: "Color Game":"-40"
# Hub sends ESP-NOW:
{
    "updateGame": {
        "RSSI": -40,
        "value": 1
    }
}
```

### Number Game Command
```python
# User clicks "Number Game" with range slider at "Medium"
# BLE receives: "Number Game":"-70"
# Hub sends ESP-NOW:
{
    "updateGame": {
        "RSSI": -70,
        "value": 2
    }
}
```

### Play Command
```python
# User clicks "Play" with range slider at "Far"
# BLE receives: "Play":"-85"
# Hub sends ESP-NOW:
{
    "updateGame": {
        "RSSI": -85,
        "value": 0
    }
}
```

### Off Command
```python
# User clicks "Off" with range slider at "All"
# BLE receives: "Off":"all"
# Hub sends ESP-NOW:
{
    "deepSleep": {
        "RSSI": -90,
        "value": 0
    }
}
```

## Legacy Command Support

For backwards compatibility, the hub also accepts these commands:

| Legacy Command | Mapped To | Notes |
|---------------|-----------|-------|
| `"BATTERY CHECK"` | `batteryCheck` | From old protocol |
| `"RAINBOW"` | `rainbow` | Same as "Win" |
| `"TURN OFF"` | `lightOff` | Same as "Pause" |

## Module Implementation

### Receiving Commands

Modules should implement handlers for these ESP-NOW commands:

```python
def process_command(msg):
    try:
        cmd_dict = eval(msg.decode())
        
        # Check each command type
        if "updateGame" in cmd_dict:
            rssi = cmd_dict["updateGame"]["RSSI"]
            game_num = cmd_dict["updateGame"]["value"]
            if check_rssi(rssi):
                start_game(game_num)
        
        elif "rainbow" in cmd_dict:
            rssi = cmd_dict["rainbow"]["RSSI"]
            if check_rssi(rssi):
                show_rainbow_animation()
        
        elif "lightOff" in cmd_dict:
            rssi = cmd_dict["lightOff"]["RSSI"]
            if check_rssi(rssi):
                turn_off_display()
        
        elif "deepSleep" in cmd_dict:
            rssi = cmd_dict["deepSleep"]["RSSI"]
            if check_rssi(rssi):
                enter_deep_sleep()
        
        elif "batteryCheck" in cmd_dict:
            rssi = cmd_dict["batteryCheck"]["RSSI"]
            if check_rssi(rssi):
                display_battery_level()
                
    except Exception as e:
        print(f"Command parse error: {e}")
```

### Game Number Meanings

When receiving `updateGame` command:

- **value: 0** → Generic play/start (default behavior)
- **value: 1** → Color-based grouping game
- **value: 2** → Number-based grouping game
- **value: 3-9** → Reserved for future games

Example game implementation:

```python
def start_game(game_num):
    if game_num == 0:
        # Generic play mode
        start_default_game()
    elif game_num == 1:
        # Color-based grouping
        assign_random_color()
        display_color()
    elif game_num == 2:
        # Number-based grouping
        assign_random_number()
        display_number()
    else:
        print(f"Unknown game: {game_num}")
```

## Testing Commands

### Expected Hub Console Output

```
BLE command received: '"Win":"-60"'
Parsed: command='Win', threshold='-60'
Processing command: Win
ESP-NOW: Sending 'Win' -> {'rainbow': {'RSSI': -60, 'value': 0}}
  Target RSSI: -60 dBm (modules stronger than this will respond)
ESP-NOW: Transmission successful
✓ Command 'Win' sent successfully
Sent acknowledgment to web app
```

### Expected Module Behavior

1. **Play**: Module starts default game animation
2. **Pause**: Module turns off display/LEDs
3. **Win**: Module shows rainbow animation
4. **Color Game**: Module displays assigned color
5. **Number Game**: Module displays assigned number
6. **Off**: Module enters deep sleep mode

## Troubleshooting

### "Unknown command" errors

If you see this in hub console:
```
Unknown command: Win
```

**Cause:** Command mapping not updated on hub  
**Solution:** Re-upload `esp_hub_new_main.py` with updated `COMMAND_MAP`

### Commands not reaching modules

**Check:**
1. Hub console shows "ESP-NOW: Transmission successful"
2. Modules are on same WiFi channel as hub
3. Modules have ESP-NOW receiver active
4. Module RSSI >= threshold value

### Wrong game starting

**Check:**
1. GAME_VALUES mapping in hub code
2. Module's game_num handler implementation
3. Hub console shows correct "value" in ESP-NOW message

## Summary

✅ **Web App → Hub:** Sends command labels via BLE  
✅ **Hub Translation:** Maps labels to ESP-NOW protocol  
✅ **Hub → Modules:** Broadcasts ESP-NOW commands  
✅ **Module Processing:** Checks RSSI and executes command  
✅ **All Commands Mapped:** 6 main commands + 3 legacy

The complete command chain is now properly mapped and documented!

