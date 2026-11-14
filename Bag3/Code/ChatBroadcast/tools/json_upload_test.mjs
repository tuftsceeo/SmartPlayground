/**
 * json_upload_test.mjs — jsonGameUpload.js against a fake Dial link.
 * Run from ChatBroadcast/:  node tools/json_upload_test.mjs
 */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { uploadGameOverJson, supportsJsonUpload, gameFiles, CHUNK_RAW } from "../js/device/jsonGameUpload.js";

let failed = 0;
async function t(name, fn) {
  try { await fn(); console.log(`ok   ${name}`); }
  catch (e) { failed++; console.log(`FAIL ${name}\n  ${e.stack}`); }
}

// Mimics game_upload.py: checks seq, size and sha; rejects like BboxLink.send on an error reply.
function fakeDial({ failOn } = {}) {
  const files = {}, log = [];
  let cur = null;
  const send = async (c) => {
    log.push(c.cmd);
    if (failOn && failOn(c)) throw new Error("write_failed: boom");
    if (c.cmd === "file.begin") cur = { ...c, parts: [], seq: 0 };
    else if (c.cmd === "file.chunk") {
      assert.equal(c.seq, cur.seq++);
      cur.parts.push(Buffer.from(c.data, "base64"));
    } else if (c.cmd === "file.end") {
      const buf = Buffer.concat(cur.parts);
      assert.equal(buf.length, cur.size);
      assert.equal(createHash("sha256").update(buf).digest("hex"), cur.sha);
      files[cur.path] = buf;
      cur = null;
    } else if (c.cmd === "file.abort") cur = null;
    else if (c.cmd === "games.rescan") return { type: "ok", active: c.active };
    return { type: "ok" };
  };
  return { send, files, log };
}

await t("only a Dial that says upload", () => {
  assert.equal(supportsJsonUpload({ device: "broadcast_dial", upload: 1 }), true);
  assert.equal(supportsJsonUpload({ device: "broadcast_dial" }), false);
  assert.equal(supportsJsonUpload({ device: "broadcast_box", upload: 1 }), false);
  assert.equal(supportsJsonUpload(null), false);
});

await t("same files as the raw-REPL path", () => {
  const f = gameFiles("x", { destPath: "/flash/games/tag.py", tags: ["red"],
    extraFiles: [{ path: "/flash/games/tag_icon.py", content: "y" }] });
  assert.deepEqual(f.map((x) => x.path),
    ["/flash/games/tag.py", "/flash/games/tag.tags.json", "/flash/games/tag_icon.py"]);
});

await t("game, tags and extras arrive intact, then rescan", async () => {
  const d = fakeDial();
  const code = "def play():\n    pass  # é\n".repeat(150);     // > 3 chunks, non-ASCII
  const r = await uploadGameOverJson(d.send, code,
    { destPath: "/flash/games/tag.py", tags: ["red"],
      extraFiles: [{ path: "/flash/games/tag_icons/star.py", content: "S = 1\n" }] });
  assert.deepEqual(r, { ok: true, restarted: false, live: true, active: "tag" });
  assert.equal(d.files["/flash/games/tag.py"].toString(), code);
  assert.ok(Buffer.byteLength(code) > 3 * CHUNK_RAW);
  assert.equal(d.files["/flash/games/tag.tags.json"].toString(), '["red"]');
  assert.equal(d.files["/flash/games/tag_icons/star.py"].toString(), "S = 1\n");
  assert.equal(d.log.at(-1), "games.rescan");
});

await t("a failed chunk aborts and throws", async () => {
  const d = fakeDial({ failOn: (c) => c.cmd === "file.chunk" && c.seq === 1 });
  await assert.rejects(uploadGameOverJson(d.send, "a".repeat(3000), { destPath: "/flash/games/a.py" }));
  assert.equal(d.log.at(-1), "file.abort");
  assert.ok(!d.log.includes("games.rescan"));
});

if (failed) { console.log(`${failed} failed`); process.exit(1); }
console.log("all passed");
