# Sharing ChatBroadcast games: ideas and options

*Brainstorm, 2026-11-11. Exploration only — nothing here is built or decided.*

Teachers can save games locally in ChatBroadcast today. This note collects ways they could share
games with each other — from "download and send to a friend" up to a moderated community board —
and the hosting options behind them. Education settings raise the bar on safety, so open public
forums are the least attractive end of the range.

Free-tier limits and third-party features below are from memory as of late 2026; check current
docs before relying on any number.

## 1. What goes in a shared game

Three layers; the sharer chooses how much to include.

| Layer | Contents | Default |
|---|---|---|
| Playable game | Game code for each device, icons used, Splat actions, game tags, title, description, age range, devices needed, target Bag/firmware | Always |
| Teacher notes | "How I ran it": rules said aloud, setup, what didn't work. AI can draft from the chat; teacher edits | Recommended |
| Chat history | Full conversation, so the receiver can keep iterating | Off — privacy risk (student names, class details) |

Middle ground: a **design summary** (original prompt + key decisions, ~300 bytes) instead of the
raw chat. Enough to remix, without exposing the conversation. If full chat is ever included, show
a review screen and offer an AI pass that strips names.

## 2. Ideas, easiest to hardest

### No backend

1. **Export / import a `.game` file.** JSON or zip. Send it any way. No accounts, nothing hosted.
2. **Share link with the game packed into the URL** (`#g1=...`). The part after `#` never reaches a
   server. Works in email, LMS, Slack, Padlet, Notion. Limited by length — see section 3.
3. **QR code.** For PD workshops and printed cards. Only works for small payloads or short codes.
4. **Printable game card.** One-page PDF: icons, rules, setup, QR. Fits classroom paper culture and
   can live in the Bag.
5. **NFC tag carrier.** Tap a tag on the Broadcast Dial to load a game. Tag capacity means it holds
   a short code, not the whole game.

### Light hosting

6. **Curated gallery.** Teachers submit an exported game; the team reviews and publishes it. The team
   is the moderator, so no accounts or moderation tooling are needed.
7. **Unlisted short codes.** "Share" uploads the game and returns a code like `FROG42`. Anyone with
   the code can import it; nothing is browsable. Add size limits, rate limits and optional expiry.

### Signed-in teachers

8. **School / district circles.** Sign in with Google or Microsoft; sharing is scoped to the
   school's domain or an invited group. Community without an open forum.
9. **Moderated community board.** Posts appear only after moderator approval. Structured reactions
   ("I ran this ✓", age group) instead of free-text comments at first.
10. **Remix lineage.** Imported games keep a pointer to their parent: "remixed from Frog Tag, 4
    versions." Credits authors; also research data on how teachers adapt games.
11. **"Ran it" reports.** After playing, a structured mini-report: grade, group size, what worked,
    what changed. Safer than comments, more useful to the next teacher, and study data.
12. **Remix by chat.** Importing a game opens a new chat seeded with its design summary ("built for
    1st graders, 12 kids, 3 devices — what would you like to change?"). Works on top of any idea above.

### Existing boards: Padlet and Notion

The school or PD leader owns the board and its permissions, so we build no forum.

- **Post a link or file** (no integration): paste the share link or attach the `.game` file.
- **"Copy for Padlet / Notion" button:** the app produces a ready-to-paste post — title, icon
  preview, age range, devices, rules, import link. Markdown pastes cleanly into Notion.
- **Embedded game card:** a static page that renders a game from its URL, with "Open in
  ChatBroadcast". Both platforms can embed or preview links.
- **App reads the board:** a "Browse our board" tab backed by a Notion database or Padlet. Needs API
  tokens behind a proxy; Padlet's API may require a paid/Education plan. Only worth it if a pilot
  board gets real use.

Padlet: familiar to teachers, often district-approved, has post approval. Notion: structured,
filterable database; better for a team-curated gallery.

## 3. How big games fit in a URL

Example: the tic-tac-toe game (wand + icon display files) is about 9 KB of Python. Estimates, not
measured:

1. **Deflate** (browser `CompressionStream`): repetitive game code compresses to ~25–35% →
   ~2.5–3 KB.
2. **Preset dictionary** of boilerplate every game shares (`def play(...)`, `enow.poll()`,
   `exit_tags_excluding`, ...): often another 30–50% on small files. Needs a library such as fflate
   or pako. The dictionary is part of the format, so version the link (`#g1=`).
3. **Base64url** adds ~33% → roughly a 2.5–3 KB link.

Don't minify: indentation is Python syntax, and compression already absorbs whitespace.

| Channel | ~3 KB link |
|---|---|
| Browser | Fine |
| Email, Slack, Teams, Classroom | Usually fine |
| Padlet / Notion | Should work; previews may truncate — test |
| SMS | Ugly, may be cut |
| QR code | No — comfortable range is ~300–500 bytes |

Workarounds:

- **Hybrid:** embed when under ~2 KB, otherwise offer file download or a short code.
- **Short codes** (idea 7): always tiny, QR-friendly; needs a small backend.
- **Share the recipe:** send the design summary and regenerate. Tiny, but the result won't be
  identical — better as "remix this idea" than as sending a finished game.
- **Library reference:** `#lib=tic_tac_toe` for games already in the gallery.

**Next step:** compress our 10 largest saved games with and without a dictionary to replace these
estimates.

## 4. Hosting options

### Cloudflare (current account, free plan)

| Service | Free limit (approx.) | Short-code use |
|---|---|---|
| Workers requests | 100,000 / day | 1 per share, 1 per open |
| Workers CPU | 10 ms / request | Store/fetch ~1–2 ms |
| KV reads | 100,000 / day | 1 per open |
| KV writes | **1,000 / day** (tightest) | 1 per share |
| KV storage | 1 GB | ~3–10 KB per game → ~100k+ games |
| D1 (alternative) | ~100k row writes, ~5M row reads / day, 5 GB | Much more headroom |

A 50-teacher pilot is on the order of 10 writes and 200 reads a day — about 1% of the limits.

Watch for:

- The Workers request quota is shared with the chat backend if that moves to Workers.
- Abuse matters more than normal use: cap upload size, rate-limit by IP, and ideally allow uploads
  only from signed-in teachers via Cloudflare Access (free up to 50 users). Opening stays public.
- Decide whether codes expire (KV supports TTL).
- If writes run out, existing links still work; the app can fall back to file download.

**Seeing what's shared:** everything is visible to us — the dashboard (KV browser, D1 console),
`wrangler` for bulk export, or a later admin page behind Access. Store metadata (title, date, Bag,
size, teacher ID) uncompressed so it's readable; D1 columns make "what was shared this week" one
query.

### Alternatives

| Option | Notes |
|---|---|
| Supabase | Database + storage + login in one; good fit for school circles. Free projects pause when idle. |
| Firebase | Similar; easy Google sign-in for Google Workspace schools. |
| Vercel / Netlify | Functions + storage; fine at this scale. |
| Deno Deploy | Close to Workers + KV. |
| AWS | Generous free tier, much more setup. |
| PocketBase (self-hosted) | Single-file backend; least lock-in. |
| Google Apps Script + Drive | Data stays in a school's Workspace; slow and clunky but easy for IT to approve. |
| GitHub | Fine for a curated gallery; teachers would need accounts to submit. |

### Tufts options

- **Tufts WordPress (sites.tufts.edu):** almost certainly can't run server code or scripts, and the
  media library likely rejects `.game` files. Good for the **public gallery page** (descriptions +
  URL-packed share links), printable PDF cards, docs and PD materials.
- **Tufts Box folder:**
  - *No code, today:* a **Box File Request** link lets teachers upload `.game` files without a Box
    account → team reviews → good ones go to the gallery.
  - *Box API:* short codes backed by Box, through a proxy (e.g. a Cloudflare Worker) holding the
    credentials. Server-to-server Box apps usually need **Tufts Box admin approval**, and Tufts's
    shared-link policy decides whether non-Tufts teachers can open files. Benefit:
    institution-approved storage, which helps IRB / FERPA conversations. Slower than KV.
- **Ask Tufts IT / research computing** whether research VMs, static hosting, or other services
  exist beyond WordPress.

## 5. Safety and privacy

- **Every imported game is untrusted input.** Run the same checks as generated games — icon,
  Splat-action and game-tag allow-lists, schema, size limits — however it arrived.
- **No student data in shares.** Chat history off by default; scan for names before sharing.
- **Tell teachers we can read shares**, e.g. "Shared games are stored by the Tufts research team and
  may be reviewed." Analysis of shared games likely falls under the IRB protocol.
- **Record target Bag / firmware** so an import into an older setup fails with a clear message.
- **Anything posted to a public board is out of our hands** once posted.

## 6. Suggested path

1. **Now, no backend:** `.game` export/import, URL-packed share links with dictionary compression,
   and a "copy for Padlet / Notion" post. Settles the game format.
2. **Curated gallery:** Box File Request as the inbox, Tufts WordPress page as the gallery. Optionally
   pilot one Padlet wall with approval on for a teacher cohort.
3. **Short codes:** Cloudflare Worker + D1 (or KV), uploads behind Cloudflare Access. In parallel,
   ask Tufts IT about a Box API app; use Box as storage if approved.
4. **Only if demand is real:** school circles, moderated board, remix lineage, "ran it" reports.
   Remix-by-chat (idea 12) can be added at any stage.

## Open questions

- Do teachers share mostly within their own school, or across districts? (Short codes vs. circles.)
- Do they copy games as-is or adapt them? (Is chat context worth its privacy cost?)
- What share of saved games fit under ~2 KB compressed? (Measure.)
- Will Tufts approve a Box API app, and do Tufts shared links work for non-Tufts teachers?
