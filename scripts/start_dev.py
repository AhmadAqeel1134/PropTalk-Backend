"""
PropTalk Dev Startup Script
============================
Automates the full local dev workflow in a single command:

  python scripts/start_dev.py

Steps performed automatically:
  1. Starts cloudflared tunnel (port 8001)
  2. Captures the generated trycloudflare.com URL
  3. Updates TWILIO_VOICE_WEBHOOK_URL in .env
  4. Updates ALL owned Twilio phone number webhooks via API
     (READ + UPDATE only — never purchases numbers)
  5. Starts uvicorn with --reload
  6. Forwards output from both processes; clean Ctrl+C shutdown
"""

import os
import re
import sys
import time
import signal
import threading
import subprocess
from pathlib import Path
from dotenv import dotenv_values, set_key
from twilio.rest import Client as TwilioClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROOT_DIR       = Path(__file__).resolve().parent.parent
ENV_FILE       = ROOT_DIR / ".env"
CLOUDFLARED    = r"D:\cloudflare\cloudflared-windows-amd64.exe"
LOCAL_PORT     = 8001
UVICORN_APP    = "app.main:app"

# Regex that matches any trycloudflare.com URL inside cloudflared output
TUNNEL_URL_RE  = re.compile(r"https://[a-z0-9\-]+\.trycloudflare\.com")

# How long (seconds) to wait for cloudflared to print its URL before giving up
TUNNEL_TIMEOUT = 60

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print(tag: str, msg: str) -> None:
    """Coloured, tagged print so cloudflared vs uvicorn output is easy to read."""
    COLORS = {
        "tunnel": "\033[94m",   # blue
        "twilio": "\033[92m",   # green
        "uvicorn": "\033[96m",  # cyan
        "error":  "\033[91m",   # red
        "info":   "\033[93m",   # yellow
    }
    reset = "\033[0m"
    color = COLORS.get(tag, "")
    print(f"{color}[{tag}]{reset} {msg}", flush=True)


def _load_env() -> dict:
    """Load .env as a plain dict (no os.environ pollution)."""
    if not ENV_FILE.exists():
        _print("error", f".env not found at {ENV_FILE}")
        sys.exit(1)
    return dotenv_values(ENV_FILE)


def _update_env_key(key: str, value: str) -> None:
    """Overwrite a single key in .env without touching other values."""
    set_key(str(ENV_FILE), key, value, quote_mode="never")


# ---------------------------------------------------------------------------
# Step 1 & 2 — Start cloudflared, capture URL
# ---------------------------------------------------------------------------

def start_tunnel() -> tuple[subprocess.Popen, str]:
    """
    Launch cloudflared and block until the tunnel URL is printed.
    Returns (process, url).
    """
    _print("tunnel", f"Starting cloudflared -> http://127.0.0.1:{LOCAL_PORT}")

    proc = subprocess.Popen(
        [CLOUDFLARED, "tunnel", "--url", f"http://127.0.0.1:{LOCAL_PORT}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,   # merge stderr into stdout for simplicity
        text=True,
        bufsize=1,
    )

    url_found = threading.Event()
    captured_url: list[str] = []          # mutable container for thread result
    buffered_lines: list[str] = []        # lines printed before URL is found

    def _reader():
        for line in proc.stdout:
            line = line.rstrip()
            match = TUNNEL_URL_RE.search(line)
            if match and not url_found.is_set():
                captured_url.append(match.group())
                url_found.set()
            # Always forward cloudflared output to terminal
            _print("tunnel", line)

    reader_thread = threading.Thread(target=_reader, daemon=True)
    reader_thread.start()

    if not url_found.wait(timeout=TUNNEL_TIMEOUT):
        proc.terminate()
        _print("error", "Timed out waiting for cloudflared URL. Is cloudflared running?")
        sys.exit(1)

    url = captured_url[0]
    _print("tunnel", f"URL captured: {url}")
    return proc, url


# ---------------------------------------------------------------------------
# Step 3 — Update .env
# ---------------------------------------------------------------------------

def update_env(new_url: str) -> None:
    _update_env_key("TWILIO_VOICE_WEBHOOK_URL", new_url)
    _print("info", f"Updated .env  TWILIO_VOICE_WEBHOOK_URL={new_url}")


# ---------------------------------------------------------------------------
# Step 4 — Update Twilio webhooks (READ + UPDATE only, zero purchases)
# ---------------------------------------------------------------------------

def update_twilio_webhooks(new_url: str, account_sid: str, auth_token: str) -> None:
    """
    List ALL phone numbers already owned on this Twilio account and update
    their voice + status webhook URLs to the new tunnel URL.

    This function ONLY calls:
      client.incoming_phone_numbers.list()          <- READ
      client.incoming_phone_numbers(sid).update()   <- UPDATE existing

    It NEVER calls available_phone_numbers or create(), so it cannot
    purchase or provision any new number.
    """
    client = TwilioClient(account_sid, auth_token)

    # Fetch owned numbers — if something fails here we abort early
    try:
        owned_numbers = client.incoming_phone_numbers.list()
    except Exception as exc:
        _print("error", f"Could not fetch Twilio numbers: {exc}")
        sys.exit(1)

    if not owned_numbers:
        _print("twilio", "No phone numbers found on this Twilio account. Skipping.")
        return

    base = new_url.rstrip("/")
    voice_url    = f"{base}/webhooks/twilio/voice"
    status_url   = f"{base}/webhooks/twilio/status"
    sms_url      = f"{base}/webhooks/twilio/sms"

    _print("twilio", f"Found {len(owned_numbers)} owned number(s) — updating voice + messaging webhooks:")
    for num in owned_numbers:
        _print("twilio", f"  {num.phone_number}  SID: {num.sid}")

    for num in owned_numbers:
        try:
            client.incoming_phone_numbers(num.sid).update(
                # Voice webhooks
                voice_url=voice_url,
                voice_method="POST",
                voice_fallback_url=voice_url,
                voice_fallback_method="POST",
                status_callback=status_url,
                status_callback_method="POST",
                # Messaging webhooks (for inbound SMS replies)
                sms_url=sms_url,
                sms_method="POST",
                sms_fallback_url=sms_url,
                sms_fallback_method="POST",
            )
            _print("twilio", f"  ✓ {num.phone_number} voice + messaging webhooks updated")
        except Exception as exc:
            _print("error", f"  ✗ Failed to update {num.phone_number}: {exc}")

    _print("twilio", f"Voice  -> {voice_url}")
    _print("twilio", f"Status -> {status_url}")
    _print("twilio", f"SMS    -> {sms_url}")


# ---------------------------------------------------------------------------
# Step 5 — Start uvicorn
# ---------------------------------------------------------------------------

def start_uvicorn() -> subprocess.Popen:
    _print("uvicorn", f"Starting uvicorn {UVICORN_APP} on http://127.0.0.1:{LOCAL_PORT}")

    # Pass the updated .env values into uvicorn's environment
    env = os.environ.copy()

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            UVICORN_APP,
            "--reload",
            "--host", "127.0.0.1",
            "--port", str(LOCAL_PORT),
        ],
        cwd=str(ROOT_DIR),
        env=env,
        text=True,
        bufsize=1,
    )
    return proc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print()
    _print("info", "PropTalk Dev — starting all services")
    _print("info", "Press Ctrl+C to stop everything cleanly")
    print()

    # Validate cloudflared binary exists
    if not Path(CLOUDFLARED).exists():
        _print("error", f"cloudflared not found at: {CLOUDFLARED}")
        _print("error", "Update the CLOUDFLARED path at the top of this script.")
        sys.exit(1)

    # Load credentials before starting subprocesses
    env_vals = _load_env()
    account_sid = env_vals.get("TWILIO_ACCOUNT_SID", "").strip()
    auth_token  = env_vals.get("TWILIO_AUTH_TOKEN", "").strip()

    if not account_sid or not auth_token:
        _print("error", "TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN missing in .env")
        sys.exit(1)

    # --- Step 1 & 2: tunnel ---
    tunnel_proc, tunnel_url = start_tunnel()
    print()

    # --- Step 3: .env ---
    update_env(tunnel_url)
    print()

    # --- Step 4: Twilio ---
    update_twilio_webhooks(tunnel_url, account_sid, auth_token)
    print()

    # --- Step 5: uvicorn ---
    uvicorn_proc = start_uvicorn()
    print()

    _print("info", "All services running. Ctrl+C to stop.")
    print()

    # --- Graceful shutdown on Ctrl+C ---
    def _shutdown(sig, frame):
        print()
        _print("info", "Shutting down...")
        uvicorn_proc.terminate()
        tunnel_proc.terminate()
        try:
            uvicorn_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            uvicorn_proc.kill()
        try:
            tunnel_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            tunnel_proc.kill()
        _print("info", "All processes stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Keep main thread alive; uvicorn handles its own --reload output
    uvicorn_proc.wait()

    # If uvicorn exits on its own (crash / port conflict), shut down tunnel too
    _print("error", "uvicorn exited unexpectedly. Stopping tunnel.")
    tunnel_proc.terminate()


if __name__ == "__main__":
    main()
