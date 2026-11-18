/**
 * Catalog of the Chat Broadcast parts a variant may hide, relabel or restyle.
 *
 * Every selector must match markup in ../ChatBroadcast/index.html;
 * tools/variant_test.mjs checks that, so a renamed id fails the test
 * instead of silently doing nothing.
 *
 * Fields:
 *   id        stable name used in variant files
 *   name      plain words for people and for Claude
 *   view      splash | gallery | detail | workspace | code | everywhere
 *   sel       CSS selector (may be a comma list)
 *   canHide   false = locked: hiding it would leave someone stuck
 *   label     true = its own text can be replaced (icons inside stay)
 *   attr      relabel this attribute instead of text (e.g. placeholder)
 */
export const REGIONS = [
    // Splash (start screen)
    { id: 'splash-logo', name: 'start screen logo star', view: 'splash', sel: '.splash-logo', canHide: true },
    { id: 'splash-title', name: 'start screen title', view: 'splash', sel: '.splash-title', canHide: true, label: true },
    { id: 'splash-tagline', name: 'start screen tagline', view: 'splash', sel: '.splash-tagline', canHide: true, label: true },
    { id: 'splash-scratch', name: '"Start from scratch" card', view: 'splash', sel: '#btn-scratch', canHide: true, splashCard: true },
    { id: 'splash-scratch-title', name: '"Start from scratch" card heading', view: 'splash', sel: '#btn-scratch h3', canHide: false, label: true },
    { id: 'splash-scratch-sub', name: '"Start from scratch" card subtext', view: 'splash', sel: '#btn-scratch p', canHide: true, label: true },
    { id: 'splash-gallery', name: '"Browse examples" card', view: 'splash', sel: '#btn-gallery', canHide: true, splashCard: true },
    { id: 'splash-gallery-title', name: '"Browse examples" card heading', view: 'splash', sel: '#btn-gallery h3', canHide: false, label: true },
    { id: 'splash-gallery-sub', name: '"Browse examples" card subtext', view: 'splash', sel: '#btn-gallery p', canHide: true, label: true },
    { id: 'splash-saved', name: '"My saved games" card', view: 'splash', sel: '#btn-saved', canHide: true, splashCard: true },
    { id: 'splash-saved-title', name: '"My saved games" card heading', view: 'splash', sel: '#btn-saved h3', canHide: false, label: true },
    { id: 'splash-saved-sub', name: '"My saved games" card subtext', view: 'splash', sel: '#btn-saved p', canHide: true, label: true },
    { id: 'splash-card-icons', name: 'icons on the start screen cards', view: 'splash', sel: '.splash-card-icon', canHide: true },

    // Gallery (examples + my games)
    { id: 'gallery-new', name: 'gallery "new game" button', view: 'gallery', sel: '#btn-gallery-new', canHide: true },
    { id: 'gallery-title', name: 'gallery page heading', view: 'gallery', sel: '#gallery-title', canHide: true },
    { id: 'gallery-search', name: 'gallery search box', view: 'gallery', sel: '#gallery-search', canHide: true, attr: 'placeholder' },
    { id: 'gallery-chips', name: 'gallery tag filter chips', view: 'gallery', sel: '#gallery-chips', canHide: true },
    { id: 'station-catalog', name: 'send list to NFC Station button (advanced)', view: 'gallery', sel: '#btn-station-catalog', canHide: true },
    { id: 'nav-tabs', name: '"My games / Examples" tabs', view: 'gallery', sel: '.app-tabs', canHide: false },

    // Example detail
    { id: 'detail-preview', name: 'example practice window', view: 'detail', sel: '#detail-preview', canHide: true },
    { id: 'detail-desc', name: 'example description', view: 'detail', sel: '#detail-desc', canHide: true },
    { id: 'detail-tag-note', name: 'example "tags needed" note', view: 'detail', sel: '#detail-tag-note', canHide: true },
    { id: 'remix', name: 'example "remix" button', view: 'detail', sel: '#btn-remix', canHide: false, label: true },
    { id: 'use-as-is', name: 'example "use as-is" button', view: 'detail', sel: '#btn-use-as-is', canHide: true, label: true },

    // Workspace header
    { id: 'brand-home', name: 'home logo (top left)', view: 'everywhere', sel: '.brand-home', canHide: false },
    { id: 'open-saved-pill', name: '"open a saved game" pill in the header', view: 'workspace', sel: '#btn-open-saved-pill', canHide: true },
    { id: 'mode-pill', name: 'Box library pill', view: 'workspace', sel: '.mode-pill', canHide: false },
    { id: 'conn-chip', name: 'connection status chip', view: 'workspace', sel: '.conn-chip', canHide: true },
    { id: 'restart-box', name: 'restart device button', view: 'workspace', sel: '.btn-restart-box', canHide: true },
    { id: 'connect', name: 'connect button', view: 'workspace', sel: '.btn-connect-header', canHide: false },
    { id: 'more-menu', name: '⋮ more menu', view: 'workspace', sel: '#btn-more', canHide: false },
    { id: 'mode-gear', name: 'simple / advanced switch', view: 'workspace', sel: '#btn-mode-gear', canHide: false },
    { id: 'dev-mode', name: 'show logs item (advanced)', view: 'workspace', sel: '#btn-dev-mode', canHide: true },

    // Workspace title bar
    { id: 'game-name', name: 'game name', view: 'workspace', sel: '#btn-game-name', canHide: true },
    { id: 'new-game', name: 'new game icon button', view: 'workspace', sel: '#btn-new-game', canHide: true },
    { id: 'save-game', name: 'save icon button', view: 'workspace', sel: '#btn-save-game', canHide: true },
    { id: 'open-game', name: 'open saved game icon button', view: 'workspace', sel: '#btn-open-game', canHide: true },
    { id: 'send-box', name: '"Send to …" button', view: 'workspace', sel: '#btn-send-box', canHide: false, label: true },

    // Workspace body
    { id: 'preview-tabs', name: '"Simulation / Icons" tabs', view: 'workspace', sel: '.preview-toolbar', canHide: true },
    { id: 'icons-tab', name: '"Icons" tab', view: 'workspace', sel: '#btn-icons-view', canHide: true },
    { id: 'preview-col', name: 'simulator side', view: 'workspace', sel: '.preview-col', canHide: false },
    { id: 'ws-resizer', name: 'drag handle between chat and simulator', view: 'workspace', sel: '#ws-resizer', canHide: true },
    { id: 'chat-col', name: 'chat side', view: 'workspace', sel: '.chat-col', canHide: false },
    { id: 'chat-box', name: 'chat messages', view: 'workspace', sel: '#chat-box', canHide: false },
    { id: 'chat-input', name: 'chat text box', view: 'workspace', sel: '#user-input', canHide: false, attr: 'placeholder' },
    { id: 'chat-send', name: 'chat send button', view: 'workspace', sel: '#btn-send', canHide: false },

    // Code drawer
    { id: 'code-drawer', name: 'code drawer', view: 'code', sel: '#code-drawer', canHide: false },
    { id: 'code-versions', name: 'code version arrows', view: 'code', sel: '#btn-prev, #btn-next, #version-label', canHide: true },
    { id: 'code-download', name: 'code download button', view: 'code', sel: '#btn-download', canHide: true },
    { id: 'code-device-tabs', name: 'code device tabs', view: 'code', sel: '#code-device-tabs', canHide: true },
    { id: 'code-close', name: 'close code drawer button', view: 'code', sel: '#btn-close-code', canHide: false },

    // Dialogs (restyle only)
    { id: 'dialogs', name: 'pop-up dialogs', view: 'everywhere', sel: '.overlay-card', canHide: false },
    { id: 'unlock', name: 'magic code screen', view: 'everywhere', sel: '#modal-overlay', canHide: false },
];

export const REGION_BY_ID = Object.fromEntries(REGIONS.map(r => [r.id, r]));

/** Color and effect tokens from ChatBroadcast/css/app.css :root. */
export const TOKENS = [
    '--pink', '--pink-dark', '--purple', '--teal', '--teal-dark', '--yellow',
    '--ink', '--muted', '--border', '--bg', '--icon-ink',
    '--serve-bg', '--serve-fg', '--write-bg', '--write-fg', '--disabled-fill',
    '--scrim', '--overlay-shadow', '--shell-shadow', '--tab-active-bg', '--tab-active-fg',
];

/** Google Fonts a variant may use. */
export const FONTS = [
    'Nunito', 'Fredoka', 'Baloo 2', 'Quicksand', 'Lexend', 'Atkinson Hyperlegible',
    'Comic Neue', 'Patrick Hand', 'Poppins', 'Inter', 'Space Grotesk', 'Press Start 2P',
];

/** CSS properties allowed in `styles` (prefix match on the listed stems). */
export const STYLE_PROPS = [
    'color', 'background', 'background-color', 'background-image',
    'border', 'border-color', 'border-width', 'border-style', 'border-radius',
    'border-top', 'border-bottom', 'border-left', 'border-right',
    'box-shadow', 'text-shadow', 'outline',
    'font-family', 'font-size', 'font-weight', 'font-style', 'letter-spacing',
    'line-height', 'text-transform', 'text-align',
    'padding', 'padding-top', 'padding-bottom', 'padding-left', 'padding-right', 'gap',
];
