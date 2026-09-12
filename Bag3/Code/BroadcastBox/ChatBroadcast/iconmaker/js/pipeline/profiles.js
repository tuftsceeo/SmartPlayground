/**
 * profiles.js -- the hardware this tool is authoring for.
 *
 * Everything geometry- or panel-dependent reads from the active profile
 * rather than assuming the 16x16 station matrix. Adding a board should mean
 * adding an entry here, not hunting constants through the pipeline.
 *
 * WORK MUST DIVIDE EVENLY BY w AND h. Cell coverage is an exact block mean
 * over a work/w square of source pixels; a fractional block size silently
 * stops being a mean and the segmentation drifts. 512 works for 16 (32/cell)
 * but NOT for 5 (102.4), which is why the wand profile uses 500 (100/cell).
 *
 * Thresholds are per-profile because several of them are counts, and a count
 * tuned for 256 cells is nonsense on 25. MIN_FEATURE_CELLS = 4 is 1.6% of a
 * 16x16 display but 16% of a 5x5 -- left alone it would flag every feature
 * on a wand as too small.
 */

export const PROFILES = {
  matrix16: {
    id: "matrix16",
    label: "Icon Matrix 16x16",
    note: "Station panel, WS2812B, USB-powered",
    w: 16,
    h: 16,
    work: 512, // 32 source px per cell
    addressing: "serpentine",
    mirrorX: true, // this panel; see icon_matrix.py
    flipY: false,
    // authoring thresholds
    maxSegments: 12,
    minFeatureCells: 4,
    maxLitColors: 8,
    // preview geometry
    previewScale: 24,
    dotRadius: 8,
    // power: readme measured the 5V/3A driver board
    ceilingMa: 3000,
    ceiling12vMa: 4000,
  },

  wand5: {
    id: "wand5",
    label: "Wand 5x5",
    note: "25 LEDs, row-major, battery powered",
    w: 5,
    h: 5,
    work: 500, // 100 source px per cell -- 512 is NOT divisible by 5
    addressing: "rowmajor", // wand strip is index = row*w + col, no serpentine
    mirrorX: false,
    flipY: false,
    // 25 cells cannot carry 12 segments; a single cell IS a feature here
    maxSegments: 5,
    minFeatureCells: 1,
    maxLitColors: 4,
    // much bigger on-screen cells, or a 5x5 preview is a postage stamp
    previewScale: 64,
    dotRadius: 21,
    // UNVERIFIED: battery-powered, and no equivalent of the readme's bench
    // measurements exists for the wand yet. Deliberately conservative.
    ceilingMa: 400,
    ceiling12vMa: 400,
  },
};

export const DEFAULT_PROFILE_ID = "matrix16";

let active = PROFILES[DEFAULT_PROFILE_ID];

export function getProfile() {
  return active;
}

export function listProfiles() {
  return Object.values(PROFILES);
}

/**
 * Best-effort match of a device's `hello` to a known profile, so connecting
 * a board generally selects the right one without the user choosing.
 * Returns null when nothing matches, leaving the current profile alone.
 */
export function profileForHello(hello) {
  if (!hello || !hello.w || !hello.h) return null;
  return listProfiles().find((p) => p.w === hello.w && p.h === hello.h) || null;
}

/** Set the active profile. Callers must re-run the pipeline afterwards. */
export function setProfile(idOrProfile) {
  const p = typeof idOrProfile === "string" ? PROFILES[idOrProfile] : idOrProfile;
  if (!p) throw new Error(`unknown device profile: ${idOrProfile}`);
  if (p.work % p.w !== 0 || p.work % p.h !== 0) {
    throw new Error(`profile ${p.id}: work ${p.work} must divide by ${p.w}x${p.h} (see module docstring)`);
  }
  active = p;
  return active;
}

/** Bytes on the wire for one frame of this profile. */
export function frameBytes(profile = active) {
  return profile.w * profile.h * 3;
}
