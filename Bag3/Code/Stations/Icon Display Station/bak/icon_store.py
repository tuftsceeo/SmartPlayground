"""
icon_store.py -- list/read/write/delete icons/<name>.py on the device
filesystem. See the top-level plan for the design rationale, notably:

  - read_icon() PARSES the file rather than __import__-ing it: import
    caches in sys.modules (so a reload right after a save would show
    stale data), compiles ~3KB of source, and executes filesystem code.
    A line-at-a-time parser has none of those problems and bounded RAM.
  - write_icon() matches iconlib/emit.py:write_icon()'s text format
    (device-contract-compatible -- main.py's cycle mode, icon_test.py,
    and the Python CLI all read the same shape) and writes tmp-then-rename
    so a mid-write disconnect can't leave a corrupt, importable-looking
    icon file behind.
"""

import os

DIR = "icons"
RESERVED = ("main", "boot", "icon_matrix", "icon_store", "icon_server", "json_link")
MAX_NAME_LEN = 24

HEADER = ("# Generated on-device by the web icon editor -- 16x16 linear "
          "PWM duty bytes, row-major from top-left.\n")


def ensure_dir():
    try:
        os.mkdir(DIR)
    except OSError:
        pass  # already exists


def _is_lower(o):
    return 97 <= o <= 122  # 'a'-'z'


def _is_digit(o):
    return 48 <= o <= 57  # '0'-'9'


def safe_name(name):
    # ord()-based checks rather than str.isdigit()/.islower() -- those
    # methods aren't guaranteed present on every MicroPython str build.
    if not name or not isinstance(name, str):
        raise ValueError("bad_name")
    if len(name) > MAX_NAME_LEN:
        raise ValueError("bad_name")
    if _is_digit(ord(name[0])):
        raise ValueError("bad_name")
    for ch in name:
        o = ord(ch)
        if not (_is_lower(o) or _is_digit(o) or ch == "_"):
            raise ValueError("bad_name")
    if name in RESERVED:
        raise ValueError("bad_name")
    return name


def path_for(name):
    return "%s/%s.py" % (DIR, name)


def exists(name):
    try:
        os.stat(path_for(name))
        return True
    except OSError:
        return False


def list_icons():
    ensure_dir()
    out = []
    for fn in os.listdir(DIR):
        if not fn.endswith(".py") or fn.startswith("_"):
            continue
        name = fn[:-3]
        try:
            size = os.stat(DIR + "/" + fn)[6]
        except OSError:
            size = 0
        out.append({"name": name, "bytes": size})
    out.sort(key=lambda e: e["name"])
    return out


def delete_icon(name):
    n = safe_name(name)
    os.remove(path_for(n))
    return n


def read_icon(name, into=None):
    """Parse icons/<name>.py -- accepts emit.write_icon()'s shape (any
    line beginning with '(' is a row of (r,g,b) tuples). Bounded RAM:
    ~220 bytes live per line, never the whole file at once."""
    n = safe_name(name)
    out = into if into is not None else bytearray(768)
    i = 0
    with open(path_for(n)) as f:
        for line in f:
            line = line.strip()
            if not line or line[0] != "(":
                continue
            for grp in line.split("),"):
                grp = grp.replace("(", "").replace(")", "").strip().strip(",").strip()
                if not grp:
                    continue
                parts = grp.split(",")
                if len(parts) != 3:
                    continue
                if i >= 768:
                    raise ValueError("more than 256 pixels")
                for k in range(3):
                    v = int(parts[k].strip())
                    out[i + k] = 0 if v < 0 else (255 if v > 255 else v)
                i += 3
    if i != 768:
        raise ValueError("expected 256 pixels, parsed %d" % (i // 3))
    return out


def write_icon(name, src, header=HEADER):
    n = safe_name(name)
    ensure_dir()
    p = path_for(n)
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        f.write(header)
        f.write("ICON = (\n")
        for row in range(16):
            base = row * 48
            parts = []
            for col in range(16):
                o = base + col * 3
                parts.append("(%d, %d, %d)" % (src[o], src[o + 1], src[o + 2]))
            f.write("    " + ", ".join(parts) + ",\n")
        f.write(")\n")
    try:
        os.remove(p)
    except OSError:
        pass
    os.rename(tmp, p)
    return os.stat(p)[6]
