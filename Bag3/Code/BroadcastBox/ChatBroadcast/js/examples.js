export const EXAMPLES = [
    {
        id: "melody",
        name: "Melody",
        emoji: "🎵",
        category: "sound",
        description: "Tap each note-tag to play a tune.",
        tagNote: "8 NFC tags",
        tags: ["note_c", "note_d", "note_e", "note_f", "note_g", "note_a", "note_b", "note_c_high"],
        starterPrompt: "Start from the Melody example — one tag per note.",
    },
    {
        id: "freezedance",
        name: "Freeze Dance",
        emoji: "❄️",
        category: "color",
        description: "Move, then freeze when the music stops.",
        tagNote: null,
        tags: ["freezedance"],
        starterPrompt: "Start from Freeze Dance — move and freeze game.",
    },
    {
        id: "rainbow",
        name: "Rainbow",
        emoji: "🌈",
        category: "color",
        description: "Shake for color.",
        tagNote: null,
        tags: ["rainbow"],
        starterPrompt: "Start from Rainbow — shake for color.",
    },
    {
        id: "cooking",
        name: "Cooking",
        emoji: "🍳",
        category: "multi",
        description: "Recipe steps with ingredient tags.",
        tagNote: "Multi-tag",
        tags: ["cooking"],
        starterPrompt: "Start from Cooking — recipe steps game.",
    },
    {
        id: "jumpin",
        name: "Jump In",
        emoji: "🦘",
        category: "color",
        description: "Simple jump game — great first project.",
        tagNote: null,
        tags: ["jumpin"],
        starterPrompt: "Make a simple jump game where shaking makes the wand light up.",
    },
];

export const CATEGORIES = [
    { id: "all", label: "All" },
    { id: "sound", label: "🎵 Sound" },
    { id: "color", label: "🎨 Color" },
    { id: "multi", label: "🏷️ Multi-tag" },
];

export function findExample(id) {
    return EXAMPLES.find((e) => e.id === id);
}
