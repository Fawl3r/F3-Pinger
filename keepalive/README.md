# ParlayGorilla Keep-Alive

Minimal keep-awake pinger for Render free-plan cold-start reduction. It hits the homepage first, then performs a deep health check (to warm DB connections), and logs one JSON line per request result.

## Local run

1. Create and activate a virtual environment:
   - Windows (PowerShell):
     - `python -m venv .venv`
     - `.\.venv\Scripts\Activate.ps1`
   - macOS/Linux:
     - `python -m venv .venv`
     - `source .venv/bin/activate`
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Create your `.env`:
   - `copy .env.example .env` (Windows)
   - `cp .env.example .env` (macOS/Linux)
4. Run the pinger:
   - `python -m keepalive.main`

## One-shot test

Run a single cycle and exit (nonzero if any URL fails after retries):

- `python -m keepalive.main --once`

## Print resolved config

- `python -m keepalive.main --print-config`

## Configuration (env)

Defaults are safe and conservative:

- `TARGET_URLS` (default: `https://www.parlaygorilla.com/,https://api.parlaygorilla.com/health`)
- `POST_LOAD_URLS` (default: `https://api.parlaygorilla.com/health?deep=1`)
  - These URLs run immediately **after** the homepage ping to warm DB connections.
- `INTERVAL_SECONDS` (default: `600`)
- `TIMEOUT_SECONDS` (default: `15`)
- `RETRIES` (default: `2`)
- `BACKOFF_SECONDS` (default: `3`)
- `ALERT_CONSECUTIVE_FAILURES` (default: `3`)
- `ALERT_LATENCY_MS` (default: `4000`)

Telegram (optional):

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## GitHub Actions setup

This repo includes `.github/workflows/keepalive.yml`, scheduled every 10 minutes.

1. Add repo secrets (Settings → Secrets and variables → Actions):
   - Optional: `TARGET_URLS`, `POST_LOAD_URLS`
   - Optional: `INTERVAL_SECONDS`, `TIMEOUT_SECONDS`, `RETRIES`, `BACKOFF_SECONDS`
   - Optional: `ALERT_CONSECUTIVE_FAILURES`, `ALERT_LATENCY_MS`
   - Optional: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
2. Actions will run: `python -m keepalive.main --once`

If a run fails, it surfaces in Actions logs (and Telegram if configured).

## Tests

From the project root:

- `python -m unittest`
