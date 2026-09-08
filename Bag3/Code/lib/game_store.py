"""
game_store.py -- the pulled-game library on flash.

Games pulled from the Broadcast Box live in /games/<module>.py, not in the
flash root: the root holds main.py and the built-in games, and a pulled file
must never shadow one. /games is on sys.path (see gamelib), so a pulled game
imports by bare name exactly the way a built-in does.

A module is named <slug> for a single-role game, or <slug>_<role> for one role
of a multi-role game. A device holds at most one module per slug, so a game is
resolved by looking at the directory:

    module_for("goalrush") -> "goalrush_teama"

Name rules live here (is_valid_module / split_module) and are shared with
ChatBroadcast/js/gameName.js. They are plain string checks, so nothing on the
game-loading path has to import a driver to ask whether a name is legal.
"""

import os

GAMES_DIR = '/games'
LAST_PULLED = GAMES_DIR + '/last_pulled.txt'


# A game is named by a slug; one device's part in it is named by a role. What
# lands on flash and gets imported is the module name:
#
#     <slug>            single-role game
#     <slug>_<role>     one role of a multi-role game
#
# A slug carries no underscore, so the first underscore always separates the
# two. Both halves are lowercase and start with a letter, and the whole is a
# legal MicroPython module name -- anything else is unimportable.
#
# Kept in lockstep with ChatBroadcast/js/gameName.js.

SLUG_MAX = 14
ROLE_MAX = 9
MODULE_MAX = 24


def _is_lower_alnum(text, allow_underscore):
    if not text or not ('a' <= text[0] <= 'z'):
        return False
    for ch in text:
        if 'a' <= ch <= 'z' or '0' <= ch <= '9':
            continue
        if ch == '_' and allow_underscore:
            continue
        return False
    return True


def is_valid_slug(slug):
    return len(slug or '') <= SLUG_MAX and _is_lower_alnum(slug, False)


def is_valid_role(role):
    return len(role or '') <= ROLE_MAX and _is_lower_alnum(role, True)


def is_valid_module(module):
    """True for "<slug>" or "<slug>_<role>"."""
    if not module or len(module) > MODULE_MAX:
        return False
    slug, sep, role = module.partition('_')
    if not is_valid_slug(slug):
        return False
    return is_valid_role(role) if sep else True


def split_module(module):
    """("<slug>", "<role>" or None). Assumes is_valid_module(module)."""
    slug, sep, role = module.partition('_')
    return (slug, role) if sep else (slug, None)


def ensure_dir():
    """Create /games if absent. Safe to call repeatedly."""
    try:
        os.stat(GAMES_DIR)
    except OSError:
        os.mkdir(GAMES_DIR)


def modules():
    """Every playable module on flash, sorted.

    Skips zero-byte files (a truncated write) and anything not a legal module
    name, so a stray file can never become a tag the device answers to.
    """
    out = []
    try:
        names = os.listdir(GAMES_DIR)
    except OSError:
        return out
    for name in names:
        if not name.endswith('.py'):
            continue
        module = name[:-3]
        if not is_valid_module(module):
            continue
        if os.stat(GAMES_DIR + '/' + name)[6] <= 0:
            continue
        out.append(module)
    out.sort()
    return out


def slugs():
    """The game slugs this device holds, sorted and unique."""
    seen = []
    for module in modules():
        slug = split_module(module)[0]
        if slug not in seen:
            seen.append(slug)
    return seen


def module_for(slug):
    """The module this device holds for a slug, or None.

    Exactly one: promoting a role for a slug removes any other role of it.
    """
    for module in modules():
        if split_module(module)[0] == slug:
            return module
    return None


def role_of(module):
    """The role half of a module name, or None for a single-role game."""
    return split_module(module)[1]


def path(module):
    return GAMES_DIR + '/' + module + '.py'


def exists(module):
    if not is_valid_module(module):
        return False
    try:
        return os.stat(path(module))[6] > 0
    except OSError:
        return False


def drop_other_roles(module):
    """Remove any other role of the same game.

    What keeps module_for() unambiguous: a device plays one part in a game, so
    taking a new role card replaces the one it held.
    """
    slug = split_module(module)[0]
    for other in modules():
        if other != module and split_module(other)[0] == slug:
            os.remove(path(other))
            print("  game_store: dropped %s for %s" % (other, module))


def set_last_pulled(module):
    """Remember what the pull that is about to reset the chip fetched.

    Closed before returning: the caller resets moments later and an unflushed
    buffer would lose it.
    """
    ensure_dir()
    with open(LAST_PULLED, 'w') as f:
        f.write(module or '')


def take_last_pulled():
    """Read and clear the just-pulled slug, or None.

    Cleared on read so a game auto-launches exactly once, on the boot right
    after its pull, and never again.
    """
    try:
        with open(LAST_PULLED, 'r') as f:
            module = f.read().strip()
    except OSError:
        return None
    os.remove(LAST_PULLED)
    if not module or not exists(module):
        return None
    return split_module(module)[0]
