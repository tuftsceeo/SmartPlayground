# SplatAuthoringRows

Experiment for the plan in
`../../BroadcastCode/docs_and_design/2026-11-13-game-authoring-rows.md`: one authoring shape per
game row, a local Splat API for solo wands, and host games rewritten to one template.
Nothing here is proven on hardware. `Wand Module/`, ChatBroadcast, Simulator and `Live_Page/` are
unchanged.

`wand/` is a copy of `Wand Module/` at `3cb1c884` (without `flash_bundle/`), then edited.

## Done (phases 0-3), `py_compile` only

| Change | Where |
|---|---|
| Local Splat API: a game declares `SPLATS_LOCAL = 1..2` and takes `splats=None` as 8th argument; no lobby. `splats.count`, `splats.unit(i)`, `splats.poll()` -> `("press", i)` / `("release", i)` / `None`. | `wand/lib/splatpair.py` (`GameSplats`, `SplatPairing.game_handle`), `wand/main.py` (`_splats_local`, `_run_games`) |
| `SPLATS_LOCAL` mixed with `SPLATS_MIN` or `SPLAT_HOST` is a load failure | `wand/main.py` `_splats_local` |
| Pooled paired-wand path removed: `_PoolSplat`, `net.owner`, `pw_cmd`, `pw_evt`, follower Splat forwarding. `net.splat(i)` is host only. | `wand/lib/lobby_game.py` |
| Pooled games removed (`splattag`, `relaycolor`, `lobbytest`) and their `GAME_MODULES`, start-signature and `game_tags` entries | `wand/games/`, `wand/main.py`, `wand/lib/game_tags.py` |
| Host games rewritten to one shape: declarations, `GAME_ICON` on player wands, `net is None` guard, `net.poll()` first, return on end/leader_lost, host/player branch, documented APIs only (`leds.fill`, `leds.show_shape`, `NfcReader`, `Pin(0)`), no Splat turn-off, no prints. A wand's identity name is already a Splat color name. | `wand/games/host_splattag.py`, `host_relaycolor.py`, `host_lobbytest.py` |

## Not done

- Phase 4: Splat host station mode.
- Phase 5: knowledge drafts and the JS send-time check (`knowledge/`, `js/`).
- Phase 6: tests (`tests/`); `deploy.py`.
- `wand/README.md`, `wand/manifest.js` and `wand/flash_bundle` still describe the pre-change tree.
- The pooled games' tags remain in the four game-tag consumers outside this tree
  (`Live_Page/WebApp2/hubCode2/game_tags.py`, `Live_Page/WebApp2/js/utils/commands.json`,
  `Live_Page/wand_icons.html`).
- Players that hold paired Splats in a host game still report a Splat count at join; the lobby
  accepts it but no game path uses it.

## Promotion checklist

1. Hardware proof on MicroPython v1.28.0 (type 2 with 2 Splats; host tag game with 4 Splats).
2. Copy the changed `wand/` files into `Wand Module/`; remove the pooled tags from the four consumers.
3. Re-run `Simulator/tools/sync_sources.py`; drop pooled cases from `Simulator/tests/test_lobby_game.py`.
4. Move the drafts into ChatBroadcast `knowledge/` and `js/splat/`.
5. Update `known_issues/2026-11-11-simple-mode-large-changes.md` (host role is hardware-tested).
