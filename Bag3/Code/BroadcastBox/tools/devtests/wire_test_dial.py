"""
Exercise the Box<->device pull wire contract host-side.

code_server.py and code_puller.py are hand-duplicated peers on different
devices; nothing at compile time makes them agree. This drives the real
functions from both files against each other over a socketpair, so a frame
that one writes and the other cannot read fails here rather than on a bench.

MicroPython-only modules are stubbed (see stubs/); the socket is wrapped to
offer MicroPython's read/write/readinto stream API over a CPython socket.
"""
import os, sys, socket, threading, tempfile, shutil

import os
# BroadcastBox/, two levels up from tools/devtests/.
_BB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = _BB
SCRATCH = os.path.dirname(os.path.abspath(__file__))

import time as _time
_time.sleep_ms = lambda ms: None          # MicroPython spelling
_time.ticks_ms = lambda: int(_time.time() * 1000)
_time.ticks_diff = lambda a, b: a - b

TMP = tempfile.mkdtemp(prefix="wire-")
os.environ["TEST_GAMES_DIR"] = os.path.join(TMP, "games")

sys.path.insert(0, os.path.join(SCRATCH, "stubs"))
sys.path.insert(0, os.path.join(REPO, "MockWand", "lib"))   # game_store, nfc_reader
sys.path.insert(0, os.path.join(REPO, "../BroadcastDial/BDialFirmware"))
import code_server
sys.path.remove(os.path.join(REPO, "../BroadcastDial/BDialFirmware"))
sys.path.insert(0, os.path.join(REPO, "MockWand"))
import code_puller

FLASH = os.path.join(TMP, "flash")
GAMES = os.path.join(FLASH, "games")
os.makedirs(GAMES)
code_server.FS_ROOT = FLASH
code_server.GAMES_DIR = GAMES
code_server.ACTIVE_PATH = os.path.join(FLASH, "active.txt")
code_server.DEFAULT_SRC = os.path.join(FLASH, "payload.py")

DEVICE_GAMES = os.path.join(TMP, "device_games")
DEVICE_ICONS = os.path.join(TMP, "device_icons")
os.makedirs(DEVICE_GAMES)


class MpSocket:
    """MicroPython stream-socket surface over a CPython socket."""
    def __init__(self, sock):
        self._s = sock
    def settimeout(self, t):
        self._s.settimeout(t)
    def write(self, data):
        self._s.sendall(bytes(data))
        return len(data)
    def read(self, n):
        return self._s.recv(n)
    def recv(self, n):
        return self._s.recv(n)
    def readinto(self, buf, n=None):
        want = len(buf) if n is None else n
        data = self._s.recv(want)
        buf[:len(data)] = data
        return len(data)
    def close(self):
        self._s.close()


def write_game(name, body):
    path = os.path.join(GAMES, name)
    with open(path, "w") as f:
        f.write(body)
    return path


def serve_once(server_sock):
    """Run the Box's real _serve_client against one connection."""
    srv = code_server.CodeServer()
    return srv._serve_client(MpSocket(server_sock))


FAILURES = []

def check(label, got, want):
    ok = got == want
    print("%-4s %-52s got=%r want=%r" % ("ok" if ok else "FAIL", label, got, want))
    if not ok:
        FAILURES.append(label)


def run_case(label, slug, hubtype, icon_dir, expect_server, expect_name,
             expect_body=None, expect_icons=None):
    a, b = socket.socketpair()
    result = {}

    def box():
        try:
            result["server"] = serve_once(a)
        except Exception as e:
            result["server"] = "EXC:%r" % (e,)
        finally:
            a.close()

    t = threading.Thread(target=box)
    t.start()

    cs = MpSocket(b)
    try:
        code_puller._write_request(cs, slug, hubtype)
        size, digest, name = code_puller._read_file_header(cs)
        if size == 0:
            result["name"] = None
        else:
            result["name"] = name
            tmp = os.path.join(DEVICE_GAMES, name + ".part")
            good = code_puller._recv_body(cs, tmp, size, digest)
            cs.write(b"OK" if good else b"NO")
            if good:
                dest = os.path.join(DEVICE_GAMES, name)
                os.replace(tmp, dest)
                result["body"] = open(dest).read()
            if icon_dir:
                shutil.rmtree(icon_dir, ignore_errors=True)
                result["icons"] = code_puller._pull_icons(cs, icon_dir)
    except Exception as e:
        result["client_exc"] = repr(e)
    finally:
        b.close()
    t.join(5)

    print("\n--- %s ---" % label)
    if "client_exc" in result:
        check(label + " / no client exception", result["client_exc"], None)
    check(label + " / server result", result.get("server"), expect_server)
    check(label + " / dest name", result.get("name"), expect_name)
    if expect_body is not None:
        check(label + " / body", result.get("body"), expect_body)
    if expect_icons is not None:
        check(label + " / icons promoted", result.get("icons"), expect_icons)
        if expect_icons:
            got = sorted(os.listdir(icon_dir))
            check(label + " / icon files", got, sorted(expect_icons_names))


WAND_SRC = "# wand file\nCOMMANDS = {'goal'}\n"
ICON_SRC = "# icon file\nCOMMANDS = {'goal'}\n"
write_game("goalrace.py", WAND_SRC)
write_game("goalrace_icon.py", ICON_SRC)
write_game("wandonly.py", "# wand only\n")

ICONS = os.path.join(GAMES, "goalrace_icons")
os.makedirs(ICONS)
for n, txt in (("whale.py", "ICON = (\n(1,2,3),\n)\n"), ("tree.py", "ICON = (\n(4,5,6),\n)\n")):
    with open(os.path.join(ICONS, n), "w") as f:
        f.write(txt)
expect_icons_names = ["whale.py", "tree.py"]

print("=" * 70)
print("v1 request (un-updated wand: no hubtype) must still get the wand file")
run_case("v1 wand", "goalrace", "", None, True, "goalrace.py", WAND_SRC)

print("=" * 70)
print("v2 wand: same file, and NO icon leg")
run_case("v2 wand", "goalrace", "wand", None, True, "goalrace.py", WAND_SRC)

print("=" * 70)
print("v2 icon_display: the _icon file, landing as plain <slug>.py, plus icons")
run_case("v2 icon_display", "goalrace", "icon_display", DEVICE_ICONS,
         True, "goalrace.py", ICON_SRC, 2)

print("=" * 70)
print("a display asking for a wand-only game is refused, not handed the wand file")
run_case("icon_display, no icon file", "wandonly", "icon_display", DEVICE_ICONS,
         False, None)

print("=" * 70)
print("an unknown hubtype is refused rather than guessed at")
run_case("unknown hubtype", "goalrace", "radar", None, False, None)

print("=" * 70)
print("an unknown slug is still the plain zero-size refusal")
run_case("unknown slug", "nosuchgame", "wand", None, False, None)

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILURES:
    print("FAILED: %d" % len(FAILURES))
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("wire contract OK")
