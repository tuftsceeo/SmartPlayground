/** Horizontal resize for the code drawer (drag left edge). */

const KEY = 'wandcoder.codeDrawerWidth';
const MIN_WIDTH = 320;
const MAX_WIDTH = 900;
const DEFAULT_WIDTH = 480;
const KEYBOARD_STEP = 32;

function loadWidth() {
    try {
        const stored = Number(localStorage.getItem(KEY));
        if (Number.isFinite(stored) && stored >= MIN_WIDTH && stored <= MAX_WIDTH) {
            return stored;
        }
    } catch (_) {}
    return DEFAULT_WIDTH;
}

function saveWidth(px) {
    try {
        localStorage.setItem(KEY, String(Math.round(px)));
    } catch (_) {}
}

function clampWidth(px) {
    const viewportCap = Math.floor(window.innerWidth * 0.92);
    return Math.min(MAX_WIDTH, viewportCap, Math.max(MIN_WIDTH, px));
}

function applyWidth(drawer, px) {
    const next = clampWidth(px);
    drawer.style.width = `${next}px`;
    return next;
}

export function initCodeDrawerSplit() {
    const drawer = document.getElementById('code-drawer');
    const resizer = document.getElementById('code-drawer-resizer');
    if (!drawer || !resizer) return;

    applyWidth(drawer, loadWidth());

    let dragging = false;
    let startX = 0;
    let startWidth = 0;

    const clientXOf = (e) => (e.touches ? e.touches[0].clientX : e.clientX);

    const onMove = (e) => {
        if (!dragging) return;
        // Left edge: dragging left grows the drawer (X decreases).
        const next = clampWidth(startWidth + (startX - clientXOf(e)));
        drawer.style.width = `${next}px`;
        e.preventDefault();
    };

    const stopDragging = () => {
        if (!dragging) return;
        dragging = false;
        resizer.classList.remove('dragging');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        saveWidth(parseInt(drawer.style.width, 10) || DEFAULT_WIDTH);
        window.removeEventListener('mousemove', onMove);
        window.removeEventListener('mouseup', stopDragging);
        window.removeEventListener('touchmove', onMove);
        window.removeEventListener('touchend', stopDragging);
    };

    const startDragging = (e) => {
        dragging = true;
        startX = clientXOf(e);
        startWidth = drawer.getBoundingClientRect().width;
        resizer.classList.add('dragging');
        document.body.style.cursor = 'ew-resize';
        document.body.style.userSelect = 'none';
        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', stopDragging);
        window.addEventListener('touchmove', onMove, { passive: false });
        window.addEventListener('touchend', stopDragging);
        e.preventDefault();
    };

    resizer.addEventListener('mousedown', startDragging);
    resizer.addEventListener('touchstart', startDragging, { passive: false });

    resizer.addEventListener('keydown', (e) => {
        if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
        const delta = e.key === 'ArrowLeft' ? KEYBOARD_STEP : -KEYBOARD_STEP;
        const next = applyWidth(
            drawer,
            (parseInt(drawer.style.width, 10) || loadWidth()) + delta,
        );
        saveWidth(next);
        e.preventDefault();
    });
}
