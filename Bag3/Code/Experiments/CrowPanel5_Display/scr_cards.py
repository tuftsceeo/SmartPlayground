"""Screen 5 - NFC tags on the chat layout: the shared left column in Tags mode holds the list,
Games / Write / Read is the switch in the heading, and the NFC target sits at its fixed spot.

The radio is off while this screen is open (the reader field is on). After each tag the next
job waits until the card is lifted (panel.need_lift), as on the Broadcast Dial. Game tags can be
written in any order: tapping a row arms that tag, tapping a written row writes another copy.
"""

import lvgl as lv

import ds_tokens as t
import library
import nfc_target
import panel
import side
import ui_kit as k

ROWS = side.ROWS
MAIN_X = side.W
MAIN_W = k.W - MAIN_X
CARD_X = MAIN_X + 16
TEXT_W = 248
MAX_TEXT = 54
READS = 6
_w = {"mode": "games", "view": "pick", "gsel": None, "slug": None, "cards": [], "done": set(),
      "err": set(), "i": None, "complete": False, "text": "", "wrote": False,
      "read": None, "blank": False, "held": False, "page": 0, "entered": False, "last": None,
      "busy": False, "counts": {}, "reads": []}


def start(mode):
    """Open in `mode` (games / write / read); call before k.go("scr_cards")."""
    _w["mode"] = mode
    _w["view"] = "pick"
    _w["page"] = 0


def _leave():
    _w["entered"] = False
    panel.P.nfc_leave()
    k.home()


def _toggle(key):
    if key == "msg":
        _leave()


def _wrap(parent, x, y, w, color, font):
    lb = k.text(parent, "", color, font, x, y)
    lb.set_width(w)
    lb.set_long_mode(lv.label.LONG_MODE.WRAP)
    return lb


def build():
    scr = k.new_screen()
    _w["side"] = side.build(scr, "tags", pick=_tap, toggle=_toggle)
    hd = k.box(scr, MAIN_X, 0, MAIN_W, 64, t.SURFACE)
    k.box(scr, MAIN_X, 63, MAIN_W, 1, t.BORDER)
    _w["head"] = k.slot(hd, 16, 22, MAIN_W - 16 - 240, t.INK, k.F_HEAD)
    tr, _w["seg"], _ = k.seg(hd, MAIN_W - 16 - 224, 8, (("games", "Games"), ("write", "Write"), ("read", "Read")),
                             _mode, 72)
    k.box(scr, CARD_X, 78, MAIN_W - 32, 314, t.SURFACE, 16, t.BORDER, 2)
    _w["kicker"] = k.slot(scr, CARD_X + 16, 120, TEXT_W, t.INK_3, k.F12)
    _w["title"] = _wrap(scr, CARD_X + 16, 142, TEXT_W, t.INK, k.F_TITLE)
    _w["hint"] = _wrap(scr, CARD_X + 16, 210, TEXT_W, t.INK_3, k.F_BODY)
    pill = k.box(scr, CARD_X + 16, 336, 44, 32, t.WARN[1], t.R_PILL)
    k.icon(pill, "radio_off_20", t.WARN[0], align=lv.ALIGN.CENTER)
    _w["radio"] = pill
    ft = k.box(scr, MAIN_X, 406, MAIN_W, 74, t.SURFACE)
    k.box(scr, MAIN_X, 406, MAIN_W, 1, t.BORDER)
    prev = k.button(ft, 16, 15, 44, lv.SYMBOL.UP, t.INK_3, px=0, w=44)
    nxt = k.button(ft, 68, 15, 44, lv.SYMBOL.DOWN, t.INK_3, px=0, w=44)
    k.on(prev, lambda: _page(-1))
    k.on(nxt, lambda: _page(1))
    _w["pager"] = (prev, nxt)
    # labels are set by _show; a button made with "" has no label to set
    _w["sec"] = k.button(ft, MAIN_W - 16 - 170 - 10 - 150, 11, 52, " ", t.INK_3, font=k.F_BODY, w=150)
    _w["pri"] = k.button(ft, MAIN_W - 16 - 170, 11, 52, " ", t.SURFACE, font=k.F_HEAD, primary="teal", w=170)
    k.on(_w["sec"], lambda: _foot("sec"))
    k.on(_w["pri"], lambda: _foot("pri"))
    _w["edges"] = k.edges(scr, 0)
    nfc_target.attach(scr)
    return scr


# -- what the list shows -------------------------------------------------------

def _pick_items():
    P = panel.P
    items = [(g["slug"], g["name"], len(P.lib.cards(g["slug"]))) for g in P.lib.games]
    items.append((library.UTILITY, "Utility", len(library.UTILITY_TAGS)))
    return items


def _tags(n):
    return f"{n} tag{'' if n == 1 else 's'}"


def _items():
    """[(key, name, note, mark, row bg)] for the left column. mark: ok / now / err / ''."""
    mode = _w["mode"]
    out = []
    if mode == "games" and _w["view"] == "pick":
        for slug, name, n in _pick_items():
            sel = slug == _w["gsel"]
            out.append((slug, name, _tags(n), "now" if sel else "", t.PINK_50 if sel else None))
    elif mode == "games":
        for n, (label, _) in enumerate(_w["cards"]):
            now = n == _w["i"] and not _w["complete"]
            if now:
                mk = "err" if n in _w["err"] else "now"
            else:
                mk = "ok" if n in _w["done"] else ("err" if n in _w["err"] else "")
            out.append((n, label, "", mk, t.PINK_50 if now else None))
    elif mode == "write":
        for s in panel.P.store.history:
            n = _w["counts"].get(s, 0)
            out.append((s, s, _tags(n) if n else "", "ok", t.PINK_50 if s == _w["text"] else None))
    else:
        for j, s in enumerate(_w["reads"]):
            title = "Blank" if s is None else " ".join(x for x in _says(s) if x)
            out.append(("r%d" % j, title, "", "ok" if s is not None else "",
                        t.PINK_50 if j == 0 and (_w["read"] or _w["blank"]) else None))
    return out


# -- actions -------------------------------------------------------------------

def _mode(mode):
    _w["mode"] = mode
    _w["view"] = "pick"
    _w["page"] = 0
    _w["held"] = False
    _arm()
    if mode == "write" and not _w["text"]:
        _type()


def _page(n):
    _w["page"] = max(0, _w["page"] + n)
    _show()


def _next_todo(after=-1):
    """The next tag not written yet after `after`, wrapping round; None when all are written."""
    cards = _w["cards"]
    for n in list(range(after + 1, len(cards))) + list(range(0, after + 1)):
        if n not in _w["done"]:
            return n
    return None


def _open_set(slug):
    _w["slug"] = slug
    _w["cards"] = panel.P.lib.cards(slug)
    _w["view"] = "set"
    _w["page"] = 0
    _w["done"] = set()
    _w["err"] = set()
    _w["i"] = _next_todo()
    _w["complete"] = _w["i"] is None
    _arm()


def _tap(key):
    mode = _w["mode"]
    if mode == "games" and _w["view"] == "pick":
        _w["gsel"] = key
        _show()
    elif mode == "games":
        _w["i"] = key               # any order; a written tag gets another copy
        _w["complete"] = False
        _arm()
    elif mode == "write":
        _w["text"] = key
        _w["wrote"] = False
        _arm()
    else:
        s = _w["reads"][int(key[1:])]
        if s is not None:
            _use_text(s)


def _use_text(s):
    _w["mode"] = "write"
    _w["text"] = s
    _w["wrote"] = False
    _w["page"] = 0
    _arm()


def _type():
    import kbd
    kbd.open("", _w["text"], MAX_TEXT, _use_text)


def _foot(which):
    mode = _w["mode"]
    if which == "pri" and _buttons()[1] in ("Done", "Exit"):
        _leave()
    elif mode == "games" and _w["view"] == "pick":
        if _w["gsel"] is not None:
            _open_set(_w["gsel"])
    elif mode == "games":
        if _w["complete"]:
            _open_set(_w["slug"])       # Write another set
        else:
            nxt = _next_todo(_w["i"])   # Skip
            if nxt is not None and nxt != _w["i"]:
                _w["i"] = nxt
                _arm()
    elif mode == "write":
        if which == "sec":
            _type()                     # Edit text / New text
        else:
            _w["wrote"] = False         # Same again
            _arm()
    elif _w["blank"]:
        _w["text"] = ""                 # Write a tag
        _w["mode"] = "write"
        _w["wrote"] = False
        _arm()
        _type()
    elif _w["read"]:
        _use_text(_w["read"])           # Write it again


def _arm():
    """Queue the reader job for what the screen is showing."""
    P = panel.P
    mode = _w["mode"]
    P.job = None
    if P.nfc_on:
        if mode == "games" and _w["view"] == "set" and _w["i"] is not None and not _w["complete"]:
            text = _w["cards"][_w["i"]][1]
            P.card_job("write", text, text, _result)
        elif mode == "write" and _w["text"] and not _w["wrote"]:
            P.card_job("write", _w["text"], _w["text"], _result)
        elif mode == "read":
            P.card_job("read", None, "", _result)
    if not _w["held"]:
        _target()
    _show()


def _target():
    """Tag target and edges for an armed (or idle) job."""
    P = panel.P
    if not P.nfc_on:
        nfc_target.state("idle")
    elif P.job is None:
        if _w["mode"] == "games" and _w["complete"]:
            nfc_target.state("done")
        elif _w["mode"] == "write" and _w["wrote"]:
            nfc_target.state("done")
        else:
            nfc_target.state("idle")
    elif P.job["mode"] == "read":
        nfc_target.state("read_wait")
    else:
        nfc_target.state("waiting")
    _w["edges"]("done" if _w["complete"] else "ready")


def _result(res, uid, text):
    P = panel.P
    mode = _w["mode"]
    if res == "busy":
        if mode != "read":
            nfc_target.state("writing")
            _w["edges"]("writing")
            _w["busy"] = True
            _show()
        return
    _w["busy"] = False
    ok = res in ("written", "already", "read")
    _w["held"] = True
    if mode == "read":
        _w["blank"] = res == "empty"
        _w["read"] = text if ok else None
        if ok or res == "empty":
            _w["reads"].insert(0, text if ok else None)
            del _w["reads"][READS:]
            _w["page"] = 0
        if res == "empty":
            nfc_target.state("read", f"Read{k.DOT}blank")
        else:
            nfc_target.state("read" if ok else "read_wait")
        _w["edges"]("done" if ok or res == "empty" else "ready")
        P.card_job("read", None, "", _result)
        _show()
        return
    if not ok:
        nfc_target.state("error")
        _w["edges"]("error")
        if mode == "games":
            _w["err"].add(_w["i"])
        _arm()
        return
    nfc_target.state("done")
    _w["edges"]("done")
    if mode == "write":
        _w["wrote"] = True
        _w["counts"][_w["text"]] = _w["counts"].get(_w["text"], 0) + 1
        P.store.remember(_w["text"])
        _arm()
        return
    i = _w["i"]
    label, tag = _w["cards"][i]
    _w["last"] = label
    _w["counts"][tag] = _w["counts"].get(tag, 0) + 1
    _w["done"].add(i)
    _w["err"].discard(i)
    _w["i"] = _next_todo(i)
    if _w["i"] is None:
        _w["complete"] = True
    _arm()


# -- drawing -------------------------------------------------------------------

def _set_hint(slug):
    """Pick view: what a game's set holds, as "Code, Play, then its 4 game tags"."""
    cards = panel.P.lib.cards(slug)
    if slug == library.UTILITY:
        return ", ".join(lb for lb, _ in cards)
    base = [lb for lb, _ in cards if lb in ("Code", "Play")]
    n = len(cards) - len(base)
    return ", ".join(base) + (f", then its {n} game tag{'' if n == 1 else 's'}" if n else "")


def _says(text):
    """Read view: (title, hint) for a tag's text: game name and tag name when it is a game's tag."""
    P = panel.P
    slug, _, rest = text.partition(":")
    if slug == "getcode":
        g = P.lib.get(rest.split("@", 1)[0])
        return (g["name"] if g else rest.split("@", 1)[0]), "Code"
    g = P.lib.get(slug)
    if g is not None:
        return g["name"], library.friendly(text) if rest else "Play"
    return text, ""


def _words():
    """(header, kicker, title, hint): the design boards' copy, nothing more."""
    P = panel.P
    mode = _w["mode"]
    if mode == "games" and _w["view"] == "pick":
        g = P.lib.get(_w["gsel"]) if _w["gsel"] else None
        name = "Utility" if _w["gsel"] == library.UTILITY else (g["name"] if g else "")
        return "Games", "GAME" if name else "", name, _set_hint(_w["gsel"]) if name else ""
    if mode == "games":
        cards = _w["cards"]
        g = P.lib.get(_w["slug"])
        head = g["name"] if g else "Utility"
        if _w["complete"]:
            return head, "SET COMPLETE", f"All {len(cards)} written", ""
        i = _w["i"]
        label = cards[i][0] if i is not None else ""
        if _w["busy"]:
            return head, "NOW WRITING", label, "Hold still"
        if _w["held"] and P.need_lift and _w["last"] and i not in _w["err"]:
            return head, "NOW WRITING", _w["last"], f"Next: {label}"
        return head, "NOW WRITING", label, "Hold until the beep"
    if mode == "write":
        if _w["wrote"]:
            return "Write a tag", "DONE", _w["text"], "Write another tag with the same text?"
        kick = "NOW WRITING" if _w["text"] else ""
        return "Write a tag", kick, _w["text"], ("Hold still" if _w["busy"] else
                                                 "Hold until the beep") if _w["text"] else ""
    if _w["blank"]:
        return "Read a tag", "THIS TAG SAYS", "Blank Tag", ""
    if _w["read"]:
        title, hint = _says(_w["read"])
        return "Read a tag", "THIS TAG SAYS", title, hint
    return "Read a tag", "READ", "Tap a tag", ""


def _buttons():
    """(secondary label or None, primary label or None, primary enabled)."""
    mode = _w["mode"]
    if mode == "games" and _w["view"] == "pick":
        return None, "Open", _w["gsel"] is not None
    if mode == "games":
        if _w["complete"]:
            return "Write another set", "Exit", True
        return "Skip", "Exit", True
    if mode == "write":
        if _w["wrote"]:
            return "New text", "Same again", True
        return "Edit text", "Done", True
    if _w["blank"]:
        return "Write a tag", "Done", True
    return ("Write it again" if _w["read"] else None), "Done", True


def _show():
    P = panel.P
    _w["seg"](_w["mode"])
    items = _items()
    pages = max(1, (len(items) + ROWS - 1) // ROWS)
    if _w["mode"] == "games" and _w["view"] == "set" and _w["i"] is not None:
        _w["page"] = _w["i"] // ROWS
    _w["page"] = min(_w["page"], pages - 1)
    side.fill(_w["side"], items[_w["page"] * ROWS:(_w["page"] + 1) * ROWS])
    for b in _w["pager"]:
        k.show_hide(b, pages > 1)
    head, kick, title, hint = _words()
    k.st(_w["head"], head)
    k.st(_w["kicker"], kick)
    k.st(_w["title"], title)
    k.st(_w["hint"], hint)
    k.show_hide(_w["radio"], P.nfc_on)
    sec, pri, en = _buttons()
    k.show_hide(_w["sec"], sec is not None)
    k.show_hide(_w["pri"], pri is not None)
    if sec is not None:
        k.st(k.lbl(_w["sec"]), sec)
    if pri is not None:
        k.st(k.lbl(_w["pri"]), pri)
        k.set_enabled(_w["pri"], en)


def refresh():
    P = panel.P
    if not _w["entered"]:
        _w["entered"] = True
        nfc_target.attach(k._scr["scr_cards"])
        _w["held"] = False
        P.nfc_enter()
        _arm()
        if _w["mode"] == "write" and not _w["text"]:
            _type()
        return
    if _w["held"] and not P.need_lift:
        _w["held"] = False
        _target()
    _show()
