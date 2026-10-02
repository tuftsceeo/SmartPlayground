"""tag_catalog.py -- known card texts grouped by game, plus the word bank.

Sources, in order:
  1. /flash/catalog.json, same shape as the Dial's games/index.json:
       {"<slug>": {"name": "Goalrace", "tags": ["goalrace", "goal", ...]}}
     ChatBroadcast (or a hand copy of a Dial's index.json) supplies this.
  2. Built-in: one group per game in game_tags.GAME_TAGS, holding that
     game's entry tag, and a "Controls" group (start, stop).

"getcode..." tags are dropped: their written form carries a Broadcast
Dial/Box host id, and this station serves no code.

Word bank (/flash/words.json, a JSON list of strings) feeds the text
entry "words" ring; every catalog tag is appended to it.
"""

import json

from game_tags import GAME_TAGS, CONTROL_TAGS

CATALOG_PATH = "/flash/catalog.json"
WORDS_PATH = "/flash/words.json"
CONTROLS_NAME = "Controls"


def _pretty(slug):
    return " ".join(w[:1].upper() + w[1:] for w in slug.replace("_", " ").split())


def _read_json(path):
    """Parsed JSON, or None if the file does not exist. Bad JSON raises."""
    try:
        f = open(path)
    except OSError:
        return None
    try:
        return json.loads(f.read())
    finally:
        f.close()


def _clean_tags(tags):
    out = []
    for t in tags:
        t = str(t).strip().lower()
        if t and not t.startswith("getcode") and t not in out:
            out.append(t)
    return out


def builtin_groups():
    groups = [(_pretty(g), [g]) for g in sorted(GAME_TAGS)]
    groups.append((CONTROLS_NAME, sorted(CONTROL_TAGS)))
    return groups


def groups_from_index(index):
    """[(name, [tag, ...])] from an index.json-shaped dict, sorted by name."""
    if not isinstance(index, dict):
        raise ValueError("catalog must be an object of slug -> {name, tags}")
    groups = []
    for slug in index:
        entry = index[slug]
        if not isinstance(entry, dict):
            raise ValueError("catalog entry %r is not an object" % slug)
        tags = _clean_tags(entry.get("tags", ()))
        if tags:
            groups.append((entry.get("name") or _pretty(slug), tags))
    groups.sort(key=lambda g: g[0].lower())
    return groups


def load_groups(path=CATALOG_PATH):
    index = _read_json(path)
    if index is None:
        return builtin_groups()
    groups = groups_from_index(index)
    if not any(name == CONTROLS_NAME for name, _ in groups):
        groups.append((CONTROLS_NAME, sorted(CONTROL_TAGS)))
    return groups


def load_words(groups, path=WORDS_PATH):
    words = _read_json(path)
    if words is None:
        words = []
    if not isinstance(words, list):
        raise ValueError("%s must be a JSON list" % path)
    out = _clean_tags(words)
    for _, tags in groups:
        for t in tags:
            if t not in out:
                out.append(t)
    return out


def save_json(path, obj):
    f = open(path, "w")
    try:
        f.write(json.dumps(obj))
    finally:
        f.close()
