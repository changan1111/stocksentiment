# Stock News Sentinel — NSE/BSE

Zero-cost stock news feed with sentiment analysis for Indian markets. Deploys on GitHub Pages. No API tokens, no CORS proxies.

## How it works

```
GitHub Actions (runs 3× daily)
  └─ fetch_news.py
       └─ Yahoo Finance RSS (RELIANCE.NS, TCS.NS ...)
            └─ docs/data.json  ←  index.html reads this (same origin, no CORS)
```

## Setup (one-time, ~5 minutes)

### 1. Create repo & enable GitHub Pages

```bash
git init
git add .
git commit -m "init"
git remote add origin https://github.com/YOUR_USERNAME/stock-news-sentinel.git
git push -u origin main
```

In GitHub → Settings → Pages → **Source: Deploy from branch** → Branch: `main`, Folder: `/docs`

### 2. Edit your stocks

Open `tickers.json` and add/remove stocks:

```json
{
  "tickers": [
    { "symbol": "RELIANCE.NS", "name": "Reliance Industries", "exchange": "NSE" },
    { "symbol": "TCS.NS",      "name": "TCS",                 "exchange": "NSE" },
    { "symbol": "SBIN.BO",     "name": "SBI",                 "exchange": "BSE" }
  ]
}
```

**Ticker format:** `SYMBOL.NS` for NSE, `SYMBOL.BO` for BSE

### 3. Run the workflow once manually

GitHub → **Actions** tab → **Fetch Stock News** → **Run workflow**

This creates `docs/data.json`. After it commits, refresh your GitHub Pages URL — news appears instantly.

## Schedule

Runs automatically on weekdays:
- 8:30 AM IST
- 2:30 PM IST  
- 6:30 PM IST

You can also trigger manually anytime from the Actions tab.

## Adding more stocks

Just edit `tickers.json` → push → workflow runs automatically.

## Local testing

```bash
pip install requests feedparser python-dateutil
python fetch_news.py
# Then open docs/index.html via a local server:
cd docs && python -m http.server 8000
```

## Notes

- Yahoo Finance RSS covers ~7 days of history. Longer ranges (1m, 3m...) will show all articles fetched across multiple runs as `data.json` accumulates.
- Sentiment is rule-based keyword scoring — fast, free, no tokens.
- All data is public and stored in your own repo.
