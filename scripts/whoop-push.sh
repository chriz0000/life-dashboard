#!/bin/bash
#
# WHOOP sync -> commit -> push.
#
# WHOOP lives here on the Mac rather than in GitHub Actions on purpose: the
# OAuth refresh token rotates on use and is stored in .whoop-tokens.json, which
# is gitignored. Actions would need a writable secret to persist each new token,
# which is fragile. This machine already holds valid tokens, so it syncs and
# pushes just the one file.
#
# Installed as a launchd agent: com.christian.whoop-sync.plist
set -uo pipefail

REPO="$HOME/Projects/life-dashboard"
LOG="$REPO/logs/whoop-$(date '+%Y-%m').log"
mkdir -p "$REPO/logs"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

cd "$REPO" || { log "FATAL: repo missing at $REPO"; exit 1; }

log "--- whoop sync start ---"

# Rebase onto origin first so the daily bot's briefing commits don't collide.
if git pull --rebase --autostash origin main >>"$LOG" 2>&1; then
  log "pull ok"
else
  log "WARN: pull failed, continuing on local copy"
fi

if python3 whoop_sync.py >>"$LOG" 2>&1; then
  log "whoop sync ok"
else
  log "ERROR: whoop sync failed (token may need re-minting via whoop_setup.py)"
  exit 1
fi

if git diff --quiet -- whoop-data.json; then
  log "no change to whoop-data.json"
else
  git add whoop-data.json
  git commit -m "WHOOP sync: $(TZ=Australia/Brisbane date '+%-d %b %Y %H:%M')" >>"$LOG" 2>&1
  if git push origin main >>"$LOG" 2>&1; then
    log "pushed"
  else
    log "ERROR: push failed"
    exit 1
  fi
fi

log "--- whoop sync end ---"
