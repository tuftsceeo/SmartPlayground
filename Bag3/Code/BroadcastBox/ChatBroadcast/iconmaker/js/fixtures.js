/**
 * Source images this copy of the Icon Maker ships in assets/.
 *
 * The six fruit also have segment maps in maps/, so they reopen exactly as
 * they were converted; the rest load unsegmented and are segmented fresh.
 * Anything not listed here is opened through the file picker instead.
 *
 * One list, two readers: main.js's loadFixture() and the top bar's picker.
 */
export const FIXTURES = [
    "apple", "cherries", "grapes", "lemon", "orange", "watermelon",
    "dino", "dolphin", "griffin", "snake", "trex",
];
