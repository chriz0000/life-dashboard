#!/usr/bin/env python3
"""
One-time WHOOP OAuth setup for the life dashboard.

Starts a local server on http://localhost:3000, opens the WHOOP login
page in your browser, captures the authorization code from the redirect,
and exchanges it for access/refresh tokens. Tokens (plus your client
credentials, needed for future refreshes) are saved to
.whoop-tokens.json for whoop_sync.py to use.

Usage:
    WHOOP_CLIENT_ID=xxx WHOOP_CLIENT_SECRET=yyy python3 whoop_setup.py

See whoop-setup.md for how to get a client ID/secret.
"""

import json
import os
import secrets
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
TOKENS_FILE = SCRIPT_DIR / ".whoop-tokens.json"

AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
REDIRECT_URI = "http://localhost:3000/callback"
SCOPES = "read:recovery read:cycles read:sleep read:workout read:profile read:body_measurement offline"

PORT = 3000
CALLBACK_TIMEOUT_SECONDS = 300
REQUEST_TIMEOUT = 30


class CallbackHandler(BaseHTTPRequestHandler):
    """Handles the OAuth redirect from WHOOP and captures the auth code."""

    expected_state = None
    auth_code = None
    error = None

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        params = parse_qs(parsed.query)

        if "error" in params:
            CallbackHandler.error = params["error"][0]
            self._respond("Authorization failed. You can close this tab and check the terminal.")
            return

        if params.get("state", [None])[0] != CallbackHandler.expected_state:
            CallbackHandler.error = "state_mismatch"
            self._respond("State mismatch (possible CSRF). You can close this tab.")
            return

        code = params.get("code", [None])[0]
        if not code:
            CallbackHandler.error = "missing_code"
            self._respond("No authorization code received. You can close this tab.")
            return

        CallbackHandler.auth_code = code
        self._respond("WHOOP connected! You can close this tab and return to the terminal.")

    def _respond(self, message):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(f"<html><body><h2>{message}</h2></body></html>".encode())

    def log_message(self, *args):
        pass  # silence default request logging


def exchange_code_for_tokens(code, client_id, client_secret):
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def main():
    client_id = os.environ.get("WHOOP_CLIENT_ID")
    client_secret = os.environ.get("WHOOP_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Set WHOOP_CLIENT_ID and WHOOP_CLIENT_SECRET environment variables first.")
        print()
        print("Example:")
        print("  WHOOP_CLIENT_ID=xxx WHOOP_CLIENT_SECRET=yyy python3 whoop_setup.py")
        print()
        print("See whoop-setup.md for how to create a WHOOP developer app.")
        sys.exit(1)

    state = secrets.token_urlsafe(16)
    CallbackHandler.expected_state = state

    auth_params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
    }
    auth_url = f"{AUTH_URL}?{urlencode(auth_params)}"

    try:
        server = HTTPServer(("localhost", PORT), CallbackHandler)
    except OSError as e:
        print(f"Could not start local server on port {PORT}: {e}")
        print("Make sure nothing else is using that port and try again.")
        sys.exit(1)

    print("Opening WHOOP login in your browser...")
    print(f"If it doesn't open automatically, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    print(f"Waiting for WHOOP callback on {REDIRECT_URI} ...")
    server.timeout = 1
    start = time.monotonic()
    while CallbackHandler.auth_code is None and CallbackHandler.error is None:
        server.handle_request()
        if time.monotonic() - start > CALLBACK_TIMEOUT_SECONDS:
            print(f"Timed out after {CALLBACK_TIMEOUT_SECONDS} seconds waiting for authorization.")
            server.server_close()
            sys.exit(1)

    server.server_close()

    if CallbackHandler.error:
        print(f"Authorization failed: {CallbackHandler.error}")
        sys.exit(1)

    print("Got authorization code, exchanging for tokens...")

    try:
        token_data = exchange_code_for_tokens(CallbackHandler.auth_code, client_id, client_secret)
    except requests.exceptions.RequestException as e:
        print(f"Failed to exchange code for tokens: {e}")
        sys.exit(1)

    tokens = {
        "client_id": client_id,
        "client_secret": client_secret,
        "access_token": token_data["access_token"],
        "refresh_token": token_data["refresh_token"],
        "token_type": token_data.get("token_type", "Bearer"),
        "scope": token_data.get("scope", SCOPES),
    }

    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)
    TOKENS_FILE.chmod(0o600)

    print(f"Tokens saved to {TOKENS_FILE}")
    print("You can now run whoop_sync.py to pull your WHOOP data.")


if __name__ == "__main__":
    main()
