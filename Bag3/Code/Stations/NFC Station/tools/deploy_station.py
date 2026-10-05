"""deploy_station.py -- per-file, verified deploy for the NFC Station.

Host-side tool; not firmware. Copied from BroadcastDial's
tools/deploy_dial.py: one mpremote invocation per file, full read-back
verify, retry, and no reset if any file failed.

The file list is every *.py at the tree root plus fonts/*.bin (to
/flash/fonts/); tools/ stays on the host. Run tools/font_probe.py and tools/ui_sketches.py
with `mpremote run` after deploying.

Follow HARDWARE_PROTOCOL.md: ask which port is the Dial, ask before
opening it, and wait for an explicit go. This script does not ask.

Usage (from "NFC Station/"):
    python3 tools/deploy_station.py /dev/cu.usbmodemXXXX [--pause 8]
"""

import argparse
import os
import pathlib
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent.parent  # NFC Station/


def device_files():
    """Root-level .py files and fonts/*.bin; main.py last so a partial
    copy cannot boot."""
    names = sorted(p.name for p in HERE.glob("*.py"))
    if "main.py" not in names:
        raise SystemExit("main.py missing from %s" % HERE)
    names.remove("main.py")
    fonts = sorted("fonts/" + p.name for p in (HERE / "fonts").glob("*.bin"))
    return fonts + names + ["main.py"]


def ensure_fonts_dir(port):
    """Create /flash/fonts; an existing directory is fine, anything else
    is a failure."""
    r = mpremote(port, "fs", "mkdir", ":/flash/fonts")
    out = (r.stderr + r.stdout).strip()
    if r.returncode != 0 and "exist" not in out.lower():
        raise SystemExit("mkdir /flash/fonts failed: %s" % out)


def mpremote(port, *args, timeout=60):
    cmd = ["python3", "-m", "mpremote", "connect", port] + list(args)
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        # A board that reset mid-command can hang the connection rather
        # than erroring promptly -- surface this the same shape as a
        # failed run so the caller's retry logic handles both uniformly.
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr=str(e))


def copy_and_verify(port, name, attempts, pause):
    local = HERE / name
    remote = "/flash/" + name
    local_bytes = local.read_bytes()

    for attempt in range(1, attempts + 1):
        r = mpremote(port, "fs", "cp", str(local), ":" + remote)
        if r.returncode != 0:
            print("  attempt %d/%d: write failed: %s"
                  % (attempt, attempts, r.stderr.strip() or r.stdout.strip()))
            time.sleep(pause)
            continue

        tmp_fd, tmp_path = tempfile.mkstemp(prefix="station_verify_")
        os.close(tmp_fd)
        try:
            rv = mpremote(port, "fs", "cp", ":" + remote, tmp_path)
            if rv.returncode == 0 and pathlib.Path(tmp_path).read_bytes() == local_bytes:
                print("  %s: OK (%d bytes, read back and verified)" % (name, len(local_bytes)))
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


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("port", help="ask which port is the Dial first")
    ap.add_argument("--pause", type=float, default=8.0,
                    help="seconds between files and before a retry (default 8)")
    ap.add_argument("--attempts", type=int, default=2,
                    help="write+verify attempts per file")
    ap.add_argument("--no-reset", action="store_true",
                    help="skip the final reset")
    args = ap.parse_args()

    files = device_files()
    if any(f.startswith("fonts/") for f in files):
        ensure_fonts_dir(args.port)
    print("# deploying %d files to %s" % (len(files), args.port))
    failed = []
    for name in files:
        print("copying %s..." % name)
        if not copy_and_verify(args.port, name, args.attempts, args.pause):
            failed.append(name)
            print("  FAILED after %d attempt(s)" % args.attempts)
        time.sleep(args.pause)

    if failed:
        print("\n# %d file(s) failed verification: %s" % (len(failed), ", ".join(failed)))
        print("# NOT resetting -- fix these and re-run.")
        sys.exit(1)
    print("\n# all %d files verified" % len(files))
    if args.no_reset:
        return
    r = mpremote(args.port, "reset")
    print("# reset:", "ok" if r.returncode == 0 else (r.stderr.strip() or r.stdout.strip()))


if __name__ == "__main__":
    main()
