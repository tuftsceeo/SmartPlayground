#!/bin/sh
# Regenerate fonts/montserrat_{28,40,48}.bin (LVGL binary fonts) for builds
# without those sizes built in. station_fonts.py loads them from
# /flash/fonts/ only when lv.font_montserrat_<size> is missing.
#
# Sources: LVGL's own built-in-font inputs (release/v9.2), so glyphs match
# the built-in Montserrat and lv.SYMBOL codepoints.
# Needs: npm install -g lv_font_conv
set -e
cd "$(dirname "$0")/.."
B=https://raw.githubusercontent.com/lvgl/lvgl/release/v9.2/scripts/built_in_font
T=$(mktemp -d)
curl -sSfL -o "$T/m.ttf" "$B/Montserrat-Medium.ttf"
curl -sSfL -o "$T/fa.woff" "$B/FontAwesome5-Solid+Brands+Regular.woff"
# lv.SYMBOL glyphs used by station_ui.py: EYE_OPEN LIST EDIT SD_CARD OK
# CLOSE WARNING REFRESH TRASH LEFT BACKSPACE
SYM=0xF06E,0xF00B,0xF304,0xF7C2,0xF00C,0xF00D,0xF071,0xF021,0xF2ED,0xF053,0xF55A
mkdir -p fonts
for px in 28 40; do
  lv_font_conv --no-compress --format bin --bpp 4 --size $px \
    --font "$T/m.ttf" -r 0x20-0x7E --font "$T/fa.woff" -r $SYM \
    -o fonts/montserrat_$px.bin
done
# 48 px draws only icons and the keyboard's enlarged character.
lv_font_conv --no-compress --format bin --bpp 4 --size 48 \
  --font "$T/m.ttf" -r 0x2D-0x2E,0x30-0x39,0x5F,0x61-0x7A --font "$T/fa.woff" -r $SYM \
  -o fonts/montserrat_48.bin
rm -rf "$T"
ls -l fonts
