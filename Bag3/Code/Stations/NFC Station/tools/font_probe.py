"""font_probe.py -- which large fonts this UIFlow2 build can draw.

Phase 0 gate for the NFC Station: the UI needs text at 28 px minimum,
40 px for selections and 48 px for glyphs (see station_fonts.py). The
BroadcastDial only used montserrat_14/16/24, so larger built-ins are
unconfirmed.

Run on the Dial with station_fonts.py already on /flash:
    mpremote run tools/font_probe.py
Prints one JSON line per size, then a summary line. Each found font is
drawn on screen in turn so legibility can be checked by eye.
"""

import gc
import json
import time

import M5
import m5ui
import lvgl as lv

import station_fonts

SIZES = (28, 32, 36, 40, 48)
REQUIRED = (station_fonts.BODY, station_fonts.FOCUS, station_fonts.GLYPH)
SAMPLE = "abc xyz 0189"


def run(hold_ms=1500):
    M5.begin()
    m5ui.init()
    page = m5ui.M5Page(bg_c=0xF7F7FB)
    page.screen_load()
    lbl = lv.label(page)
    lbl.set_style_text_color(lv.color_hex(0x231F2E), 0)
    lbl.set_width(200)
    lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
    lbl.align(lv.ALIGN.CENTER, 0, 0)

    found = {}
    for size in SIZES:
        font, source = station_fonts.find(size)
        if font is None:
            print(json.dumps({"size": size, "found": False}))
            continue
        lbl.set_style_text_font(font, 0)
        lbl.set_text("%d px\n%s" % (size, SAMPLE))
        lv.refr_now(None)
        gc.collect()
        print(json.dumps({
            "size": size, "found": True, "source": source,
            "line_height": font.line_height, "mem_free": gc.mem_free(),
        }))
        found[size] = source
        time.sleep_ms(hold_ms)

    missing = [s for s in REQUIRED if s not in found]
    print(json.dumps({"summary": found, "required_missing": missing}))
    if missing:
        lbl.set_style_text_font(lv.font_montserrat_24, 0)
        lbl.set_text("MISSING\n%s" % " ".join(str(s) for s in missing))
    else:
        lbl.set_text("FONTS OK")
    return found


run()
