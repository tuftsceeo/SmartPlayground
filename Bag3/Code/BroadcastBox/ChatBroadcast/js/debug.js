/**
 * debug.js — lightweight, always-visible console logging for app state.
 * Uses console.log/warn/error (not console.debug) so entries show up
 * under the default DevTools filter level without enabling "Verbose".
 */

const PREFIX = "[WandCoder]";
const t0 = performance.now();

function ts() {
    return `+${(performance.now() - t0).toFixed(0)}ms`;
}

export function dbg(scope, msg, data) {
    if (data !== undefined) {
        console.log(`${PREFIX} ${ts()} [${scope}] ${msg}`, data);
    } else {
        console.log(`${PREFIX} ${ts()} [${scope}] ${msg}`);
    }
}

export function dbgWarn(scope, msg, data) {
    if (data !== undefined) {
        console.warn(`${PREFIX} ${ts()} [${scope}] ${msg}`, data);
    } else {
        console.warn(`${PREFIX} ${ts()} [${scope}] ${msg}`);
    }
}

export function dbgError(scope, msg, data) {
    if (data !== undefined) {
        console.error(`${PREFIX} ${ts()} [${scope}] ${msg}`, data);
    } else {
        console.error(`${PREFIX} ${ts()} [${scope}] ${msg}`);
    }
}

/** Group related logs visually in the console (collapsed by default). */
export function dbgGroup(scope, label, fn) {
    console.groupCollapsed(`${PREFIX} ${ts()} [${scope}] ${label}`);
    try {
        fn();
    } finally {
        console.groupEnd();
    }
}
