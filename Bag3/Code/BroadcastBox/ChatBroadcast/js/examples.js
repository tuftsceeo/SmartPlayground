/**
 * The example gallery.
 *
 * `vendorGame` names the real wand game in
 * `Simulator/vendor/games/<name>.py`, which is what previews load and what
 * `loadExampleCode()` fetches. These used to be hand-written simplifications
 * of each game held in this file; they drifted from the real code (Melody's,
 * for one, filled the whole matrix with one colour instead of lighting a
 * pixel per note), so nothing is duplicated here any more.
 *
 * `simProfile` still matters, but only for code loaded as *source* — a
 * generated or remixed game. py/runtime.py's _TEACHER_TABLE is keyed by
 * vendored module name and never matches source, so without a profile such
 * a preview falls back to "show every control" and buries a tag game under
 * the whole pose-and-move wall. A preview loaded by `vendorGame` gets the
 * real table entry and needs no profile. `button` is "tap"/"hold"/"none";
 * `motion` is the subset of poses/moves the game reads. The NFC tag row
 * always comes from the code's own COMMANDS.
 */
export const EXAMPLES = [
    {
        id: "melody",
        name: "Melody",
        icon: "music",
        category: "sound",
        description: "Tap each note-tag to play a tune.",
        tagNote: "10 NFC tags",
        tags: ["note_c", "note_d", "note_e", "note_f", "note_g", "note_a", "note_b", "note_c_high",
               "erase", "backspace"],
        starterPrompt: "Start from the Melody example — one tag per note.",
        vendorGame: "melody",
        simProfile: {
            button: "tap",
            motion: [],
        },
    },
    {
        id: "freezedance",
        name: "Freeze Dance",
        icon: "snowflake",
        category: "color",
        description: "Move, then freeze when the music stops.",
        tagNote: null,
        tags: ["freezedance"],
        starterPrompt: "Start from Freeze Dance — move and freeze game.",
        vendorGame: "freeze_dance",
        simProfile: {
            button: "none",
            motion: ["shake"],
        },
    },
    {
        id: "rainbow",
        name: "Rainbow",
        icon: "rainbow",
        category: "color",
        description: "Shake for color.",
        tagNote: null,
        tags: ["rainbow"],
        starterPrompt: "Start from Rainbow — shake for color.",
        vendorGame: "rainbow",
        simProfile: {
            button: "tap",
            motion: ["shake"],
        },
    },
    {
        id: "shakerainbow",
        name: "Shake Rainbow",
        icon: "rainbow",
        category: "color",
        description: "Shake harder to climb through rainbow colors.",
        tagNote: null,
        tags: ["shakerainbow"],
        starterPrompt: "Start from Shake Rainbow — sticky high-score shake colors.",
        vendorGame: "shake_rainbow",
        simProfile: {
            button: "tap",
            motion: ["shake"],
        },
    },
    {
        id: "jump",
        name: "Jump",
        icon: "arrow-up",
        category: "color",
        description: "Jump (freefall) to light more LEDs on the matrix.",
        tagNote: null,
        tags: ["jump"],
        starterPrompt: "Start from Jump — freefall jump counter on the LEDs.",
        vendorGame: "jump",
        simProfile: {
            button: "tap",
            motion: ["jump"],
        },
    },
    {
        id: "cooking",
        name: "Cooking",
        icon: "chef-hat",
        category: "multi",
        description: "Recipe steps with ingredient tags.",
        tagNote: "Multi-tag",
        tags: ["flour", "egg", "milk", "butter", "sugar"],
        starterPrompt: "Start from Cooking — recipe steps game.",
        vendorGame: "cooking",
        simProfile: {
            button: "tap",
            motion: [],
        },
    },
    {
        id: "jumpin",
        name: "Jump In",
        icon: "brain-circuit",
        category: "color",
        description: "Simple jump game — great first project.",
        tagNote: null,
        tags: ["jumpin"],
        starterPrompt: "Make a simple jump game where shaking makes the wand light up.",
        vendorGame: "jumpin",
        simProfile: {
            button: "tap",
            motion: ["shake"],
        },
    },
];

export const CATEGORIES = [
    { id: "all", label: "All", icon: null },
    { id: "sound", label: "Sound", icon: "music" },
    { id: "color", label: "Color", icon: "palette" },
    { id: "multi", label: "Multi-tag", icon: "tag" },
];

export function findExample(id) {
    return EXAMPLES.find((e) => e.id === id);
}


/**
 * The real Python for an example, fetched from the Simulator's vendored
 * copy. Resolved against this module's own URL, the same way
 * Simulator/wand-sim.js resolves its assets, so it works from whatever path
 * the app is served at — both trees still have to be served from a common
 * `Bag3/Code/` root.
 *
 * Previews don't need this: they set `<wand-sim>.game = vendorGame` and let
 * Pyodide read the file it already has. This is for the paths that need the
 * code as text — remix, use as-is, the code drawer, Save, Send to Box.
 */
export async function loadExampleCode(ex) {
    const name = ex && ex.vendorGame;
    if (!name) throw new Error(`example "${ex && ex.id}" has no vendorGame`);
    const url = new URL(`../../../Simulator/vendor/games/${name}.py`, import.meta.url);
    // Same reason as wand-sim.js's fetchText: a static server sends no
    // Cache-Control, and a stale game file here would silently show the
    // teacher last week's code.
    const res = await fetch(url, { cache: "no-cache" });
    if (!res.ok) throw new Error(`fetch ${name}.py: ${res.status}`);
    return res.text();
}
