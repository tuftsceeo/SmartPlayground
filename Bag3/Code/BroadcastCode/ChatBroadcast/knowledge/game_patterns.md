# Game patterns: many players, many device types, or both

Read this whenever a game involves more than one wand, or a wand plus the icon display or Splat
Companion. The message rules it builds on are in the platform section ("Talking between devices").

## Facts that shape every multi-player game

- **Today, every wand gets the same game file.** The Box currently serves one file per device
  type for each game, so different children cannot be sent different code. Anything that differs
  between wands (caller or player, green team or blue team) is chosen **while the game runs**.
  This is how distribution works now, not a design rule; it may change.
- **Choose roles with cards.** A child taps a role card (`"caller"`, `"player"`) or a team card
  (`"green"`, `"blue"`) after the game starts. Show the chosen role on the lights straight away
  (a color or a shape) so the teacher can see who is what. Give every wand a **default role** so a
  child who taps nothing can still play.
- **One device is in charge.** When several wands could decide the same thing at once ("who won?"),
  let one device decide and announce it: the caller wand, or the icon display as referee. The
  first message of a round wins; later ones are ignored until the next round.
- **A device does not hear its own broadcast.** Update your own state directly when you send.
- **Messages can be missed.** A device in charge that sets the state ("everyone freeze") should
  repeat that state about once a second, so a wand that missed it, or joined late, catches up.
- **Every file exits** on `"stop"` / `"start_game"`, whatever its role.

## Designing the messages

Plan the messages before writing any file, and use exactly the same names in every file.

- **One message type per game**: the game's slug, e.g. `{"type": "frogs", ...}`. Never a reserved
  type (platform section).
- **Say who sent it and what happened**, in short keys:
  `{"type": "frogs", "from": "caller", "e": "go"}`,
  `{"type": "frogs", "from": "wand", "team": "green", "e": "goal"}`.
- **Role-specific messages** name who should act on them with a `"to"` key (`"to": "players"`),
  and each receiver ignores messages not meant for its role.
- **Send what the receiver needs**, as small plain values: an event name, a team name, a count, a
  color name or a short `[r, g, b]` list. About 240 bytes at most.
- The `mac` returned by `enow.poll()` identifies the sending device, if a game needs to tell wands
  apart (for example to count players). Most games only need the role or team.

In the reply, describe the plan in one plain sentence per role under **How to play** ("The
teacher's wand is the caller: press to start the music…").

## Pattern A — many wands, same game, each on its own

Every wand plays the same game independently (a shake counter, a color hunt). No messages are
needed. This is the simplest multi-player game: each child holds a wand running the same file.

## Pattern B — many wands with roles

One wand leads and the others follow (Freeze Dance: the caller starts and freezes; players dance
or hold still), or wands play on teams.

```python
# Inside the wand's play(): the role is chosen by card, with a default.
role = "player"                      # default role
...
if cmd == "caller":
    role = "caller"; leds.show_shape(SHAPE_STAR, YELLOW)
elif cmd == "player":
    role = "player"; leds.show_shape(SHAPE_HAPPY_FACE, GREEN)

# Caller: announce, and repeat the state about once a second
if role == "caller" and frame % 20 == 0:
    enow.broadcast({"type": "frogs", "from": "caller", "to": "players", "e": state})

# Player: act only on messages for players
if (msg_type == "raw" and isinstance(data, dict) and data.get("type") == "frogs"
        and data.get("to") == "players"):
    state = data.get("e")
```

Role and team cards go in `COMMANDS` and in `[NFC_CARDS: ...]`.

## Pattern C — wands with other device types

Each device type gets its own complete file under its own `[DEVICE:]` marker. Decide, for each
thing that happens, which device notices it and broadcasts, and which devices react.

Worked example — the wand and the Splat echo each other (the built-in Jump In game):

- Wand: button pressed → `enow.broadcast({"type": "jumpin", "from": "wand"})`.
- Splat: `"raw"` message with `type == "jumpin"` and `from == "wand"` → blink the Splat.
- Splat: pressed → `enow.broadcast({"type": "jumpin", "from": "splat", "rgb": [r, g, b]})`.
- Wand: that message → `leds.fill(tuple(data["rgb"]))`.

## Pattern D — many wands on teams, plus other devices

The icon display usually acts as **referee and scoreboard**: the wands report, the display
decides, and everyone reacts to the display. Based on the built-in Team Goal Race (which predates
the slug-as-type rule and uses the types `"goal"` and `"winner"`; new games use their slug):

- Wand: tap `"green"` or `"blue"` to join a team (shown on the lights).
- Wand: tap the `"goal"` card → `{"type": "<slug>", "e": "goal", "team": "green"}`.
- Display: the **first** goal message of a round wins; it shows the team's picture and broadcasts
  `{"type": "<slug>", "e": "winner", "team": "green"}`.
- Wands: on the winner message, the winning team celebrates and the others show a friendly
  "next round" color. Nobody is out.

A Splat can join the same way: a press is a report (`{"type": "<slug>", "from": "splat",
"team": ...}`) that the display counts.

## For young children

- **The teacher holds the leading wand** in role games, and tells the class what each light means.
- **Role and team cards should carry a picture or color**, since children cannot read the names.
- **Everyone stays in.** Being caught or losing a round shows a short, friendly signal, then the
  wand is back in the game.
