/**
 * Friend wands for <sim-room>: the virtual peer wands (js/peers.js) of a
 * party game, and the room's pw_* traffic. Shown for party games in
 * advanced mode only (sim-room's style hides it otherwise).
 *
 * Collapsed by default to one line: a dot per friend wand in its identity
 * color and a count. Opened, one row per friend wand: its name (identity
 * color, numbered when two wands share one), a status chip, its Splats
 * (createSplatToy, a click presses one), "Press its button" (the peer
 * wand's own button, which does what the game's script says) and a remove
 * button; "+ Add a friend wand" adds a follower with one Splat.
 *
 * Advanced mode (:host([advanced]) on the room) adds, per row, the MAC and
 * Splat count, "Go quiet"/"Come back" (the peer stops ACKing, for
 * wand_lost / leader_lost), "Leave the game" on a follower and
 * "Start game"/"End game" on a leader; "+ Add a player"/"+ Add a host" with
 * a Splat count; and the radio message log.
 *
 *   createPeerStrip({ mount, host })   host is js/party.js's party host
 *     .refresh()   redraw rows after a change
 *     .pushLog(line, frame)
 *     .clearLog()
 */

import { icon } from "../icons.js";
import { createSplatToy } from "./splats.js";

const LOG_LIMIT = 120;

/** Display colors per splatpair identity name. */
export const WAND_LOOK = {
  turnred: { name: "Red", ink: "#d63c3c", dot: "#f05252", tint: "#fdecec" },
  turngreen: { name: "Green", ink: "#1f8a52", dot: "#34c77b", tint: "#e7f8ef" },
  turnblue: { name: "Blue", ink: "#2f6fe0", dot: "#3b82f6", tint: "#e8f0fe" },
  turnpurple: { name: "Purple", ink: "#6c4cd1", dot: "#9b5de5", tint: "#f2eefc" },
  turnyellow: { name: "Yellow", ink: "#8a5f0e", dot: "#ffd23f", tint: "#fff8e0" },
  turnwhite: { name: "White", ink: "#5b5468", dot: "#ffffff", tint: "#f4f2fa" },
};

export const PEERS_STYLE = `
.friends { display: flex; flex-direction: column; }
.friends-head { display: flex; align-items: center; gap: 10px; width: 100%; min-height: 52px;
  padding: 8px 16px; box-sizing: border-box; border: 0; background: none; color: #231f2e;
  font: 800 14px 'Nunito', system-ui, sans-serif; text-align: left; cursor: pointer; border-radius: 16px; }
.friends-head:focus-visible { outline: none; box-shadow: 0 0 0 3px rgba(233,78,155,.14); }
.friends-head .dots { display: flex; }
.friends-head .dots span { width: 22px; height: 22px; border-radius: 50%; border: 2px solid #fff;
  box-shadow: 0 0 0 1px #e8e6f0; }
.friends-head .dots span + span { margin-left: -6px; }
.friends-head .toggle { margin-left: auto; display: inline-flex; align-items: center; gap: 4px;
  font: 700 12px 'Nunito', system-ui, sans-serif; color: #5b5468; }
.friends-head:hover .toggle { color: #6c4cd1; }
.friends-head .toggle .icon { transition: transform .15s ease; }
.friends.open .friends-head .toggle .icon { transform: rotate(180deg); }
.friends-body { display: none; flex-direction: column; gap: 8px; padding: 12px 16px 14px;
  border-top: 1px solid #f4f2fa; }
.friends.open .friends-body { display: flex; }
.friend-rows { display: flex; flex-direction: column; gap: 8px; }
.friend { display: flex; flex-direction: column; gap: 8px; padding: 8px 10px; border: 1.5px solid #e8e6f0;
  border-radius: 14px; background: #fff; }
.friend.dropped { background: #f7f7fb; }
.friend-main { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.friend .avatar { width: 40px; height: 40px; flex: none; border-radius: 50%; display: inline-flex;
  align-items: center; justify-content: center; }
.friend .who { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.friend .name { display: flex; align-items: center; gap: 6px; font: 800 14px 'Nunito', system-ui, sans-serif; color: #231f2e; }
.friend .chip { align-self: flex-start; font: 800 11px 'Nunito', system-ui, sans-serif; padding: 3px 9px;
  border-radius: 20px; }
.friend .chip.playing { background: #e9fbf6; color: #14806b; }
.friend .chip.waiting { background: #fff8e0; color: #8a5f0e; }
.friend .chip.quiet { background: #f4f2fa; color: #5b5468; }
.friend .chip.host { background: #f2eefc; color: #6c4cd1; padding: 2px 8px; }
.friend .detail { display: none; font: 400 11px ui-monospace, monospace; color: #5b5468; }
:host([advanced]) .friend .detail { display: block; }
.friend .splats { display: flex; flex-wrap: wrap; gap: 6px; }
.friend .acts { margin-left: auto; display: flex; gap: 6px; }
.friends button.out { min-height: 44px; padding: 0 14px; border-radius: 12px; border: 1.5px solid #e8e6f0;
  background: #fff; font: 800 12px 'Nunito', system-ui, sans-serif; color: #5b5468; cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center; transition: all .15s ease; }
.friends button.out:hover:not(:disabled) { border-color: #6c4cd1; color: #6c4cd1; }
.friends button.out:disabled { opacity: .7; cursor: not-allowed; }
.friends button.out.on { border-color: #6c4cd1; background: #f2eefc; color: #6c4cd1; }
.friends button.square { width: 44px; padding: 0; flex: none; }
.friend .adv { display: none; flex-wrap: wrap; gap: 6px; padding-left: 50px; }
:host([advanced]) .friend .adv { display: flex; }
.friend .adv button.out { min-height: 36px; padding: 0 12px; font-size: 11px; font-weight: 700; }
.friends .add-simple { width: 100%; }
.friends .add-simple:hover { border-color: #ef4d92 !important; color: #d13a7c !important; background: #fff0f6 !important; }
.friends .add-adv { display: none; flex-wrap: wrap; align-items: center; gap: 8px; }
:host([advanced]) .friends .add-adv { display: flex; }
:host([advanced]) .friends .add-simple { display: none; }
.friends .add-adv label { margin-left: auto; display: flex; align-items: center; gap: 8px;
  font: 700 12px 'Nunito', system-ui, sans-serif; color: #5b5468; }
.friends select { font: 700 12px 'Nunito', system-ui, sans-serif; color: #231f2e; padding: 6px 10px;
  border-radius: 12px; border: 1.5px solid #e8e6f0; background: #fafafd; }
.friends .empty { font: 400 17px 'Patrick Hand', 'Nunito', system-ui, sans-serif; color: #5b5468; }
.friends .radio { display: none; flex-direction: column; gap: 8px; border-top: 1px solid #f4f2fa; padding-top: 10px; }
:host([advanced]) .friends .radio { display: flex; }
.friends .radio-head { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.friends .radio-head > span { font: 800 10px 'Nunito', system-ui, sans-serif; letter-spacing: .06em; color: #5b5468; }
.friends .radio-head label { display: flex; align-items: center; gap: 6px; font: 700 11px 'Nunito', system-ui, sans-serif; color: #5b5468; }
.friends .radio-head input { accent-color: #ef4d92; margin: 0; }
.friends .radio-head button { margin-left: auto; font: 700 11px 'Nunito', system-ui, sans-serif; padding: 6px 11px;
  border-radius: 12px; border: 1.5px solid #e8e6f0; background: #fff; color: #5b5468; cursor: pointer; }
.friends .radio-head button:hover { border-color: #6c4cd1; color: #6c4cd1; }
.friends .buslog { font: 400 11px/1.5 ui-monospace, monospace; color: #3a3345; max-height: 160px; overflow-y: auto;
  background: #f7f7fb; border-radius: 10px; padding: 8px 10px; margin: 0; white-space: pre-wrap; word-break: break-all; }
.friends .buslog:empty::before { content: "no radio messages yet"; color: #5b5468; }
`;

/** Status chip: [label, class]. */
function status(peer) {
  if (peer.dropped) return ["Gone quiet", "quiet"];
  switch (peer.state) {
    case "game": case "lead_game": return ["Playing", "playing"];
    case "lobby": case "lead": return ["Waiting to start", "waiting"];
    case "find": case "join": return ["Looking for a game", "waiting"];
    default: return ["Not in a game", "quiet"];
  }
}

/** "Red wand", numbered when this wand or another peer has the same identity. */
function wandNames(host, identOf) {
  const seen = { [identOf(host.wandMac)]: 1 };
  const names = new Map();
  for (const { peer } of host.peers) {
    const n = (seen[peer.ident] || 0) + 1;
    seen[peer.ident] = n;
    const look = WAND_LOOK[peer.ident] || WAND_LOOK.turnwhite;
    names.set(peer, n > 1 ? `${look.name} wand ${n}` : `${look.name} wand`);
  }
  return names;
}

export function createPeerStrip({ mount, host, identOf }) {
  const root = document.createElement("div");
  root.className = "friends";
  root.dataset.el = "peer-strip";
  root.innerHTML = `
    <button type="button" class="friends-head" aria-expanded="false">
      <span class="dots"></span><span class="summary"></span>
      <span class="toggle"><span class="toggle-label">Show</span>${icon("chevronDown", 15)}</span>
    </button>
    <div class="friends-body">
      <div class="friend-rows"></div>
      <button type="button" class="out add-simple" data-add="follower">+ Add a friend wand</button>
      <div class="add-adv">
        <button type="button" class="out" data-add="follower">+ Add a player</button>
        <button type="button" class="out" data-add="leader">+ Add a host</button>
        <label>Splats each <select data-el="splat-count">
          <option value="0">0</option><option value="1" selected>1</option><option value="2">2</option>
        </select></label>
      </div>
      <div class="radio">
        <div class="radio-head"><span>RADIO MESSAGES</span>
          <label><input type="checkbox" data-el="show-hb"> Show heartbeats and lobby beacons</label>
          <button type="button" data-el="clear-log">Clear</button></div>
        <pre class="buslog" data-el="buslog"></pre>
      </div>
    </div>`;
  mount.appendChild(root);
  const head = root.querySelector(".friends-head");
  const rows = root.querySelector(".friend-rows");
  const log = root.querySelector('[data-el="buslog"]');
  const showHb = root.querySelector('[data-el="show-hb"]');
  const lines = [];
  let tiles = [];

  head.addEventListener("click", () => {
    const open = root.classList.toggle("open");
    head.setAttribute("aria-expanded", String(open));
    head.querySelector(".toggle-label").textContent = open ? "Hide" : "Show";
  });

  root.querySelectorAll("[data-add]").forEach((b) => b.addEventListener("click", () => {
    const simple = b.classList.contains("add-simple");
    const splats = simple ? 1 : Number(root.querySelector('[data-el="splat-count"]').value);
    host.addPeer({ mode: b.dataset.add, splats });
  }));
  root.querySelector('[data-el="clear-log"]').addEventListener("click", () => clearLog());

  function button(label, onClick, { enabled = true, cls = "out", aria = null } = {}) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = cls;
    b.textContent = label;
    b.disabled = !enabled;
    if (aria) b.setAttribute("aria-label", aria);
    b.addEventListener("click", onClick);
    return b;
  }

  function drawHead(names) {
    const n = host.peers.length;
    const dots = head.querySelector(".dots");
    dots.textContent = "";
    for (const { peer } of host.peers) {
      const d = document.createElement("span");
      d.style.background = (WAND_LOOK[peer.ident] || WAND_LOOK.turnwhite).dot;
      dots.appendChild(d);
    }
    head.querySelector(".summary").textContent = n === 0
      ? "Playing alone — add a friend wand"
      : n === 1 ? `${names.get(host.peers[0].peer)} playing along` : `${n} friend wands playing along`;
  }

  let shape = "";
  function refresh() {
    const key = host.peers.map(({ peer }) =>
      `${peer.mac}|${peer.state}|${peer.dropped}|${peer.canStart?.()}|${peer.splats.map((s) => s.mac).join("+")}`).join(",");
    if (key === shape) {
      for (const t of tiles) t.refresh();
      return;
    }
    shape = key;
    const names = wandNames(host, identOf);
    drawHead(names);
    rows.textContent = "";
    tiles = [];
    if (!host.peers.length) {
      rows.innerHTML = `<div class="empty">just this wand — add a friend to play together</div>`;
      return;
    }
    for (const { peer } of host.peers) {
      const name = names.get(peer);
      const lower = name.toLowerCase();
      const look = WAND_LOOK[peer.ident] || WAND_LOOK.turnwhite;
      const [statusText, statusCls] = status(peer);
      const row = document.createElement("div");
      row.className = "friend";
      row.dataset.peer = peer.mac;
      row.classList.toggle("dropped", peer.dropped);
      row.innerHTML = `<div class="friend-main">
          <span class="avatar"></span>
          <div class="who"><span class="name"></span><span class="chip"></span><span class="detail"></span></div>
          <div class="splats"></div>
          <div class="acts"></div>
        </div>
        <div class="adv"></div>`;
      const avatar = row.querySelector(".avatar");
      avatar.style.background = look.tint;
      avatar.style.color = look.ink;
      avatar.innerHTML = icon("wand", 18);
      const nameEl = row.querySelector(".name");
      nameEl.textContent = name;
      if (peer.mode === "leader") {
        const h = document.createElement("span");
        h.className = "chip host";
        h.textContent = "Host";
        nameEl.appendChild(h);
      }
      const chip = row.querySelector(".chip:not(.host)");
      chip.textContent = statusText;
      chip.classList.add(statusCls);
      const count = peer.splats.length;
      row.querySelector(".detail").textContent = `${peer.mac} · ${count} Splat${count === 1 ? "" : "s"}`;
      const splatsEl = row.querySelector(".splats");
      peer.splats.forEach((s, i) => {
        const t = createSplatToy(s, {
          size: 40,
          label: count === 1 ? `The ${lower}'s Splat` : `Splat ${i + 1} on the ${lower}`,
          onButton: (down) => peer.splatButton(i, down),
        });
        tiles.push(t);
        splatsEl.appendChild(t.el);
      });
      const acts = row.querySelector(".acts");
      acts.appendChild(button("Press its button", () => peer.button(), { aria: `Press the ${lower}'s button` }));
      const rm = button("", () => host.removePeer(peer), { cls: "out square", aria: `Take the ${lower} away` });
      rm.innerHTML = icon("close", 15);
      acts.appendChild(rm);
      const adv = row.querySelector(".adv");
      const quiet = button(peer.dropped ? "Come back" : "Go quiet", () => host.peerDropped(peer, !peer.dropped));
      quiet.classList.toggle("on", peer.dropped);
      adv.appendChild(quiet);
      if (peer.mode === "leader") {
        adv.appendChild(button("Start game", () => peer.start(), { enabled: peer.canStart() }));
        adv.appendChild(button("End game", () => peer.end(), { enabled: peer.state === "lead" || peer.state === "lead_game" }));
      } else {
        adv.appendChild(button("Leave the game", () => peer.leave(), { enabled: ["join", "lobby", "game"].includes(peer.state) }));
      }
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
