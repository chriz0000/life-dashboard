# Dashboard Refresh Checklist

Run through this every time the dashboard refreshes. Goal: every number on the
dashboard should be traceable to a live source, not stale prose.

**The dashboard is a PA-style daily briefing. Never touch `index.html` during a
refresh.** There are five data files, and only two of them change daily:

| File | Changes | What it is |
|---|---|---|
| `briefing.json` | **daily** | The editorial layer the page displays |
| `data.json` | **daily** | Machine-readable state (bills, pillars, training week) |
| `plan.json` | when the strategy changes | The 150-day content plan |
| `czech.json` | when the course changes | The 30-lesson Czech block |
| `whoop-data.json` | every ~6h, automatically | Written by the desktop sync — never hand-edit |

## Writing `briefing.json`

Write it like a personal assistant talking to Christian:

- `date` (YYYY-MM-DD, Brisbane) and `writtenAt` (ISO, `+10:00`)
- `handwritten: true` — set this whenever you write the prose by hand. The
  5:50am job checks it and refreshes the numbers underneath without touching
  your text. It clears the flag when it does overwrite, so it never goes stale.
- `message`: 3–4 short paragraphs in second person. Match the time of day it's
  written (a 9 PM briefing reads differently from a 7 AM one). Lead with a win
  if there is one, then the hardest thing, each with the ONE concrete next
  action. Never carry over yesterday's wording.
- `today`: 4–6 checkable actions, most impactful first
  (levels: `critical` / `warning` / `good` / `neutral`)
- `numbers`: 3–5 stat tiles — only numbers that matter *today*. They sit at the
  very top of the page, above the prose, so they have to earn that spot

The page fetches `briefing.json`, `whoop-data.json`, `plan.json` and
`czech.json` with no caching on every load, on focus, and every 5 minutes —
pushed updates appear without reinstall. If `briefing.json`'s `date` is not
today, the page flags the briefing as old automatically. If WHOOP synced within
36h, a Recovery tile is injected automatically — don't duplicate it in
`numbers`.

## 1. The automated half (`.github/workflows/daily.yml`)

A GitHub Action runs `scripts/daily.mjs` at 05:50 Brisbane every day. It rolls
overdue Daily tasks forward, mirrors the list into `briefing.json`, totals the
bills, and commits. It writes a plain template briefing — it deliberately does
not attempt prose.

- It needs the **`TODOIST_TOKEN`** repo secret. Without it the run goes red and
  everything Todoist-derived is reported as "not checked" rather than faked.
- Run it by hand from the Actions tab (`workflow_dispatch`, with a `dry_run`
  option) to test a change.

## 2. Verify connections are live

Before trusting any data, confirm each source actually responds:

- [ ] **Gmail** (`chrishstyles123@gmail.com`) — `search_threads` returns results, no auth error
- [ ] **Todoist** (`christians.t@outlook.com`) — `user-info` returns the account, no auth error
- [ ] **Notion** — `notion-search` returns workspace results
- [ ] **WHOOP** — check `whoop-data.json`'s `synced_at`. This remote environment
      has no WHOOP credentials and cannot reach the API; WHOOP refreshes only
      from Christian's desktop, where a launchd job runs `scripts/whoop-push.sh`
      every ~6 hours. The page flags itself as "Stale" when `synced_at` is more
      than ~36h old — never guess new numbers.

If any source errors out, stop and report it rather than leaving old data in place.

## 3. Update `data.json` per section

| `data.json` field | Source | What to update |
|---|---|---|
| `focusToday` | Everything below | Regenerate from current bill/recovery/content numbers — don't carry over yesterday's wording |
| `money.bills` | Todoist (`💰 My Bills & Debts`, `📺 Subscriptions`) | Re-check every due date against today; set `status` to `overdue` / `due-today` / `upcoming` |
| `money.revenue` | The channel | There is no revenue until YouTube Partner Program is reached. Say `$0` and why, don't leave a placeholder |
| `pillars[*].score` / `status` / `level` | Judgement + Todoist `get-productivity-stats` | `level` drives the colour |
| `marathon` / `week` | Manual | Only when the training plan changes; the countdown is computed from `raceDate` |
| `meta.updatedAt` | — | Current ISO timestamp with `+10:00` |

WHOOP values are **not** in `data.json` — the page reads `whoop-data.json`
directly.

## 4. Self-updating fields — don't hand-edit these

The page derives these at load time; fix the anchor data instead:

- Day N of 150 — computed from `plan.startDate`
- Czech day and streak — computed from `czech.startDate` plus local completion marks
- WHOOP staleness flag — from `whoop-data.json`'s `synced_at`

## 5. Known data-quality issue (not fixed automatically)

The Todoist `💰 My Bills & Debts` project has duplicate/conflicting entries
(two "Internet" bills at $50 and $80, two "CBA credit card" entries, two "Zip"
entries — an old tracker mixed with a new one, some tagged `Christian` vs
`Karin`). Don't auto-resolve this — it needs a human pass. Until then the money
numbers reflect the bills curated in `data.json`, not the full project.

## 6. Finally

- [ ] Set `meta.updatedAt` to the current time (ISO, `+10:00`)
- [ ] Confirm `meta.sources` lists only sources actually wired up
- [ ] Validate: `python3 -c "import json,sys; [json.load(open(f)) for f in ['data.json','briefing.json','plan.json','czech.json']]"`
- [ ] Commit with a clear message (e.g. `Daily refresh: <date>`)
