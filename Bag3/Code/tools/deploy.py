"""
deploy.py -- batched deploy for the Broadcast device trees (Dial, Box,
Mock Wand, Icon Display), to one or many boards in a row.

Host-side tool. Not firmware; never upload this to a device.

Follows HARDWARE_PROTOCOL.md "Routine updates": per board, a plain
`mpremote reset`, then ONE `mpremote ... resume` invocation that makes the
directories and copies every file (chained with `+`), then a plain `reset`
to start the new code. The cost of an mpremote call is breaking into the
running program (75-85 s measured on the Dial), not the transfer, so this
makes three calls per board instead of two per file.

The old per-file, read-back-verified version is tools/deploy_bak.py; use
it only if a batched copy is suspected of landing corrupt files.

Mock Wand: main.py is compiled to wand_main.mpy with mpy-cross ONCE per
run on the host, then the same .mpy goes to every port listed -- the
board itself never compiles main.py (see _precompile_wand_main).

File selection:
  - default: every file in the device's manifest / tree.
  - --since COMMIT: only files that differ between COMMIT and the working
    tree (`git diff --name-only COMMIT`, so uncommitted edits count too).
    COMMIT is whatever the boards were last deployed from.

No read-back verification: check the boot log (tools/serial_monitor.py).

Follow HARDWARE_PROTOCOL.md before running this: ask which port is which,
ask before opening it, and wait for an explicit go.

Usage:
    python3 tools/deploy.py                                   # interactive
    python3 tools/deploy.py /dev/cu.usbmodemA /dev/cu.usbmodemB --type wand
    python3 tools/deploy.py PORT1 PORT2 PORT3 --type wand --since 2adb99b
    python3 tools/deploy.py PORT --type icon --code-only
    python3 tools/deploy.py PORT --type wand --dry-run        # print commands only
"""

import argparse
import glob
import os
import re
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))           # Bag3/Code/tools
CODE = os.path.dirname(HERE)                                # Bag3/Code

DEVICE_TYPES = [
    ("Broadcast Dial", "dial"),
    ("Broadcast Box", "box"),
    ("Mock Wand", "wand"),
    ("Icon Display", "icon"),
]

# Source directory per device type, for --since (git diff scope).
SOURCE_DIRS = {
    "dial": os.path.join("TeacherTools", "BroadcastDial", "BDialFirmware"),
    "box": os.path.join("TeacherTools", "BroadcastBox", "BBoxFirmware"),
    "icon": os.path.join("Stations", "IconDisplay"),
}

SKIP_DIRS = {"tools", "__pycache__"}
SKIP_NAMES = {"README.md"}

# A call against a running program takes 75-85 s to break in; leave room.
CALL_TIMEOUT = 600


def _list_ports():
    """Serial ports mpremote can see, falling back to a glob if that fails
    or finds nothing (e.g. `mpremote` too old for `connect list`)."""
    try:
        r = subprocess.run([sys.executable, "-m", "mpremote", "connect", "list"],
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
    r = subprocess.run([sys.executable, "-m", "mpy_cross", staged, "-o", mpy,
                        "-s", WAND_APP + ".py"],
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


def _files_for(dev_key, code_only, wand_tree="Wand Module", since=None):
    """(local, remote) pairs to copy. With `since`, filtered to files git
    reports changed BEFORE the wand precompile, so main.py -> wand_main.mpy
    + stub only happens when main.py itself changed."""
    def pick(files, source_dir):
        return _select_since(files, since, source_dir) if since else files

    if dev_key in ("dial", "box"):
        firmware_dir = os.path.join(CODE, SOURCE_DIRS[dev_key])
        boot_local = os.path.join(firmware_dir, "boot.py")
        extra_boot = (boot_local, "/flash/boot.py") if os.path.exists(boot_local) else None
        export = "DIAL_FILES" if dev_key == "dial" else "BOX_FILES"
        files = _boot_main_first(_manifest_files(firmware_dir, "manifest.js", export), extra_boot)
        return pick(files, firmware_dir)
    if dev_key == "wand":
        root = os.path.join(CODE, wand_tree)
        if wand_tree == "Wand Module":
            files = pick(_manifest_files(root, "manifest.js", "WAND_FILES"), root)
            return _precompile_wand_main(files)
        return pick(_boot_main_first(_tree_files(root)), root)
    # icon
    skip = {"icons"} if code_only else ()
    root = os.path.join(CODE, SOURCE_DIRS["icon"])
    return pick(_boot_main_first(_tree_files(root, skip_dirs=skip)), root)


def _git_changed(since, source_dir):
    """Absolute paths under source_dir that differ between `since` and the
    working tree."""
    top = subprocess.run(["git", "-C", CODE, "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True, check=True).stdout.strip()
    r = subprocess.run(["git", "-C", top, "diff", "--name-only", since, "--", source_dir],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("git diff failed: %s" % r.stderr.strip())
    return {os.path.realpath(os.path.join(top, p)) for p in r.stdout.splitlines()}


def _select_since(files, since, source_dir):
    changed = _git_changed(since, source_dir)
    return [(l, r) for l, r in files if os.path.realpath(l) in changed]


def build_copy_cmd(port, files, dev_key):
    """One mpremote invocation: an exec that makes directories (ignoring
    ones that exist, which `fs mkdir` would abort the chain on) and, for the
    wand, removes /boot_ok; then every `fs cp`, chained with `+`."""
    dirs = []
    for _, remote in files:
        parts = remote.strip("/").split("/")[:-1]
        for i in range(1, len(parts) + 1):
            d = "/" + "/".join(parts[:i])
            if d != "/flash" and d not in dirs:
                dirs.append(d)
    setup = "import os\nfor d in %r:\n    try:\n        os.mkdir(d)\n    except OSError:\n        pass\n" % (dirs,)
    if dev_key == "wand":
        # New code: the next boot is a debug boot (MockWand/main.py BOOT_OK_PATH).
        setup += "try:\n    os.remove('/boot_ok')\nexcept OSError:\n    pass\n"
    cmd = [sys.executable, "-m", "mpremote", "connect", port, "resume", "exec", setup]
    for local, remote in files:
        cmd += ["+", "fs", "cp", local, ":" + remote]
    return cmd


def _run(cmd, dry_run):
    if dry_run:
        print("  $ " + " ".join(repr(c) if (" " in c or "\n" in c) else c for c in cmd))
        return 0
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=CALL_TIMEOUT)
    except subprocess.TimeoutExpired:
        print("  timed out after %d s" % CALL_TIMEOUT)
        return 1
    status = "ok" if r.returncode == 0 else (r.stderr.strip() or r.stdout.strip())
    print("  %.0f s: %s" % (time.time() - t0, status))
    return r.returncode


def deploy_one(port, files, dev_key, no_reset, dry_run):
    reset = [sys.executable, "-m", "mpremote", "connect", port, "reset"]
    print("\n== %s ==" % port)
    print("# reset (break in once, so the copy hits a freshly booted board)")
    _run(reset, dry_run)  # a failure here is reported; the copy is the real test
    print("# copy %d files in one invocation" % len(files))
    if _run(build_copy_cmd(port, files, dev_key), dry_run) != 0:
        print("# copy FAILED -- not resetting; board is at the REPL with a "
              "possibly partial image. Re-run for this port.")
        return False
    if no_reset:
        print("# --no-reset: leaving the board at the REPL")
        return True
    print("# reset to start the new code")
    _run(reset, dry_run)
    return True


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ports", nargs="*", help="serial port(s); omitted to pick one interactively")
    ap.add_argument("--type", choices=[key for _, key in DEVICE_TYPES],
                     help="device type; omitted to pick interactively")
    ap.add_argument("--since", metavar="COMMIT",
                     help="only files changed between COMMIT and the working tree")
    ap.add_argument("--no-reset", action="store_true",
                     help="skip the final reset; leave the board at the REPL")
    ap.add_argument("--code-only", action="store_true",
                     help="Icon Display only: skip icons/ (already on the device)")
    ap.add_argument("--skip-lib", action="store_true",
                     help="skip lib/ (already on the device)")
    ap.add_argument("--wand-tree", default="Wand Module",
                     help="Mock Wand only: tree to deploy, relative to Bag3/Code/ "
                          "(e.g. Experiments/EspnowModem/MockWandEUM)")
    ap.add_argument("--dry-run", action="store_true",
                     help="print the mpremote commands; touch no port")
    ap.add_argument("-y", "--yes", action="store_true",
                     help="skip the confirmation prompt")
    args = ap.parse_args()

    print("Follow HARDWARE_PROTOCOL.md: ask which board is on which port, and")
    print("wait for an explicit go before this touches a real serial port.\n")

    ports = list(args.ports)
    if not ports:
        print("Serial ports:")
        found = _list_ports()
        if not found:
            ports = [input("No ports auto-detected. Enter one manually: ").strip()]
        else:
            ports = [found[_choose("Pick a port", found, 0 if len(found) == 1 else None)]]

    dev_key = args.type
    if dev_key is None:
        idx = _choose("\nDevice type", [label for label, _ in DEVICE_TYPES])
        dev_key = DEVICE_TYPES[idx][1]
    type_label = next(label for label, key in DEVICE_TYPES if key == dev_key)

    files = _files_for(dev_key, args.code_only, args.wand_tree, args.since)
    if args.skip_lib:
        files = [f for f in files if "/lib/" not in f[1]]
    if not files:
        print("# nothing to deploy")
        return

    print("%s, %d file(s) -> %s" % (type_label, len(files), ", ".join(ports)))
    for local, remote in files:
        print("  %s" % remote)
    if not (args.yes or args.dry_run):
        if input("Go? [y/N] ").strip().lower() not in ("y", "yes"):
            print("aborted")
            return

    failed = [p for p in ports if not deploy_one(p, files, dev_key, args.no_reset, args.dry_run)]
    if failed:
        print("\n# FAILED on: %s" % ", ".join(failed))
        sys.exit(1)
    print("\n# done: %d board(s). Check a boot log to confirm." % len(ports))


if __name__ == "__main__":
    main()
