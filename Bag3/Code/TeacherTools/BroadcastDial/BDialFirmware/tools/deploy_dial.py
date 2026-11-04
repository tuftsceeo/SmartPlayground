"""
deploy_dial.py — per-file, verified deploy for the Broadcast Dial.

Host-side tool. Not firmware; never upload this to a device.

Why this exists: the batched one-shot
`mpremote ... fs cp a + fs cp b + ... + reset` chain documented in
../../README.md's "Deploy" section gave a dropped/truncated copy during
the multi-client SERVE bench pass (2026-09-21) -- traced afterward to the
invocation not following HARDWARE_PROTOCOL.md's `resume` rule on every
call, not to the Dial itself. This script makes the safer path repeatable
and documented instead of something done by hand: one mpremote invocation
per file (each properly `resume`d), a full-content read-back to verify the
write actually landed (not just a size check -- catches truncation AND
corruption), and a retry if a file fails.

The file list comes from manifest.js (DIAL_FILES), not a hardcoded copy,
so it can't drift from what ChatBroadcast's own installer deploys.

Follow HARDWARE_PROTOCOL.md before running this: ask which port is the
Dial, ask before opening it, and wait for an explicit go. This script does
not ask for you.

Usage (from BDialFirmware/):
    python3 tools/deploy_dial.py /dev/cu.usbmodemXXXX
    python3 tools/deploy_dial.py /dev/cu.usbmodemXXXX --pause 8

--pause default is 8s -- the value that happened to work in the session
that found this. It is NOT a confirmed minimum; if a file still fails
verification at the default, try a larger --pause before assuming
something else is wrong.
"""

import argparse
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent.parent  # BDialFirmware/
MANIFEST = HERE / "manifest.js"


def parse_manifest_files():
    """Pull the DIAL_FILES path list out of manifest.js.

    A small regex, not a JS parser -- manifest.js's own docstring says
    "every module reachable from main.py must be listed" here, so reading
    it rather than hand-keeping a second copy is what keeps this script
    from drifting the same way the tree already warns against for other
    PEER-duplicated files.
    """
    text = MANIFEST.read_text()
    paths = re.findall(r"path:\s*'([^']+)'", text)
    if not paths:
        raise SystemExit("no files found in %s -- did its format change?" % MANIFEST)
    return paths


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

        tmp_fd, tmp_path = tempfile.mkstemp(prefix="dial_verify_")
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
    ap.add_argument("port", help="e.g. /dev/cu.usbmodemXXXX -- ask which port is the Dial first")
    ap.add_argument("--pause", type=float, default=8.0,
                     help="seconds between files, and before a retry (default 8, "
                          "see module docstring -- not a confirmed minimum)")
    ap.add_argument("--attempts", type=int, default=2,
                     help="write+verify attempts per file before giving up on it")
    ap.add_argument("--no-reset", action="store_true",
                     help="skip the final reset; leave the board as-is")
    args = ap.parse_args()

    files = parse_manifest_files()
    print("# deploying %d files to %s, %.1fs between files (from %s)"
          % (len(files), args.port, args.pause, MANIFEST.name))

    failed = []
    for name in files:
        print("copying %s..." % name)
        if not copy_and_verify(args.port, name, args.attempts, args.pause):
            failed.append(name)
            print("  FAILED after %d attempt(s) -- continuing with the rest" % args.attempts)
        time.sleep(args.pause)

    if failed:
        print("\n# %d file(s) failed verification: %s"
              % (len(failed), ", ".join(failed)))
        print("# NOT resetting -- the board would boot a half-deployed image. "
              "Fix these and re-run before resetting.")
        sys.exit(1)

    print("\n# all %d files verified" % len(files))
    if args.no_reset:
        print("# --no-reset: leaving the board as-is")
        return
    r = mpremote(args.port, "reset")
    print("# reset:", "ok" if r.returncode == 0 else (r.stderr.strip() or r.stdout.strip()))


if __name__ == "__main__":
    main()
