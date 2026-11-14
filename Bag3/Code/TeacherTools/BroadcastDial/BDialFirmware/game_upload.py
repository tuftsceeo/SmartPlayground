# game_upload.py -- write a game file over the JSON link, with no reset.
# Imported lazily by bdial_server on the first file.* command, after the radio
# is up (AGENTS.md: nothing may allocate before the radio claims its memory).
#
# file.begin {path, size, sha?}  open <path>.part (path under /flash/games/)
# file.chunk {seq, data}         base64 data, seq counts from 0
# file.end   {}                  check size and sha, rename into place
# file.abort {}                  drop the partial file
# Every reply is {"type":"ok"} or {"type":"error"} carrying the command's id.

import os

ROOT = "/flash/games/"
MAX_BYTES = 96 * 1024
CHUNK_RAW = 1024        # app-side chunk size; base64 line stays well under MAX_LINE


def _bad_path(path):
    if not isinstance(path, str) or not path.startswith(ROOT):
        return "path must be under " + ROOT
    rest = path[len(ROOT):]
    if not rest or ".." in rest or rest.endswith("/") or "//" in rest:
        return "bad path"
    for ch in rest:
        if not (ch.isalpha() or ch.isdigit() or ch in "_-./"):
            return "bad character in path"
    return None


def _mkdirs(path):
    d = path[:path.rfind("/")]
    parts = d.split("/")
    cur = ""
    for p in parts:
        if not p:
            continue
        cur += "/" + p
        try:
            os.mkdir(cur)
        except OSError:
            pass


class Upload:
    def __init__(self):
        self.f = None
        self.path = None
        self.size = 0
        self.got = 0
        self.seq = 0
        self.sha = None
        self.h = None

    def _drop(self):
        if self.f is not None:
            try:
                self.f.close()
            except Exception:
                pass
            try:
                os.remove(self.path + ".part")
            except OSError:
                pass
        self.f = None
        self.path = None

    def begin(self, cmd):
        path = cmd.get("path")
        why = _bad_path(path)
        if why:
            return {"code": "bad_path", "msg": why}
        size = cmd.get("size")
        if not isinstance(size, int) or size < 0 or size > MAX_BYTES:
            return {"code": "bad_size", "msg": "size 0..%d" % MAX_BYTES}
        self._drop()
        _mkdirs(path)
        try:
            self.f = open(path + ".part", "wb")
        except OSError as e:
            return {"code": "open_failed", "msg": str(e)}
        import hashlib
        self.h = hashlib.sha256()
        self.path = path
        self.size = size
        self.got = 0
        self.seq = 0
        self.sha = cmd.get("sha")
        return None

    def chunk(self, cmd):
        if self.f is None:
            return {"code": "no_upload", "msg": "file.begin first"}
        if cmd.get("seq") != self.seq:
            return {"code": "bad_seq", "msg": "expected %d" % self.seq, "seq": self.seq}
        import binascii
        try:
            data = binascii.a2b_base64(cmd.get("data") or "")
        except Exception:
            return {"code": "bad_data", "msg": "not base64"}
        if self.got + len(data) > self.size:
            self._drop()
            return {"code": "too_long", "msg": "more data than size"}
        try:
            self.f.write(data)
        except OSError as e:
            self._drop()
            return {"code": "write_failed", "msg": str(e)}
        self.h.update(data)
        self.got += len(data)
        self.seq += 1
        return None

    def end(self, cmd):
        if self.f is None:
            return {"code": "no_upload", "msg": "file.begin first"}
        self.f.close()
        self.f = None
        part = self.path + ".part"
        if self.got != self.size:
            os.remove(part)
            return {"code": "short", "msg": "got %d of %d bytes" % (self.got, self.size)}
        if self.sha:
            import binascii
            got = binascii.hexlify(self.h.digest()).decode()
            if got != self.sha:
                os.remove(part)
                return {"code": "bad_sha", "msg": "checksum mismatch"}
        try:
            os.remove(self.path)
        except OSError:
            pass
        os.rename(part, self.path)
        self.path = None
        return None

    def abort(self, cmd):
        self._drop()
        return None
