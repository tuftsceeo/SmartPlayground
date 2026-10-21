"""
deploy.py — interactive, per-file, verified deploy for any of the four
Broadcast device trees (Dial, Box, Mock Wand, Icon Display).

Host-side tool. Not firmware; never upload this to a device.

Carries the same core technique BroadcastDial/BDialFirmware/tools/
deploy_dial.py already proved on hardware: one `mpremote` invocation per
file, a full-content read-back to verify the write actually landed (not
just a size check -- catches truncation AND corruption), and a retry if a
file fails. Every `mpremote fs`/`exec` call passes `resume`, per
HARDWARE_PROTOCOL.md -- without it, a Box/Dial/Stamp de-enumerates its USB
CDC port on the very first such call. deploy_dial.py stays in place
(BroadcastDial/README.md points at it by name); this script exists for the
other three trees, and for deploying all four from one place.

File lists, per device type:
  - Dial, Box: read from that firmware's own manifest.js (DIAL_FILES /
    BOX_FILES), not a hand-kept copy -- so this can't drift from what
    ChatBroadcast's own installer deploys.
  - Mock Wand, Icon Display: no manifest exists for either, so this walks
    the tree for every `.py` file plus `hubtype.txt`, preserving `lib/`,
    `games/` and (Icon Display) `icons/`, and skipping `tools/` and
    `README.md` (never deployed).

Destinations: `/flash/...` for the Dial and Box (the only path M5/UIFlow
writes accept -- see HARDWARE_PROTOCOL.md), the flash root for Mock Wand
and Icon Display (see MockWand/README.md's Deploy section).

Follow HARDWARE_PROTOCOL.md before running this: ask which port is which,
ask before opening it, and wait for an explicit go. This script does not
ask for you -- it only prompts for the choices it cannot make on its own
(which port, which device type, whether to proceed).

Usage:
    python3 tools/deploy.py                    # fully interactive
    python3 tools/deploy.py /dev/cu.usbmodemX --type wand
    python3 tools/deploy.py /dev/cu.usbmodemX --type wand --wand-tree EspnowModem/MockWandEUM
    python3 tools/deploy.py /dev/cu.usbmodemX --type icon --code-only
    python3 tools/deploy.py /dev/cu.usbmodemX --type dial --pause 8
    python3 tools/deploy.py /dev/cu.usbmodemX --type wand --batch 0 --verify none --no-mkdir

Speed. Every mpremote call opens the port and enters the raw REPL, which
dominates the time per file. By default the files go in batches of 10 per
mpremote call (`fs cp a :a + fs cp b :b ...`), directories are created by one
call, and the result is checked by one on-device sha256 pass over every file.
Each step is optional:
    --batch N           files per mpremote call; 0 = all in one call, 1 = one at a time
    --verify MODE       hash (default): one sha256 pass on the device
                        readback: copy each file back and compare (slowest)
                        none: no verification
    --no-mkdir          assume the target directories already exist
Progress (chunk, files done, elapsed) prints before each mpremote call.
A pause (--pause, default 8 for the Dial) defaults --batch to 1.

--pause default is 8s for the Dial (the value deploy_dial.py's own history
found necessary on real hardware -- NOT a confirmed minimum) and 0 for
everything else; override either way with --pause.
"""

import argparse
import glob
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))           # BroadcastCode/tools
BROADCASTCODE = os.path.dirname(HERE)

DEVICE_TYPES = [
    ("Broadcast Dial", "dial"),
    ("Broadcast Box", "box"),
    ("Mock Wand", "wand"),
    ("Icon Display", "icon"),
]

SKIP_DIRS = {"tools", "__pycache__"}
SKIP_NAMES = {"README.md"}


def _list_ports():
    """Serial ports mpremote can see, falling back to a glob if that fails
    or finds nothing (e.g. `mpremote` too old for `connect list`)."""
    try:
        r = subprocess.run(["python3", "-m", "mpremote", "connect", "list"],
                            capture_output=True, text=True, timeout=15)
        ports = []
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.startswith("/dev/") or line.startswith("COM"):
                ports.append(line.split()[0])
        if ports:
            return ports
    except Exception:
        pass
    return sorted(glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/ttyACM*"))


def _choose(prompt, options, default_index=None):
    for i, label in enumerate(options, 1):
        print("  %d) %s" % (i, label))
    suffix = " (default %d)" % (default_index + 1) if default_index is not None else ""
    while True:
        raw = input("%s [1-%d]%s: " % (prompt, len(options), suffix)).strip()
        if not raw and default_index is not None:
            return default_index
        try:
            n = int(raw)
            if 1 <= n <= len(options):
                return n - 1
        except ValueError:
            pass
        print("  not a valid choice, try again")


def _manifest_files(firmware_dir, manifest_name, export_name):
    """(local_path, remote_path) pairs from a manifest.js FILES array.

    A small regex, not a JS parser -- same technique deploy_dial.py uses
    for the same reason (manifest.js's own docstring: "every module
    reachable from main.py must be listed" here).
    """
    manifest_path = os.path.join(firmware_dir, manifest_name)
    text = open(manifest_path).read()
    m = re.search(re.escape(export_name) + r"\s*=\s*\[(.*?)\]\s*;", text, re.S)
    if not m:
        raise SystemExit("no %s array found in %s -- did its format change?"
                          % (export_name, manifest_path))
    pairs = re.findall(r"path:\s*'([^']+)'\s*,\s*remotePath:\s*'([^']+)'", m.group(1))
    if not pairs:
        raise SystemExit("no files found in %s's %s -- did its format change?"
                          % (manifest_path, export_name))
    return [(os.path.join(firmware_dir, p), r) for p, r in pairs]


def _tree_files(root, skip_dirs=()):
    """(local_path, remote_path) pairs for a device with no manifest.js --
    every .py file plus hubtype.txt, preserving subdirectory layout.
    """
    skip = SKIP_DIRS | set(skip_dirs)
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for name in filenames:
            if name in SKIP_NAMES:
                continue
            if not (name.endswith(".py") or name == "hubtype.txt"):
                continue
            local = os.path.join(dirpath, name)
            rel = os.path.relpath(local, root).replace(os.sep, "/")
            out.append((local, "/" + rel))
    out.sort(key=lambda pair: pair[1])
    return out


def mpremote(port, *args, timeout=60):
    # `resume` on every call -- see module docstring / HARDWARE_PROTOCOL.md.
    cmd = ["python3", "-m", "mpremote", "connect", port, "resume"] + list(args)
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        # A board that reset mid-command can hang the connection rather than
        # erroring promptly -- surface this the same shape as a failed run so
        # the caller's retry logic handles both uniformly.
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr=str(e))


def _run_streamed(port, args, timeout):
    """mpremote with `resume`, echoing its output line by line.

    Returns a CompletedProcess (stdout holds everything printed, stderr is
    merged into it). A hung connection is killed at `timeout` seconds and
    reported as returncode 1.
    """
    cmd = ["python3", "-m", "mpremote", "connect", port, "resume"] + list(args)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True)
    timed_out = []

    def _kill():
        timed_out.append(True)
        proc.kill()

    timer = threading.Timer(timeout, _kill)
    timer.start()
    lines = []
    try:
        for line in proc.stdout:
            lines.append(line)
            print("    " + line.rstrip())
        proc.wait()
    finally:
        timer.cancel()
    out = "".join(lines)
    if timed_out:
        out += "timed out after %ds" % timeout
        return subprocess.CompletedProcess(cmd, 1, stdout=out, stderr="")
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout=out, stderr="")


def _make_dirs(port, files):
    """Create every parent directory of `files` in one mpremote call.

    Only EEXIST (errno 17) is tolerated; any other OSError aborts the call.
    """
    dirs = []
    for _, remote in files:
        parts = remote.strip("/").split("/")[:-1]
        for i in range(1, len(parts) + 1):
            d = "/" + "/".join(parts[:i])
            if d != "/flash" and d not in dirs:
                dirs.append(d)
    if not dirs:
        return
    script = ("import os\n"
              "for d in %r:\n"
              "    try:\n"
              "        os.mkdir(d)\n"
              "    except OSError as e:\n"
              "        if e.args[0] != 17:\n"
              "            raise\n") % (dirs,)
    print("creating %d director%s ..." % (len(dirs), "y" if len(dirs) == 1 else "ies"))
    r = _run_streamed(port, ["exec", script], 60)
    if r.returncode != 0:
        sys.exit("mkdir failed: %s" % r.stdout.strip())


def _copy_batched(port, files, batch, attempts, pause, t0, total):
    """Copy `files` in chunks of `batch` per mpremote call (0 = one call).

    Returns the remote paths of chunks that still failed after `attempts`.
    A chunk is retried whole; `fs cp` overwrites, so a retry is safe.
    """
    size = batch or len(files)
    failed = []
    done = total - len(files)
    for start in range(0, len(files), size):
        chunk = files[start:start + size]
        args = []
        for i, (local, remote) in enumerate(chunk):
            if i:
                args.append("+")
            args += ["fs", "cp", local, ":" + remote]
        for attempt in range(1, attempts + 1):
            print("[%d-%d/%d] copying %d file(s), attempt %d/%d, %.0fs elapsed"
                  % (done + start + 1, done + start + len(chunk), total,
                     len(chunk), attempt, attempts, time.time() - t0))
            r = _run_streamed(port, args, 60 + 10 * len(chunk))
            if r.returncode == 0:
                break
            print("  chunk failed: %s" % (r.stdout.strip().splitlines() or ["no output"])[-1])
            time.sleep(pause)
        else:
            failed += [remote for _, remote in chunk]
    return failed


def _verify_hashes(port, files):
    """Remote paths whose on-device sha256 differs from the local file.

    One mpremote call hashes every file on the device. A missing file makes
    the on-device script raise, which is reported as every file failing.
    """
    script = ("import hashlib, binascii\n"
              "for p in %r:\n"
              "    h = hashlib.sha256()\n"
              "    with open(p, 'rb') as f:\n"
              "        while True:\n"
              "            b = f.read(512)\n"
              "            if not b:\n"
              "                break\n"
              "            h.update(b)\n"
              "    print('SHA', p, binascii.hexlify(h.digest()).decode())\n"
              ) % ([remote for _, remote in files],)
    r = _run_streamed(port, ["exec", script], 60 + 5 * len(files))
    remote_hash = {}
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] == "SHA":
            remote_hash[parts[1]] = parts[2]
    bad = []
    for local, remote in files:
        with open(local, "rb") as f:
            want = hashlib.sha256(f.read()).hexdigest()
        if remote_hash.get(remote) != want:
            bad.append(remote)
    if r.returncode != 0 and not remote_hash:
        print("  hash pass failed: %s" % (r.stdout.strip().splitlines() or ["no output"])[-1])
    return bad


def copy_and_verify(port, local, remote, attempts, pause):
    local_bytes = open(local, "rb").read()
    for attempt in range(1, attempts + 1):
        r = mpremote(port, "fs", "cp", local, ":" + remote)
        if r.returncode != 0:
            print("  attempt %d/%d: write failed: %s"
                  % (attempt, attempts, r.stderr.strip() or r.stdout.strip()))
            time.sleep(pause)
            continue

        tmp_fd, tmp_path = tempfile.mkstemp(prefix="deploy_verify_")
        os.close(tmp_fd)
        try:
            rv = mpremote(port, "fs", "cp", ":" + remote, tmp_path)
            if rv.returncode == 0 and open(tmp_path, "rb").read() == local_bytes:
                print("  %s: OK (%d bytes, read back and verified)" % (remote, len(local_bytes)))
                return True
            print("  attempt %d/%d: verify failed (%s)"
                  % (attempt, attempts, rv.stderr.strip() or "content mismatch on read-back"))
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        time.sleep(pause)
    return False


def _boot_main_first(files, extra_boot=None):
    """Move boot.py and main.py to the front of the write order.

    Confirmed necessary 2026-09-23: a Dial wedged mid-deploy (raw REPL
    unreachable) only came back after boot.py/main.py were rewritten by
    hand. main.py used to sort last (manifest order) and boot.py wasn't
    written at all for Dial/Box -- so an interrupted deploy could leave a
    board with no path back to a working REPL. extra_boot is a
    (local, remote) pair to inject when boot.py isn't already in `files`
    (true for Dial/Box, whose manifest.js doesn't list it).
    """
    files = list(files)
    if extra_boot and not any(os.path.basename(r) == "boot.py" for _, r in files):
        files.insert(0, extra_boot)
    order = {"boot.py": 0, "main.py": 1}
    return sorted(files, key=lambda pair: order.get(os.path.basename(pair[1]), 2))


# MockWand's main.py is compiled at boot otherwise, and that compile can leave
# the contiguous IDF block the radio needs fragmented: a few bytes added to
# main.py took idf_largest after imports from 208896 to 77824, and the same
# source precompiled stayed at 208896 (docs_and_design/2026-10-07-splat-pairing/
# RESULTS-PartB.md). The wand gets wand_main.mpy plus a one-line main.py.
WAND_APP = "wand_main"
WAND_STUB = "import %s\n" % WAND_APP


def _precompile_wand_main(files):
    """Replace MockWand's main.py with wand_main.mpy and a stub main.py.
    Needs mpy-cross (`pip install --user mpy-cross==1.28.0.post2`, matching
    the wands' MicroPython). Order: boot.py, wand_main.mpy, then main.py, so an
    interrupted deploy never leaves a stub that imports a missing module."""
    src = next((l for l, r in files if r == "/main.py"), None)
    if src is None:
        return files
    tmp = tempfile.mkdtemp(prefix="deploy_wand_")
    mpy = os.path.join(tmp, WAND_APP + ".mpy")
    staged = os.path.join(tmp, WAND_APP + ".py")
    with open(src, "rb") as f_in, open(staged, "wb") as f_out:
        f_out.write(f_in.read())
    r = subprocess.run([sys.executable, "-m", "mpy_cross", staged, "-o", mpy],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("mpy-cross failed (pip install --user mpy-cross==1.28.0.post2): %s"
                 % (r.stderr.strip() or r.stdout.strip()))
    stub = os.path.join(tmp, "main.py")
    with open(stub, "w") as f:
        f.write(WAND_STUB)
    rest = [(l, r) for l, r in files if r not in ("/main.py", "/boot.py")]
    boot = [(l, r) for l, r in files if r == "/boot.py"]
    return boot + [(mpy, "/" + WAND_APP + ".mpy"), (stub, "/main.py")] + rest


def _files_for(dev_key, code_only, wand_tree="MockWand"):
    if dev_key == "dial":
        firmware_dir = os.path.join(BROADCASTCODE, "BroadcastDial", "BDialFirmware")
        boot_local = os.path.join(firmware_dir, "boot.py")
        extra_boot = (boot_local, "/flash/boot.py") if os.path.exists(boot_local) else None
        files = _manifest_files(firmware_dir, "manifest.js", "DIAL_FILES")
        return _boot_main_first(files, extra_boot), 8.0
    if dev_key == "box":
        firmware_dir = os.path.join(BROADCASTCODE, "BroadcastBox", "BBoxFirmware")
        boot_local = os.path.join(firmware_dir, "boot.py")
        extra_boot = (boot_local, "/flash/boot.py") if os.path.exists(boot_local) else None
        files = _manifest_files(firmware_dir, "manifest.js", "BOX_FILES")
        return _boot_main_first(files, extra_boot), 0.0
    if dev_key == "wand":
        files = _tree_files(os.path.join(BROADCASTCODE, wand_tree))
        if wand_tree == "MockWand":
            return _precompile_wand_main(files), 0.0
        return _boot_main_first(files), 0.0
    # icon
    skip = {"icons"} if code_only else ()
    files = _tree_files(os.path.join(BROADCASTCODE, "IconDisplay"), skip_dirs=skip)
    return _boot_main_first(files), 0.0


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("port", nargs="?", help="serial port; omitted to pick interactively")
    ap.add_argument("--type", choices=[key for _, key in DEVICE_TYPES],
                     help="device type; omitted to pick interactively")
    ap.add_argument("--pause", type=float, default=None,
                     help="seconds between files, and before a retry "
                          "(default: 8 for the Dial, 0 otherwise -- see module docstring)")
    ap.add_argument("--attempts", type=int, default=2,
                     help="copy+verify attempts per file (or chunk) before giving up on it")
    ap.add_argument("--batch", type=int, default=None,
                     help="files per mpremote call; 0 = all in one call, 1 = one at a time "
                          "(default: 10, or 1 when --pause is non-zero)")
    ap.add_argument("--verify", choices=("hash", "readback", "none"), default="hash",
                     help="hash: one on-device sha256 pass; readback: copy each file back "
                          "and compare (one file at a time, slowest); none: skip")
    ap.add_argument("--no-mkdir", action="store_true",
                     help="skip creating target directories; assume they exist")
    ap.add_argument("--no-reset", action="store_true",
                     help="skip the final reset; leave the board as-is")
    ap.add_argument("--code-only", action="store_true",
                     help="Icon Display only: skip icons/ (already on the device)")
    ap.add_argument("--wand-tree", default="MockWand",
                     help="Mock Wand only: tree to deploy, relative to BroadcastCode/ "
                          "(e.g. EspnowModem/MockWandEUM)")
    ap.add_argument("-y", "--yes", action="store_true",
                     help="skip the confirmation prompt")
    args = ap.parse_args()

    print("Follow HARDWARE_PROTOCOL.md: ask which board is on which port, and")
    print("wait for an explicit go before this touches a real serial port.\n")

    port = args.port
    if port is None:
        print("Serial ports:")
        ports = _list_ports()
        if not ports:
            port = input("No ports auto-detected. Enter one manually: ").strip()
        else:
            default_index = 0 if len(ports) == 1 else None
            port = ports[_choose("Pick a port", ports, default_index)]

    dev_key = args.type
    if dev_key is None:
        idx = _choose("\nDevice type", [label for label, _ in DEVICE_TYPES])
        dev_key = DEVICE_TYPES[idx][1]
    type_label = next(label for label, key in DEVICE_TYPES if key == dev_key)

    files, default_pause = _files_for(dev_key, args.code_only, args.wand_tree)
    pause = args.pause if args.pause is not None else default_pause

    print("\n%s -> %s, %d files." % (type_label, port, len(files)))
    if not args.yes:
        if input("Go? [y/N] ").strip().lower() not in ("y", "yes"):
            print("aborted")
            return

    t0 = time.time()
    total = len(files)
    if not args.no_mkdir:
        # `fs cp` does not create parent directories.
        _make_dirs(port, files)

    if args.verify == "readback":
        # One file at a time: copy, copy back, compare.
        failed = []
        for n, (local, remote) in enumerate(files, 1):
            print("[%d/%d] %s -> %s, %.0fs elapsed"
                  % (n, total, os.path.relpath(local, BROADCASTCODE), remote,
                     time.time() - t0))
            if not copy_and_verify(port, local, remote, args.attempts, pause):
                failed.append(remote)
                print("  FAILED after %d attempt(s) -- continuing with the rest" % args.attempts)
            if pause:
                time.sleep(pause)
    else:
        batch = args.batch if args.batch is not None else (1 if pause else 10)
        failed = _copy_batched(port, files, batch, args.attempts, pause, t0, total)
        if args.verify == "hash":
            pending = [(l, r) for l, r in files if r not in failed]
            for attempt in range(1, args.attempts + 1):
                print("verifying %d file(s) by sha256, %.0fs elapsed"
                      % (len(pending), time.time() - t0))
                bad = _verify_hashes(port, pending)
                if not bad:
                    pending = []
                    break
                print("  %d file(s) differ: %s" % (len(bad), ", ".join(bad)))
                pending = [(l, r) for l, r in pending if r in bad]
                if attempt == args.attempts:
                    break
                _copy_batched(port, pending, batch, 1, pause, t0, len(pending))
            failed += [r for _, r in pending]

    if failed:
        print("\n# %d file(s) failed: %s" % (len(failed), ", ".join(failed)))
        print("# NOT resetting -- the board would boot a half-deployed image. "
              "Fix these and re-run before resetting.")
        sys.exit(1)

    print("\n# all %d files copied%s in %.0fs"
          % (total, "" if args.verify == "none" else " and verified", time.time() - t0))
    if args.no_reset:
        print("# --no-reset: leaving the board as-is")
        return
    # Plain reset, no `resume` -- the write-side calls above only avoided
    # the reboot; this is what brings the new code up (HARDWARE_PROTOCOL.md).
    r = subprocess.run(["python3", "-m", "mpremote", "connect", port, "reset"],
                        capture_output=True, text=True)
    print("# reset:", "ok" if r.returncode == 0 else (r.stderr.strip() or r.stdout.strip()))


if __name__ == "__main__":
    main()
