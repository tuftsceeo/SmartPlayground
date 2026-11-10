# Icon feedback (new agent-drawn icons)

Collected one at a time, 2026-11-06. No drawing changes until all feedback is in.

| name | verdict | notes |
|---|---|---|
| bee | fix | OK overall. Stripes should be yellow and black/dark gray; wings too small, read as ears — make bigger. |
| frog | redraw | Really bad: legs tiny, mouth/face huge, weird red lips; looks like an alien or jelly bean with a mouth. Bad perspective (head-on). Complete redraw from the SIDE view. Also: does not match existing animal style. |
| goat | fix | A little better than frog. Eye far too large — at this size use a single black pixel (not 6px). The "beard" makes the neck look weird. User message said "try" followed by a screenshot (saved at /private/tmp/claude-505/-Users-jcross04-Documents-GitHub-SmartPlayground/83baee18-60a2-4157-9d63-542e9c73ac54/images/1.png): cyan side-view goat, orange horns, pink nose; unclear if reference or current state. Also: style mismatch with existing animals. |
| lion | redraw | As bad as the frog: reads like a sad emoji with an orange border. Redo in profile, or at least with simple shading. Also: style mismatch with existing animals. |
| monkey | fix | OK. Tail should not touch the body at the top (currently makes a full ring). |
| mouse | approve | Good as is. |
| octopus | fix | Fine overall. For kids, 8 legs is better; color should differ from spider. |
| owl | fix | 4x4 eyes too large; try 3x3. Add flat two-tone shading on body and beak. Also: style mismatch with existing animals. |
| penguin | fix | OK. The blue color is odd. |
| polar_bear | fix | Light shading would help; smaller eyes for scale in a side view. User attached two pixel-art references (images/2.png: front-view bear head; images/3.png: side-view walking bear with light shading) in /private/tmp/claude-505/-Users-jcross04-Documents-GitHub-SmartPlayground/83baee18-60a2-4157-9d63-542e9c73ac54/images/ — apparently side view (3.png) is the style target; confirm if needed. |
| shark | redraw | Needs a redo. Method for later: look at the example png in the folder and how the dolphin png relates to the dolphin icon, then use a similar process to make the shark icon from the shark png. |
| worm | replace? | Looks like a pink mustache on top of the ground; a worm should be underground. Suggest trying ant or caterpillar instead — worm is hard to do (needs darker banding like an earthworm). |
| griffin | redraw | Redraw not great; refer to the reference png. Same problem as shark and shrimp: converting the png with "toned outlines" to the icon went badly. Remove some of the toned outline; keep the two-tone flat shading. Side view, so AGAIN a 1-pixel eye (not 2x2); eye must fit animal scale. |
| goldfish (existing name, not in the 42) | redraw | Looks like a shrimp. Same png-to-icon conversion problem as shark/griffin (toned outlines; fix by trimming some outline, keeping flat two-tone shading). |
| sandwich | redraw | Colors are bad but OK. Goes edge to edge on the display — too wide. Should read as a sandwich; consider some perspective and two-tone shading (single-level shadow) instead of the toned outline around the bread only. |
| sparkles | approve | Approved as is. |
| grass | fix | Grass SHOULD go edge to edge (end to end). Currently has a round bottom, like a pixelated vignette — make the bottom straight/full width. |
| sprout | approve | Good. Related new-icon ideas (not changes to sprout): add seed and other plant growth stages, a watering can, and a sun with proper rays instead of weird blotches. |
| ocean | redraw | Too regular, looks like blue mountains. Why is there a sun? Try an underwater scene instead. |
| forest | fix | Fine, but needs clearer distinction between the tree colors. |
| desert | approve | Good as is. |
| pond | approve | Fine. |
| (new icon ideas) | add | More ecosystems: mountain (priority — students are in California), jungle, plains/grasslands, space, other ecosystems. |
| igloo | drop? (pending) | Concern about culturally respectful representation; igloos are not common. Prefer other polar/tundra ecosystem representations, and add dwellings from other ecosystems too (e.g. desert-style dwellings) for balance. Verdict inferred as drop/replace — confirm. |
| helicopter | fix | Fine, but why school-bus yellow? Reconsider the color. |
| bicycle | fix | Frame is stretched vertically / too tall. Old version was better (revert or base on it). Note: these kids likely ride tricycles (relevant to tricycle icon next). |
| tricycle | redraw | Looks like an old-school Victorian (penny-farthing) bike. Needs three wheels visible, so use an isometric-ish / 3/4 view. |
| fire_truck | fix | Old two-tone / single-shadow version was better — revert to or base on that style. |
| ambulance | fix | Use the bus wheels (best ones) — same wheel representation on fire_truck, car, ambulance, dump_truck, etc. across all vehicles. |
| dump_truck | fix | Currently reads as a cement mixer (user: "it is fine" as a concept, but not a dump truck). Needs two-tone shading and the bus ("good") wheels. Clarify: keep as cement_mixer and/or redraw a true dump truck. |
| mail_carrier | redraw | Body shape is quite different from doctor/firefighter/police — use those existing icons as the basis for general humans. All people icons should show equitable representation of genders, races and disabilities; career pathways shown as equitable, accessible and positive for all students. |
| (addendum to mail_carrier / all people icons) | guideline | Be respectful. Do not promote stereotypes. Be sensitive and empowering in representation. |
| mail | fix | Good shape. Remove the stamp (no stamp on the flap side). |
| book | fix | Cover color only shows at the bottom — show it properly. A library should have books (plural) — consider a multi-book/library version. |
| (global guideline) | guideline | For all icons: draw inspiration from common emoji. Images recognizable at ~10pt font size will also work well at 16x16. (Shopping_cart verdict still pending.) |
| shopping_cart | fix | OK. Make it taller? Wheels like the bus wheels. |
| slide | fix (minor) | Good, has some shading, but could be clearer/more readable. |
| swings | redraw | The two swings have merged together — need two separate swings. Alternative: a single swing rendered in more detail with simple shading. |
| seesaw | fix | OK, needs shading. Idea for ALL playground equipment: add "children"/meeple-style figures on it (apply equitable-representation guideline). |
| (clarifies seesaw / playground idea) | guideline | "Meeple" = simple Playmobil-style figures. (monkey_bars verdict still pending.) |
| monkey_bars | fix | Has a child figure, which is better, but hard to recognize as monkey bars and has no shading. |
| sandbox | fix (minor) | Nice. Add shading? |
| bubbles | approve | Good as is. |
| jump_rope | redraw | Child has huge eyes ("idees" likely eyes), no diversity, weird hands. Why is there a rope both above and below the child? Fix rope depiction; apply equitable-representation and simple Playmobil-style figure guidelines. |
| (jump_rope clarification) | note | "idees" = huge eyes, confirmed. |
| splat | fix | Round the tips of the splat. No red dot (the 2x2 dot in the top-left of the screenshot). Plan for the splat body ("white" area, shown cyan/white) to be a color variable/parameter so it can be recolored. Screenshot: /private/tmp/claude-505/-Users-jcross04-Documents-GitHub-SmartPlayground/83baee18-60a2-4157-9d63-542e9c73ac54/images/4.png |
| hand | fix | Okay-ish, but thumb looks smaller/thinner than the fingers. Remember race and representation (skin tone not default). Representation ideas across people icons: a kid in a wheelchair, vitiligo, painted nails, etc. |
| tooth | approve | OK. Not originally requested by user (came from an agent brief), but user is fine keeping it; fits a "senses/body" set. |

## New icon ideas (user direction; ideation only, nothing drawn)

- **Senses / body set:** eyes (human, not creepy), nose, ears, mouth, feet, lightbulb/idea. (tooth already fits.)
- **Game concepts:** go, stop, traffic lights, ready, play, pause, win, lose, right, wrong, error, score, point, end, start, run, walk, fast, slow, etc.
- **Wand / input / output concepts:** lights, colors, button press, button release, freeze, rotate, spin, flip, yaw, pitch, roll, left, right, etc.
- **Ecosystems:** mountain (priority, California), jungle, plains/grasslands, space, polar/tundra alternative to igloo, dwellings from other ecosystems.
- **Other:** seed and plant growth stages, watering can, sun with proper rays, caterpillar/ant (worm replacement), underwater scene (ocean replacement), cement_mixer vs true dump truck, tricycle-friendly vehicles.

## Global guidelines from user

- Original human-drawn icons were chosen on purpose: clean up, don't rework.
- Side view animals: single-pixel eye scaled to the animal; two-tone flat shading, trim toned outlines.
- Vehicles: reuse the bus wheels everywhere.
- People: equitable, respectful, non-stereotyped, empowering; diverse skin tones, abilities (wheelchair, vitiligo, painted nails, etc.); simple Playmobil-style figures based on doctor/firefighter/police.
- Draw inspiration from common emoji; must read at ~10pt.
| (goldfish addendum) | note | User sent a screenshot of the current goldfish icon (/private/tmp/claude-505/-Users-jcross04-Documents-GitHub-SmartPlayground/83baee18-60a2-4157-9d63-542e9c73ac54/images/5.png): pink/salmon, shrimp-like, noisy. Intended as an example of a bad png-to-icon conversion, to guide the conversion approach for dolphin, shark, griffin, etc. |
| (goldfish correction) | relabel | The icon named goldfish IS a shrimp (images/5.png is that icon): mislabeled, needs relabeling as shrimp. It is not a bad drawing of a fish. If a goldfish or other fish is wanted, draw it from scratch. Supersedes the earlier goldfish "redraw" row and addendum. |

## Animal sheet review, round 2 (2026-11-06, after rev 11)

User's verdicts on the full animal sheet. Standard: children's-cartoon caricature of distinctive features, not biological accuracy.

| name | verdict | notes |
|---|---|---|
| dog | good | Cartoon caricature: ears, nose, tongue. |
| deer | good | Elk/moose silhouette, four legs, antlers. |
| dolphin | great | Shading, flippers, belly, tail, bottlenose head. |
| dove | great | Olive branch helps. |
| elephant, elephant2 | great | |
| shrimp | great | |
| lion | good | Mane, muzzle colouring, ears. |
| monarch, torogoz | great | Colouring. |
| pig, swan | great | |
| shark | great | Rev 9. |
| fish, hedgehog, sheep, snake, turtle, teddy_bear, mouse | fine | |
| trex, octopus | ok | |
| goat | fix | Weird shape, missing limbs/detail. |
| frog | fix | Weird shape, missing limbs/detail. |
| monkey | fix (minor) | Head somewhat huge; ears and tail good. |
| owl | fix | Weird body shape, pupils too small, needs visible wings. |
| parrot | fix | Use best-known colouring (macaw). |
| penguin | fix | Eyes copied from the human style; use animal eyes. |
| polar_bear | redraw | Worst of the set; head shape very wrong. |
| spider | fix | Reads as smile emoji with squiggles and a white square on top. |
| whale | fix | Iffy; whale2 better, neither as good as dolphin. |
| worm | fix | Why is it flying above the grass? |
| griffin | fix | Better, but stumpy legs with no joints; fourth leg detached. |
| caterpillar | redraw | Kids expect the "hungry caterpillar": stacked round segments. |

## Target standard: the dolphin (user, 2026-11-06)

All icons should aim for the cartoon level of `dolphin`. How the dolphin does it:

- **Light comes from above (the rule):** light tone on top surfaces, darker tone on undersides, bellies and legs in shadow.
- **Three tones per subject:** a mid body colour (110,80,70), a darker tone (60,50,60) and a light/white (measured white) for the belly and highlights.
- **Dark tone as a partial rim, not a full outline:** it sits only on the shadow side and along the back and fin edges. The lit side has no outline.
- **Light tone marks the belly and one or two highlights**, which is what makes the body read as rounded.
- **Every distinctive part is its own readable shape:** both flippers, the tail flukes, the snout and the head bump.

Check every icon for **body part locations**: legs attached with joints, the right number of limbs, ears and eyes where the animal has them, the subject standing on the ground rather than floating.

## LED colour lessons (user, 2026-11-06, owl revs 30 to 39)

- **Value contrast is the strongest tool.** Lit against nearly off gives the biggest step. Use a near-off dark (X=(30,8,0)) for the outlines between parts; a dim line is the point, not a fault.
- **Hue steps must be big.** At the same value and saturation, neighbouring hues (brown, tan, orange) all read as dim orange. Pick distant hues: orange vs yellow vs white vs green.
- **Avoid steps in saturation alone.** White balance is unpredictable, so pastels and creams read as "weird white".
- **Saturated cartoon colours beat biological accuracy.** Brown animals and close greens look muddy. Vary each animal's main hue across the set; there are already many purple animals.
- **Big shapes and three-tone shading come before texture.** Spots and bars read as blur.
