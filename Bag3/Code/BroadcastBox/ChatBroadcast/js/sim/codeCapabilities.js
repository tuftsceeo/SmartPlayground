/**
 * Scan generated MicroPython for wand API usage.
 * Shared by wand simulation and component checklist.
 *
 * KNOWN LIMITATION: computeLedFrames() is a regex + indentation heuristic,
 * not a real Python interpreter. It cannot evaluate arbitrary expressions,
 * loops that build state over iterations, or deeply nested/unusual branch
 * structures. It reliably handles the common wand pattern of "if
 * pressed: <leds call>" / "elif released: <leds call>" seen in
 * jump.py-style games. For a fully accurate simulation, running the real
 * code in-browser via Pyodide/PyScript (stubbing nfc/leds/buz/accel as JS
 * objects) would be the robust long-term fix — see project notes.
 */

import { computeLedFrames } from "./ledShapes.js";
import { dbg, dbgWarn, dbgGroup } from "../debug.js";

export function scanCapabilities(code) {
    const src = code || "";

    // Best-effort per-pixel (25-LED) preview frames — see ledShapes.js.
    // idle = release/unconditional calls; pressed = idle + press-branch
    // calls layered on top. Off pixels are black; lit pixels carry color.
    const classifyLog = [];
    let ledFrames;
    dbgGroup("ledSim", `scanCapabilities() — parsing ${src.length} chars of code`, () => {
        ledFrames = computeLedFrames(src, {
            onLog: (kind, data) => {
                if (kind === "classify") {
                    classifyLog.push(data);
                    dbg("ledSim", `call leds.${data.method}() @${data.index} — context="${data.context}" -> branch=${data.branch || "none"}`);
                } else if (kind === "frames") {
                    dbg("ledSim", `parsed ${data.totalCalls} leds.* call(s), ${data.pressCalls} press-classified`, {
                        hasDistinctPressedFrame: data.hasDistinctPressedFrame,
                        idle: data.idle,
                        pressed: data.pressed,
                    });
                }
            },
        });
    });
    const hasLedCall = /\bleds\.(off|solid|fill|show_shape|show_pattern)\s*\(/.test(src);
    const looksButtonDriven = /\bbtn\.value\b|\b_check_button\b/.test(src);

    // If the code clearly reads the button AND drives the LEDs, but the
    // classifier found no press-branch call, something about this code's
    // structure doesn't match the heuristics in ledShapes.js — surface an
    // EXPANDED (not collapsed) diagnostic with the full source so it's
    // easy to copy out of the console and report back for a fix.
    if (hasLedCall && looksButtonDriven && ledFrames && !ledFrames.pressDetected) {
        dbgGroup(
            "ledSim",
            "⚠ button + LED code detected, but no press-branch LED call was classified — sim will not react to the button. Copy this group to report the mismatch.",
            () => {
                dbgWarn("ledSim", "per-call classification results:", classifyLog);
                dbgWarn("ledSim", "full source that was scanned:\n" + src);
            },
            { expanded: true }
        );
    }

    const usesBuzzer = /\bbuz\.(beep|tone|play|melody)\b/.test(src) || /\bbuzzer\b/i.test(src);
    const usesAccel =
        /\baccel\.(read|get)\b/.test(src) ||
        /\bmagnitude\b/.test(src) ||
        /\bshake\b/i.test(src) ||
        /\bfreefall\b/i.test(src);
    const usesButton =
        /\bbtn\.value\b/.test(src) ||
        /\b_check_button\b/.test(src) ||
        /\bBUTTON_PIN\b/.test(src) ||
        /\bPin\(BUTTON_PIN/.test(src);
    const usesNfc =
        /\bnfc\./.test(src) ||
        /\bNfcReader\b/.test(src) ||
        /\bread_command\b/.test(src) ||
        /\b_EXIT_TAGS\b/.test(src);

    let nfcTagCount = 0;
    const noteTags = src.match(/note_[a-g](?:_high)?/gi);
    if (noteTags) nfcTagCount = new Set(noteTags.map((t) => t.toLowerCase())).size;

    return {
        ledFrames,
        usesLeds: hasLedCall,
        usesBuzzer,
        usesAccel,
        usesButton,
        usesNfc,
        nfcTagCount,
        hasCode: src.trim().length > 0 && !src.trim().startsWith("# AI-generated"),
    };
}
