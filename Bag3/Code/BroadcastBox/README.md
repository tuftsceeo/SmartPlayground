
# ChatBroadcast + Broadcast Box Plan (not yet implemented)

ChatBroadcast will be a javascript web app interface which will connect with a new component, the BroadcastBox over web serial, the Broadcast Box (planned to be a M5 StickS3 with PN532 NFC Reader/Writer Driver, 240x135 lcd screen, and one button). 


## User Experience Mock-Up

The full task:
1. Teacher opens Chat Broadcast app (splash page / example games options)
2. Teacher uses chat to generate code for game (or modify an exisiting game from a provided library of examples) and is shown a simulation of the wand (and possibly other components in the future?) behaviors coded and possibly references some light documentation about the palette of sensor/output options available.
  - Depending on the game there might be multiple code files generated if there are different roles or device types. Ex1: code for wands and code for stations. Ex2: code for wands on Team A and wands on Team B)
  - If there are multiple devices or NFC cards needed for the game, these compenents should be listed as expected hardware that will be available.
  - Teacher may optionally refine the code through further discussion with chat.
4. When ready, teacher connects Chat Broadcast app to the  Broadcast Box prototype over usb serial.
5. Teacher sends generated code(s) to the BBox
6. Teacher taps blank nfc cards to BBox and uses the BBox to assign/write any additional NFC tags required for the game and a tag representing the game code to a nfc card. BBox now associates that generated game code with that card.
7. Students tap that nfc with their wands can "pick up" (transfer and run that generated game code) to their wand via the BBox (the wand will broadcast a request for the new generated game over espnow which the BBox will pick up, perhaps the BBox could even specificy their mac address on the nfc card so the wand can direct the message appropriately and then the BBox and wand will use the SoftAP/TCP file transfer approach provided in the prototype)
9. Teacher can also go around to any stations involved in the game and tap the nfc card on those to trigger a similar code uploading process for the station specific code.
10. Optional (but a nice to have) would be if the Chat Broadcast app via the BBox tracks which modules/stations (via mac address) had received / picked up the code and which NFC cards have been written/skipped/still need to write. 


A Claude Design  UI mockup for Chat Broadcast app is in Bag3/Code/BroadcastBox/design/Wand Coder App Mockups.dc.html
A Prototype flow logic document for that UI mockup is in Bag3/Code/BroadcastBox/design/Prototype Flow Logic.md


## Rough Notes and Design Thoughts
The CB/BB communication will use a web serial protocol likely similar to the  Bag3/Code/Stations/Icon Display Station and Bag3/Code/Stations/Radar Station. Critical web serial notes: Bag3/Code/Stations/serial_protocol_notes.md. 

The BroadcastBox will be write NFC cards and transmit python code to other Bag 3 playground components in order to run ChatBroadcast developed/modified games on the Smart Playground system. 

Currently the Bag3/Code/BroadcastBox/BBoxPrototype contains proof of concept code where a S3 runs a SoftAP and a C6 connects directly to it to receive the python code.

- **`s3_sender.py`**  (to become the BBox) runs on a ESP32-S3. It's a SoftAP + an unthreaded TCP server that accepts exactly one connection, sends one file, and closes.
- **`c6_receiver.py`** (standing in for Wands and other components) runs on a ESP32-C6. It joins the S3's AP as a station and is the TCP client — it connects out, pulls the file, verifies it, and atomically promotes it into place. Having the receiver and server transition between SoftAP and ESPNow was previously tested but not currently in this code (8/29).

Claude Design Wireframes of possible Screens for the BBox are shown in  Bag3/Code/BroadcastBox/design/Wand Coder + Broadcast Box Wireframe 2.dc.html


## Notes from Claude Design
Code-first default fights the audience. Kindergarten teachers don't read Python. Putting a code editor at 50% width by default signals "this is for programmers." The result (what the wand/station will actually do) should be the hero; code should be an expert drawer, not a pane.
No error/failure states. Missing: AI misunderstands the request, board not detected, wrong board plugged in, NFC write fails/times out, card already has a game (overwrite confirm), wand/station low battery, no wifi for the AI call. These will happen constantly with kids/hardware and need friendly, non-technical copy.
No iteration/refinement UX. Real chat-coding needs quick-reply chips ("make it faster," "add sound," "try a different color") instead of forcing a full sentence every time — much lower friction for non-coders than free text.
No first-run guidance in the empty state. Splash has a tutorial button, but the chat's empty state itself should suggest example prompts ("Try: 'wand glows red when shaken'") — teachers won't know what's askable.
No library/save-for-later. Teachers will want to reuse a game across class periods/days. Nothing lets them name and revisit past games.
Overwrite confirmation missing on the Box. Tapping a card that already holds a game needs a confirm step — with only one button and kids around, an accidental overwrite is a real risk.
No "which station am I at" context when walking around — station screens show a MAC-ish label, which means nothing to a teacher. Needs a friendly station name/number set during setup.
Tracking is deprioritized correctly, but log screen has no way back to idle cleanly stated — minor, fixable in the button legend.
Progressive disclosure — concrete proposal: Default "Simple" view = chat + a big preview/simulation panel (the visual outcome — glow, motion, sound cues), full width, no code visible. Code becomes a collapsed drawer ("</> Show code") that slides out only when a teacher taps it — that's your gate for the rare technical teacher, not a permanent 50/50 split. This also justifies the "simulator" step you flagged: it should be the main artifact, not a placeholder tab.

Borrowing from WebApp2 (the group-text remote): that app treats each device as a contact/thread with message-bubble status ("Wand 3: ready ✓"). That mental model transfers well here — treat Wand code and Station code not as tabs but as two separate chat threads/contacts, like a group text with two people. Sending code = "sending a text" to that thread, which is a familiar, low-anxiety action for non-technical teachers. Card-writing progress could reuse the same bubble/status-ping visual language instead of a generic progress bar.

### Additional Notes

8/29: ChatBroadcast is currently a copy of ChatApp: Use this portal to program your Wand. To be adapted to incorperate the design features of  Bag3/Code/BroadcastBox/design/Wand Coder App Mockups.dc.html

9/3: ChatBroadcast's game preview panel now embeds the `Bag3/Code/Simulator` `<wand-sim>` element directly (`ChatBroadcast/js/app.js`'s `setupSim()` imports `../../Simulator/wand-sim.js`), so it must be served from a root that covers both trees: `cd Bag3/Code && python3 -m http.server`, then open `/BroadcastBox/ChatBroadcast/` — serving `ChatBroadcast/` alone 404s on that import.