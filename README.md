## Arbitrage Bot

Cross-platform prediction market arbitrage bot between **Polymarket** and **Manifold**, with a real-time **Streamlit** dashboard and **Telegram** alerts.

### Features

- **Cross-platform scanner**: Fetches upcoming binary markets from Polymarket and Manifold.
- **Event matching**: Matches markets by title similarity and resolution date.
- **Arbitrage detection**: Finds buy-YES / buy-NO combinations across platforms with positive expected profit after fees.
- **Telegram alerts**: Sends formatted messages with links to both platforms when opportunities are found.
- **Live dashboard**: Streamlit dashboard showing current opportunities, history, and stats based on `dashboard_stats.json`.

### Project Structure

- `paper_trader.py` – main async scanner loop; runs continuously and writes stats.
- `platforms/` – platform clients:
  - `base.py` – `PlatformClient` abstract base class.
  - `polymarket.py` – Polymarket implementation.
  - `manifold.py` – Manifold Markets implementation.
- `matcher.py` – event matching logic (title similarity, date tolerance).
- `arbitrage.py` – arbitrage opportunity calculation.
- `stats_writer.py` – writes/reads `dashboard_stats.json` for the dashboard.
- `dashboard.py` – Streamlit UI for viewing scans and stats.

### Requirements

Python 3.10+ is recommended.

Install dependencies:

```bash
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root (already present in your local setup but **never commit it**) with:

```bash
POLYMARKET_PRIVATE_KEY=...
CLOB_API_KEY=...
CLOB_SECRET=...
CLOB_PASSPHRASE=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
MANIFOLD_API_KEY=...   # optional, only needed for authenticated Manifold calls
```

Also make sure `.env`, `venv/`, and `dashboard_stats.json` are in `.gitignore`.

### Running the Scanner

From the project root:

```bash
python paper_trader.py
```

This will:

- Continuously fetch events from Polymarket and Manifold.
- Match events using:
  - `TITLE_SIMILARITY_THRESHOLD = 0.5`
  - `DATE_MATCH_TOLERANCE_DAYS = 3`
- Detect arbitrage opportunities with:
  - `MIN_PROFIT_AFTER_FEES_PCT = 0.5`
- Send Telegram alerts (respecting `ALERT_COOLDOWN_SECONDS`).
- Update `dashboard_stats.json` after each scan.

You can tweak these parameters directly in `paper_trader.py`.

### Running the Dashboard

In another terminal, from the project root:

```bash
streamlit run dashboard.py
```

The dashboard will:

- Read `dashboard_stats.json` written by the scanner.
- Show total scans, events, matched pairs, and opportunities.
- Display current opportunities with prices and profit.
- Plot scan history trends and show sample events and matched pairs.

Use the **sidebar**:

- Toggle **Auto-refresh** and set the refresh interval.
- Use **Refresh Now** for a manual reload without waiting.

### Notes

- This repo is intended for **paper trading / research**; do your own due diligence before trading real money.
- APIs and fee structures for Polymarket/Manifold may change; if things break, check their latest docs and update the platform clients accordingly.

# arb-bot
