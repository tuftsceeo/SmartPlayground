# IPS096 colour investigation

## Outcome

The panel's response is non-monotonic but has many usable levels. Brightness rises from level 0
to 13 (5-bit), drops through 14-21, then rises again to 31, in every channel (light output read against
dithers on the Ref page, see `Bag3/Code/known_issues/2026-10-28-ips096-colour-levels.md`). No register or
bus setting changed it, and viewing angle is ruled out, so the driver stays on the generic init
and `display_lvgl.color()` maps each design colour through a per-channel lookup that skips the
dip. Gradients are replaced with flat fills.

## Observations

| # | Observation | How seen |
|---|---|---|
| O1 | Fully saturated colours (R, G, B, yellow, white, black) render correctly | Test pattern, palette page |
| O2 | Any channel value below its maximum renders very dark. Red 15/31 and blue 15/31 are nearly black, and red 8/16 are a faint red | Raw RGB565 squares written with LVGL bypassed |
| O3 | Brightness is non-monotonic: red 16 is darker than red 15, and in the LVGL ramp value 145 is darker than 109 | Raw squares and ramps |
| O4 | O2 and O3 are the same in red, green, blue and grey | Ramps |
| O5 | No change from SPI 40 to 20 MHz, or from mode 0 to 3. Mode 1 is worse | Raw squares |
| O6 | No visible change from three gamma tables (LVGL, TFT_eSPI, Seeed) or from Seeed's VCOM/VRH/LCMCTRL values. Seeed's full 80x160 init made mid-tones darker (red 15 nearly black) | Ramps and raw squares |
| O7 | Clearing LCMCTRL XINV and sending INVON gives a clean negative: white background, cyan and yellow squares | Live register write |
| O8 | LVGL gradients show banding: only a few distinct steps | Header page |

## Hypotheses

| ID | Cause | Fits | Against | Likelihood |
|---|---|---|---|---|
| H1 | The panel has only a few usable grey levels (cheap glass, or the source driver is missing frame-rate dithering) | O1, O2, O4, O8 | Doesn't explain the non-monotonic O3 alone | High |
| H2 | Multi-byte register writes (gamma, porch, power) don't reach the panel, so it runs on reset defaults | O6 | The background changed slightly with Seeed's init, and the XINV/INVON write worked (O7), but those were 1-byte writes | Medium |
| H3 | The panel's source voltage range is wrong (VRH/VDV/VCOM), so most data levels map to "dark" | O2, O4 | Seeed's values changed nothing | Medium |
| H4 | The pixel charge time is too short (frame rate or porch), so pixels can't reach intermediate voltages | O2, O3, O4 | Untested | Medium |
| H5 | It's a TN panel, not IPS, and mid-tones invert with viewing angle | O2, O3 | The vendor says IPS, and the image holds until extreme angles | Ruled out |
| H6 | The 16-to-18-bit expansion (RAMCTRL EPF) or the colour mode is wrong | O3 | Saturated colours are exact, and the effect is far too large | Low |
| H7 | Bit errors on MOSI | O3 | Clock rate made no difference, and blue never uses bit 7 yet is affected | Low |
| H8 | The controller isn't really an ST7789, so some registers mean different things | O6 | The vendor library and wiki say ST7789 | Low |
| H9 | A power-supply sag on USB lowers VCI | O2 | Saturated colours are fully bright | Low |
| H10 | It's the camera or the eye | — | You confirmed it in person on several tests | Ruled out |

## Tests

| Test | Distinguishes | Cost | Pass means |
|---|---|---|---|
| T1 | H5 | 10 s, no code | Tilting the board a lot changes the dark squares → TN/viewing-angle |
| T2 | H2 | 1 live write | A deliberately absurd gamma table (all zeros, then all 0x3F) visibly changes the image → multi-byte writes land |
| T3 | H4 | Live writes | Slower frame rate (FRCTR2 `0x1F`) or longer porches (PORCTRL `0x7F`) brightens the mid squares |
| T4 | H3 | Live sweep | Sweeping VRHS `0x0A..0x20` or VCOMS `0x10..0x30` moves the mid squares |
| T5 | H7 | Reboot | SPI at 1 MHz makes no difference → not signal integrity |
| T6 | H6 | 1 live write | RAMCTRL EPF variants (`0xF0`, `0xC0`, `0xE0`) make no difference |
| T7 | H1 vs everything | Arduino build plus reflash | Seeed's own HelloWorld shows the same crushed mid-tones → the panel is just like this |

## Decision tree

You look once, not per test. The board cycles through labelled settings on its own, and you report which letter looked best.

1. **T1 by hand (10 s):** tilt the board. If the mid squares change a lot, it's H5. Skip to the fallback and calibrate for straight-on viewing.
2. **One automated pass of T2, T3, T4 and T6:** a calibration screen shows red, green, blue and grey at 8 levels. Every 4 s the board applies the next setting and shows its letter (A = baseline, B = absurd gamma, C = slow frame rate, D = long porch, E–H = VRHS sweep, I–K = EPF). You note which letters looked different.
   - **B looks the same as A:** H2. Fix the multi-byte write path, then repeat the pass.
   - **One of C–H looks clearly better:** H3 or H4. Adopt that setting, then stop.
   - **Nothing differs except B:** H1 is very likely. Go to the fallback.
3. **T5 and T7 only if step 2 is ambiguous.** T7 is the definitive check, but it costs an Arduino build and a reflash.

## Fallback: minimal driver and a colour lookup

1. **Strip the experiments:**
   - Remove `LCD_SPI_MODE` from `board.py` and `display_lvgl.py`, and restore `LCD_SPI_HZ = 40_000_000`.
   - Remove `_st7789_init_type1.py`: the vendor's full init made mid-tones darker.
   - Remove the scratch ramp and raw scripts.
2. **Measure the panel's response:** a calibration page shows each channel at all 32 levels (5 px stripes). You send one straight-on photo. I read the brightness of each stripe and build a per-channel table of which input levels the panel actually renders distinctly.
3. **Map design colours to panel colours:**
   - `display_lvgl.py` gains `color(hex)`, which maps each channel through the measured table to the nearest level that renders as intended (for example, a mid level that would collapse to black is pushed up to the lowest visible step).
   - `gallery.py` passes every colour through `panel()`.
   - Gradients are replaced with flat fills.
4. **Record the result:** a known-issue note in `Bag3/Code/known_issues/` with the measured table, and a Results row in `README.md`.
