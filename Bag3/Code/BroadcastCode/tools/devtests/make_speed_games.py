"""
make_speed_games.py — write exact-size game files for pull-speed benches.

Each file is a valid wand game whose play() returns immediately, padded with
comment lines to an exact byte size. Comments keep compile() cheap on the
wand, so the timing measures transfer rather than parsing; the file still has
to be read into RAM whole for the compile check, which is what makes the
largest size a limit probe as well as a speed point.

Usage:
    python3 tools/devtests/make_speed_games.py OUT_DIR [SIZE_KB ...]

Default sizes: 5 10 20 40. Writes speedNN.py (slug speedNN) per size.
"""

import os
import sys

HEADER = (
    '"""Pull-speed bench file. play() returns at once."""\n'
    '\n'
    '\n'
    'def play(nfc, leds, buz, accel, i2c, enow, batt=None):\n'
    '    return None\n'
    '\n'
)
PAD_LINE = '# ' + 'x' * 61 + '\n'   # 64 bytes


def build(size):
    """Return file text of exactly `size` bytes."""
    body = HEADER
    while len(body) + len(PAD_LINE) <= size:
        body += PAD_LINE
    rest = size - len(body)
    if rest == 1:
        body += '\n'
    elif rest > 1:
        body += '#' + 'x' * (rest - 2) + '\n'
    assert len(body.encode('utf-8')) == size
    return body


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    out = argv[1]
    sizes = [int(a) for a in argv[2:]] or [5, 10, 20, 40]
    os.makedirs(out, exist_ok=True)
    for kb in sizes:
        name = 'speed%02d.py' % kb
        path = os.path.join(out, name)
        text = build(kb * 1024)
        compile(text, name, 'exec')
        with open(path, 'w') as f:
            f.write(text)
        print('%s  %d bytes' % (path, len(text)))


if __name__ == '__main__':
    main(sys.argv)
