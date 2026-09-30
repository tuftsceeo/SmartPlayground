/**
 * Starter ideas for the chat, and the guided "Help me make a game" steps.
 *
 * Ideas are tagged with the device roles they need (roles.js keys). Each
 * new chat draws a few, always including at least one that uses a device
 * other than the wand, so teachers see what the display and Splat can do.
 * A device added to roles.js gets ideas here (knowledge/ADDING_A_DEVICE.md).
 */

/** @type {{text: string, icon: string, roles: string[]}[]} */
export const STARTER_IDEAS = [
    // Wand only
    { text: 'Every wand glows a different color when the button is pressed', icon: 'palette', roles: ['wand'] },
    { text: 'Shake the wand to make a rainbow', icon: 'rainbow', roles: ['wand'] },
    { text: 'Play a happy sound when a child taps the star card', icon: 'nfcCard', roles: ['wand'] },
    { text: 'Show a smiley face when the wand is held upright and a sleepy face when it lies flat', icon: 'wand', roles: ['wand'] },
    { text: 'Hold the wand still like a statue until it turns green', icon: 'snowflake', roles: ['wand'] },
    { text: 'Jump with the wand to light up one more star each time', icon: 'sparkles', roles: ['wand'] },
    { text: 'Tap the red, blue or yellow card and the wand turns that color', icon: 'palette', roles: ['wand'] },
    { text: 'Tilt the wand to play high and low notes', icon: 'music', roles: ['wand'] },
    { text: 'Freeze dance: my wand starts and stops the music, the children dance', icon: 'snowflake', roles: ['wand'] },
    { text: 'Two teams: tap your team card, then race to the goal card', icon: 'gamepad', roles: ['wand'] },
    // Icon display
    { text: 'Show a whale on the big display when someone shakes a wand', icon: 'grid-3x3', roles: ['wand', 'icon'] },
    { text: 'Count how many cards the class taps, shown as stars on the display', icon: 'grid-3x3', roles: ['wand', 'icon'] },
    { text: 'The display shows which team reached the goal first', icon: 'grid-3x3', roles: ['wand', 'icon'] },
    { text: 'The display shows an animal and children find the matching card', icon: 'grid-3x3', roles: ['wand', 'icon'] },
    { text: 'A countdown on the display, then every wand lights up', icon: 'grid-3x3', roles: ['wand', 'icon'] },
    // Splat Companion
    { text: 'Jump on the Splat to make it turn green and bark', icon: 'cable', roles: ['splat'] },
    { text: 'Each Splat plays a different animal sound', icon: 'volume-2', roles: ['splat'] },
    { text: 'Press the Splat and every wand lights up the same color', icon: 'cable', roles: ['wand', 'splat'] },
    { text: 'Press the wand button to make the Splat light up', icon: 'cable', roles: ['wand', 'splat'] },
    { text: 'Splat, wands and the display: every Splat press adds a block on the display', icon: 'cable', roles: ['wand', 'splat', 'icon'] },
    // Questions
    { text: 'What can the wand show on its lights?', icon: 'message-circle', roles: ['wand'] },
    { text: 'What can the big display and the Splat do?', icon: 'message-circle', roles: ['icon', 'splat'] },
];

/**
 * Pick `n` ideas at random, at least one of which uses a non-wand device.
 * @param {number} n
 * @param {() => number} [rand]  0..1 random source, for tests
 */
export function drawStarterIdeas(n = 4, rand = Math.random) {
    const pool = STARTER_IDEAS.slice();
    for (let i = pool.length - 1; i > 0; i--) {
        const j = Math.floor(rand() * (i + 1));
        [pool[i], pool[j]] = [pool[j], pool[i]];
    }
    const picked = pool.slice(0, n);
    if (!picked.some(x => x.roles.some(r => r !== 'wand'))) {
        const other = pool.find(x => x.roles.some(r => r !== 'wand'));
        picked[picked.length - 1] = other;
    }
    return picked;
}

/**
 * Guided mode: a few instant choices, answered in the app without a model
 * call, then turned into one request. Each option's `says` is its phrase in
 * that request.
 */
export const GUIDED_STEPS = [
    {
        question: 'Which devices will the children use?',
        options: [
            { label: 'Just wands', says: 'wands' },
            { label: 'Wands and the big display', says: 'wands and the icon display' },
            { label: 'Wands and the Splat', says: 'wands and the Splat Companion' },
            { label: 'The Splat on its own', says: 'the Splat Companion' },
        ],
    },
    {
        question: 'How do the children play?',
        options: [
            { label: 'Tap a card', says: 'The children tap cards' },
            { label: 'Shake or move', says: 'The children shake or move' },
            { label: 'Press a button or the Splat', says: 'The children press a button or the Splat' },
            { label: 'Take turns', says: 'The children take turns' },
        ],
    },
    {
        question: 'What should happen?',
        options: [
            { label: 'Lights and colors', says: 'lights and colors change' },
            { label: 'Sounds and music', says: 'sounds and music play' },
            { label: 'A picture or a count', says: 'a picture or a count shows on the display' },
            { label: 'Surprise me', says: 'something fun happens that you choose' },
        ],
    },
];

/** The request built from one chosen option per GUIDED_STEPS entry. */
export function guidedPrompt(answers) {
    const [devices, play, happen] = answers;
    return `Make a simple game for my kindergarten class using ${devices.says}. ` +
        `${play.says}, and ${happen.says}. Keep it short and easy to explain, ` +
        `and offer me a few ways to change it.`;
}
