# WHOOP Integration Setup

This connects the life dashboard to your WHOOP data (recovery, sleep, strain,
HRV, resting heart rate) via the official WHOOP API v2.

## One-time setup

1. Go to [developer.whoop.com](https://developer.whoop.com) and create an app.
2. Set the redirect URI to `http://localhost:3000/callback`.
3. Copy your **Client ID** and **Client Secret**.
4. Run the setup script with those credentials:

   ```bash
   WHOOP_CLIENT_ID=xxx WHOOP_CLIENT_SECRET=yyy python3 whoop_setup.py
   ```

5. A browser window will open - log in to WHOOP and approve access.
6. Done. Tokens are saved to `.whoop-tokens.json` (gitignored, never committed).

## Daily sync

Run:

```bash
python3 whoop_sync.py
```

This refreshes the access token automatically and writes the latest
recovery, sleep, and strain data to `whoop-data.json`.

To keep the dashboard up to date automatically, schedule this to run
daily (e.g. with `cron` or `launchd`).

## Troubleshooting

- **"WHOOP is not connected"** - run `whoop_setup.py` again as described above.
- **Refresh fails repeatedly** - your refresh token may have been revoked
  (e.g. if you disconnected the app in WHOOP). Re-run `whoop_setup.py`.
- **Port 3000 already in use** - stop whatever is using that port, or
  temporarily change `PORT` and `REDIRECT_URI` in `whoop_setup.py` *and*
  the redirect URI in your WHOOP developer app settings to match.
