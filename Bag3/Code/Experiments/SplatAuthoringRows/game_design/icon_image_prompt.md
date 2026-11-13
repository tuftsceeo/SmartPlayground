# Image generation prompt: icon sheets

For an image generation agent. Produces source art for the missing icons in `icon_needs.md`.
Post-processing (outside this prompt) downsamples each cell to 16x16 for the icon display and,
for the shapes marked "5x5", to a one-color 5x5 wand shape.

The icons go on two LED matrices: a 16x16 display and the wand's 5x5 grid. The art must survive
being shrunk to 16x16 pixels, so simplicity matters more than detail.

## Prompt (paste one sheet's block per request, after the shared style block)

### Shared style block

```
Create a sheet of simple flat icons in a 4 x 4 grid (16 cells).

Canvas: square, 2048 x 2048 px. Each cell is a 512 x 512 px square. Pure black background
(#000000) everywhere, including between cells. No grid lines, borders, frames, labels, text,
captions or watermarks.

Each icon:
- One subject, centered, filling about 80% of its cell, with an even black margin on all sides.
  Nothing crosses into a neighboring cell.
- Square composition; the subject reads as a bold silhouette.
- Recognizable when shrunk to 16 x 16 pixels: big simple shapes, thick parts, no thin lines,
  no small details, no texture, no text or letters inside the icon.
- Flat, posterized color: 2 to 4 solid colors per icon, bright and saturated so they glow on
  an LED panel. Simple shading allowed as one darker tone of the same color; no gradients,
  glow, blur, outlines in black, drop shadows or reflections.
- Front or three-quarter view, whichever gives the clearer silhouette.
- Friendly, child-appropriate (ages 5-9). No scary, violent or branded content; no logos,
  trademarked characters or recognizable products.
- Avoid using pure black inside the icon (it disappears into the background); use dark gray
  or a dark color instead.

Consistent style across all cells: same line weight, same level of simplicity, same palette
family, as if from one icon set.

Order: left to right, top to bottom, in the order listed. If a sheet lists fewer than 16
subjects, leave the remaining cells black.
```

### Sheet 1: built-in game shapes and marks (P1)

```
Cells, in order:
1. circle: a solid filled circle, blue.
2. triangle: a solid filled equilateral triangle pointing up, yellow.
3. square: a solid filled square, purple.
4. star: a solid five-point star, white.
5. check: a thick check mark, green.
6. cross: a thick X mark, neutral orange (not red).
7. hand: an open hand, palm facing forward, fingers spread (waving).
8. snowflake: a six-arm snowflake, thick arms, light blue.
9. spiral: a thick spiral, two and a half turns.
10. chest: a closed treasure chest, brown wood with gold bands.
11. question: a thick question mark.
12. hourglass: an hourglass with sand, gold frame.
13. arrow_up: a thick arrow pointing up.
14. arrow_down: a thick arrow pointing down.
15. arrow_left: a thick arrow pointing left.
16. arrow_right: a thick arrow pointing right.
```

### Sheet 2: cooking ingredients and dishes (P2)

```
Cells, in order:
1. tomato: a round red tomato with a green leafy top.
2. cheese: a wedge of yellow cheese with two or three round holes.
3. flour: a white flour sack, tied at the top, with a small wheat stalk mark on the front
   (no letters).
4. egg: a whole white egg, upright.
5. butter: a yellow stick of butter, partly unwrapped.
6. sugar: a small pile of white sugar cubes (three cubes).
7. milk: a milk carton.
8. fried_egg: a fried egg seen from above, white with a yellow yolk.
9. pancakes: a stack of three pancakes with butter on top.
10. pasta: a bowl of spaghetti with red sauce.
11. cupcake: a cupcake with pink frosting.
12. pizza: a slice of pizza with red pepperoni circles.
13. flame: a cooking flame, orange and yellow.
14. pie: a whole round pie with a lattice top, seen from slightly above.
15. rice: a bowl of white rice.
16. corn: an ear of yellow corn with green husks.
```

### Sheet 3: foods from several cultures (P2)

```
Cells, in order:
1. tamal: a Mexican/Central American tamal in an open corn husk, the yellow masa visible.
2. masa: a round ball of yellow corn dough.
3. pupusa: a round, thick, golden Salvadoran pupusa, lightly browned spots.
4. tortilla: a stack of corn tortillas.
5. beans: a small bowl of brown beans.
6. apple: a red apple with a leaf.
7. bread: a loaf of bread.
8. soup: a bowl of soup with steam (steam as two thick wavy shapes).
9. banana: a yellow banana.
10. orange: an orange with a leaf.
11. carrot: an orange carrot with green top.
12. watermelon: a watermelon slice.
Show foods as the people who make them do; no caricature.
```

### Sheet 4: treasure, teams and feelings (P3)

```
Cells, in order:
1. coin: a gold coin with a star on it.
2. key: a gold key.
3. lock: a closed padlock.
4. gem: a cut gemstone, cyan.
5. trophy: a gold trophy cup.
6. crown: a gold crown.
7. medal: a medal on a ribbon.
8. flag: a plain white flag on a pole (the game recolors it).
9. scared: a round face, scared expression, yellow.
10. calm: a round face, calm closed-eye smile, yellow.
11. proud: a round face, proud smile, yellow.
12. neutral: a round face, straight mouth, yellow.
13. start: a green start flag.
14. finish: a black-and-white checkered finish flag (use white and dark gray, not black).
15. loop: a thick circular arrow.
16. target: a bullseye target, red and white rings.
```

### Sheet 5: moves and instructions (P3)

```
Use a simple, gender-neutral child figure: round head, rounded body, no facial details, in one
bright color. Same figure in every move cell.
Cells, in order:
1. spin: the figure turning, with a curved motion arrow around it.
2. clap: the figure clapping, hands together above its head.
3. stomp: one foot stomping, with short impact marks.
4. run: the figure running.
5. reach: the figure with both arms straight up.
6. crouch: the figure crouching low.
7. jump: the figure jumping, arms up, feet off the ground.
8. freeze: the figure standing still, with a small snowflake beside it.
9. wand: a short handheld wand with a small square grid of colored dots on its head.
10. card: a small rounded rectangle card with a wave symbol, as if tapped.
11. ear: an ear (for "listen").
12. rest: a figure sitting, relaxed.
```

### Sheet 6: instruments, weather and growing (P3)

```
Cells, in order:
1. drum: a small hand drum.
2. guitar: an acoustic guitar.
3. marimba: a marimba with wooden bars, seen from slightly above.
4. bell: a hand bell.
5. trumpet: a trumpet.
6. wind: three thick curved wind lines.
7. storm: a dark gray cloud with a yellow lightning bolt and rain.
8. raindrop: one large blue raindrop.
9. seed: a single brown seed.
10. pot: a flower pot with soil.
11. plus: a thick plus sign.
12. exclaim: a thick exclamation mark.
13. play: a thick play triangle (pointing right) in a circle.
14. pause: two thick pause bars in a circle.
15. diamond: a solid diamond shape (rhombus).
16. cloud: a single white cloud.
```

### Sheet 7: habitats and story (P3)

```
Cells, in order:
1. jungle: dense jungle leaves with a vine.
2. cave: a rocky cave opening.
3. sky: a blue sky with one cloud and one bird.
4. farm: a field with a fence and a sun.
5. castle: a small castle with two towers.
6. dragon: a friendly small dragon, green.
7. robot: a friendly boxy robot.
8. fairy: a small fairy with wings.
9. frog_small: a frog, very simplified, for a 5x5 grid.
10. bunny_small: a bunny, very simplified, for a 5x5 grid.
11. cat_small: a cat face, very simplified, for a 5x5 grid.
12. dog_small: a dog face, very simplified, for a 5x5 grid.
For cells 9-12: a solid one-color silhouette, as few shapes as possible.
```

## Notes for the requester

- **One sheet per request.** Sixteen cells is the most an image model places reliably; a single
  sheet of all ~100 icons comes out muddled.
- **Check each sheet** for: icons in the right cells and order, nothing crossing cell edges,
  no text, a pure black background, no black inside icons. Regenerate single cells that fail.
- **Post-processing:** crop each 512 x 512 cell, then downsample to 16x16 with nearest-color
  quantization to the icon display palette. For 5x5 shapes (sheet 1 cells 1-3, 7, 8; sheet 7
  cells 9-12), threshold to one color and hand-correct; at 5x5 the result usually needs a
  pixel-level touch-up.
- **Shapes that carry meaning** (sheet 1 cells 1-4) are distinguished by outline, so they stay
  readable for color-blind children.
- **Names** match `icon_needs.md`; use them as the icon filenames.
- **Not included:** icons that already exist (see `icon_needs.md`), and the wand's
  `SHAPE_PACMAN` / `SHAPE_INVADER`, which resemble trademarked characters.
