/** Vertical resize for the advanced-mode serial drawer (entire panel). */

const KEY = 'wandcoder.serialDrawerHeight';
const MIN_HEIGHT = 120;
const MAX_HEIGHT = 560;
const DEFAULT_HEIGHT = 220;
const COLLAPSED_MIN = 40;
const KEYBOARD_STEP = 24;

function loadHeight() {
    try {
        const stored = Number(localStorage.getItem(KEY));
        if (Number.isFinite(stored) && stored >= MIN_HEIGHT && stored <= MAX_HEIGHT) {
            return stored;
        }
    } catch (_) {}
    return DEFAULT_HEIGHT;
}

function saveHeight(px) {
    try {
        localStorage.setItem(KEY, String(Math.round(px)));
    } catch (_) {}
}

function clampHeight(px) {
    const viewportCap = Math.floor(window.innerHeight * 0.65);
    return Math.min(MAX_HEIGHT, viewportCap, Math.max(MIN_HEIGHT, px));
}

function setDrawerHeight(panel, px) {
    const next = clampHeight(px);
    panel.style.height = `${next}px`;
    return next;
}

function clearDrawerHeight(panel) {
    panel.style.height = '';
}

/**
 * @param {{ onResize?: () => void, onOpenChange?: (open: boolean) => void }} [opts]
 */
export function initSerialSplit(opts = {}) {
    const onResize = typeof opts === 'function' ? opts : opts.onResize;
    const onOpenChange = typeof opts === 'function' ? null : opts.onOpenChange;

    const resizer = document.getElementById('serial-log-resizer');
    const panel = document.getElementById('serial-log-panel');
    if (!resizer || !panel) return;

    const applyOpenHeight = () => {
        if (panel.classList.contains('open')) {
            setDrawerHeight(panel, loadHeight());
        } else {
            clearDrawerHeight(panel);
        }
        onResize?.();
    };
    applyOpenHeight();

    // Host toggles .open; keep height in sync when that happens.
    new MutationObserver(() => applyOpenHeight()).observe(panel, {
        attributes: true,
        attributeFilter: ['class'],
    });

    let dragging = false;
    let startY = 0;
    let startHeight = 0;

    const clientYOf = (e) => (e.touches ? e.touches[0].clientY : e.clientY);

    const onMove = (e) => {
        if (!dragging) return;
        const next = clampHeight(startHeight + (startY - clientYOf(e)));
        panel.style.height = `${next}px`;
        if (!panel.classList.contains('open') && next > COLLAPSED_MIN + 20) {
            panel.classList.add('open');
            onOpenChange?.(true);
        }
        onResize?.();
        e.preventDefault();
    };

    const stopDragging = () => {
        if (!dragging) return;
        dragging = false;
        resizer.classList.remove('dragging');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        const h = panel.getBoundingClientRect().height;
        if (panel.classList.contains('open')) {
            saveHeight(h);
        }
        window.removeEventListener('mousemove', onMove);
        window.removeEventListener('mouseup', stopDragging);
        window.removeEventListener('touchmove', onMove);
        window.removeEventListener('touchend', stopDragging);
    };

    const startDragging = (e) => {
        dragging = true;
        startY = clientYOf(e);
        startHeight = panel.getBoundingClientRect().height || loadHeight();
        if (!panel.classList.contains('open')) {
            panel.classList.add('open');
            onOpenChange?.(true);
            startHeight = setDrawerHeight(panel, loadHeight());
        }
        resizer.classList.add('dragging');
        document.body.style.cursor = 'ns-resize';
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
        if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
        if (!panel.classList.contains('open')) {
            panel.classList.add('open');
            onOpenChange?.(true);
            setDrawerHeight(panel, loadHeight());
        }
        const delta = e.key === 'ArrowUp' ? KEYBOARD_STEP : -KEYBOARD_STEP;
        const next = setDrawerHeight(
            panel,
            (parseInt(panel.style.height, 10) || loadHeight()) + delta,
        );
        saveHeight(next);
        onResize?.();
        e.preventDefault();
    });
}
