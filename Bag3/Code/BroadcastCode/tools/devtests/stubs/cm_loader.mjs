/**
 * ESM loader hook: redirects editor.js's four esm.sh CodeMirror imports to
 * the local codemirror_stub.mjs, so editor.js can be imported under plain
 * Node. Registered via node:module's register() from role_state.mjs itself
 * -- no CLI flag needed, and no network access to esm.sh either.
 */
import { fileURLToPath } from 'node:url';
import { dirname, resolve as resolvePath } from 'node:path';

const STUB = 'file://' + resolvePath(dirname(fileURLToPath(import.meta.url)), 'codemirror_stub.mjs');

export async function resolve(specifier, context, nextResolve) {
    if (specifier.startsWith('https://esm.sh/')) {
        return { url: STUB, shortCircuit: true };
    }
    return nextResolve(specifier, context);
}
