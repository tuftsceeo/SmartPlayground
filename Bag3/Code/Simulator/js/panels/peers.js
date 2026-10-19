/**
 * Peer strip for <sim-room>: one row per virtual peer wand (js/peers.js)
 * and the room's pw_* traffic. Shown for party games.
 *
 * Row: identity swatch, name and MAC, state, and buttons: "button" (the
 * peer wand's own button, which does what the game's script says, e.g.
 * partytest's follower asks the leader to light a Splat), "drop"/"back"
 * (the peer goes silent and stops ACKing, for wand_lost / leader_lost),
 * "leave" on a follower, "start"/"end" on a leader, and "remove".
 * "+ follower" / "+ leader" add peers with the chosen Splat count.
 *
 *   createPeerStrip({ mount, host })   host is js/party.js's party host
 *     .refresh()   redraw rows after a change
 *     .pushLog(line, frame)
 *     .clearLog()
 */

const LOG_LIMIT = 120;

export const PEERS_STYLE = `
.peer-strip { display: flex; flex-direction: column; gap: 8px; }
.peer-rows { display: flex; flex-direction: column; gap: 6px; }
.peer-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 0.8rem; }
.peer-row .swatch { width: 14px; height: 14px; border-radius: 4px; border: 1px solid #0002; }
.peer-row .who { font-weight: 700; }
.peer-row .mac { font: 12px ui-monospace, monospace; color: #8b859a; }
.peer-row .state { color: #6c4cd1; min-width: 6em; }
.peer-row.dropped .state { color: #d13a7c; }
.peer-strip button, .peer-strip select { font: 700 0.75rem 'Nunito', system-ui, sans-serif; padding: 3px 9px;
  border-radius: 10px; border: 1.5px solid #e8e6f0; background: #fff; cursor: pointer; }
.peer-strip button:disabled { opacity: 0.4; cursor: default; }
.peer-strip .add { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; font-size: 0.8rem; }
.peer-strip .log-head { display: flex; gap: 10px; align-items: center; font-size: 0.75rem; color: #8b859a; }
.peer-strip .buslog { font: 11px/1.35 ui-monospace, monospace; max-height: 180px; overflow-y: auto;
  background: #f7f7fb; border-radius: 8px; padding: 6px 8px; margin: 0; white-space: pre-wrap;
  word-break: break-all; }
.peer-strip .buslog:empty::before { content: "no pw_ messages yet"; color: #8b859a; }
.peer-strip .empty { font-size: 0.8rem; color: #8b859a; }
`;

const css = (rgb) => `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;

const STATE_TEXT = {
  idle: "idle", find: "looking for a lobby", join: "joining", lobby: "in the lobby",
  game: "playing", lead: "lobby open", lead_game: "leading the game",
};

export function createPeerStrip({ mount, host }) {
  const root = document.createElement("div");
  root.className = "peer-strip";
  root.dataset.el = "peer-strip";
  root.innerHTML = `
    <div class="peer-rows"></div>
    <div class="add">
      <button type="button" data-add="follower">+ follower</button>
      <button type="button" data-add="leader">+ leader</button>
      <label>Splats each <select data-el="splat-count">
        <option value="0">0</option><option value="1" selected>1</option><option value="2">2</option>
      </select></label>
    </div>
    <div class="log-head"><span>pw_ messages</span>
      <label><input type="checkbox" data-el="show-hb"> heartbeats and lobby beacons</label>
      <button type="button" data-el="clear-log">clear</button></div>
    <pre class="buslog" data-el="buslog"></pre>`;
  mount.appendChild(root);
  const rows = root.querySelector(".peer-rows");
  const log = root.querySelector('[data-el="buslog"]');
  const showHb = root.querySelector('[data-el="show-hb"]');
  const lines = [];

  root.querySelectorAll("[data-add]").forEach((b) => b.addEventListener("click", () => {
    const splats = Number(root.querySelector('[data-el="splat-count"]').value);
    host.addPeer({ mode: b.dataset.add, splats });
  }));
  root.querySelector('[data-el="clear-log"]').addEventListener("click", () => clearLog());

  function button(label, onClick, enabled = true) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    b.disabled = !enabled;
    b.dataset.action = label;
    b.addEventListener("click", onClick);
    return b;
  }

  let shape = "";
  function refresh() {
    const key = host.peers.map(({ peer }) => `${peer.mac}|${peer.state}|${peer.dropped}|${peer.canStart?.()}`).join(",");
    if (key === shape) return;
    shape = key;
    rows.textContent = "";
    if (!host.peers.length) {
      rows.innerHTML = `<div class="empty">no peer wands: this wand plays alone</div>`;
      return;
    }
    for (const { peer } of host.peers) {
      const row = document.createElement("div");
      row.className = "peer-row";
      row.dataset.peer = peer.mac;
      row.classList.toggle("dropped", peer.dropped);
      row.innerHTML = `<span class="swatch"></span><span class="who"></span><span class="mac"></span>
        <span class="state"></span>`;
      row.querySelector(".swatch").style.background = css(peer.rgb);
      row.querySelector(".who").textContent = `${peer.name} (${peer.splats.length} Splat${peer.splats.length === 1 ? "" : "s"})`;
      row.querySelector(".mac").textContent = peer.mac;
      row.querySelector(".state").textContent = peer.dropped ? "silent" : (STATE_TEXT[peer.state] || peer.state);
      row.appendChild(button("button", () => peer.button()));
      row.appendChild(button(peer.dropped ? "back" : "drop", () => host.peerDropped(peer, !peer.dropped)));
      if (peer.mode === "leader") {
        row.appendChild(button("start", () => peer.start(), peer.canStart()));
        row.appendChild(button("end", () => peer.end(), peer.state === "lead" || peer.state === "lead_game"));
      } else {
        row.appendChild(button("leave", () => peer.leave(), ["join", "lobby", "game"].includes(peer.state)));
      }
      row.appendChild(button("remove", () => host.removePeer(peer)));
      rows.appendChild(row);
    }
  }

  function renderLog() {
    log.textContent = lines.filter((l) => showHb.checked || !l.beacon).map((l) => l.text).join("\n");
    log.scrollTop = log.scrollHeight;
  }
  showHb.addEventListener("change", renderLog);

  function pushLog(text, frame) {
    const beacon = ["pw_hb", "pw_lobby", "pw_find"].includes(frame?.type);
    lines.push({ text, beacon });
    if (lines.length > LOG_LIMIT) lines.splice(0, lines.length - LOG_LIMIT);
    if (beacon && !showHb.checked) return;
    renderLog();
  }

  function clearLog() {
    lines.length = 0;
    renderLog();
  }

  refresh();
  return { root, refresh, pushLog, clearLog };
}
