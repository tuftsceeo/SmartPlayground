/**
 * Splat model: one simulated Splat's visible state.
 *
 * A Splat shows a color, plays an animal sound or a note, and has a button.
 * The vocabulary mirrors MockWand/lib/splat_api.py (COLOR_RGB, NOTE_VALUES,
 * ANIMAL_SOUNDS); the names are checked against the generated
 * ChatBroadcast/js/splat/splatActions.js by tests/js/peers.test.mjs.
 *
 * Two ways in:
 *   applyAction(op, v)   the pw_cmd / splat_api level: op "color" | "sound" |
 *                        "note" | "play" | "off", v a card name or name list
 *   applyWrite(op, args) the BLE-write level py/shims/splat_hub.py reports
 *                        for the simulated wand's own Splats ("leds",
 *                        "sound", "noteOn", "noteOff", "tasksOff", "ledsOff")
 *
 * State: rgb [r,g,b], color (name or null), sound (name or null), note
 * (name or null), ready (link up), pressed, and sounds (count of sounds and
 * notes started, so a view can tell a repeat from no change).
 * onChange(splat, what) fires after every change; what is "color" |
 * "sound" | "note" | "off" | "ready" | "press".
 */

export const COLOR_RGB = {
  turnred: [255, 0, 0], turngreen: [0, 255, 0], turnblue: [0, 0, 255],
  turnpurple: [160, 0, 200], turnyellow: [255, 180, 0], turnwhite: [200, 200, 200],
  turnoff: [0, 0, 0],
};

export const NOTE_VALUES = {
  note_c: [0, 0], note_d: [2, 0], note_e: [4, 0], note_f: [5, 0], note_g: [7, 0],
  note_a: [9, 0], note_b: [11, 0], note_c_high: [0, 1], playnote: [0, 0],
};

export const ANIMAL_SOUNDS = {
  cat: 19, chicken: 20, cow: 21, dog: 22, pig: 23, duck: 24, elephant: 25, horse: 26, goat: 28,
};

/** splat_api.NOTE_OCTAVE */
export const NOTE_OCTAVE = 4;

/** Frequency in Hz of a note card, at splat_api's octave. */
export function noteFreq(name) {
  const v = NOTE_VALUES[name];
  if (!v) return null;
  const midi = 12 * (NOTE_OCTAVE + v[1] + 1) + v[0];
  return 440 * 2 ** ((midi - 69) / 12);
}

function noteName(value, octave) {
  for (const [n, [v, o]] of Object.entries(NOTE_VALUES)) {
    if (n !== "playnote" && v === value && NOTE_OCTAVE + o === octave) return n;
  }
  return `note ${value}/${octave}`;
}

function soundName(idx) {
  for (const [n, i] of Object.entries(ANIMAL_SOUNDS)) if (i === idx) return n;
  return `sound ${idx}`;
}

function colorName(rgb) {
  for (const [n, c] of Object.entries(COLOR_RGB)) {
    if (c[0] === rgb[0] && c[1] === rgb[1] && c[2] === rgb[2]) return n;
  }
  return null;
}

const HISTORY_MAX = 200;

export function createSplat({ mac, owner = null, onChange = null } = {}) {
  const s = {
    mac,
    owner,
    rgb: [0, 0, 0],
    color: null,
    sound: null,
    note: null,
    ready: true,
    pressed: false,
    sounds: 0,
    /** Applied actions, oldest first: [op, v]. */
    history: [],
    onChange,
  };
  const changed = (what) => s.onChange?.(s, what);

  function setColor(name) {
    const rgb = COLOR_RGB[name];
    if (!rgb) throw new Error(`unknown Splat color: ${name}`);
    s.rgb = [...rgb];
    s.color = name;
    changed("color");
  }

  function setSound(name) {
    if (!(name in ANIMAL_SOUNDS)) throw new Error(`unknown Splat sound: ${name}`);
    s.sound = name;
    s.sounds++;
    changed("sound");
  }

  function setNote(name) {
    if (!(name in NOTE_VALUES)) throw new Error(`unknown Splat note: ${name}`);
    s.note = name;
    s.sounds++;
    changed("note");
  }

  function off() {
    s.rgb = [0, 0, 0];
    s.color = null;
    s.sound = null;
    s.note = null;
    changed("off");
  }

  s.applyAction = (op, v) => {
    s.history.push([op, v]);
    if (s.history.length > HISTORY_MAX) s.history.splice(0, s.history.length - HISTORY_MAX);
    if (op === "color") setColor(v);
    else if (op === "sound") setSound(v);
    else if (op === "note") setNote(v);
    else if (op === "off") off();
    else if (op === "play") {
      if (!Array.isArray(v)) throw new Error(`play needs a list of names, got ${JSON.stringify(v)}`);
      for (const name of v) {
        if (name in COLOR_RGB) setColor(name);
        else if (name in ANIMAL_SOUNDS) setSound(name);
        else if (name in NOTE_VALUES) setNote(name);
        else throw new Error(`unknown Splat action: ${name}`);
      }
    } else throw new Error(`unknown Splat op: ${op}`);
  };

  s.applyWrite = (op, args = []) => {
    s.history.push([op, args]);
    if (s.history.length > HISTORY_MAX) s.history.splice(0, s.history.length - HISTORY_MAX);
    if (op === "leds") {
      s.rgb = [args[0] | 0, args[1] | 0, args[2] | 0];
      s.color = colorName(s.rgb);
      changed("color");
    } else if (op === "sound") {
      s.sound = soundName(args[0]);
      s.sounds++;
      changed("sound");
    } else if (op === "noteOn") {
      s.note = noteName(args[0], args[1]);
      s.sounds++;
      changed("note");
    } else if (op === "noteOff") {
      s.note = null;
      changed("note");
    } else if (op === "tasksOff") {
      s.sound = null;
      s.note = null;
      changed("off");
    } else if (op === "ledsOff") {
      s.rgb = [0, 0, 0];
      s.color = null;
      changed("off");
    } else throw new Error(`unknown Splat write: ${op}`);
  };

  s.setReady = (up) => {
    s.ready = !!up;
    changed("ready");
  };

  s.setPressed = (down) => {
    s.pressed = !!down;
    changed("press");
  };

  return s;
}
