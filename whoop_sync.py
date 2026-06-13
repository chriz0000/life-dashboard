#!/usr/bin/env python3
"""
WHOOP data sync for the life dashboard.

Reads stored OAuth tokens from .whoop-tokens.json, refreshes the access
token, pulls the latest recovery, sleep, and cycle (strain) data from the
WHOOP API v2, and writes a summary to whoop-data.json.

Run this daily (e.g. via cron or launchd) to keep the dashboard fresh.
If no tokens are found, run whoop_setup.py first (see whoop-setup.md).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
TOKENS_FILE = SCRIPT_DIR / ".whoop-tokens.json"
OUTPUT_FILE = SCRIPT_DIR / "whoop-data.json"

TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
API_BASE = "https://api.prod.whoop.com/developer/v2"

REQUEST_TIMEOUT = 30


def print_auth_instructions():
    print("=" * 60)
    print("WHOOP is not connected (no valid tokens found).")
    print()
    print("Run the one-time setup script to authenticate:")
    print()
    print("  WHOOP_CLIENT_ID=xxx WHOOP_CLIENT_SECRET=yyy python3 whoop_setup.py")
    print()
    print("See whoop-setup.md for full instructions.")
    print("=" * 60)


def load_tokens():
    if not TOKENS_FILE.exists():
        return None
    try:
        with open(TOKENS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_tokens(tokens):
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)
    TOKENS_FILE.chmod(0o600)


def refresh_access_token(tokens):
    """Exchange the stored refresh token for a fresh access token."""
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": tokens["client_id"],
            "client_secret": tokens["client_secret"],
            "scope": "offline",
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    new_tokens = response.json()

    tokens["access_token"] = new_tokens["access_token"]
    # WHOOP doesn't always rotate the refresh token - keep the old one
    # if a new one isn't issued.
    tokens["refresh_token"] = new_tokens.get("refresh_token", tokens["refresh_token"])
    tokens["token_type"] = new_tokens.get("token_type", tokens.get("token_type", "Bearer"))
    save_tokens(tokens)
    return tokens


def api_get(path, access_token, params=None):
    response = requests.get(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def get_latest_record(path, access_token):
    """Fetch the most recent record from a paginated WHOOP collection endpoint."""
    data = api_get(path, access_token, params={"limit": 1})
    records = data.get("records", [])
    return records[0] if records else None


def build_summary(recovery, sleep, cycle):
    summary = {"synced_at": datetime.now(timezone.utc).isoformat()}

    if recovery:
        score = recovery.get("score", {})
        summary["recovery"] = {
            "date": recovery.get("created_at"),
            "recovery_score": score.get("recovery_score"),
            "hrv_ms": score.get("hrv_rmssd_milli"),
            "resting_heart_rate": score.get("resting_heart_rate"),
        }

    if sleep:
        score = sleep.get("score", {})
        summary["sleep"] = {
            "date": sleep.get("start"),
            "sleep_score": score.get("sleep_performance_percentage"),
            "efficiency_percentage": score.get("sleep_efficiency_percentage"),
        }

    if cycle:
        score = cycle.get("score", {})
        summary["strain"] = {
            "date": cycle.get("start"),
            "strain_score": score.get("strain"),
            "average_heart_rate": score.get("average_heart_rate"),
        }

    return summary


def main():
    tokens = load_tokens()
    if not tokens or not tokens.get("refresh_token"):
        print_auth_instructions()
        sys.exit(0)

    try:
        tokens = refresh_access_token(tokens)
    except requests.exceptions.RequestException as e:
        print(f"Failed to refresh WHOOP access token: {e}")
        print_auth_instructions()
        sys.exit(1)

    access_token = tokens["access_token"]

    try:
        recovery = get_latest_record("/recovery", access_token)
        sleep = get_latest_record("/activity/sleep", access_token)
        cycle = get_latest_record("/cycle", access_token)
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch WHOOP data: {e}")
        sys.exit(1)

    summary = build_summary(recovery, sleep, cycle)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Synced WHOOP data to {OUTPUT_FILE}")
    if "recovery" in summary:
        print(f"  Recovery: {summary['recovery']['recovery_score']}%")
    if "sleep" in summary:
        print(f"  Sleep: {summary['sleep']['sleep_score']}%")
    if "strain" in summary:
        print(f"  Strain: {summary['strain']['strain_score']}")


if __name__ == "__main__":
    main()
