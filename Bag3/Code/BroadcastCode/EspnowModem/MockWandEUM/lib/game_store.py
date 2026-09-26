"""
game_store.py — pulled-game library on wand flash.

Games pulled from the Broadcast Box live in /games/<slug>.py, NOT in the
flash root. Two reasons:

  * the root already holds the built-in games, main.py and the boot files,
    and a pulled game must never be able to shadow one of them;
  * /games is appended to sys.path (see main.py), so a pulled game imports
    by its bare slug exactly the way a built-in does -- __import__(slug) --
    with no special-case loader.

A slug is therefore a MicroPython module name. It must be a legal identifier:
lowercase, leading letter, [a-z0-9_], max 16 chars. That rule is enforced in
three places that must agree -- ChatBroadcast/js/gameName.js (where the
teacher's pretty name becomes a slug), lib/nfc_reader.py's is_valid_slug()
(what a card is allowed to say), and here (what is allowed on flash).
"""

import os

GAMES_DIR = '/games'
LAST_PULLED = GAMES_DIR + '/last_pulled.txt'

try:
    from nfc_reader import is_valid_slug
except ImportError:  # nfc_reader pulls in hardware deps in some contexts
    def is_valid_slug(slug):
        if not slug or len(slug) > 16:
            return False
        if not ('a' <= slug[0] <= 'z'):
            return False
        for ch in slug:
            if not (('a' <= ch <= 'z') or ('0' <= ch <= '9') or ch == '_'):
                return False
        return True


def ensure_dir():
    """Create /games if absent. Safe to call repeatedly."""
    try:
        os.mkdir(GAMES_DIR)
    except OSError:
        pass  # already exists, or read-only fs -- callers degrade to empty


def path(slug):
    return GAMES_DIR + '/' + slug + '.py'


def slugs():
    """Every playable pulled game, as a sorted list of slugs.

    Skips zero-byte files (a truncated write) and anything whose name is not
    a legal slug, so a stray file can never become a tag the wand answers to.
    """
    out = []
    try:
        names = os.listdir(GAMES_DIR)
    except OSError:
        return out
    for name in names:
        if not name.endswith('.py'):
            continue
        slug = name[:-3]
        if not is_valid_slug(slug):
            continue
        try:
            if os.stat(GAMES_DIR + '/' + name)[6] <= 0:
                continue
        except OSError:
            continue
        out.append(slug)
    out.sort()
    return out


def exists(slug):
    if not is_valid_slug(slug):
        return False
    try:
        return os.stat(path(slug))[6] > 0
    except OSError:
        return False


def set_last_pulled(slug):
    """Remember what the pull that is about to reset the chip fetched.

    Closed before returning: the caller resets moments later and an unflushed
    buffer would lose it (same reasoning as pull_flag._write).
    """
    try:
        ensure_dir()
        with open(LAST_PULLED, 'w') as f:
            f.write(slug or '')
        return True
    except OSError:
        return False


def take_last_pulled():
    """Read and clear the just-pulled slug. Returns None if unset/invalid.

    Cleared on read so a game auto-launches exactly once, on the boot right
    after its pull -- never again on later boots.
    """
    try:
        with open(LAST_PULLED, 'r') as f:
            slug = f.read().strip()
    except OSError:
        return None
    try:
        os.remove(LAST_PULLED)
    except OSError:
        pass
    return slug if slug and exists(slug) else None
