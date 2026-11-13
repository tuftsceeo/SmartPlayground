# accessibility.md changes (gaps K1, K2)

DRAFT. Applies to `BroadcastCode/ChatBroadcast/knowledge/accessibility.md`. Run
`ChatBroadcast/tools/prompt_eval.mjs` before applying (it needs an API key).

## K2: no game vibration

Wands have a vibration motor, but `play()` gets no handle to it (only `main.py` uses it, for
Splat feedback). Until games get one, the knowledge must not suggest vibration.

In "Blind and low-vision children", replace:

> give each kind of event its own sound (a turn, a reward, a direction), and confirm actions with
> a short wand vibration, so the game can be followed by ear and touch.

with:

> give each kind of event its own sound (a turn, a reward, a direction), and confirm each action
> with a short sound, so the game can be followed by ear. Wands cannot vibrate in a game.

In "Neurodivergent and sensory-sensitive children", replace:

> - Make mistakes gentle: a soft sound or a short vibration, not a scolding. Keep vibrations under
>   about 4 seconds; long and short buzzes are easy to tell apart.

with:

> - Make mistakes gentle: one soft, low beep and a dim light, not a scolding or flashing. Keep
>   every sound under about 4 seconds; long and short beeps are easy to tell apart.

## K1: mobility (new bullet, after "Deaf and hard-of-hearing children")

> - **Children with limited mobility, including wheelchair users:** no game should need running.
>   Put cards and Splats where a seated child can reach them (Splats can be pressed by hand
>   instead of stomped), use zones a short walk or roll apart rather than a race, and offer a
>   partner role (holding the wand, calling the moves, tapping cards). In movement games, every
>   move has a seated version (wave arms instead of jump), and the game never checks how a move
>   is done.
