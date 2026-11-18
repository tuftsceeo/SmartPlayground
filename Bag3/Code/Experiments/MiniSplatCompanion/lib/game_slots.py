# game_slots.py -- at most MAX custom (pulled) games in /games.
# Import lazily, after the radio is up (AGENTS.md: nothing may allocate
# before the radio claims its memory). Per-tree copy: the IconDisplay keeps
# its own, which differs only in BUILTIN.
#
# /games/slots.json is [[slug, mode], ...], oldest first. mode is one letter
# from the game's declarations (see mode_of).
# Built-in games (BUILTIN) never count and are never removed.

import os
import json

GAMES_DIR = '/games'
SLOTS = GAMES_DIR + '/slots.json'
MAX = 3

# Must equal the .py files in this tree's games/ (tools/tests/test_game_slots.py).
BUILTIN = ('colorpads', 'colorsays', 'echobeat', 'host_lobbytest',
           'host_patternstomp', 'host_relaycolor', 'host_splattag',
           'movemixer', 'picturemoves', 'simonstomp')


def _on_disk():
    out = []
    try:
        names = os.listdir(GAMES_DIR)
    except OSError:
        return out
    for n in names:
        if n.endswith('.py') and n[:-3] not in BUILTIN:
            try:
                if os.stat(GAMES_DIR + '/' + n)[6] > 0:
                    out.append(n[:-3])
            except OSError:
                pass
    out.sort()
    return out


def _decl(line):
    # (name, value) for a top-level NAME = value line, else None.
    line = line.split('#', 1)[0]
    i = line.find('=')
    if i < 1 or line[i + 1:i + 2] == '=' or line[0] in ' \t':
        return None
    return line[:i].strip(), line[i + 1:].strip()


def mode_of(slug):
    """s solo, h Splat host, l plain lobby, o ordinary, x invalid (the wand
    refuses it). Presence decides, as in main.py _splat_limits/_splats_local;
    values are left to the wand's own load check."""
    seen = set()
    try:
        with open(GAMES_DIR + '/' + slug + '.py') as f:
            while True:
                line = f.readline()
                if not line:
                    break
                d = _decl(line)
                if d is None:
                    continue
                k, v = d
                if k == 'SPLAT_HOST':
                    if v == 'True':
                        seen.add(k)
                    else:
                        seen.discard(k)
                elif k in ('SPLATS_MIN', 'SPLATS_MAX', 'SPLATS_LOCAL', 'PLAYERS_MIN'):
                    seen.add(k)
    except OSError:
        pass
    host = 'SPLAT_HOST' in seen
    if (('SPLATS_MIN' in seen or 'SPLATS_MAX' in seen) and not host) or (
            'SPLATS_LOCAL' in seen and (host or 'SPLATS_MIN' in seen
                                        or 'PLAYERS_MIN' in seen)):
        return 'x'
    if 'SPLATS_LOCAL' in seen:
        return 's'
    if host:
        return 'h'
    if 'PLAYERS_MIN' in seen:
        return 'l'
    return 'o'


def load():
    """Slot list, reconciled with the files actually in /games."""
    try:
        with open(SLOTS) as f:
            items = [[e[0], e[1]] for e in json.load(f)]
    except Exception:
        items = []
    disk = _on_disk()
    items = [e for e in items if e[0] in disk]
    held = [e[0] for e in items]
    extra = [[s, mode_of(s)] for s in disk if s not in held]
    return extra + items


_cache = None


def report(role):
    """Fields for status_report: device role and the slot list (cached)."""
    global _cache
    if _cache is None:
        _cache = load()
    return {'role': role or 'player', 'g': _cache}


def _save(items):
    global _cache
    _cache = items
    try:
        with open(SLOTS, 'w') as f:
            json.dump(items, f)
    except OSError:
        pass


def _remove(slug):
    try:
        os.remove(GAMES_DIR + '/' + slug + '.py')
    except OSError:
        pass
    d = GAMES_DIR + '/' + slug + '_icons'
    try:
        for n in os.listdir(d):
            os.remove(d + '/' + n)
        os.rmdir(d)
    except OSError:
        pass


def record(slug, replace=''):
    """Call after a successful pull of slug. Returns the evicted slugs."""
    if not slug or slug in BUILTIN:
        return []
    items = [e for e in load() if e[0] != slug]
    items.append([slug, mode_of(slug)])
    gone = []
    while len(items) > MAX:
        i = 0
        for j in range(len(items) - 1):
            if items[j][0] == replace:
                i = j
                break
        gone.append(items.pop(i)[0])
    for s in gone:
        _remove(s)
    _save(items)
    return gone
