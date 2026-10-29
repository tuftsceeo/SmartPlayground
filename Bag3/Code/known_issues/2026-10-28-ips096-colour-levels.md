---
title: IPS096 Display mid-tone colours are non-monotonic
date: 2026-10-28
status: workaround (calibrated lookup in display_lvgl.py; pink and teal confirmed by eye)
devices: [IPS096 Display (Seeed XIAO 0.96in IPS, ESP32-S3)]
components: [ST7789 80x160 panel, lvgl_micropython]
code:
  - Bag3/Code/Experiments/IPS096 Display/display_lvgl.py
  - Bag3/Code/Experiments/IPS096 Display/gallery.py
  - Bag3/Code/Experiments/IPS096 Display/colour_investigation.md
open:
  - Lookup is built from one straight-on photo of one board; a second board is unmeasured
  - Anti-aliased text and rounded edges are blended by LVGL after the lookup, so edge pixels can land in the dip (slightly dark fringes)
keywords: [IPS096, ST7789, colour, color, gamma, mid-tone, LUT, lookup, RGB565, levels, gradient, banding]
---

# IPS096 Display mid-tone colours

Saturated colours (any channel at 0 or full) render correctly. Intermediate channel levels do
not: brightness rises from level 0 to 13 (5-bit), drops through 14-21, then rises again to 31.
The shape is the same in red, green, blue and grey, so design colours with mid-range channels
render with the wrong hue and brightness (for example, pink renders red because its blue
channel sits in the dip), and LVGL gradients band.

No driver setting changed this. Tested without effect: three gamma tables, Seeed's VCOM/VRH/LCMCTRL
values, SPI at 20 MHz, SPI mode 3. Worse: SPI mode 1, and Seeed's full 80x160 init sequence.
Viewing angle is ruled out (the panel is IPS and looks the same until extreme angles). Details
and the hypothesis table are in `Experiments/IPS096 Display/colour_investigation.md`.

## Workaround

`display_lvgl.color(hexval)` maps each channel through a per-channel table (`_LUT_R/_G/_B`) to
the panel level whose light output is closest to the sRGB-decoded target, skipping the dip.
`gallery.py` routes every colour through it and uses flat fills instead of gradients.

The gallery's Ref page draws, per channel, the 32 flat levels above dithers of only levels 0 and
full (1/8, 1/4, 1/2, full light). Both are uncorrected and pass through the same camera
processing, so each stripe's light output is read against the dithers in the same photo.

## Light output per level

Fraction of full light per level (0-31), read from a photo of the Ref page with each row's
dithers as the scale, 2026-10-28. Green was drawn at the odd 6-bit levels.

| Channel | 0-7 | 8-15 | 16-23 | 24-31 |
|---|---|---|---|---|
| R | .00 .00 .00 .00 .00 .00 .00 .01 | .01 .02 .03 .04 .05 .06 .05 .02 | .01 .00 .00 .01 .02 .04 .07 .19 | .28 .43 .40 .38 .36 .39 .46 1 |
| G | .00 .01 .01 .01 .01 .01 .02 .03 | .05 .08 .09 .11 .13 .14 .12 .07 | .04 .02 .03 .04 .07 .11 .19 .25 | .35 .49 .48 .49 .67 .65 .76 1 |
| B | .00 .01 .01 .02 .02 .03 .04 .06 | .08 .11 .14 .15 .16 .18 .17 .14 | .09 .06 .05 .07 .09 .13 .17 .24 | .27 .39 .42 .44 .43 .48 .50 1 |

Photo pixel values are not usable directly: auto white balance, the colour matrix and the tone
curve distort them (the 1/8, 1/4, 1/2 dithers read 0.2, 0.42, 0.83 after sRGB decoding).
