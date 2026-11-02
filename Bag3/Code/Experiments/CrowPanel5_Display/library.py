"""Game library: built-in wand games plus the games on flash (/flash/games)."""

import json
import os

from code_link import GAMES_DIR, ACTIVE_PATH, HOST_ID

INDEX_PATH = GAMES_DIR + "/index.json"
STAGING = ("_icon.py", "_splat.py")

# Built-in classroom games, from the wand's game_tags (bench-only games left out).
BUILTIN = (
    ("colorquest", "Color Quest"), ("freezedance", "Freeze Dance"), ("jumpin", "Jump In"),
    ("cooking", "Cooking"), ("melody", "Melody"), ("shake", "Shake"),
    ("shakerainbow", "Shake Rainbow"), ("rainbow", "Rainbow"), ("jump", "Jump"),
    ("sound", "Sound"), ("nfcsound", "NFC Sound"), ("simpleicecream", "Ice Cream"),
    ("multiicecream", "Ice Cream Team"), ("gestures", "Gestures"),
)
COLORS = (0xBF75C9, 0x22C3A6, 0xEF4D92, 0x6C4CD1, 0xF2A33A, 0x2F6BFF, 0x34C759)


def _color(slug):
    return COLORS[sum(slug.encode()) % len(COLORS)]


def _pretty(slug):
    return " ".join(p[:1].upper() + p[1:] for p in slug.replace("_", "-").split("-") if p)


class Library:
    def __init__(self):
        self.games = []     # dicts: slug, name, flash, color, tags, bytes
        self.scan()

    def ensure_dirs(self):
        for d in ("/flash", GAMES_DIR):
            try:
                os.mkdir(d)
            except OSError:
                pass

    def _tags(self, slug):
        try:
            with open(f"{GAMES_DIR}/{slug}.tags.json") as f:
                d = json.loads(f.read() or "[]")
            return [x for x in d if isinstance(x, str) and x] if isinstance(d, list) else []
        except Exception:
            return []

    def scan(self):
        """Rebuild the list from flash; keeps index.json (names, as the host wrote it) current."""
        self.ensure_dirs()
        try:
            with open(INDEX_PATH) as f:
                idx = json.loads(f.read() or "{}")
        except Exception:
            idx = {}
        flash = []
        try:
            names = os.listdir(GAMES_DIR)
        except OSError:
            names = []
        nxt = {}
        for n in names:
            if not n.endswith(".py") or n.endswith(STAGING):
                continue
            slug = n[:-3]
            try:
                size = os.stat(f"{GAMES_DIR}/{n}")[6]
            except OSError:
                continue
            if size <= 0:
                continue
            meta = idx.get(slug) or {"name": _pretty(slug)}
            meta["tags"] = self._tags(slug)
            nxt[slug] = meta
            flash.append({"slug": slug, "name": meta.get("name") or slug, "flash": True,
                          "color": _color(slug), "tags": meta["tags"], "bytes": size})
        try:
            with open(INDEX_PATH, "w") as f:
                f.write(json.dumps(nxt))
        except Exception:
            pass
        self.games = [{"slug": s, "name": n, "flash": False, "color": _color(s), "tags": [], "bytes": 0}
                      for s, n in BUILTIN] + flash
        self._set_active(flash)

    def _set_active(self, flash):
        """code_link serves the active game; keep it pointing at one that exists."""
        try:
            with open(ACTIVE_PATH) as f:
                want = f.read().strip()
        except OSError:
            want = ""
        if flash and want not in [g["slug"] for g in flash]:
            try:
                with open(ACTIVE_PATH, "w") as f:
                    f.write(flash[0]["slug"])
            except OSError:
                pass

    def get(self, slug):
        for g in self.games:
            if g["slug"] == slug:
                return g
        return None

    def flash_games(self):
        return [g for g in self.games if g["flash"]]

    def delete(self, slug):
        for p in (f"{GAMES_DIR}/{slug}.py", f"{GAMES_DIR}/{slug}.tags.json"):
            try:
                os.remove(p)
            except OSError:
                pass
        self.scan()

    def clear(self):
        try:
            for n in os.listdir(GAMES_DIR):
                if n.endswith(".py") or n.endswith(".tags.json"):
                    try:
                        os.remove(f"{GAMES_DIR}/{n}")
                    except OSError:
                        pass
        except OSError:
            pass
        try:
            os.remove(ACTIVE_PATH)
        except OSError:
            pass
        self.scan()

    def cards(self, slug):
        """(label, text) for each card of a game: Code, Play, then its own tags."""
        g = self.get(slug)
        if g is None:
            return []
        out = []
        if g["flash"]:
            out.append(("Code", f"getcode:{slug}@{HOST_ID}"))
        out.append(("Play", slug))
        for tg in g["tags"]:
            if tg not in (f"getcode:{slug}", slug):
                out.append((tg, tg))
        return out
