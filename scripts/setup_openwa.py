"""One-shot helper to finish wiring OpenWA: list sessions, create the webhook,
and update the main .env with the session UUID.

Usage:
    python scripts/setup_openwa.py [--webhook-url URL] [--secret SECRET] [--session-name NAME]

Defaults:
    --webhook-url  http://localhost:8000/webhook
    --secret       barber-webhook-secret  (must match OPENWA_WEBHOOK_SECRET)
    --session-name barber-bot
"""
import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import httpx

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env", override=True)

OPENWA_URL = os.getenv("OPENWA_API_URL", "http://localhost:2785").rstrip("/")
OPENWA_KEY = os.getenv("OPENWA_API_KEY", "").strip()
WEBHOOK_URL = os.getenv("OPENWA_WEBHOOK_SECRET", "barber-webhook-secret")  # placeholder
ENV_PATH = PROJECT_ROOT / ".env"


def hdr() -> dict:
    return {"X-API-Key": OPENWA_KEY, "Content-Type": "application/json"}


def find_session_id_by_name(name: str) -> str | None:
    r = httpx.get(f"{OPENWA_URL}/api/sessions", headers=hdr(), timeout=10)
    r.raise_for_status()
    for s in r.json():
        if s.get("name") == name:
            return s["id"]
    return None


def upsert_env(session_uuid: str) -> None:
    if not ENV_PATH.exists():
        print(f"  .env not found at {ENV_PATH}")
        return
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    new_lines = []
    seen_session = False
    seen_key = False
    for line in lines:
        if line.startswith("OPENWA_SESSION_ID="):
            new_lines.append(f"OPENWA_SESSION_ID={session_uuid}")
            seen_session = True
        elif line.startswith("OPENWA_API_KEY="):
            new_lines.append(line)
            seen_key = True
        else:
            new_lines.append(line)
    if not seen_session:
        new_lines.append(f"OPENWA_SESSION_ID={session_uuid}")
    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def create_webhook(session_id: str, url: str, secret: str) -> dict:
    body = {
        "url": url,
        "events": ["message.received", "session.status"],
        "secret": secret,
    }
    r = httpx.post(
        f"{OPENWA_URL}/api/sessions/{session_id}/webhooks",
        headers=hdr(),
        json=body,
        timeout=15,
    )
    return r.json()


def update_webhook_secret(session_id: str, webhook_id: str, secret: str) -> None:
    r = httpx.put(
        f"{OPENWA_URL}/api/sessions/{session_id}/webhooks/{webhook_id}",
        headers=hdr(),
        json={"secret": secret},
        timeout=15,
    )
    r.raise_for_status()


def list_existing_webhooks(session_id: str) -> list:
    r = httpx.get(
        f"{OPENWA_URL}/api/sessions/{session_id}/webhooks",
        headers=hdr(),
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--webhook-url", default="http://localhost:8000/webhook")
    ap.add_argument("--secret", default="barber-webhook-secret")
    ap.add_argument("--session-name", default="barber-bot")
    args = ap.parse_args()

    print("=" * 60)
    print(" OpenWA one-shot setup")
    print("=" * 60)
    print(f"  OpenWA URL:  {OPENWA_URL}")
    print(f"  Session name: {args.session_name}")
    print(f"  Webhook URL:  {args.webhook_url}")
    print(f"  Secret:       {args.secret}")
    print("=" * 60)

    if not OPENWA_KEY:
        print("\nERROR: OPENWA_API_KEY is empty in .env. Set it and retry.")
        return 1

    print("\n[1/4] Looking up session by name...")
    session_id = find_session_id_by_name(args.session_name)
    if not session_id:
        print(f"  ERROR: No session named '{args.session_name}'.")
        print(f"  Create it first via the dashboard or POST /api/sessions")
        return 1
    print(f"  Found: {session_id}")

    print(f"\n[2/4] Checking session status...")
    r = httpx.get(f"{OPENWA_URL}/api/sessions/{session_id}", headers=hdr(), timeout=10)
    r.raise_for_status()
    status = r.json().get("status")
    print(f"  Status: {status}")
    if status != "ready" and status != "qr_ready":
        print(f"  (Session is not ready yet; status='{status}'. Continue anyway.)")

    print(f"\n[3/4] Checking existing webhooks...")
    existing = list_existing_webhooks(session_id)
    if existing:
        print(f"  Found {len(existing)} existing webhook(s):")
        for w in existing:
            print(f"    - id={w.get('id')[:8]}  url={w.get('url')}  secret={bool(w.get('secret'))}")
            if w.get("url") == args.webhook_url and not w.get("secret"):
                print(f"      Updating existing webhook to set secret...")
                update_webhook_secret(session_id, w["id"], args.secret)
                print(f"      Secret set.")
    else:
        print("  No webhooks yet.")

    print(f"\n[4/4] Creating webhook...")
    try:
        created = create_webhook(session_id, args.webhook_url, args.secret)
        print(f"  Created: {created}")
    except httpx.HTTPStatusError as exc:
        body = exc.response.text
        if "already exists" in body.lower() or exc.response.status_code == 409:
            print("  Webhook already exists for this URL (skipping).")
        else:
            print(f"  ERROR: {exc.response.status_code} {body}")
            return 1

    print("\nUpdating .env OPENWA_SESSION_ID with the UUID...")
    upsert_env(session_id)
    print(f"  Set OPENWA_SESSION_ID={session_id}")

    print()
    print("=" * 60)
    print(" Done! Next steps:")
    print("   1. In the dashboard, scan the QR with WhatsApp on the")
    print("      barber's phone (if you haven't already).")
    print("   2. Run  stop.bat  then  start-openwa.bat  to reload the bot")
    print("      with the new OPENWA_SESSION_ID.")
    print("   3. Send 'hi' to the linked WhatsApp number to test.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
