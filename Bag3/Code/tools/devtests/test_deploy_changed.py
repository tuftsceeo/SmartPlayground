"""Offline test of deploy.py --changed selection (mpremote helper mocked).

Run: python3 tools/devtests/test_deploy_changed.py
"""
import hashlib
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import deploy


def sha(b):
    return hashlib.sha256(b).hexdigest()


tmp = tempfile.mkdtemp()
files = []
for name, data in (("a.py", b"a"), ("b.py", b"b"), ("c.py", b"c"), ("w.mpy", b"mpy")):
    p = os.path.join(tmp, name)
    open(p, "wb").write(data)
    files.append((p, "/" + name))

remote = {"/a.py": sha(b"a"), "/b.py": sha(b"OLD"), "/c.py": None, "/w.mpy": sha(b"mpy")}


def fake_ok(port, *args, timeout=60):
    assert args[0] == "exec"
    out = "".join("H|%s|%s\n" % (k, v) for k, v in remote.items())
    return subprocess.CompletedProcess(args, 0, stdout=out, stderr="")


def fake_fail(port, *args, timeout=60):
    return subprocess.CompletedProcess(args, 1, stdout="", stderr="boom")


def fake_partial(port, *args, timeout=60):
    return subprocess.CompletedProcess(args, 0, stdout="H|/a.py|None\n", stderr="")


deploy.mpremote = fake_ok
h = deploy._remote_hashes("p", [r for _, r in files])
assert h == remote, h
sel = deploy.select_changed(files, h)
assert [r for _, r in sel] == ["/b.py", "/c.py"], sel

deploy.mpremote = fake_fail
assert deploy._remote_hashes("p", ["/a.py"]) is None
deploy.mpremote = fake_partial
assert deploy._remote_hashes("p", ["/a.py", "/b.py"]) is None

# the generated remote script compiles
import ast
captured = []
deploy.mpremote = lambda port, *a, timeout=60: (captured.append(a[1]), fake_fail(port))[1]
deploy._remote_hashes("p", ["/a.py"])
ast.parse(captured[0])
print("OK")
