/**
 * Source images this copy of the Icon Maker ships in assets/.
 *
 * Listed names reopen through loadFixture(); anything else goes through the
 * file picker. A name with a matching maps/<name>.json reopens with its
 * segment decisions intact, so it comes back exactly as it was converted.
 *
 * NOT listed: the icons drawn procedurally by the station's
 * hand_author_icons.py (ball, cat, dog, heart, star and the rest of that
 * set). They have maps but no source image -- there is nothing for
 * loadFixture() to decode -- so they are edited by re-running that script,
 * or painted here from a blank grid.
 *
 * One list, two readers: main.js's loadFixture() and the top bar's picker.
 */
export const FIXTURES = [
    // In the icon library
    "airplane", "apple", "astronaut", "balloon", "blocks", "camel", "car",
    "cherries", "cloud", "deer", "dino", "doctor", "dolphin", "dove",
    "firefighter", "goldfish", "grapes", "hedgehog", "hospital", "leaf",
    "lemon", "lightning", "milk", "orange", "parrot", "pig", "police",
    "rain_cloud", "school", "ship", "snowflake", "strawberry", "teddy_bear",
    "train", "trex", "watermelon",

    // Converted but not promoted -- see the station's drafts/README.md
    "bicycle", "fire_truck", "goat", "grass", "griffin", "helicopter",
    "mail_carrier", "monkey", "mouse", "sandwich", "shark", "slide",
    "sparkles",

    // Ships as an image only, with no segment map
    "snake",
];
