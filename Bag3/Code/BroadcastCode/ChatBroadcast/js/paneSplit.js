/** Draggable divider between the chat column and the simulator preview.
 * .chat-col gets a fixed pixel width (not a flex-basis) so dragging can set
 * it directly; .preview-col is flex:1 and just takes whatever's left. The
 * chosen width is persisted in localStorage, same pattern as uiMode.js. */

const KEY = "wandcoder.chatWidth";
const MIN_WIDTH = 260;
const MAX_WIDTH = 480;
const MIN_PREVIEW_WIDTH = 180;
const DEFAULT_WIDTH = 340;
const KEYBOARD_STEP = 24;

function loadWidth() {
    try {
        const stored = Number(localStorage.getItem(KEY));
        if (Number.isFinite(stored) && stored >= MIN_WIDTH && stored <= MAX_WIDTH) return stored;
    } catch (_) {}
    return DEFAULT_WIDTH;
}

function saveWidth(px) {
    try {
        localStorage.setItem(KEY, String(Math.round(px)));
    } catch (_) {}
}

/** How wide .chat-col is allowed to get right now — bounded by MAX_WIDTH
 * and by leaving at least MIN_PREVIEW_WIDTH for the sim panel, so dragging
 * can never push the preview off-screen on a narrow browser window. */
function currentMaxWidth(wsBody, resizer) {
    const railWidth = wsBody.querySelector('.role-rail')?.getBoundingClientRect().width || 0;
    const resizerWidth = resizer.getBoundingClientRect().width;
    const available = wsBody.getBoundingClientRect().width - railWidth - resizerWidth;
    return Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, available - MIN_PREVIEW_WIDTH));
}

export function initPaneSplit() {
    const resizer = document.getElementById('ws-resizer');
    const chatCol = document.querySelector('.chat-col');
    const wsBody = document.querySelector('.ws-body');
    if (!resizer || !chatCol || !wsBody) return;

    chatCol.style.width = `${loadWidth()}px`;

    let dragging = false;
    let startX = 0;
    let startWidth = 0;

    const clientXOf = (e) => (e.touches ? e.touches[0].clientX : e.clientX);

    const onMove = (e) => {
        if (!dragging) return;
        const maxWidth = currentMaxWidth(wsBody, resizer);
        const next = Math.min(maxWidth, Math.max(MIN_WIDTH, startWidth + (clientXOf(e) - startX)));
        chatCol.style.width = `${next}px`;
        e.preventDefault();
    };

    const stopDragging = () => {
        if (!dragging) return;
        dragging = false;
        resizer.classList.remove('dragging');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        saveWidth(parseInt(chatCol.style.width, 10) || DEFAULT_WIDTH);
        window.removeEventListener('mousemove', onMove);
        window.removeEventListener('mouseup', stopDragging);
        window.removeEventListener('touchmove', onMove);
        window.removeEventListener('touchend', stopDragging);
    };

    const startDragging = (e) => {
        dragging = true;
        startX = clientXOf(e);
        startWidth = chatCol.getBoundingClientRect().width;
        resizer.classList.add('dragging');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', stopDragging);
        window.addEventListener('touchmove', onMove, { passive: false });
        window.addEventListener('touchend', stopDragging);
        e.preventDefault();
    };

    resizer.addEventListener('mousedown', startDragging);
    resizer.addEventListener('touchstart', startDragging, { passive: false });

    // Arrow-key nudge for keyboard/screen-reader users (role="separator").
    resizer.addEventListener('keydown', (e) => {
        if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
        const maxWidth = currentMaxWidth(wsBody, resizer);
        const delta = e.key === 'ArrowRight' ? KEYBOARD_STEP : -KEYBOARD_STEP;
        const next = Math.min(maxWidth, Math.max(MIN_WIDTH, chatCol.getBoundingClientRect().width + delta));
        chatCol.style.width = `${next}px`;
        saveWidth(next);
        e.preventDefault();
    });
}
