"""test_game_upload.py -- host tests for file.* and games.rescan (CPython).

Sends a game to a fake Dial over the JSON commands, in a temp directory
standing in for /flash/games. No hardware.

    python3 Bag3/Code/TeacherTools/BroadcastDial/BDialFirmware/tools/test_game_upload.py
"""

import base64
import hashlib
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_dial_station as T                   # noqa: E402  (fakes and make())
BS = T.BS
import game_upload as GU                        # noqa: E402


class Upload(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        games = self.tmp + "/flash/games"
        os.makedirs(games)
        self.saved = (GU.ROOT, BS.GAMES_DIR, BS.INDEX_PATH, BS.ACTIVE_PATH)
        GU.ROOT = games + "/"
        BS.GAMES_DIR = games
        BS.INDEX_PATH = games + "/index.json"
        BS.ACTIVE_PATH = games + "/active.txt"
        self.games = games
        self.srv = T.make(T.MELODY)
        self.srv.code.sender = None
        self.srv.code.set_game = lambda slug: None
        self.n = 0

    def tearDown(self):
        GU.ROOT, BS.GAMES_DIR, BS.INDEX_PATH, BS.ACTIVE_PATH = self.saved
        shutil.rmtree(self.tmp)

    def cmd(self, **c):
        self.n += 1
        c["id"] = self.n
        self.srv.dispatch(c)
        r = self.srv.link.sent[-1] if c["cmd"] != "games.rescan" else [
            m for m in self.srv.link.sent if m.get("id") == self.n][0]
        self.assertEqual(r["id"], self.n)
        return r

    def send(self, path, data, chunk=GU.CHUNK_RAW, sha=True):
        r = self.cmd(cmd="file.begin", path=path, size=len(data),
                     sha=hashlib.sha256(data).hexdigest() if sha else None)
        self.assertEqual(r["type"], "ok", r)
        for seq, i in enumerate(range(0, len(data), chunk)):
            r = self.cmd(cmd="file.chunk", seq=seq,
                         data=base64.b64encode(data[i:i + chunk]).decode())
            self.assertEqual(r["type"], "ok", r)
        return self.cmd(cmd="file.end")

    def test_identity_says_upload(self):
        self.assertEqual(self.srv._identity_payload()["upload"], 1)

    def test_send_and_rescan_makes_it_active(self):
        code = b"def play():\n    pass\n" * 200       # several chunks
        self.assertEqual(self.send(GU.ROOT + "tag.py", code)["type"], "ok")
        self.send(GU.ROOT + "tag.tags.json", b'["red"]')
        with open(self.games + "/tag.py", "rb") as f:
            self.assertEqual(f.read(), code)
        self.assertFalse(os.path.exists(self.games + "/tag.py.part"))
        r = self.cmd(cmd="games.rescan", active="tag")
        self.assertEqual((r["type"], r["active"]), ("ok", "tag"))
        self.assertIn("tag", self.srv._index)
        self.assertEqual(self.srv._index["tag"]["tags"], ["red"])
        self.assertTrue(self.srv.running)              # no reset

    def test_resent_game_becomes_active_and_keeps_pulls(self):
        self.send(GU.ROOT + "a.py", b"x = 1\n")
        self.send(GU.ROOT + "b.py", b"x = 2\n")
        self.cmd(cmd="games.rescan", active="b")
        self.srv._pulls["a"] = 3
        self.send(GU.ROOT + "a.py", b"x = 3\n")
        r = self.cmd(cmd="games.rescan", active="a")
        self.assertEqual(r["active"], "a")
        self.assertEqual(self.srv._pulls["a"], 3)

    def test_icon_subdir_is_made(self):
        self.assertEqual(self.send(GU.ROOT + "t_icons/star.bin", b"\x00\x01")["type"], "ok")
        self.assertTrue(os.path.exists(self.games + "/t_icons/star.bin"))

    def test_bad_path(self):
        for p in ("/flash/main.py", GU.ROOT + "../main.py", GU.ROOT + "a b.py", GU.ROOT):
            r = self.cmd(cmd="file.begin", path=p, size=1)
            self.assertEqual(r["code"], "bad_path", p)

    def test_bad_sha_keeps_old_file(self):
        self.send(GU.ROOT + "a.py", b"old\n")
        self.cmd(cmd="file.begin", path=GU.ROOT + "a.py", size=4, sha="0" * 64)
        self.cmd(cmd="file.chunk", seq=0, data=base64.b64encode(b"new\n").decode())
        self.assertEqual(self.cmd(cmd="file.end")["code"], "bad_sha")
        with open(self.games + "/a.py", "rb") as f:
            self.assertEqual(f.read(), b"old\n")

    def test_wrong_seq_and_short(self):
        self.cmd(cmd="file.begin", path=GU.ROOT + "a.py", size=10)
        r = self.cmd(cmd="file.chunk", seq=1, data="")
        self.assertEqual((r["code"], r["seq"]), ("bad_seq", 0))
        self.cmd(cmd="file.chunk", seq=0, data=base64.b64encode(b"abc").decode())
        self.assertEqual(self.cmd(cmd="file.end")["code"], "short")
        self.assertFalse(os.path.exists(self.games + "/a.py"))

    def test_chunk_without_begin(self):
        self.assertEqual(self.cmd(cmd="file.chunk", seq=0, data="")["code"], "no_upload")


if __name__ == "__main__":
    unittest.main()
