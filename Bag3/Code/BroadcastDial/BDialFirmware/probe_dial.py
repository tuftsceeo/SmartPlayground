"""
probe_dial.py -- Phase 0 hardware discovery for M5Stack Dial 2 (StampS3A).

Nothing in this repo documents this board yet. Every "fact" below (pins,
buses, class names) is a guess to be confirmed or killed by this probe --
see Bag3/AGENTS.md, "Phase 0 pins still open". Bag2/Code/DialSpeaker/
Dial_Music.py is the nearest reference in-tree, but it targets M5 Dial
*v1* -- treat anything it implies about pins as unverified for this board.

Eleven numbered stages, each its own function, each wrapped in run()'s own
try/except so one stage's crash cannot hide the others -- see the
comment on run() for why broad except is correct here.

Deploy and run (see P0_RUNBOOK.md for the batched command):
  mpremote connect $PORT fs cp probe_dial.py :/flash/probe_dial.py + \\
    fs cp ws1850s.py :/flash/ws1850s.py + \\
    exec "import probe_dial; probe_dial.run()"

Re-run a single stage that failed:
  mpremote connect $PORT exec "import probe_dial; probe_dial.run(stages=[4])"
"""

import time
import gc

# --- Stage 4 candidate I2C pin table -------------------------------------
# One clearly-marked module-level table. Add pairs here and re-run stage 4
# -- never brute-force every GPIO; an arbitrary pin may be wired to a real
# peripheral and driving it blind is how hardware gets damaged. Order
# matters only for readability; stage 4 tries all of them and reports each.
#
#   label                    (sda, scl)
I2C_CANDIDATES = [
    ("m5dial_v1_internal",   (11, 12)),   # M5 Dial v1's internal I2C pair
    ("dial_port_a_grove",    (13, 15)),   # Dial's Port A Grove header (guess)
    ("sticks3_pair",         (9, 10)),    # from BBoxFirmware/bbox_server.py
]

RESULTS = []


def _result(n, line):
    print("RESULT %d: %s" % (n, line))
    RESULTS.append((n, line))


def _banner(n, name):
    print("== STAGE %d: %s ==" % (n, name))


# --- Stage 1: firmware identity -------------------------------------------

def stage1_identity():
    _banner(1, "firmware identity")
    import sys
    import os
    print("sys.implementation:", sys.implementation)
    print("sys.version:", sys.version)
    try:
        print("os.uname():", os.uname())
    except Exception as e:
        print("os.uname() FAILED:", e)
    try:
        print("os.listdir('/'):", os.listdir('/'))
    except Exception as e:
        print("os.listdir('/') FAILED:", e)
    try:
        print("os.listdir('/flash'):", os.listdir('/flash'))
    except Exception as e:
        print("os.listdir('/flash') FAILED:", e)
    _result(1, "sys.implementation=%s uname=%s" % (
        getattr(sys.implementation, "name", "?"), _safe_uname()))


def _safe_uname():
    import os
    try:
        return os.uname()
    except Exception as e:
        return "FAILED(%s)" % e


# --- Stage 2: introspection BEFORE guessing any pins -----------------------

def _safe_dir(mod, name):
    """dir(mod) is NOT side-effect-free on this board: a module that defines
    a module-level __getattr__ (PEP 562 lazy loading) can trigger a real,
    blocking hardware init just from attribute enumeration -- confirmed live
    on `hardware`, where dir() hung inside hardware/__init__.py's __getattr__
    with no card/peripheral touched and no way to interrupt except pulling
    the board's own Ctrl-C. So: check for a lazy loader via mod.__dict__
    (a real, already-materialized attribute -- this lookup does not itself
    fall through to __getattr__) and, if present, report only the eagerly
    defined names instead of calling dir().
    """
    if "__getattr__" in mod.__dict__:
        names = sorted(mod.__dict__.keys())
        print("dir(%s) SKIPPED -- module defines __getattr__ (lazy loader); "
              "dir() can block on real hardware init. Eager __dict__ names "
              "[%d]:" % (name, len(names)))
        print(names)
        return names
    names = sorted(dir(mod))
    print("dir(%s) [%d names]:" % (name, len(names)))
    print(names)
    return names


def stage2_introspection():
    _banner(2, "introspection (before guessing pins)")
    modules_of_interest = ["M5", "hardware", "unit", "m5ui"]
    found = {}
    for name in modules_of_interest:
        try:
            mod = __import__(name)
            found[name] = _safe_dir(mod, name)
        except ImportError as e:
            print("import %s FAILED: %s" % (name, e))
            found[name] = None

    # Look for anything that smells like a pre-built RFID/NFC class or I2C
    # bus object -- if the vendor already exposes one, it answers stages 4
    # and 5 without probing pins at all.
    prebuilt_i2c = []
    rfid_hits = []
    for name, names in found.items():
        if not names:
            continue
        for attr in names:
            low = attr.lower()
            if "i2c" in low or "bus" in low:
                prebuilt_i2c.append("%s.%s" % (name, attr))
            if "rfid" in low or "nfc" in low or "mfrc" in low or "ws1850" in low:
                rfid_hits.append("%s.%s" % (name, attr))

    if prebuilt_i2c:
        print("!!! PRE-BUILT I2C-LIKE ATTRS FOUND, CHECK THESE BEFORE STAGE 4:", prebuilt_i2c)
    else:
        print("no pre-built I2C bus object found in the modules above")

    if rfid_hits:
        print("!!! VENDOR RFID/NFC CLASS ALREADY EXPOSED, THIS MAY ANSWER STAGE 5 DIRECTLY:", rfid_hits)
    else:
        print("no vendor RFID/NFC class found in the modules above")

    # Try to find any board/pin/config module by name -- best-effort guesses,
    # not a filesystem scan, since we don't yet know this board's layout.
    for guess in ("board", "pins", "config", "boardconfig", "m5dial"):
        try:
            mod = __import__(guess)
            found[guess] = _safe_dir(mod, guess)
        except ImportError:
            pass

    _result(2, "modules_seen=%s prebuilt_i2c=%s rfid_hits=%s" % (
        [k for k, v in found.items() if v], prebuilt_i2c, rfid_hits))


# --- Stage 3: display -------------------------------------------------------

def stage3_display():
    _banner(3, "display")
    import M5
    M5.begin()
    native_w = M5.Lcd.width()
    native_h = M5.Lcd.height()
    print("native (pre-rotation): w=%d h=%d" % (native_w, native_h))

    colors = [
        (0xFF0000, "red"),
        (0x00FF00, "green"),
        (0x0000FF, "blue"),
        (0xFFFF00, "yellow"),
    ]
    per_rotation = []
    for rot in range(4):
        M5.Lcd.setRotation(rot)
        w = M5.Lcd.width()
        h = M5.Lcd.height()
        color, cname = colors[rot % len(colors)]
        M5.Lcd.fillScreen(color)
        print("rotation=%d w=%d h=%d color=%s" % (rot, w, h, cname))
        per_rotation.append((rot, w, h))
        time.sleep(1.5)
    changes = len(set((w, h) for _, w, h in per_rotation)) > 1
    _result(3, "native=%dx%d rotation_changes_wh=%s per_rotation=%s" % (
        native_w, native_h, changes, per_rotation))


# --- Stage 4: I2C buses -----------------------------------------------------

def stage4_i2c():
    _banner(4, "I2C buses (candidate pin pairs only, see I2C_CANDIDATES)")
    import machine

    # If stage 2 already found a pre-built bus object, this is where you'd
    # scan it first -- left as a manual follow-up since the object's name
    # is only known after reading stage 2's output, not before.
    print("candidate table:", I2C_CANDIDATES)

    all_found = []
    for label, (sda, scl) in I2C_CANDIDATES:
        try:
            i2c = machine.SoftI2C(
                sda=machine.Pin(sda), scl=machine.Pin(scl), freq=100_000)
            addrs = i2c.scan()
            print("candidate=%s sda=%d scl=%d -> addrs=%s" % (
                label, sda, scl, ["0x%02X" % a for a in addrs]))
            for a in addrs:
                all_found.append((label, sda, scl, a))
        except Exception as e:
            print("candidate=%s sda=%d scl=%d FAILED: %s" % (label, sda, scl, e))
        time.sleep_ms(1)

    if all_found:
        _result(4, "found=%s" % [
            "%s(sda=%d,scl=%d)->0x%02X" % (l, s, c, a) for l, s, c, a in all_found])
    else:
        _result(4, "NOT FOUND -- no address answered on any candidate pin pair")
    return all_found


# --- Stage 5: reader identity -----------------------------------------------

def stage5_reader(i2c_found=None):
    _banner(5, "reader identity (WS1850S @ 0x28)")
    import machine
    from ws1850s import WS1850S

    if i2c_found is None:
        i2c_found = stage4_i2c()

    hits_0x28 = [(label, sda, scl) for (label, sda, scl, addr) in i2c_found if addr == 0x28]

    if not hits_0x28:
        all_addrs = sorted(set("0x%02X" % addr for (_l, _s, _c, addr) in i2c_found))
        print("NOTHING at 0x28. Addresses actually found:", all_addrs)
        print("H2 (WS1850S reader present) is UNCONFIRMED -- not guessing a chip.")
        _result(5, "NOT FOUND at 0x28; other addresses=%s; H2 unconfirmed" % all_addrs)
        return

    for label, sda, scl in hits_0x28:
        try:
            i2c = machine.SoftI2C(
                sda=machine.Pin(sda), scl=machine.Pin(scl), freq=100_000)
            nfc = WS1850S(i2c, WS1850S.DEFAULT_ADDR)
            ver = nfc.version()
            print("candidate=%s sda=%d scl=%d version=0x%02X" % (label, sda, scl, ver))
            # ws1850s.py exposes read_uid_full(), not detect_tag() -- that
            # method name doesn't exist in this driver. read_uid_full() is
            # the closest equivalent: an unattended detect attempt with no
            # blocking wait, which is what "no card present" calls for.
            try:
                found = nfc.read_uid_full()
                print("read_uid_full() (no card expected) ->", found)
            except Exception as e:
                print("read_uid_full() raised:", e)
            _result(5, "WS1850S ver=0x%02X at %s sda=%d scl=%d" % (ver, label, sda, scl))
        except Exception as e:
            print("candidate=%s FAILED constructing WS1850S: %s" % (label, e))
            _result(5, "0x28 present at %s but WS1850S() FAILED: %s" % (label, e))


# --- Stage 6: memory ladder (H5) --------------------------------------------

def stage6_memory():
    _banner(6, "memory ladder (H5)")
    import M5

    gc.collect()
    print("after import:", gc.mem_free())

    M5.begin()
    gc.collect()
    print("after M5.begin():", gc.mem_free())

    try:
        import m5ui
        m5ui.init()
        gc.collect()
        print("after m5ui.init():", gc.mem_free())

        scr = m5ui.M5Screen() if hasattr(m5ui, "M5Screen") else None
        gc.collect()
        print("after building one throwaway LVGL screen:", gc.mem_free())
    except Exception as e:
        print("m5ui stage FAILED:", e)

    try:
        from ws1850s import WS1850S
        import machine
        # Reuse whatever candidate stage 4/5 would have found; if none is
        # known in this isolated run, just report the attempt failed.
        found = False
        for _label, (sda, scl) in I2C_CANDIDATES:
            try:
                i2c = machine.SoftI2C(sda=machine.Pin(sda), scl=machine.Pin(scl), freq=100_000)
                if 0x28 in i2c.scan():
                    WS1850S(i2c, WS1850S.DEFAULT_ADDR)
                    found = True
                    break
            except Exception:
                continue
        gc.collect()
        print("after reader init (found=%s):" % found, gc.mem_free())
    except Exception as e:
        print("reader-init memory step FAILED:", e)

    _result(6, "see labelled mem_free() lines above")


# --- Stage 7: buttons -------------------------------------------------------

def stage7_buttons():
    _banner(7, "buttons")
    import M5

    M5.begin()
    candidates = ["BtnA", "BtnB", "BtnC", "BtnPWR"]
    present = []
    for name in candidates:
        btn = getattr(M5, name, None)
        if btn is not None:
            present.append(name)
    print("buttons present:", present)
    if not present:
        print("NOT FOUND -- no M5.Btn* objects exist on this build")
        _result(7, "NOT FOUND -- no button objects present")
        return

    try:
        import M5
        M5.Lcd.fillScreen(0x000000)
        M5.Lcd.setCursor(4, 4)
        M5.Lcd.print("Press every button")
        M5.Lcd.setCursor(4, 24)
        M5.Lcd.print("for 20s. Watch serial.")
    except Exception:
        pass
    print("# press every physical button on the Dial now -- 20s window")

    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 20000:
        M5.update()
        for name in present:
            btn = getattr(M5, name)
            if btn.wasPressed():
                print("%dms %s PRESSED" % (time.ticks_diff(time.ticks_ms(), t0), name))
            if btn.wasReleased():
                print("%dms %s RELEASED" % (time.ticks_diff(time.ticks_ms(), t0), name))
        time.sleep_ms(1)

    _result(7, "present=%s (see PRESSED/RELEASED lines above for timing)" % present)


# --- Stage 8: encoder --------------------------------------------------------

def stage8_encoder():
    _banner(8, "encoder")
    import hardware

    rot_cls = getattr(hardware, "Rotary", None)
    if rot_cls is None:
        print("NOT FOUND -- hardware.Rotary does not exist on this build")
        _result(8, "NOT FOUND -- hardware.Rotary missing")
        return

    rotary = rot_cls()
    rotary.reset_rotary_value()

    try:
        import M5
        M5.Lcd.fillScreen(0x000000)
        M5.Lcd.setCursor(4, 4)
        M5.Lcd.print("Spin the dial for 20s")
        M5.Lcd.setCursor(4, 24)
        M5.Lcd.print("slow, then fast. Watch serial.")
    except Exception:
        pass
    print("# spin the dial now -- 20s window. Try slow clicks, then a fast spin.")

    last_val = rotary.get_rotary_value()
    t0 = time.ticks_ms()
    max_abs_delta = 0
    while time.ticks_diff(time.ticks_ms(), t0) < 20000:
        if rotary.get_rotary_status():
            val = rotary.get_rotary_value()
            delta = val - last_val
            last_val = val
            max_abs_delta = max(max_abs_delta, abs(delta))
            print("%dms status=1 value=%d delta=%d" % (
                time.ticks_diff(time.ticks_ms(), t0), val, delta))
        time.sleep_ms(1)

    _result(8, "final_value=%d max_abs_delta_seen=%d (see per-event lines above)" % (
        last_val, max_abs_delta))


# --- Stage 9: touch ----------------------------------------------------------

def stage9_touch():
    _banner(9, "touch")
    try:
        import m5ui
        import lvgl as lv
    except ImportError as e:
        print("NOT FOUND -- m5ui/lvgl import failed: %s" % e)
        _result(9, "NOT FOUND -- lvgl/m5ui unavailable: %s" % e)
        return

    # Report whatever touch object/driver stage 2 may have turned up.
    for name in ("touch", "Touch", "indev", "touch_drv"):
        obj = getattr(m5ui, name, None) or getattr(lv, name, None)
        if obj is not None:
            print("touch-related attr found: %s = %r" % (name, obj))

    m5ui.init()
    scr = m5ui.M5Screen() if hasattr(m5ui, "M5Screen") else lv.obj()
    events = []

    def make_cb(label):
        def _cb(e):
            events.append((label, time.ticks_ms()))
            print("%dms CLICKED %s" % (time.ticks_ms(), label))
        return _cb

    labels = ["BUTTON 1", "BUTTON 2", "BUTTON 3"]
    btns = []
    for i, label in enumerate(labels):
        btn = lv.btn(scr)
        btn.set_size(180, 50)
        btn.align(lv.ALIGN.TOP_MID, 0, 10 + i * 60)
        lbl = lv.label(btn)
        lbl.set_text(label)
        btn.add_event_cb(make_cb(label), lv.EVENT.CLICKED, None)
        btns.append(btn)

    print("# tap each of the 3 buttons on screen at least once -- 20s window")
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 20000:
        lv.task_handler()
        time.sleep_ms(1)

    _result(9, "clicks=%s" % events)


# --- Stage 10: LVGL-during-block (H4) ---------------------------------------

def stage10_lvgl_block():
    _banner(10, "LVGL-during-block (H4)")
    try:
        import m5ui
        import lvgl as lv
    except ImportError as e:
        print("NOT FOUND -- m5ui/lvgl import failed: %s" % e)
        _result(10, "NOT FOUND -- lvgl/m5ui unavailable: %s" % e)
        return

    m5ui.init()
    scr = m5ui.M5Screen() if hasattr(m5ui, "M5Screen") else lv.obj()
    spinner = lv.spinner(scr) if hasattr(lv, "spinner") else lv.obj(scr)
    spinner.set_size(80, 80)
    spinner.align(lv.ALIGN.CENTER, 0, 0)

    print("# an animating spinner should now be on screen.")
    print("# now blocking with time.sleep(5) and NOTHING else -- ")
    print("# watch whether the animation keeps moving and whether touch still responds.")
    time.sleep(5)
    print("# block finished. Report: did the animation keep running during the 5s? did touch respond?")

    _result(10, "blocked 5s with no task_handler() pump -- see physical report needed above")


# --- Stage 11: M5Roller construction + heap, for the light-UI redesign ------

def stage11_roller_and_heap():
    """Gate for dial_ui.py's redesign: can this build construct an
    M5Roller, push real option rows into it, and move the selection --
    and does the new 4-screen UI actually leave more heap free than the
    old 17-screen one did (the H5 SoftAP-OOM failure this redesign exists
    to fix). Does NOT arm SoftAP itself -- that needs the full server
    stack (games index, CodeServer) this isolated probe does not build;
    treat a good mem_free() reading here as necessary, not sufficient --
    confirm the real H5 retest by running bdial_server end-to-end and
    checking its own _log_mem() lines around ui.begin() and CodeServer.arm().
    """
    _banner(11, "M5Roller + heap (redesign gate)")
    try:
        import M5
        import m5ui
        import lvgl as lv
    except ImportError as e:
        print("NOT FOUND -- m5ui/lvgl import failed: %s" % e)
        _result(11, "NOT FOUND: %s" % e)
        return

    gc.collect()
    print("before M5.begin():", gc.mem_free())
    M5.begin()
    gc.collect()
    print("after M5.begin():", gc.mem_free())

    m5ui.init()
    gc.collect()
    print("after m5ui.init():", gc.mem_free())

    pg = m5ui.M5Page(bg_c=0xFFFFFF)
    rows = ["Game %d" % i for i in range(1, 13)] + ["Utility Tags", "DONE"]
    roller = m5ui.M5Roller(
        x=20, y=48, w=190, h=118, options=[""],
        mode=lv.roller.MODE.NORMAL, selected=0, visible_row_count=3,
        font=lv.font_montserrat_16, parent=pg)
    try:
        roller.set_options(rows, lv.roller.MODE.NORMAL)
        opts_kind = "list"
    except Exception:
        roller.set_options("\n".join(rows), lv.roller.MODE.NORMAL)
        opts_kind = "newline-joined string"
    print("# set_options accepted a %s" % opts_kind)
    roller.set_selected(6, lv.ANIM.OFF)
    try:
        sel = roller.get_selected_str()
        print("# get_selected_str() ->", sel)
        _result(11, "roller ok, selected='%s' (expect 'Game 7')" % sel)
    except Exception as e:
        print("# get_selected_str() FAILED: %s" % e)
        _result(11, "roller built but get_selected_str() failed: %s" % e)

    gc.collect()
    print("after building 1 page + roller (4-screen design target):", gc.mem_free())
    print("# compare against stage 6's 'after building one throwaway LVGL "
          "screen' and against the OLD 17-screen build's mem_free() -- "
          "this number must be comfortably higher for H5 to be considered fixed.")


STAGES = {
    1: stage1_identity,
    2: stage2_introspection,
    3: stage3_display,
    4: stage4_i2c,
    5: stage5_reader,
    6: stage6_memory,
    7: stage7_buttons,
    8: stage8_encoder,
    9: stage9_touch,
    10: stage10_lvgl_block,
    11: stage11_roller_and_heap,
}


def run(stages=None):
    """Run the given stage numbers (default: all 11, in order).

    Each stage runs in its own try/except that prints the exception and
    CONTINUES -- this is the one place in this file where catching broadly
    is correct: a probe whose stage 4 crashes must not hide stages 5-10,
    since each one answers a different, independent hardware question and
    a hidden crash costs a whole extra hardware cycle to notice.
    """
    global RESULTS
    RESULTS = []
    order = stages if stages else sorted(STAGES.keys())
    print("# probe_dial start (stages=%s)" % order)
    for n in order:
        fn = STAGES.get(n)
        if fn is None:
            print("# unknown stage %d, skipping" % n)
            continue
        try:
            fn()
        except Exception as e:
            print("STAGE %d CRASHED: %s" % (n, e))
            _result(n, "CRASHED: %s" % e)
        time.sleep_ms(1)
    print("# probe_dial done -- grep for RESULT above")
    return RESULTS
