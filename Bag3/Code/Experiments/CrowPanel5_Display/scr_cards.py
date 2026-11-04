"""Screen 5 - NFC tag modes: Games / Write / Read, with the NFC target.

The radio is paused while this screen is open (the reader field is on). After each tag the
next job waits until the card is lifted (panel.need_lift), as on the Broadcast Dial.
"""

import lvgl as lv

import ds_tokens as t
import library
import nfc_target
import panel
import ui_kit as k
from ui_kit import F12

ROWS = 6
LIST_W = 290
MID_X = 322
MID_W = 192
MAX_TEXT = 54
_rows = []
_w = {"mode": "games", "view": "pick", "gsel": None, "slug": None, "cards": [], "done": set(),
      "err": set(), "i": None, "run": None, "complete": False, "text": "", "wrote": False,
      "read": None, "blank": False, "held": False, "page": 0, "entered": False, "last": None,
      "busy": False, "counts": {}}


def start(mode):
    """Open in `mode` (games / write / read); call before k.go("scr_cards")."""
    _w["mode"] = mode
    _w["view"] = "pick"
    _w["page"] = 0


def opened():
    """After k.go("scr_cards"): Write with no text starts at the keyboard."""
    if _w["mode"] == "write" and not _w["text"]:
        _type()


def _leave():
    _w["entered"] = False
    panel.P.nfc_leave()
    k.back()


def _wrap(parent, x, y, w, color, font):
    lb = k.text(parent, "", color, font, x, y)
    lb.set_width(w)
    lb.set_long_mode(lv.label.LONG_MODE.WRAP)
    return lb


def build():
    scr = k.new_screen()
    hd, _w["head"] = k.header(scr, "", _leave, w=230)
    tr, _w["seg"], _ = k.seg(hd, 0, 8, (("games", "Games"), ("write", "Write"), ("read", "Read")), _mode, 96)
    tr.set_x(k.W - 16 - 296)
    _w["lhead"] = k.slot(scr, 16, 74, LIST_W, t.INK_3, F12)
    for i in range(ROWS):
        r = k.box(scr, 16, 96 + i * 46, LIST_W, 42, t.SURFACE, 10, t.BORDER)
        mk = k.box(r, 9, 8, 22, 22, k.GREY, 11)
        ml = k.text(mk, "", t.SURFACE, F12, align=lv.ALIGN.CENTER)
        nm = k.slot(r, 40, 10, 170, t.INK, k.F_BODY)
        sd = k.slot(r, 214, 12, 64, t.INK_3, F12)
        d = {"row": r, "mk": mk, "ml": ml, "name": nm, "side": sd, "key": None}
        k.on(r, lambda d=d: d["key"] is not None and _tap(d["key"]))
        _rows.append(d)
    _w["kicker"] = k.slot(scr, MID_X, 84, MID_W, t.PURPLE, F12)
    _w["title"] = _wrap(scr, MID_X, 106, MID_W, t.INK, k.F_TITLE)
    _w["hint"] = _wrap(scr, MID_X, 200, MID_W, t.INK_3, k.F_BODY)
    _w["radio"] = k.radio_icon(scr, MID_X, 372)
    _w["edges"] = k.edges(scr, 64)
    ft = k.box(scr, 0, 416, k.W, 64, t.SURFACE)
    k.box(scr, 0, 416, k.W, 1, t.BORDER)
    prev = k.button(ft, 16, 10, 44, "<", t.INK, w=44)
    nxt = k.button(ft, 68, 10, 44, ">", t.INK, w=44)
    k.on(prev, lambda: _page(-1))
    k.on(nxt, lambda: _page(1))
    _w["pager"] = (prev, nxt)
    # labels are set by _show; a button made with "" has no label to set
    _w["sec"] = k.button(ft, k.W - 16 - 170 - 12 - 150, 8, 48, " ", t.INK, font=k.F_HEAD, w=150)
    _w["pri"] = k.button(ft, k.W - 16 - 170, 8, 48, " ", t.SURFACE, font=k.F_HEAD, primary="teal", w=170)
    k.on(_w["sec"], lambda: _foot("sec"))
    k.on(_w["pri"], lambda: _foot("pri"))
    nfc_target.attach(scr)
    return scr


# -- what the list shows -------------------------------------------------------

def _pick_items():
    P = panel.P
    items = [(g["slug"], g["name"], len(P.lib.cards(g["slug"])), g["color"]) for g in P.lib.games]
    items.append((library.UTILITY, "Utility", len(library.UTILITY_TAGS), t.INK_3))
    return items


def _items():
    """[(key, name, side, mark, mark color)] for the list. mark: ok / now / err / dot / ''."""
    mode = _w["mode"]
    out = []
    if mode == "games" and _w["view"] == "pick":
        for slug, name, n, col in _pick_items():
            out.append((slug, name, f"{n} tag{'' if n == 1 else 's'}", "now" if slug == _w["gsel"] else "", col))
    elif mode == "games":
        cards = _w["cards"]
        all_done = len(_w["done"]) == len(cards)
        out.append(("all", "All", "",
                    "ok" if all_done else ("now" if _w["run"] == "all" else ""), t.TEAL))
        for n, (label, _) in enumerate(cards):
            if n == _w["i"]:
                mk = "err" if n in _w["err"] else "now"
            else:
                mk = "ok" if n in _w["done"] else ("err" if n in _w["err"] else "")
            out.append((n, label, "", mk, t.TEAL))
    elif mode == "write":
        for s in panel.P.store.history:
            n = _w["counts"].get(s, 0)
            out.append((s, s, f"{n} tag{'' if n == 1 else 's'}" if n else "", "ok", t.PURPLE))
    return out


_MARK = {"ok": (lv.SYMBOL.OK, t.TEAL), "now": (lv.SYMBOL.RIGHT, t.PINK), "err": ("!", t.DANGER[0])}


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
    cards = _w["cards"]
    for n in list(range(after + 1, len(cards))) + list(range(0, after + 1)):
        if n not in _w["done"]:
            return n
    return None


def _run_all(fresh=False):
    if fresh:
        _w["done"] = set()
        _w["err"] = set()
    _w["run"] = "all"
    _w["i"] = _next_todo()
    _w["complete"] = _w["i"] is None
    if _w["complete"]:
        _w["run"] = None
    _arm()


def _open_set(slug):
    _w["slug"] = slug
    _w["cards"] = panel.P.lib.cards(slug)
    _w["view"] = "set"
    _w["page"] = 0
    _run_all(fresh=True)


def _tap(key):
    mode = _w["mode"]
    if mode == "games" and _w["view"] == "pick":
        _w["gsel"] = key
        _show()
    elif mode == "games":
        if key == "all":
            _run_all(fresh=len(_w["done"]) == len(_w["cards"]))
        else:
            _w["run"] = "one"
            _w["i"] = key
            _w["complete"] = False
            _arm()
    elif mode == "write":
        _w["text"] = key
        _w["wrote"] = False
        _arm()
    else:
        _use_text(key)


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
    if which == "pri" and _buttons()[1] == "Done":
        _leave()
    elif mode == "games" and _w["view"] == "pick":
        if _w["gsel"] is not None:
            _open_set(_w["gsel"])
    elif mode == "games":
        if _w["complete"]:
            _run_all(fresh=True)        # Write another set
        elif _w["run"] == "one":
            _run_all()                  # Back to the set
        else:
            _w["done"].add(_w["i"])     # Skip
            _run_all()
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
    _w["last"] = _w["cards"][i][0]
    _w["done"].add(i)
    _w["err"].discard(i)
    if _w["run"] == "all":
        _w["i"] = _next_todo(i)
        if _w["i"] is None:
            _w["complete"] = True
            _w["run"] = None
    _arm()


# -- drawing -------------------------------------------------------------------

def _set_hint(slug):
    """Pick view: what a game's set holds, as "All, Code, Play, then its 4 game tags"."""
    cards = panel.P.lib.cards(slug)
    base = ["All"] + [lb for lb, _ in cards if lb in ("Code", "Play")]
    n = len(cards) - len(base) + 1
    if slug == library.UTILITY:
        return ", ".join(["All"] + [lb for lb, _ in cards])
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
    """(header, list head, kicker, title, hint): the design boards' copy, nothing more."""
    P = panel.P
    mode = _w["mode"]
    if mode == "games" and _w["view"] == "pick":
        g = P.lib.get(_w["gsel"]) if _w["gsel"] else None
        name = "Utility" if _w["gsel"] == library.UTILITY else (g["name"] if g else "")
        return "Games", "Pick a Game", "GAME" if name else "", name, _set_hint(_w["gsel"]) if name else ""
    if mode == "games":
        cards = _w["cards"]
        g = P.lib.get(_w["slug"])
        head = g["name"] if g else "Utility"
        if _w["complete"]:
            return head, "Tags in this Game", "SET COMPLETE", f"All {len(cards)} written", ""
        i = _w["i"]
        label = cards[i][0] if i is not None else ""
        kick = "REWRITE ONE TAG" if _w["run"] == "one" else "NOW WRITING"
        if _w["busy"]:
            return head, "Tags in this Game", kick, label, "Hold still"
        if _w["held"] and P.need_lift and _w["last"] and i not in _w["err"] and _w["run"] != "one":
            return head, "Tags in this Game", kick, _w["last"], f"Next: {label}"
        return head, "Tags in this Game", kick, label, "Hold until the beep"
    if mode == "write":
        if _w["wrote"]:
            return "Write a tag", "Write History", "DONE", _w["text"], "Write another tag with the same text?"
        kick = "NOW WRITING" if _w["text"] else ""
        return "Write a tag", "Write History", kick, _w["text"], ("Hold still" if _w["busy"] else
                                                                 "Hold until the beep") if _w["text"] else ""
    if _w["blank"]:
        return "Read a tag", "", "THIS TAG SAYS", "Blank Tag", ""
    if _w["read"]:
        title, hint = _says(_w["read"])
        return "Read a tag", "", "THIS TAG SAYS", title, hint
    return "Read a tag", "", "READ", "Tap a tag", ""


def _buttons():
    """(secondary label or None, primary label or None, primary enabled)."""
    mode = _w["mode"]
    if mode == "games" and _w["view"] == "pick":
        return None, "Open", _w["gsel"] is not None
    if mode == "games":
        if _w["complete"]:
            return "Write another set", "Done", True
        if _w["run"] == "one":
            return "Back to the set", "Done", True
        return "Skip", "Done", True
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
        _w["page"] = (_w["i"] + 1) // ROWS
    _w["page"] = min(_w["page"], pages - 1)
    items = items[_w["page"] * ROWS:(_w["page"] + 1) * ROWS]
    for j, d in enumerate(_rows):
        it = items[j] if j < len(items) else None
        k.show_hide(d["row"], it is not None)
        d["key"] = it[0] if it else None
        if it is None:
            continue
        key, name, side, mark, col = it
        k.st(d["name"], name)
        k.st(d["side"], side)
        if mark:
            sym, mc = _MARK[mark]
            k.sty(d["mk"], "bg", mc)
            k.st(d["ml"], sym)
        else:
            k.sty(d["mk"], "bg", k.GREY)
            k.st(d["ml"], "")
        on_ = mark == "now" or (_w["mode"] == "write" and key == _w["text"])
        k.sty(d["row"], "border", t.PINK if on_ else t.BORDER)
        k.sty(d["row"], "bg", t.PINK_50 if on_ else t.SURFACE)
    for b in _w["pager"]:
        k.show_hide(b, pages > 1)
    head, lhead, kick, title, hint = _words()
    k.st(_w["head"], head)
    k.st(_w["lhead"], lhead)
    k.st(_w["kicker"], kick)
    k.st(_w["title"], title)
    k.st(_w["hint"], hint)
    _w["radio"](not P.nfc_on)
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
        return
    if _w["held"] and not P.need_lift:
        _w["held"] = False
        _target()
    _show()
