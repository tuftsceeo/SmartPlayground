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
    python3 tools/deploy.py /dev/cu.usbmodemX --type icon --code-only
    python3 tools/deploy.py /dev/cu.usbmodemX --type dial --pause 8

--pause default is 8s for the Dial (the value deploy_dial.py's own history
found necessary on real hardware -- NOT a confirmed minimum) and 0 for
everything else; override either way with --pause.
"""

import argparse
import glob
import os
import re
import subprocess
import sys
import tempfile
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


def _files_for(dev_key, code_only):
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
        files = _tree_files(os.path.join(BROADCASTCODE, "MockWand"))
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
                     help="write+verify attempts per file before giving up on it")
    ap.add_argument("--no-reset", action="store_true",
                     help="skip the final reset; leave the board as-is")
    ap.add_argument("--code-only", action="store_true",
                     help="Icon Display only: skip icons/ (already on the device)")
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

    files, default_pause = _files_for(dev_key, args.code_only)
    pause = args.pause if args.pause is not None else default_pause

    print("\n%s -> %s, %d files." % (type_label, port, len(files)))
    if not args.yes:
        if input("Go? [y/N] ").strip().lower() not in ("y", "yes"):
            print("aborted")
            return

    failed = []
    for local, remote in files:
        print("copying %s -> %s ..." % (os.path.relpath(local, BROADCASTCODE), remote))
        if not copy_and_verify(port, local, remote, args.attempts, pause):
            failed.append(remote)
            print("  FAILED after %d attempt(s) -- continuing with the rest" % args.attempts)
        if pause:
            time.sleep(pause)

    if failed:
        print("\n# %d file(s) failed verification: %s" % (len(failed), ", ".join(failed)))
        print("# NOT resetting -- the board would boot a half-deployed image. "
              "Fix these and re-run before resetting.")
        sys.exit(1)

    print("\n# all %d files verified" % len(files))
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
