/**
 * Code per device role, with a version history for each, like the web app's
 * editor (ChatBroadcast/js/editor.js) without CodeMirror or the DOM.
 */
export function createVersions(roles) {
    const store = Object.fromEntries(roles.map(r => [r, { list: [], index: -1 }]));
    const ensure = (role) => (store[role] ||= { list: [], index: -1 });
    return {
        /** Current code for one role ('' if none). */
        get(role) {
            const s = ensure(role);
            return s.index >= 0 ? s.list[s.index].code : '';
        },
        /** Every role that has code, as {role: code}. */
        all() {
            const out = {};
            for (const [role, s] of Object.entries(store)) if (s.index >= 0 && s.list[s.index].code.trim()) out[role] = s.list[s.index].code;
            return out;
        },
        /** Add a version and make it current. Same code as now: no new version. */
        save(role, code, label = 'AI generated') {
            const s = ensure(role);
            if (s.index >= 0 && s.list[s.index].code === code) return;
            s.list = s.list.slice(0, s.index + 1);
            s.list.push({ code, label, t: Date.now() });
            s.index = s.list.length - 1;
        },
        prev(role) { const s = ensure(role); if (s.index > 0) s.index--; },
        next(role) { const s = ensure(role); if (s.index < s.list.length - 1) s.index++; },
        clear() { for (const s of Object.values(store)) { s.list = []; s.index = -1; } },
        /** Plain copy for kit.state: {role: {list:[{label,t}], index}}. */
        summary() {
            return Object.fromEntries(Object.entries(store).map(([r, s]) => [r, {
                index: s.index, list: s.list.map(v => ({ label: v.label, t: v.t })),
            }]));
        },
    };
}
