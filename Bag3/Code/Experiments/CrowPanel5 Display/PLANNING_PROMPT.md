# Prompt: plan the CrowPanel5 teacher tool

You are planning (not yet building) the full implementation of the CrowPanel5 teacher tool: every
screen of the "CrowPanel Teacher Tool" design, running on the Elecrow CrowPanel 5.0" V3, with a
working back end based mostly on the Broadcast Dial firmware.

## Deliverable

A plan document, `Bag3/Code/Experiments/CrowPanel5 Display/IMPLEMENTATION_PLAN.md`, reviewed
with the user before any code is written. It should contain:

1. **Screen inventory:** every design screen. For each one: its purpose, how you get to it and
   where it leads, the data it shows, the actions it takes, and the back-end call behind each
   action.
2. **Back-end map:** for each action, the Broadcast Dial module and function that does it today
   (`bdial_server.py`, `station.py`, `fleet.py`, `code_sender.py`, `code_link.py`,
   `card_writer.py`, `json_link.py`, `stats_log.py`). Say whether it can be reused as is, needs
   adapting, or doesn't exist yet. Example of the last kind: sending start, stop, code or find to
   a chosen list of MACs, which `teacher_tool_features.md` flags as needed.
3. **Architecture:** how the modules are laid out on the CrowPanel, covering:
   - the UI layer versus the radio and storage layer;
   - how screens are cached and switched;
   - whether a host (ChatBroadcast over USB) is still in the loop, as `bdial_server.py` is for
     the Dial, or the panel runs on its own;
   - memory order: the radio must claim its memory before anything else allocates (see
     `AGENTS.md`).
4. **Gaps and risks:**
   - **NFC:** the CrowPanel has no reader; a PN5180-class reader through the screen is untested.
   - **Fonts:** only the built-in Montserrat 12/14/16; custom fonts need tool installs the user
     must approve.
   - **Flash:** the app partition is full.
   - **PSRAM and memory** for cached screens and icons.
   - **Touch-bus loss** after a soft reset.
5. **Build order:** milestones small enough for the user to check each by eye on the board,
   each with what "done" looks like.

Ask the user questions where the design and the Dial behaviour disagree. Don't guess, and
don't treat the design mock as the authority on behaviour.

## Read first

Read the following:

- **`AGENTS.md`:** at minimum the radio memory-order rule, "Station is not one thing", and the
  shared-library copies.
- **`Bag3/Code/HARDWARE_PROTOCOL.md`**
- **`Bag3/Code/known_issues/README.md`**, and the CrowPanel and Dial notes it indexes.
- **`Bag3/Code/Experiments/CrowPanel5 Display/`:**
  - `README.md`
  - `teacher_tool_features.md`: what each existing tool does today, by teacher task.
  - `home.py`: the design's screen 1, built and approved by eye.
  - `gallery.py` and `ds_tokens.py`: the Design System components.
  - `display_lvgl.py`
- **`Bag3/Code/TeacherTools/BroadcastDial/`:** its `README.md` and `BDialFirmware/`.
- **The design itself:** it is not in the repo. Ask the user for the link, or ask the
  UI-development session that built the home screen.

## Current state

- **Firmware:** custom lvgl_micropython (LVGL 9.4), board `CROWPANEL_S3_5`, built from
  `~/build/lvgl_micropython_crowpanel`. Never touch the IPS096 files or `~/build/lvgl_micropython`.
- **Display and touch:**
  - 800x480 RGB panel at 12 MHz with a bounce buffer;
  - GT911 touch, read every 10 ms;
  - backlight always on: PWM caused shimmer, so the screen can't be dimmed.
- **Built and approved by eye:** the 8-page Design System gallery, and screen 1 (home) with 30
  PNG icons tinted at runtime. Next in the design order is screen 2, "Who gets it?".
- **Hardware rules:**
  - Port `/dev/cu.usbserial-310`. Always use `mpremote ... resume`, and check `lsof` first.
  - Reset only through EN: the RST button, or an RTS pulse.
  - The USB cable is loose; a "Device not configured" error means reseat it.

## Constraints

- This is planning only. Do not edit firmware or device files in this session.
- On-screen text is ASCII only: write " - ", not an em dash.
- Docs state current behaviour only.
- Commit only when the user asks.
