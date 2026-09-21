/**
 * api.js -- the Icon Maker's capabilities, without its chrome.
 *
 * Every verb here is something one of the Maker's buttons already does; this
 * module is the seam between "what the editor can do" and "what the toolbar
 * looks like", so a replacement UI -- the Maker's own, or ChatBroadcast's
 * drawer header around the iframe -- can drive the editor without reaching
 * into App internals or synthesising clicks on buttons it does not own.
 *
 * Two ways in, both live:
 *
 *   in-page    window.iconMaker.library.save()
 *   iframe     frame.contentWindow.iconMaker.library.save()
 *   postMessage  frame.contentWindow.postMessage(
 *                  {type:'iconmaker:call', id:1, method:'library.save'}, origin)
 *
 * The iframe route works because the Maker is served same-origin with its
 * host. The postMessage route exists so a host does not have to depend on
 * that staying true, and so a UI can be written against a serialisable
 * contract; it carries no File objects and no pixel arrays larger than one
 * icon.
 *
 * Nothing in the existing UI calls this module. It is additive: removing it
 * changes no on-screen behaviour.
 */

import { state, setState, onStateChange } from "./state/store.js";
import { doc } from "./state/doc.js";
import { FIXTURES } from "./fixtures.js";
import { listProfiles } from "./pipeline/profiles.js";
import { isValidIconName } from "../../js/ledicons/iconLibrary.js";
import { flatToPixels, library, setLibraryBackend } from "./libraryBridge.js";

/** The API version. Bump the major when a verb changes shape or disappears. */
export const API_VERSION = "1.0.0";

/**
 * Everything a UI needs to render a toolbar, in one serialisable object.
 * Deliberately flat and named for the concept rather than the internal field
 * (`brightness`, not `intensity`), so the contract survives a rename inside
 * the pipeline.
 */
function snapshot() {
    return {
        name: state.iconName,
        hasIcon: !!state.mode && !!doc.pixels,
        mode: state.mode,                       // 'exact' | 'quantize' | null
        segments: state.maxSegments,
        segmentsUsed: state.fills.length,
        canUndo: doc.undoStack.length > 0,
        brightness: state.intensity,            // 0..1
        profileId: state.profileId,
        tool: state.activeTool,                 // 'pencil' | 'eraser' | 'revert'
        loading: state.loading,
        error: state.loadError,
        problems: state.problems.length,
        // Present so a host can decide whether to offer device actions at all.
        // Inside ChatBroadcast's drawer this is false and should stay false:
        // the host owns the serial port.
        deviceConnected: state.deviceConnected,
        deviceRunning: state.deviceRunning,
    };
}

export function createIconMakerApi(app, { embedded = false } = {}) {
    const listeners = new Set();
    onStateChange(() => {
        const snap = snapshot();
        listeners.forEach((cb) => {
            try { cb(snap); } catch (e) { console.error("[iconMaker] listener threw", e); }
        });
    });

    const requireIcon = () => {
        if (!doc.pixels) throw new Error("no icon open — import an image or open one from the library first");
    };

    const api = {
        version: API_VERSION,

        /**
         * True when loaded as `iconmaker/?embed=1`. A UI reads this to decide
         * what a host-owned panel should show — notably that the hardware plug
         * must not appear, because the host owns the serial port.
         */
        embedded,

        /** Current editor state. Cheap; safe to call on every render. */
        getState: snapshot,

        /** Subscribe to state changes. Returns an unsubscribe function. */
        on(event, cb) {
            if (event !== "change") throw new Error(`unknown event "${event}" — only "change" exists`);
            listeners.add(cb);
            return () => listeners.delete(cb);
        },

        // ── the open document ────────────────────────────────────────────
        doc: {
            /** The 256 [r,g,b] triples currently shown, as a copy. */
            getPixels() {
                requireIcon();
                return doc.pixels.map((p) => p.slice());
            },
            /** A PNG data URL of the LED preview, for a host-drawn thumbnail. */
            getPreviewDataUrl() {
                requireIcon();
                return app.previewCanvas.toDataURL("image/png");
            },
            /**
             * Rename the open icon. The name is how a generated game refers to
             * the picture, so an unusable one is rejected rather than mangled.
             */
            rename(name) {
                const clean = (name || "").trim();
                if (!isValidIconName(clean)) {
                    throw new Error(`"${clean}" is not a usable icon name — letters, digits and _ or - only, up to 24 characters`);
                }
                setState({ iconName: clean });
                return clean;
            },
            undo() { app.undo(); },
            setTool(tool) {
                if (!["pencil", "eraser", "revert"].includes(tool)) throw new Error(`unknown tool "${tool}"`);
                setState({ activeTool: tool });
            },
            setBrightness(v) {
                const n = Number(v);
                if (!(n >= 0 && n <= 1)) throw new Error("brightness must be between 0 and 1");
                app.commitIntensity(n);
            },
            setSegments(n) { app.changeMaxSegments(Number(n)); },
            /** Show/hide the pixelation & segment-colour panel. Returns the new state. */
            toggleAdjust() {
                setState({ showAdjust: !state.showAdjust });
                return !!state.showAdjust;
            },
        },

        // ── getting a picture in ─────────────────────────────────────────
        source: {
            /** Sample images this build ships. */
            listSamples: () => FIXTURES.slice(),
            loadSample: (name) => app.loadFixture(name),
            /**
             * Import a File/Blob. Skipped by the postMessage bridge — pass the
             * file through the in-page object, or let the Maker's own picker
             * handle it.
             */
            importImage: (file) => app.loadFile(file),
            /** Target hardware. Fixed to the 16x16 matrix inside ChatBroadcast. */
            listProfiles: () => listProfiles().map((p) => ({ id: p.id, label: p.label })),
            setProfile: (id) => app.changeProfile(id),
            /** Clear and start from the apple sample. No confirm — the UI owns that. */
            newIcon: () => app.loadFixture("apple"),
        },

        // ── the game library: the contract ChatBroadcast actually cares about ──
        library: {
            /**
             * Point every read and write at a host-supplied store instead of
             * this window's own. ChatBroadcast injects its per-game icon store
             * here when it opens the drawer, so an edit is saved with the open
             * game rather than into a map shared by every game. Pass nothing to
             * go back to the local library.
             *
             * @param {{list, get, save, revert, isCustom}} [b]
             */
            setBackend: (b) => { setLibraryBackend(b); },

            list: () => library().list(),
            isCustom: (name) => library().isCustom(name),
            /** Open a saved icon for editing. */
            open(name) {
                const flat = library().get(name);
                if (!flat) throw new Error(`no icon named "${name}" in the library`);
                app.loadFromLibrary(name, flatToPixels(flat));
                return name;
            },
            /**
             * Save the open icon under its current name — into the library
             * this Maker is pointed at, and nowhere else. Embedded, that is
             * the open game, and this does NOT reach any device: the only
             * route to hardware is the host's own Send to Box/Dial.
             */
            async save() {
                requireIcon();
                await app.saveIcon();
                return state.iconName;
            },
            /** Drop an edit and restore the underlying icon. Destructive. */
            revert(name) {
                if (!library().isCustom(name)) throw new Error(`"${name}" has no custom edit to drop`);
                library().revert(name);
                app.library?.refreshList?.(name);
                return name;
            },
        },

        // ── file downloads ───────────────────────────────────────────────
        exportFile: {
            icon: () => app.exportIcon(),
            map: () => app.exportMap(),
            preview: () => app.exportPreview(),
        },
    };

    return api;
}

/** Resolve a dotted path like "library.save" against the api object. */
function resolve(api, path) {
    const parts = String(path || "").split(".");
    let owner = null;
    let fn = api;
    for (const part of parts) {
        if (fn == null) return null;
        owner = fn;
        fn = fn[part];
    }
    return typeof fn === "function" ? { fn, owner } : null;
}

/**
 * Answer `iconmaker:call` messages and broadcast `iconmaker:event`.
 *
 * Replies go back to the sender's own origin, never "*", so an icon's pixels
 * are not readable by any frame that happens to be listening.
 */
export function attachMessageBridge(api, target = window) {
    target.addEventListener("message", async (e) => {
        const msg = e.data;
        if (!msg || msg.type !== "iconmaker:call") return;
        const reply = (body) => e.source?.postMessage(
            { type: "iconmaker:result", id: msg.id, ...body },
            e.origin === "null" ? "*" : e.origin
        );
        const hit = resolve(api, msg.method);
        if (!hit) {
            reply({ ok: false, error: `unknown method "${msg.method}"` });
            return;
        }
        try {
            reply({ ok: true, value: await hit.fn.apply(hit.owner, msg.args || []) });
        } catch (err) {
            reply({ ok: false, error: String(err?.message || err) });
        }
    });

    api.on("change", (snap) => {
        // Only the embedder is told, and only when there is one. "*" is safe
        // here and only here: a snapshot is metadata (name, flags, counts) and
        // carries no pixels. Anything that returns image data goes through a
        // call, which replies to the caller's own origin.
        if (window.parent && window.parent !== window) {
            window.parent.postMessage({ type: "iconmaker:event", name: "change", detail: snap }, "*");
        }
    });
}
