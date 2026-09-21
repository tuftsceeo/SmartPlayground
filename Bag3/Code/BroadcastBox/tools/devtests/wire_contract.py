"""
The pull wire contract, exercised host-side against either device's server.

code_server.py and code_puller.py are hand-duplicated peers on different
devices; nothing at compile time makes them agree. This drives the real
functions from both files against each other, so a frame that one writes and
the other cannot read fails here rather than on a bench.

Both devices run the same multi-client CodeServer: a non-blocking state
machine with no _serve_client() to call, so the only way in is poll(). This
runs a real loopback listener, spins poll() in the main thread, and drives
each puller from its own thread -- which is also what makes the concurrency
cases at the bottom possible.

Entry points: wire_test.py (Box) and wire_test_dial.py (Dial) each call run()
with their own firmware directory. The Box and Dial copies of code_server.py
are the same file bar their heap comments, so they are held to the same cases.

MicroPython-only modules are stubbed (see stubs/); sockets are wrapped to
offer MicroPython's read/write stream API (read -> None when nothing is
ready) over CPython sockets.
"""
import os, sys, socket, threading, tempfile, shutil, time

# The real select, imported before stubs/ goes on the path: the stub there is
# a no-op for JsonLink's poll(), and code_server genuinely multiplexes on
# select.select(). Caching it in sys.modules keeps code_server's own
# `import select` off the stub.
import select as _real_select
sys.modules["select"] = _real_select

import time as _time
_time.sleep_ms = lambda ms: None          # MicroPython spelling
_time.ticks_ms = lambda: int(_time.time() * 1000)
_time.ticks_diff = lambda a, b: a - b
_time.ticks_add = lambda t, d: t + d      # code_server's per-client deadlines

import gc as _gc
# MicroPython spelling, used by _accept_new()'s MIN_FREE_ACCEPT guard. Report
# plenty of headroom so the accept path under test is the normal one; the
# low-memory branch is a deliberate deferral, not a wire-contract behaviour.
_gc.mem_free = lambda: 1 << 20

SCRATCH = os.path.dirname(os.path.abspath(__file__))
# BroadcastBox/, two levels up from tools/devtests/.
REPO = os.path.dirname(os.path.dirname(SCRATCH))


class MpSocket:
    """MicroPython stream-socket surface over a CPython socket.

    read() returns None when a non-blocking socket has nothing ready, which
    is the MicroPython behaviour code_server's step functions are written
    against (CPython raises BlockingIOError instead). write() returns the
    count actually sent, so partial writes exercise the same resume path a
    real transfer does.
    """
    def __init__(self, sock):
        self._s = sock
    def fileno(self):
        return self._s.fileno()          # so select.select() accepts us
    def setblocking(self, flag):
        self._s.setblocking(flag)
    def settimeout(self, t):
        self._s.settimeout(t)
    def write(self, data):
        try:
            return self._s.send(bytes(data))
        except BlockingIOError:
            return 0
    def read(self, n):
        try:
            return self._s.recv(n)
        except BlockingIOError:
            return None
    def recv(self, n):
        return self._s.recv(n)
    def readinto(self, buf, n=None):
        want = len(buf) if n is None else n
        data = self._s.recv(want)
        buf[:len(data)] = data
        return len(data)
    def close(self):
        self._s.close()


class Listener:
    """The listening socket, handing code_server MpSocket-wrapped clients."""
    def __init__(self, backlog):
        self._s = socket.socket()
        self._s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._s.bind(("127.0.0.1", 0))
        self._s.listen(backlog)
        self._s.setblocking(False)
        self.port = self._s.getsockname()[1]
    def accept(self):
        conn, addr = self._s.accept()    # BlockingIOError is an OSError
        return MpSocket(conn), addr
    def close(self):
        self._s.close()


def run(firmware_dir, device):
    """Drive every case against one device's code_server.py.

    firmware_dir: path to the firmware directory, relative to BroadcastBox/.
    device:       name for the banner ("Box" / "Dial").
    Returns the number of failed checks.
    """
    tmp = tempfile.mkdtemp(prefix="wire-")
    os.environ["TEST_GAMES_DIR"] = os.path.join(tmp, "games")

    sys.path.insert(0, os.path.join(SCRATCH, "stubs"))
    sys.path.insert(0, os.path.join(REPO, "MockWand", "lib"))  # game_store, nfc_reader
    sys.path.insert(0, os.path.join(REPO, firmware_dir))
    import code_server
    sys.path.remove(os.path.join(REPO, firmware_dir))
    sys.path.insert(0, os.path.join(REPO, "MockWand"))
    import code_puller

    flash = os.path.join(tmp, "flash")
    games = os.path.join(flash, "games")
    os.makedirs(games)
    code_server.FS_ROOT = flash
    code_server.GAMES_DIR = games
    code_server.ACTIVE_PATH = os.path.join(flash, "active.txt")
    code_server.DEFAULT_SRC = os.path.join(flash, "payload.py")

    device_games = os.path.join(tmp, "device_games")
    device_icons = os.path.join(tmp, "device_icons")
    os.makedirs(device_games)

    failures = []

    def check(label, got, want):
        ok = got == want
        print("%-4s %-58s got=%r want=%r" % ("ok" if ok else "FAIL", label, got, want))
        if not ok:
            failures.append(label)

    def write_game(name, body):
        path = os.path.join(games, name)
        with open(path, "w") as f:
            f.write(body)
        return path

    def pull(port, slug, hubtype, dest_dir, icon_dir=None):
        """One device's pull, driven through code_puller's real frame helpers.

        Runs in its own thread; returns what it saw.
        """
        out = {}
        s = socket.create_connection(("127.0.0.1", port), timeout=10)
        cs = MpSocket(s)
        try:
            code_puller._write_request(cs, slug, hubtype)
            size, digest, name = code_puller._read_file_header(cs)
            if size == 0:
                out["name"] = None           # the zero-size refusal
            else:
                out["name"] = name
                part = os.path.join(dest_dir, name + ".part")
                good = code_puller._recv_body(cs, part, size, digest)
                cs.write(b"OK" if good else b"NO")
                if good:
                    dest = os.path.join(dest_dir, name)
                    os.replace(part, dest)
                    out["body"] = open(dest).read()
                if icon_dir:
                    shutil.rmtree(icon_dir, ignore_errors=True)
                    out["icons"] = code_puller._pull_icons(cs, icon_dir)
        except Exception as e:
            out["client_exc"] = repr(e)
        finally:
            s.close()
        return out

    def new_server(listener):
        """A CodeServer armed against an already-listening socket.

        arm() would bring up a real SoftAP, so the two things it sets are set
        here instead; everything below arm() is the code under test.
        """
        srv = code_server.CodeServer()
        srv._srv = listener
        srv._armed = True
        return srv

    def serve_until_idle(srv, threads, should_abort=None, timeout=15):
        """Spin poll() the way the device's main loop does, until the clients
        are done and nothing is left in flight. Returns the events fired."""
        events = []
        deadline = time.time() + timeout
        aborted = False
        while time.time() < deadline:
            r = srv.poll(on_event=events.append, should_abort=should_abort)
            if r == "abort":
                aborted = True
                break
            if not any(t.is_alive() for t in threads) and srv.serving_count == 0:
                break
            time.sleep(0.001)
        if aborted:
            events.append("abort")
        for t in threads:
            t.join(5)
        return events

    def run_case(label, requests, expect):
        """Drive `requests` concurrently and compare against `expect`.

        requests: list of (key, slug, hubtype, icon_dir)
        expect:   key -> the fields to check on that client's result
        """
        print("\n--- %s ---" % label)
        listener = Listener(code_server.MAX_CLIENTS)
        srv = new_server(listener)
        results = {}
        threads = []

        def one(key, slug, hubtype, icon_dir):
            dest = os.path.join(device_games, key)
            shutil.rmtree(dest, ignore_errors=True)
            os.makedirs(dest)
            results[key] = pull(listener.port, slug, hubtype, dest, icon_dir)

        for key, slug, hubtype, icon_dir in requests:
            t = threading.Thread(target=one, args=(key, slug, hubtype, icon_dir))
            threads.append(t)
            t.start()
        events = serve_until_idle(srv, threads)
        srv._drop_all()
        listener.close()

        for key, wanted in expect.items():
            got = results.get(key, {})
            if "client_exc" in got:
                check("%s/%s no client exception" % (label, key), got["client_exc"], None)
            for field, want in wanted.items():
                check("%s/%s %s" % (label, key, field), got.get(field), want)
        return events, srv

    wand_src = "# wand file\nCOMMANDS = {'goal'}\n"
    icon_src = "# icon file\nCOMMANDS = {'goal'}\n"
    jump_src = "# another wand file\nCOMMANDS = {'jump'}\n"
    write_game("goalrace.py", wand_src)
    write_game("goalrace_icon.py", icon_src)
    write_game("wandonly.py", "# wand only\n")
    write_game("jumpin.py", jump_src)

    icons = os.path.join(games, "goalrace_icons")
    os.makedirs(icons)
    for n, txt in (("whale.py", "ICON = (\n(1,2,3),\n)\n"),
                   ("tree.py", "ICON = (\n(4,5,6),\n)\n")):
        with open(os.path.join(icons, n), "w") as f:
            f.write(txt)
    expect_icon_names = ["tree.py", "whale.py"]

    print("=" * 78)
    print("%s: THE V2 CONTRACT" % device.upper())

    run_case("v1 wand (un-updated: no hubtype) still gets the wand file",
             [("a", "goalrace", "", None)],
             {"a": {"name": "goalrace.py", "body": wand_src}})

    run_case("v2 wand: same file, and NO icon leg",
             [("a", "goalrace", "wand", None)],
             {"a": {"name": "goalrace.py", "body": wand_src}})

    run_case("v2 icon_display: the _icon file, landing as <slug>.py, plus icons",
             [("a", "goalrace", "icon_display", device_icons)],
             {"a": {"name": "goalrace.py", "body": icon_src, "icons": 2}})
    check("icon files promoted", sorted(os.listdir(device_icons)), expect_icon_names)

    run_case("a display asking for a wand-only game is refused, not handed the wand file",
             [("a", "wandonly", "icon_display", None)], {"a": {"name": None}})

    run_case("an unknown hubtype is refused rather than guessed at",
             [("a", "goalrace", "radar", None)], {"a": {"name": None}})

    run_case("an unknown slug is still the plain zero-size refusal",
             [("a", "nosuchgame", "wand", None)], {"a": {"name": None}})

    # A zero-length slug is the "serve whatever is active" frame -- the
    # shortest v1 request there is, and the one the length-prefix parser has
    # to complete without reading a slug at all.
    with open(code_server.ACTIVE_PATH, "w") as f:
        f.write("jumpin\n")
    run_case("an empty slug serves whatever active.txt names",
             [("a", "", "", None)],
             {"a": {"name": "jumpin.py", "body": jump_src}})
    os.remove(code_server.ACTIVE_PATH)

    print()
    print("=" * 78)
    print("%s: CONCURRENCY (several devices at once)" % device.upper())

    events, srv = run_case(
        "three devices, different games and roles, all served at once",
        [("wand1", "goalrace", "wand", None),
         ("wand2", "jumpin", "wand", None),
         ("disp", "goalrace", "icon_display", device_icons)],
        {"wand1": {"name": "goalrace.py", "body": wand_src},
         "wand2": {"name": "jumpin.py", "body": jump_src},
         "disp": {"name": "goalrace.py", "body": icon_src, "icons": 2}})
    check("three 'serving' events", events.count("serving"), 3)
    check("three 'ok' events", events.count("ok"), 3)
    check("no 'fail' events", events.count("fail"), 0)
    check("pickups counted per device", srv.pickups, 3)

    events, srv = run_case(
        "a refused device does not disturb the two real transfers beside it",
        [("good1", "goalrace", "wand", None),
         ("bad", "nosuchgame", "wand", None),
         ("good2", "jumpin", "wand", None)],
        {"good1": {"name": "goalrace.py", "body": wand_src},
         "bad": {"name": None},
         "good2": {"name": "jumpin.py", "body": jump_src}})
    check("two ok, one fail", (events.count("ok"), events.count("fail")), (2, 1))

    # Abort: the teacher leaves SERVE mid-transfer. Every in-flight device is
    # dropped without an ack, and none of them promotes a file.
    print("\n--- abort drops every in-flight device ---")
    listener = Listener(code_server.MAX_CLIENTS)
    srv = new_server(listener)
    results = {}
    threads = []
    for key, slug in (("a", "goalrace"), ("b", "jumpin")):
        dest = os.path.join(device_games, "abort_" + key)
        shutil.rmtree(dest, ignore_errors=True)
        os.makedirs(dest)

        def one(key=key, slug=slug, dest=dest):
            results[key] = pull(listener.port, slug, "wand", dest)
        t = threading.Thread(target=one)
        threads.append(t)
        t.start()

    # Let the clients connect and get accepted, then pull the plug.
    ticks = [0]

    def abort_once_serving():
        ticks[0] += 1
        return ticks[0] > 2 and srv.serving_count > 0

    events = serve_until_idle(srv, threads, should_abort=abort_once_serving, timeout=10)
    check("poll() reported the abort", "abort" in events, True)
    check("nothing left in flight", srv.serving_count, 0)
    check("no device was told its pull succeeded", events.count("ok"), 0)
    check("abort is not counted as a pickup", srv.pickups, 0)
    for key in ("a", "b"):
        promoted = [n for n in os.listdir(os.path.join(device_games, "abort_" + key))
                    if not n.endswith(".part")]
        check("device %s promoted nothing" % key, promoted, [])
    srv._drop_all()
    listener.close()

    shutil.rmtree(tmp, ignore_errors=True)
    print()
    if failures:
        print("FAILED: %d" % len(failures))
        for f in failures:
            print("  -", f)
    else:
        print("%s wire contract + concurrency OK" % device)
    return len(failures)
