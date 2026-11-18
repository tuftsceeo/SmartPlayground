/** The minimal contract every Playground Coder front end must meet. */
export const REQUIRED = {
    'chat-log': 'a chat column that shows the conversation',
    'chat-input': 'a text box for the message',
    'chat-send': 'a button that sends the message',
    'connect': 'a button that connects the Dial or Box',
    'send-to-device': 'a button that sends the game to the controller',
};
/** Parts a front end may add; each is backed by kit functions (SKILL.md). */
export const OPTIONAL = {
    'game-name': 'the game name field',
    'choices': 'Claude\'s suggested replies',
    'log': 'the activity log',
    'home': 'the start screen',
    'examples': 'the example games',
    'saved-games': 'saved games',
    'interview': 'the plan-a-game interview',
    'code-view': 'the code and its versions',
    'simulator': 'the simulator',
    'device-panel': 'the games on the controller',
    'distribute': 'sending a game to many devices',
};
const ALLOWED_SCRIPT_HOSTS = ['cdn.tailwindcss.com'];

/** @returns {string[]} problems; empty means the front end is OK. */
export function checkFrontEnd(html) {
    const problems = [];
    for (const [key, what] of Object.entries(REQUIRED)) {
        if (!new RegExp(`data-kit\\s*=\\s*["']${key}["']`).test(html)) problems.push(`Missing ${what} (data-kit="${key}").`);
    }
    for (const m of html.matchAll(/<script[^>]*\ssrc\s*=\s*["']([^"']+)["']/gi)) {
        let host = null;
        try { host = new URL(m[1], 'https://local.invalid/').host; } catch (_) {}
        if (host !== 'local.invalid' && !ALLOWED_SCRIPT_HOSTS.includes(host)) problems.push(`Script from ${m[1]} is not allowed; only ${ALLOWED_SCRIPT_HOSTS.join(', ')}.`);
    }
    return problems;
}

/** @returns {string[]} warnings (not errors), e.g. unknown data-kit values. */
export function warnFrontEnd(html) {
    const known = new Set([...Object.keys(REQUIRED), ...Object.keys(OPTIONAL)]);
    const warnings = [];
    for (const m of html.matchAll(/data-kit\s*=\s*["']([^"']+)["']/g)) {
        if (!known.has(m[1])) warnings.push(`Unknown part data-kit="${m[1]}"; the kit does nothing with it.`);
    }
    return [...new Set(warnings)];
}
