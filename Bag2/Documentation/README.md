# Documentation

System-level documentation for the Smart Playground Bag2 project. Each game has its own detailed reference covering architecture, message formats, wiring, and setup.

## Games

### [Color Quest](./COLOR_QUEST_README.md)

A multi-device scavenger hunt where students race to find and tap NFC color tags in order. A hub station broadcasts a color sequence, wand modules guide players through the hunt, and a scoreboard displays live results as a proportional bar graph. Three ESP-NOW devices coordinate wirelessly.

Key topics: system architecture diagram, ESP-NOW message formats (station broadcasts and score submissions), scoreboard bar scaling logic, per-device wiring tables, MAC address configuration, and timing behavior.

### [Freeze Dance](./FREEZE_DANCE_README.md)

A multiplayer motion game where one caller controls GO and FREEZE commands while all player wands detect movement. Any wand can be the caller or a player — roles are chosen by tapping NFC tags after entering the game. Players caught moving during FREEZE are penalized for 30 seconds.

Key topics: game state machine and LED effects, ESP-NOW broadcast protocol, caller vs. player role selection, accelerometer-based motion detection algorithm, tuning parameters, and integration with the programming engine.
