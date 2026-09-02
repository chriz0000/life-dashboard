#!/usr/bin/env node
/**
 * Daily dashboard refresh.
 *
 * Runs in GitHub Actions, not in a Claude session — so it has real logs you
 * can read when it breaks, and it pushes with the repo's own token.
 *
 * What it does:
 *   1. Works out what day of the 150 it is.
 *   2. Rolls still-open tasks in the Daily project forward to today.
 *   3. Mirrors those tasks into briefing.json so the dashboard matches Todoist.
 *   4. Recomputes the money numbers from the bills + subscriptions projects.
 *   5. Writes briefing.json. The caller commits it.
 *
 * What it deliberately does NOT do: write the prose briefing. A script can't
 * judge what matters today. It leaves a short honest placeholder and Christian
 * gets the written one when he messages.
 *
 * Env:
 *   TODOIST_TOKEN  required for the Todoist half. Without it the script still
 *                  writes an honest briefing (everything Todoist-derived is
 *                  reported as "not checked") and then exits 1, so the run goes
 *                  RED. It used to exit 0, which meant a missing secret looked
 *                  identical to a healthy run -- 29 days of green no-ops.
 *   ALLOW_NO_TODOIST  set to "1" to keep the old exit-0 behaviour for local
 *                  runs where you genuinely don't have the token to hand.
 *   DRY_RUN        set to "1" to log everything and write nothing.
 */

import { readFileSync, writeFileSync } from "node:fs";

const TZ = "Australia/Brisbane";
const DRY = process.env.DRY_RUN === "1";
const TOKEN = process.env.TODOIST_TOKEN;
const ALLOW_NO_TODOIST = process.env.ALLOW_NO_TODOIST === "1";

const PROJECTS = {
  daily: "6h56xJPfVRX5MRMg",
  bills: "6gmg49J5v83jcpv4",
  subscriptions: "6gp7pFW68M8wP66G",
};

const log = (...a) => console.log(...a);
const fail = (msg) => { console.error(`FAILED: ${msg}`); process.exit(1); };

/* ---------- dates, all in Brisbane ---------- */
function brisbaneToday() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(new Date());
  const get = (t) => parts.find((p) => p.type === t).value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}
function brisbaneNowISO() {
  const d = new Intl.DateTimeFormat("en-GB", {
    timeZone: TZ, hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(new Date());
  return `${brisbaneToday()}T${d}:00+10:00`;
}
const daysBetween = (a, b) => Math.round((Date.parse(`${b}T00:00:00+10:00`) - Date.parse(`${a}T00:00:00+10:00`)) / 86400000);

/* ---------- Todoist ----------
   Todoist has both a unified v1 API and the older REST v2, and which one
   serves a given account has moved around. Try v1, fall back to v2, and say
   loudly which one worked so a future break is obvious in the log. */
const BASES = ["https://api.todoist.com/api/v1", "https://api.todoist.com/rest/v2"];
let base = null;

async function td(path, options = {}) {
  const tryBases = base ? [base] : BASES;
  let lastErr;
  for (const b of tryBases) {
    const res = await fetch(`${b}${path}`, {
      ...options,
      headers: {
        Authorization: `Bearer ${TOKEN}`,
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    });
    if (res.ok) {
      if (!base) { base = b; log(`  Todoist API: ${b}`); }
      const text = await res.text();
      return text ? JSON.parse(text) : null;
    }
    lastErr = `${res.status} ${res.statusText} from ${b}${path}`;
    if (res.status === 401) fail(`Todoist rejected the token (401). Check the TODOIST_TOKEN secret.`);
  }
  throw new Error(lastErr);
}

// v1 returns {results:[...]}, v2 returns a bare array. Accept either.
const listOf = (d) => (Array.isArray(d) ? d : d?.results || d?.items || []);

async function openTasks(projectId) {
  const data = await td(`/tasks?project_id=${projectId}`);
  const items = listOf(data);
  if (!Array.isArray(items)) fail(`Unexpected Todoist response shape: ${JSON.stringify(data).slice(0, 300)}`);
  return items.filter((t) => !t.is_completed && !t.checked);
}

const dueDateOf = (t) => t?.due?.date?.slice(0, 10) || null;

async function rollForward(task, today) {
  if (DRY) { log(`  [dry] would roll "${task.content}" → ${today}`); return; }
  await td(`/tasks/${task.id}`, { method: "POST", body: JSON.stringify({ due_date: today }) });
}

/* ---------- money ---------- */
const money = (t) => {
  const m = `${t.content} ${t.description || ""}`.match(/\$\s?([\d,]+(?:\.\d{2})?)/);
  return m ? parseFloat(m[1].replace(/,/g, "")) : 0;
};

/* ---------- main ---------- */
const today = brisbaneToday();
log(`Daily refresh — ${today} (${TZ})${DRY ? " [DRY RUN]" : ""}`);

const plan = JSON.parse(readFileSync("plan.json", "utf8"));
const briefing = JSON.parse(readFileSync("briefing.json", "utf8"));
const day = daysBetween(plan.startDate, today) + 1;
log(`Day ${day} of 150`);

const weekday = new Intl.DateTimeFormat("en-AU", { timeZone: TZ, weekday: "short" }).format(new Date());
const rhythm = plan.rhythm.days.find((d) => d.day === weekday);
log(`${weekday} — rhythm says: ${rhythm ? rhythm.what : "(no entry)"}`);

let todayItems = [];
let overdueTotal = 0;
let overdueCount = 0;
let rolled = 0;

if (!TOKEN) {
  console.error(
    "TODOIST_TOKEN is not set — the Todoist half is being skipped and the day " +
    "counter is all that will update. Add the secret to the repo " +
    "(gh secret set TODOIST_TOKEN) or set ALLOW_NO_TODOIST=1 for a local run."
  );
} else {
  log("Reading Todoist…");
  const daily = await openTasks(PROJECTS.daily);
  log(`  ${daily.length} open task(s) in the Daily project`);

  for (const t of daily) {
    const d = dueDateOf(t);
    if (d && d < today) { await rollForward(t, today); rolled++; log(`  rolled forward: ${t.content}`); }
  }
  if (rolled) log(`  ${rolled} overdue task(s) moved to today`);

  todayItems = daily.map((t) => ({
    level: t.priority >= 4 ? "critical" : t.priority === 3 ? "warning" : "neutral",
    text: t.content.replace(/^[^\p{L}\p{N}]+/u, "").trim(),
  }));

  for (const pid of [PROJECTS.bills, PROJECTS.subscriptions]) {
    for (const t of await openTasks(pid)) {
      const d = dueDateOf(t);
      if (d && d <= today) { overdueTotal += money(t); overdueCount++; }
    }
  }
  log(`  $${overdueTotal.toFixed(2)} across ${overdueCount} due or overdue item(s)`);
}

/* ---------- briefing ----------
   Anything Todoist wasn't consulted about is reported as "not checked".
   A dashboard that says "nothing overdue" when it never looked is worse
   than one that admits it doesn't know. */
const fmtMoney = (n) => `$${n.toFixed(2).replace(/\.00$/, "")}`;
const checked = Boolean(TOKEN);
const behind = checked && todayItems.some((t) => /baseline|Day 1/i.test(t.text));
const rhythmText = (rhythm ? rhythm.what : "no fixed slot today").replace(/\.$/, "");

briefing.date = today;
briefing.writtenAt = brisbaneNowISO();
briefing.message = [
  `Day ${day} of 150. This is the automatic refresh — the written briefing comes when you message me.`,
  behind
    ? `Day 1 still isn't filmed. Everything in the arc is measured against a baseline that doesn't exist yet, and it gets weaker the longer it waits.`
    : `${weekday} in the rhythm: ${rhythmText}.`,
  !checked
    ? `I couldn't reach Todoist this morning, so the list and the money below are from the last time someone looked — treat them as stale, not current.`
    : overdueCount
    ? `${fmtMoney(overdueTotal)} sitting due or overdue across ${overdueCount} item${overdueCount === 1 ? "" : "s"}.`
    : `Nothing overdue — bills and subscriptions are clear.`,
];

// Only overwrite the list when Todoist actually answered.
if (checked && todayItems.length) briefing.today = todayItems;

briefing.numbers = [
  { label: "The build", value: `Day ${day}`, note: "of 150", level: behind ? "warning" : "info" },
  checked
    ? { label: "Open today", value: String(todayItems.length), note: rolled ? `${rolled} rolled over` : "from Todoist", level: todayItems.length > 7 ? "warning" : "neutral" }
    : { label: "Open today", value: "—", note: "Todoist unreachable", level: "warning" },
  checked
    ? { label: "Due / overdue", value: overdueCount ? fmtMoney(overdueTotal) : "$0", note: `${overdueCount} item${overdueCount === 1 ? "" : "s"}`, level: overdueCount ? "critical" : "good" }
    : { label: "Due / overdue", value: "—", note: "not checked", level: "warning" },
];

if (DRY) {
  log("\n[dry] briefing.json would become:\n" + JSON.stringify(briefing, null, 2).slice(0, 1200));
} else {
  writeFileSync("briefing.json", JSON.stringify(briefing, null, 2) + "\n");
  log("briefing.json written");
}
log("Done.");

/* A missing connector must not look like a healthy run. The briefing above is
   written and committed either way, so the dashboard still tells the truth --
   but the job itself goes red so the failure is actually noticed. */
if (!TOKEN && !ALLOW_NO_TODOIST) {
  console.error(
    "\nRun marked FAILED: briefing.json was written, but it contains no live " +
    "Todoist data. Fix TODOIST_TOKEN and re-run."
  );
  process.exit(1);
}
