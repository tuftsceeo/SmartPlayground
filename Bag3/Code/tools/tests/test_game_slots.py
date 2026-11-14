"""Off-device test of game_slots.py (wand and IconDisplay copies).

Run: python3 Bag3/Code/tools/tests/test_game_slots.py
"""
import importlib.util
import json
import os
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.normpath(os.path.join(HERE, '..', '..'))
TREES = {
    'wand': os.path.join(CODE, 'Wand Module'),
    'icon_display': os.path.join(CODE, 'Stations', 'IconDisplay'),
}


def load(tree, games_dir):
    spec = importlib.util.spec_from_file_location(
        'game_slots_' + tree, os.path.join(TREES[tree], 'lib', 'game_slots.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.GAMES_DIR = games_dir
    m.SLOTS = games_dir + '/slots.json'
    return m


def write(d, slug, body='def play(*a):\n    pass\n'):
    with open(os.path.join(d, slug + '.py'), 'w') as f:
        f.write(body)


def check_builtin_matches_tree(tree):
    with tempfile.TemporaryDirectory() as d:
        m = load(tree, d)
    real = sorted(n[:-3] for n in os.listdir(os.path.join(TREES[tree], 'games'))
                  if n.endswith('.py'))
    assert sorted(m.BUILTIN) == real, (tree, sorted(m.BUILTIN), real)


def check_policy(tree):
    with tempfile.TemporaryDirectory() as d:
        m = load(tree, d)
        b = m.BUILTIN[0]
        write(d, b)                                      # a built-in on flash
        write(d, 'aaa', 'SPLAT_HOST = True\nSPLATS_MIN = 2\n')
        write(d, 'bbb', 'SPLATS_LOCAL = 2\n')
        write(d, 'ccc', 'PLAYERS_MIN = 2\n')
        os.mkdir(os.path.join(d, 'aaa_icons'))
        write(os.path.join(d, 'aaa_icons'), 'star')

        # No slots.json: rebuilt from disk, built-ins excluded, modes scanned.
        assert m.load() == [['aaa', 'h'], ['bbb', 's'], ['ccc', 'l']], m.load()

        # Fourth game, no replace: oldest (aaa) goes, with its icons folder.
        write(d, 'ddd')
        assert m.record('ddd') == ['aaa']
        assert not os.path.exists(os.path.join(d, 'aaa.py'))
        assert not os.path.exists(os.path.join(d, 'aaa_icons'))
        assert os.path.exists(os.path.join(d, b + '.py'))
        assert [e[0] for e in m.load()] == ['bbb', 'ccc', 'ddd']

        # Replace names a held game: that one goes.
        write(d, 'eee')
        assert m.record('eee', replace='ccc') == ['ccc']
        assert [e[0] for e in m.load()] == ['bbb', 'ddd', 'eee']

        # Replace names a built-in or a game not held: oldest goes instead.
        write(d, 'fff')
        assert m.record('fff', replace=b) == ['bbb']
        write(d, 'ggg')
        assert m.record('ggg', replace='zzz') == ['ddd']

        # Re-pulling a held game moves it to newest, evicts nothing.
        assert m.record('eee') == []
        assert [e[0] for e in m.load()] == ['fff', 'ggg', 'eee']

        # A built-in pull is not recorded.
        assert m.record(b) == []

        # Corrupt slots.json: rebuilt from disk.
        with open(m.SLOTS, 'w') as f:
            f.write('{nope')
        assert sorted(e[0] for e in m.load()) == ['eee', 'fff', 'ggg']

        # Report reflects the cache.
        r = m.report('')
        assert r['role'] == 'player' and len(r['g']) == 3, r


MODE_CASES = [
    ('o', ''),
    ('s', 'SPLATS_LOCAL = 2\n'),
    ('s', 'SPLATS_LOCAL = 5\n'),                       # value left to the wand
    ('h', 'SPLAT_HOST = True\nSPLATS_MIN = 2\n'),
    ('h', 'SPLAT_HOST = True  # host\nSPLATS_MIN = 1\nSPLATS_MAX = 4\nPLAYERS_MIN = 2\n'),
    ('l', 'PLAYERS_MIN = 2\n'),
    ('l', 'SPLAT_HOST = False\nPLAYERS_MIN = 2\n'),    # False counts as absent
    ('x', 'SPLATS_MIN = 2\n'),
    ('x', 'SPLAT_HOST = False\nSPLATS_MAX = 2\n'),
    ('x', 'SPLATS_LOCAL = 1\nPLAYERS_MIN = 2\n'),
    ('x', 'SPLATS_LOCAL = 1\nSPLAT_HOST = True\n'),
    ('x', 'SPLATS_LOCAL = 1\nSPLATS_MIN = 1\n'),
    ('o', '    SPLAT_HOST = True\n'),                  # not top level
    ('o', '# SPLATS_LOCAL = 1\n'),                     # commented out
    ('o', 'if SPLATS_LOCAL == 1:\n    pass\n'),
    ('o', 'x = "SPLATS_LOCAL = 1"\n'),
    ('h', '\n' * 300 + 'SPLAT_HOST = True\nSPLATS_MIN = 2\n'),  # deep in file
]


def check_modes(tree):
    with tempfile.TemporaryDirectory() as d:
        m = load(tree, d)
        for i, (want, body) in enumerate(MODE_CASES):
            write(d, 'm%d' % i, body)
            got = m.mode_of('m%d' % i)
            assert got == want, (tree, want, got, body[-80:])
    if tree == 'wand':                                  # the shipped games
        m.GAMES_DIR = os.path.join(TREES[tree], 'games')
        got = {s: m.mode_of(s) for s in m.BUILTIN}
        print('  wand built-in modes:', got)
        assert got['host_patternstomp'] == 'h', got


def check_payload_size():
    rep = {'type': 'status_report', 'battery': 100, 'rssi': -100,
           'kind': 'icon_display', 'role': 'splat_host',
           'g': [['abcdefghijklmnop', 'h'], ['bcdefghijklmnopq', 's'],
                 ['cdefghijklmnopqr', 'l']]}
    n = len(json.dumps(rep))
    assert n < 250, n
    return n


if __name__ == '__main__':
    for t in TREES:
        check_builtin_matches_tree(t)
        check_policy(t)
        check_modes(t)
        print('ok', t)
    print('ok payload, worst case %d bytes' % check_payload_size())
