# Dashboard Refresh Checklist

Run through this every time the dashboard refreshes (the automated cycle runs
every ~5 hours). Goal: every number on the dashboard should be traceable to a
live source, not stale prose.

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
      manually, on desktop). If `synced_at` is more than ~24h old, flag it as stale
      rather than guessing new numbers.

If any source errors out, stop and report it rather than leaving old data in place.

## 2. Pull fresh data per section

| Section | Source | What to update |
|---|---|---|
| Recovery / Sleep / Strain | `whoop-data.json` | Pull latest values as-is (see WHOOP note above) |
| Bills & subscriptions | Todoist (`💰 My Bills & Debts`, `📺 Subscriptions` projects) | Re-check every due date against today; recompute overdue/due-today/upcoming status — don't carry over yesterday's wording |
| Revenue (Square) | Square `payments.list`, `begin_time` = 1st of current month | Sum `amount_money` for the month |
| Revenue (Shopify) | Shopify `list-orders` | Count + sum orders this month |
| Karma / streak / completion | Todoist `get-productivity-stats` | `karma`, `karmaGraphData` (last 7 entries), `goals.currentDailyStreak`, `weekItems` |
| Content calendar | Notion search "Content Calendar" | Last-updated timestamp shown in Brand pillar |
| Email highlights | Gmail `search_threads` (`in:inbox`, most recent) | Top 3-4 threads with sender/subject/relative time |
| Marathon countdown / training week | Computed automatically | See note below — no manual edit needed |

## 3. Self-updating fields — don't hand-edit these

The script now derives the following from the real calendar at load time
(see the `syncDates()` block right after the `DATA` object). **Do not
hand-edit them** — fix the anchor data instead if something looks wrong:

- `schedule.today` / `weekSchedule.today` — today's weekday abbreviation
- `physical.today` — pulled from the matching `weekSchedule` entry for today
- `physical.marathon.daysOut` — computed from `physical.marathon.raceDate` (fixed ISO date)
- `physical.trainingBlock.items` (done/current/future) — computed from days remaining to the race

If the race date changes, update `marathon.raceDate` once — everything else follows.

## 4. Things that are still manual (flag, don't fabricate)

- `focusToday` — prose highlights regenerated from current bill/recovery/revenue
  numbers each cycle (not computed automatically)
- `schedule.events` — today's agenda; should match `weekSchedule` for the
  current day, not be left over from a previous day
- `spirit.readingPlan.currentBook` / `todaysReading` — manual, tracks actual reading progress
- `knowledge.areas` — manual, tracks actual study progress
- Todoist task list under Discipline → "Today's Tasks" — these are illustrative
  daily intentions, **not** pulled from a real Todoist project. If you want this
  live, create a dedicated Todoist project for daily habits.

## 5. Known data-quality issue to clean up (not fixed automatically)

The Todoist `💰 My Bills & Debts` project has duplicate/conflicting entries
(e.g. two different "Internet" bills at $50 and $80, two "CBA credit card"
entries, two "Zip" entries — looks like leftovers from an old tracker mixed
with a new one, some tagged `Christian` vs `Karin`). Don't auto-resolve this —
it needs a human pass to decide which entries are current. Until cleaned up,
the Capital pillar only reflects the bills already curated in the dashboard,
not the full Todoist project.

## 6. Connections that are NOT live (by design, for now)

Only one Gmail account (`chrishstyles123@gmail.com`) is connected. The other
inboxes once listed (iCloud, Personal Outlook, and the separate business
inboxes for other brands) have no MCP/API access from this environment and
were removed from the live dashboard rather than left as stale placeholders.
Re-add them once they have a real connection.

## 7. Finally

- [ ] Update `meta.updated` to the current time
- [ ] Confirm `meta.sources` still lists only sources actually wired up
- [ ] Commit with a clear message (e.g. `Auto-update: <date> <time> — dashboard refresh`)
