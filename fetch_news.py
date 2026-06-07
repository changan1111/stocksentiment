#!/usr/bin/env python3
"""
fetch_news.py  —  reads tickers.json, fetches Yahoo Finance RSS,
scores sentiment, writes docs/data.json
No API keys needed. Runs in GitHub Actions (no CORS issue server-side).
"""

import json, re, math, feedparser, requests
from datetime import datetime, timezone
from dateutil import parser as dateparser

# ── Sentiment word lists ────────────────────────────────────────────────────
POS = set([
    'surge','rally','gain','beat','profit','growth','record','strong','bullish',
    'upgrade','buy','outperform','revenue','boost','soar','rise','positive','exceed',
    'optimistic','improve','recover','breakout','high','launch','win','success',
    'milestone','jump','advance','expand','increase','profitable','dividend',
    'acquisition','approval','breakthrough','orders','deal','partnership','raised',
    'targets','confident','delivers','rises','quarterly','multibagger','ipo',
    'listing','nifty','sensex','recommended','inflow','demand','exports','award',
    'returns','yield','bonus','buyback','split','momentum','robust','steady',
    'rebound','recovery','turnaround','merger','synergy','capex','investment',
])
NEG = set([
    'fall','drop','crash','loss','miss','weak','bearish','downgrade','sell',
    'underperform','decline','plunge','slump','risk','warn','concern','cut',
    'reduce','negative','disappoint','fail','debt','layoff','resign','fine',
    'penalty','fraud','lawsuit','recall','delay','halt','suspend','investigation',
    'probe','violation','plummet','tank','selloff','correction','slowdown',
    'defaults','fire','exits','sebi','npa','stressed','impairment','hit',
    'losses','liability','write','writeoff','shortage','inflation','tariff',
    'sanction','ban','delist','bleed','outflow','dumping','weakness','pressure',
    'margin','contraction','headwind','uncertainty','volatile','overvalued',
])

def score_sentiment(text: str) -> dict:
    words = re.findall(r'[a-z]+', text.lower())
    pos = sum(1 for w in words if w in POS)
    neg = sum(1 for w in words if w in NEG)
    total = pos + neg
    if total == 0:
        return {"label": "Neutral", "score": 0, "pos": 0, "neg": 0}
    score = round((pos - neg) / total, 3)
    label = "Positive" if score > 0.1 else "Negative" if score < -0.1 else "Neutral"
    return {"label": label, "score": score, "pos": pos, "neg": neg}

def source_from_link(link: str) -> str:
    m = re.search(r'https?://(?:www\.)?([^/]+)', link or '')
    if m:
        host = m.group(1)
        # strip common suffixes for display
        host = re.sub(r'\.(com|in|co\.in|net|org|io)$', '', host)
        return host[:30]
    return ''

def fetch_ticker(symbol: str, max_articles: int = 20) -> list:
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=IN&lang=en-IN"
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; StockNewsFetcher/1.0)"}
        resp = requests.get(url, headers=headers, timeout=12)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception as e:
        print(f"  ✗ {symbol}: {e}")
        return []

    articles = []
    for entry in feed.entries[:max_articles]:
        title   = entry.get('title', '').strip()
        summary = re.sub(r'<[^>]+>', '', entry.get('summary', '')).strip()
        link    = entry.get('link', '')
        pub_str = entry.get('published', '')

        try:
            pub_dt = dateparser.parse(pub_str)
            if pub_dt and pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            pub_iso = pub_dt.isoformat() if pub_dt else None
        except Exception:
            pub_iso = None

        sent = score_sentiment(title + ' ' + summary)

        articles.append({
            "title":   title,
            "summary": summary[:250] + ('…' if len(summary) > 250 else ''),
            "link":    link,
            "source":  source_from_link(link),
            "pubDate": pub_iso,
            "sentiment": sent,
        })

    print(f"  ✓ {symbol}: {len(articles)} articles")
    return articles

def main():
    # Load tickers config
    with open('tickers.json', 'r') as f:
        config = json.load(f)

    tickers = config.get('tickers', [])
    print(f"Fetching news for: {[t['symbol'] for t in tickers]}")

    results = []
    for t in tickers:
        symbol = t['symbol']   # e.g. "RELIANCE.NS"
        name   = t.get('name', symbol)
        exch   = t.get('exchange', 'NSE')
        articles = fetch_ticker(symbol)

        results.append({
            "symbol":   symbol,
            "name":     name,
            "exchange": exch,
            "articles": articles,
        })

    # Compute overall stats
    all_articles = [a for r in results for a in r['articles']]
    pos = sum(1 for a in all_articles if a['sentiment']['label'] == 'Positive')
    neg = sum(1 for a in all_articles if a['sentiment']['label'] == 'Negative')
    neu = sum(1 for a in all_articles if a['sentiment']['label'] == 'Neutral')

    output = {
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "tickerCount": len(tickers),
        "articleCount": len(all_articles),
        "overview": {"positive": pos, "negative": neg, "neutral": neu},
        "stocks": results,
    }

    with open('docs/data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Wrote docs/data.json — {len(all_articles)} total articles across {len(tickers)} stocks")

if __name__ == '__main__':
    main()
