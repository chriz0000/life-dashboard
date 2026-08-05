# Dashboard Refresh Checklist

Run through this every time the dashboard refreshes (the automated cycle runs
every ~5 hours). Goal: every number on the dashboard should be traceable to a
live source, not stale prose.

**The dashboard is a PA-style daily briefing. Each refresh cycle produces two
files — never touch `index.html`:**

1. **`data.json`** — the machine-readable state (bills, revenue, pillar scores).
   Update it from the sources below exactly as before.
2. **`briefing.json`** — the editorial layer the page actually displays. After
   updating `data.json`, WRITE THE BRIEFING like a personal assistant talking
   to Christian:
   - `date` (YYYY-MM-DD, Brisbane) and `writtenAt` (ISO, +10:00)
   - `message`: 3–4 short paragraphs in second person. Match the time of day
     it's written (a 9 PM briefing reads differently from a 7 AM one). Lead
     with a win if there is one, then the hardest thing, each with the ONE
     concrete next action. Ask a question when input is needed (next race,
     ambiguous bills). Never carry over yesterday's wording.
   - `today`: 4–6 checkable actions, most impactful first
     (levels: critical / warning / good / neutral)
   - `numbers`: 3–5 stat tiles — only numbers that matter *today*
   - `radar`: 2–4 quiet items being tracked, each with what would resolve it

The page fetches `briefing.json` + `whoop-data.json` with no caching on every
load, on focus, and every 5 minutes — pushed updates appear without reinstall.
If `briefing.json`'s `date` is not today, the page flags the briefing as old
automatically. If WHOOP synced within 36h, a Recovery tile is injected
automatically — don't duplicate it in `numbers`.

## 0. The chat (`api/chat.js`)

The dashboard has a live chat that talks to Claude directly — no app switching.
It's a Vercel Edge function that streams replies, and it builds its system
prompt by fetching `briefing.json`, `data.json` and `whoop-data.json` from the
deployment at request time. **That means a refreshed briefing updates what the
chat knows, automatically — there is nothing extra to do here.**

Two environment variables in the Vercel project:

- `ANTHROPIC_API_KEY` — **required**, or the chat replies with a setup message
- `CHAT_PASSCODE` — optional but recommended; the site is public, so without it
  anyone who finds the URL can spend the API credit. The page prompts once and
  remembers it.

Model is `claude-opus-5` at `effort: low` (fast replies for phone use), with
server-side refusal fallback enabled. Conversations are stored per-day in the
browser only — they are never written back to `data.json` or `briefing.json`,
so anything Christian tells the chat must be carried into the next briefing by
hand.

## 1. Verify connections are live

Before trusting any data, confirm each source actually responds:

- [ ] **Gmail** (`chrishstyles123@gmail.com`) — `search_threads` returns results, no auth error
- [ ] **Todoist** (`christians.t@outlook.com`) — `user-info` returns the account, no auth error
- [ ] **Square** (NRICH Wellness POS) — `make_api_request` (payments/list) returns data
- [ ] **Shopify** (nrichwellness.store) — `get-shop-info` returns the store
- [ ] **Notion** — `notion-search` returns workspace results
- [ ] **WHOOP** — check `whoop-data.json`'s `synced_at`. This dashboard's remote
      environment has no WHOOP credentials — WHOOP only refreshes when
      `whoop_sync.py` is run somewhere that holds `.whoop-tokens.json` (currently:
      manually, on desktop). The page flags itself as "Stale" automatically when
      `synced_at` is more than ~36h old — never guess new numbers.

If any source errors out, stop and report it rather than leaving old data in place.

## 2. Update `data.json` per section

| `data.json` field | Source | What to update |
|---|---|---|
| `focusToday` | Everything below | Regenerate the prose highlights from current bill/recovery/revenue numbers — don't carry over yesterday's wording. `level` is `good` / `warning` / `critical` / `neutral` |
| `money.bills` | Todoist (`💰 My Bills & Debts`, `📺 Subscriptions` projects) | Re-check every due date against today; set `status` to `overdue` / `due-today` / `upcoming` |
| `money.revenue` | Square `payments.list` (`begin_time` = 1st of month) + Shopify `list-orders` | Sum the month; note the Square/online split in `sub` |
| `pillars[*].score` / `status` / `level` | Judgement + Todoist `get-productivity-stats` | `level` drives the color, same values as above |
| `marathon` / `week` | Manual | Only when the training plan changes; countdown and current week are computed from `raceDate` at load time |
| `meta.updatedAt` | — | Set to the current ISO timestamp with `+10:00` offset |

WHOOP values are **not** in `data.json` — the page reads `whoop-data.json`
directly, so `whoop_sync.py` output is live without a second copy.

## 3. Self-updating fields — don't hand-edit these

The page derives these from the real calendar at load time — fix the anchor
data in `data.json` instead if something looks wrong:

- Today's weekday highlight in the week strip
- Days-to-race countdown and "Week N of M" — computed from `marathon.raceDate`
  (if the race date passes, the page says so; set the next goal in `data.json`)
- Life score — weighted average of `pillars[*].score × weight`
- WHOOP staleness flag — from `whoop-data.json`'s `synced_at`

## 4. Known data-quality issue to clean up (not fixed automatically)

The Todoist `💰 My Bills & Debts` project has duplicate/conflicting entries
(e.g. two different "Internet" bills at $50 and $80, two "CBA credit card"
entries, two "Zip" entries — leftovers from an old tracker mixed with a new
one, some tagged `Christian` vs `Karin`). Don't auto-resolve this — it needs a
human pass. Until cleaned up, the Money section only reflects the bills
already curated in `data.json`, not the full Todoist project.

## 5. Connections that are NOT live (by design, for now)

Only one Gmail account (`chrishstyles123@gmail.com`) is connected. Other
inboxes have no MCP/API access from this environment and were removed from
the dashboard rather than left as stale placeholders.

## 6. Finally

- [ ] Set `meta.updatedAt` to the current time (ISO, `+10:00`)
- [ ] Confirm `meta.sources` still lists only sources actually wired up
- [ ] Validate: `python3 -c "import json; json.load(open('data.json'))"`
- [ ] Commit with a clear message (e.g. `Auto-update: <date> <time> — dashboard refresh`)
