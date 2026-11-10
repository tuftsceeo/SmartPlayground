/**
 * manifest.js — Bag3 wand (Mock Wand) file list for tools/deploy.py --type wand.
 * Same shape as the Box/Dial manifest.js. Only what is listed here ships.
 *
 * Not shipped (tests / bench only): games/lobbytest.py, games/relaycolor.py,
 * games/splattag.py, goalrace.py, splatecho.py, jumpin.py, import_bench.py,
 * utilities/. Add a new example game here or it will not reach the wands.
 * main.py is compiled by deploy.py to /wand_main.mpy plus a stub /main.py.
 */

export const WAND_FILES = [
    { path: 'boot.py', remotePath: '/boot.py' },  // Sets the first NeoPixel dim white at power-on, before main runs
    { path: 'main.py', remotePath: '/main.py' },  // NFC multi-trigger event engine: boot, radio, tag dispatch, game loader
    { path: 'hubtype.txt', remotePath: '/hubtype.txt' },  // Device identity ("wand") read by lib/hubtype.py
    // Hidden: targeted identify animation (device-list ping)
    { path: 'finddevice.py', remotePath: '/finddevice.py' },  // Hidden identify animation when a teacher pings this wand from a device list
    // Example games
    { path: 'color_quest.py', remotePath: '/color_quest.py' },  // Color Quest: tap NFC tags matching a color sequence sent over ESP-NOW
    { path: 'cooking.py', remotePath: '/cooking.py' },  // Cooking Recipes: tap ingredient tags to collect a recipe
    { path: 'freeze_dance.py', remotePath: '/freeze_dance.py' },  // Freeze Dance: multiplayer GO / FREEZE / DANCE motion game over ESP-NOW
    { path: 'gestures.py', remotePath: '/gestures.py' },  // Gestures: train and classify wand motions
    { path: 'jump.py', remotePath: '/jump.py' },  // Jump Counter: each freefall jump lights one more LED
    { path: 'melody.py', remotePath: '/melody.py' },  // Melody Builder: scan note tags to record and play a melody
    { path: 'multiicecream.py', remotePath: '/multiicecream.py' },  // Multi Ice Cream: build up to three scoops by button count and flips
    { path: 'nfc_sound.py', remotePath: '/nfc_sound.py' },  // NFC Bell Choir: tap a note tag, hold the button to ring it
    { path: 'rainbow.py', remotePath: '/rainbow.py' },  // Rainbow Show: battery level, then a static rainbow
    { path: 'shake.py', remotePath: '/shake.py' },  // Shake Fill: shake harder to light more LEDs
    { path: 'shake_rainbow.py', remotePath: '/shake_rainbow.py' },  // Shake Rainbow: shake to climb through rainbow colors
    { path: 'simpleicecream.py', remotePath: '/simpleicecream.py' },  // Simple Ice Cream: count scoops with the button while upright
    { path: 'sound.py', remotePath: '/sound.py' },  // Bell Choir: random note per wand, hold the button to ring it
    { path: 'target.py', remotePath: '/target.py' },  // Stores the MAC of the scoreboard/hub that receives this wand's ESP-NOW results
    // lib (espnow_code + game_store = Box/Dial game pull)
    { path: 'lib/actions.py', remotePath: '/lib/actions.py' },  // Action definitions, resource mapping and action-chain execution
    { path: 'lib/battery.py', remotePath: '/lib/battery.py' },  // Shows battery level on the LEDs
    { path: 'lib/ble_splat.py', remotePath: '/lib/ble_splat.py' },  // BLE driver for Open Splat devices
    { path: 'lib/brightness.py', remotePath: '/lib/brightness.py' },  // System-wide LED brightness scaled from the ambient light sensor
    { path: 'lib/buzzer.py', remotePath: '/lib/buzzer.py' },  // PWM piezo beeps, notes, melodies and audio icons
    { path: 'lib/espnow_code.py', remotePath: '/lib/espnow_code.py' },  // Game pull: receives a game file from the Broadcast Box/Dial over ESP-NOW
    { path: 'lib/espnow_manager.py', remotePath: '/lib/espnow_manager.py' },  // ESP-NOW init, send, receive and peer management
    { path: 'lib/game_store.py', remotePath: '/lib/game_store.py' },  // Pulled-game library in /games/<slug>.py on flash
    { path: 'lib/game_tags.py', remotePath: '/lib/game_tags.py' },  // Game and control tag names (the NFC card wire format)
    { path: 'lib/hubtype.py', remotePath: '/lib/hubtype.py' },  // Device type detection and per-device pin/LED/I2C config
    { path: 'lib/leds.py', remotePath: '/lib/leds.py' },  // NeoPixel helpers for the 5x5 matrix and status display
    { path: 'lib/lis2dw12.py', remotePath: '/lib/lis2dw12.py' },  // LIS2DW12 accelerometer driver with wake-up interrupt
    { path: 'lib/lobby_game.py', remotePath: '/lib/lobby_game.py' },  // Ad hoc ESP-NOW lobby games: lobby, roster and the net object
    { path: 'lib/max17048.py', remotePath: '/lib/max17048.py' },  // MAX17048 LiPo fuel gauge driver
    { path: 'lib/memprobe.py', remotePath: '/lib/memprobe.py' },  // Heap probes (bench diagnostics; main.py imports it, so it must ship)
    { path: 'lib/nfc_reader.py', remotePath: '/lib/nfc_reader.py' },  // NFC tag scanning and command extraction
    { path: 'lib/opt3002.py', remotePath: '/lib/opt3002.py' },  // OPT3002 ambient light sensor driver
    { path: 'lib/pairing.py', remotePath: '/lib/pairing.py' },  // Paired-Splat list stored in /pairing.json
    { path: 'lib/pn532.py', remotePath: '/lib/pn532.py' },  // PN532 NFC reader/writer driver (I2C 0x24)
    { path: 'lib/power_led.py', remotePath: '/lib/power_led.py' },  // Power/status LED on GPIO 2
    { path: 'lib/pwire.py', remotePath: '/lib/pwire.py' },  // ESP-NOW unicast helpers shared by splatpair and lobby_game
    { path: 'lib/splat_api.py', remotePath: '/lib/splat_api.py' },  // The splat object games receive (SplatGroup)
    { path: 'lib/splat_hub.py', remotePath: '/lib/splat_hub.py' },  // BLE links to one or more Splats on one radio
    { path: 'lib/splat_link.py', remotePath: '/lib/splat_link.py' },  // Non-blocking BLE link to one Splat
    { path: 'lib/splatpair.py', remotePath: '/lib/splatpair.py' },  // This wand's BLE links to its paired Splats
];
