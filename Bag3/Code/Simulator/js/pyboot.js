/**
 * The wand's Python side: the files its Pyodide needs and the bootstrap
 * that installs them. Shared by <wand-sim> (browser) and js/headless.js
 * (Node), so the two boot the same runtime.
 *
 * The files below are one unit with wand-sim.js: the bootstrap calls
 * sim_state functions by name, so a stale copy of any of them breaks boot
 * outright (see wand-sim.js fetchText for the caching side of this).
 */

export const FILE_LIST = [
  "py/transform.py",
  "py/runtime.py",
  "py/shims/sim_state.py",
  "py/shims/machine.py",
  "py/shims/neopixel.py",
  "py/shims/_thread.py",
  "py/shims/network.py",
  "py/shims/espnow.py",
  "py/shims/ubluetooth.py",
  "py/shims/micropython.py",
  "py/shims/time_patch.py",
  "py/shims/splat_hub.py",
  "py/devices/lis2dw12.py",
  "py/devices/max17048.py",
  "py/devices/opt3002.py",
  "py/devices/pn532.py",
  "py/devices/nfc_reader.py",
  "vendor/hubtype.txt",
  "vendor/lib/brightness.py",
  "vendor/lib/hubtype.py",
  "vendor/lib/leds.py",
  "vendor/lib/buzzer.py",
  "vendor/lib/game_tags.py",
  "vendor/lib/actions.py",
  "vendor/lib/battery.py",
  "vendor/lib/espnow_manager.py",
  "vendor/lib/pairing.py",
  "vendor/lib/splat_api.py",
  "vendor/lib/pwire.py",
  "vendor/lib/splatpair.py",
  "vendor/lib/party.py",
  "vendor/games/jump.py",
  "vendor/games/shake.py",
  "vendor/games/shake_rainbow.py",
  "vendor/games/sound.py",
  "vendor/games/rainbow.py",
  "vendor/games/jumpin.py",
  "vendor/games/nfc_sound.py",
  "vendor/games/gestures.py",
  "vendor/games/simpleicecream.py",
  "vendor/games/melody.py",
  "vendor/games/cooking.py",
  "vendor/games/multiicecream.py",
  "vendor/games/freeze_dance.py",
  "vendor/games/goalrace.py",
  "vendor/games/color_quest.py",
  "vendor/games/finddevice.py",
  "vendor/games/partytest.py",
  "vendor/games/splattag.py",
  "vendor/games/relaycolor.py",
  // Not a game: color_quest.py imports SCORE_MAC from it.
  "vendor/games/target.py",
];

/** sim_state hooks the host wires; a cached, older sim_state.py lacks some. */
export const CALLBACKS = [
  "set_led_callback", "set_pwm_callback", "set_motor_callback",
  "set_print_callback", "set_log_callback", "set_error_callback",
  "set_enow_sent_callback",
];

/**
 * Write FILE_LIST into the Pyodide FS under /sim and bootstrap the runtime.
 * readText(rel) returns a file's text, relative to the Simulator root.
 */
export async function bootWand(pyodide, readText) {
  const contents = {};
  await Promise.all(FILE_LIST.map(async (rel) => {
    contents[rel] = await readText(rel);
  }));
  pyodide.FS.mkdirTree("/sim");
  for (const [rel, text] of Object.entries(contents)) {
    const path = "/sim/" + rel;
    pyodide.FS.mkdirTree(path.slice(0, path.lastIndexOf("/")));
    pyodide.FS.writeFile(path, text);
  }
  await pyodide.runPythonAsync(`
import sys
sys.path.insert(0, "/sim/py")
sys.path.insert(0, "/sim/py/shims")
sys.path.insert(0, "/sim/py/devices")
from runtime import get_runtime, load_game, start, stop, get_commands, get_capabilities
import os
contents = {}
for root, dirs, files in os.walk("/sim"):
    for f in files:
        p = os.path.join(root, f)
        rel = p[len("/sim/"):]
        with open(p) as fh:
            contents[rel] = fh.read()
rt = get_runtime()
rt.bootstrap(file_contents=contents, workdir="/sim/vendor")
`);
}

/**
 * Hand sim_state the host's callbacks: an object keyed by CALLBACKS names
 * (missing ones are left unset). Raises when sim_state is out of date.
 */
export async function wireCallbacks(pyodide, callbacks) {
  for (const [name, fn] of Object.entries(callbacks)) pyodide.globals.set(`_js_${name}`, fn);
  pyodide.globals.set("_js_callback_names", Object.keys(callbacks).join(","));
  await pyodide.runPythonAsync(`
import sim_state
_missing = [n for n in ${JSON.stringify(CALLBACKS)} if not hasattr(sim_state, n)]
if _missing:
    raise RuntimeError(
        "sim_state.py is out of date with wand-sim.js (missing %s) — "
        "a cached copy is being served; reload without cache"
        % ", ".join(_missing)
    )
for _n in _js_callback_names.split(","):
    if _n:
        getattr(sim_state, _n)(globals()["_js_" + _n])
`);
}

let jspiHidden = 0;
let jspiSaved = null;

/**
 * loadPyodide(opts) with WebAssembly's stack-switching (JSPI) API hidden, so
 * Pyodide takes its non-JSPI path, as it does under Node. Pyodide 0.27.0
 * on Chrome 152's JSPI dies with a fatal "function signature mismatch" or
 * "invalid address in funcref table" after a minute or so of a party game's
 * Python/JS traffic; with JSPI hidden the same play runs on. Nothing here
 * uses what JSPI adds (run_sync, blocking on a JS promise). The API is put
 * back once every load in flight has finished.
 */
export async function loadPyodideNoJspi(load, opts) {
  if (jspiHidden++ === 0) {
    jspiSaved = {};
    for (const k of ["Suspending", "promising", "Function"]) {
      if (k in WebAssembly) {
        jspiSaved[k] = WebAssembly[k];
        delete WebAssembly[k];
      }
    }
  }
  try {
    return await load(opts);
  } finally {
    if (--jspiHidden === 0) Object.assign(WebAssembly, jspiSaved);
  }
}

/** How often (real ms) the wand's mirror of the room clock is re-anchored. */
const CLOCK_SYNC_MS = 1000;

/**
 * Put a booted wand on a room's bus and clock: its own MAC, sends onto the
 * bus, ticks from the clock. tx(src, dst, hex) returns the ACK count.
 *
 * The wand's ticks mirror the clock (time_patch.set_clock_anchor) rather
 * than calling it: Python calling a JS function on every ticks_ms() has
 * crashed Pyodide in the browser. The anchor is refreshed every
 * CLOCK_SYNC_MS, and at once by sync() after a change to the clock's scale.
 * Returns { detach(), sync() }.
 */
export function attachWand(pyodide, { bus, clock, mac, tx }) {
  const simState = pyodide.pyimport("sim_state");
  pyodide.globals.set("_room_tx", (src, dst, hex) => tx(String(src), String(dst), String(hex)));
  simState.set_own_mac(mac);
  // Registered from Python, as wand-sim.js does its callbacks: a JS function
  // handed to a Python setter from JS has ended in Pyodide fatal errors.
  pyodide.runPython("import sim_state\nsim_state.set_radio_tx(_room_tx)");
  const timePatch = pyodide.pyimport("time_patch");
  const sync = () => {
    timePatch.set_clock_anchor(clock.nowMs(), clock.getScale());
    timePatch.set_time_scale(clock.getScale());
  };
  sync();
  const timer = setInterval(sync, CLOCK_SYNC_MS);
  const detachBus = bus.attach(mac, (src, payload) => {
    simState.deliver_enow(src, Array.from(payload, (b) => b.toString(16).padStart(2, "0")).join(""));
  });
  return {
    sync,
    detach() {
      clearInterval(timer);
      detachBus();
    },
  };
}
