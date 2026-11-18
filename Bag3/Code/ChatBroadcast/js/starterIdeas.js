/**
 * Starter ideas for the chat, and the guided "Help me make a game" steps.
 *
 * Ideas are tagged with the device roles they need (roles.js keys). Each
 * new chat draws one question about the devices and two game ideas, at least
 * one of the three using a device other than the wand, so teachers see what
 * the display can do. Questions carry `question: true`.
 * A device added to roles.js gets ideas here (knowledge/ADDING_A_DEVICE.md).
 */

/** @type {{text: string, icon: string, roles: string[], question?: boolean}[]} */
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
    // Questions
    { text: 'What can the wand show on its lights?', icon: 'message-circle', roles: ['wand'], question: true },
    { text: 'What can the big display do?', icon: 'message-circle', roles: ['icon'], question: true },
];

/** Fisher-Yates shuffle of a copy of `list`. */
function shuffled(list, rand) {
    const out = list.slice();
    for (let i = out.length - 1; i > 0; i--) {
        const j = Math.floor(rand() * (i + 1));
        [out[i], out[j]] = [out[j], out[i]];
    }
    return out;
}

const usesOtherDevice = x => x.roles.some(r => r !== 'wand');

/**
 * One question and two game ideas, question first. At least one of the
 * three uses a non-wand device.
 * @param {() => number} [rand]  0..1 random source, for tests
 */
export function drawStarterIdeas(rand = Math.random) {
    const [question] = shuffled(STARTER_IDEAS.filter(x => x.question), rand);
    const games = shuffled(STARTER_IDEAS.filter(x => !x.question), rand);
    const picked = games.slice(0, 2);
    if (!usesOtherDevice(question) && !picked.some(usesOtherDevice)) {
        picked[1] = games.find(usesOtherDevice);
    }
    return [question, ...picked];
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
        ],
    },
    {
        question: 'How do the children play?',
        options: [
            { label: 'Tap a card', says: 'The children tap cards' },
            { label: 'Shake or move', says: 'The children shake or move' },
            { label: 'Press a button', says: 'The children press the wand button' },
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
