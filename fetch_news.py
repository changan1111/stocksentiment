#!/usr/bin/env python3
"""
fetch_news.py — Multi-source Indian stock news fetcher
Sources: Economic Times, Business Standard, Moneycontrol, LiveMint, NSE Announcements
No API key needed. Runs in GitHub Actions (full internet access).
"""

import json, re, os, time, feedparser, requests
from datetime import datetime, timezone
from dateutil import parser as dateparser

# ── Sentiment ────────────────────────────────────────────────────────────────
POS = set(['surge','rally','gain','beat','profit','growth','record','strong','bullish',
    'upgrade','buy','outperform','revenue','boost','soar','rise','positive','exceed',
    'optimistic','improve','recover','breakout','high','launch','win','success',
    'milestone','jump','advance','expand','increase','profitable','dividend',
    'acquisition','approval','breakthrough','orders','deal','partnership','raised',
    'targets','confident','delivers','rises','quarterly','multibagger','ipo',
    'listing','recommended','inflow','demand','exports','award','returns','yield',
    'bonus','buyback','split','momentum','robust','steady','rebound','recovery',
    'turnaround','merger','capex','investment','contract','wins','secures','bags',
    'signs','expands','launches','new','fresh','strong','healthy'])

NEG = set(['fall','drop','crash','loss','miss','weak','bearish','downgrade','sell',
    'underperform','decline','plunge','slump','risk','warn','concern','cut',
    'reduce','negative','disappoint','fail','debt','layoff','resign','fine',
    'penalty','fraud','lawsuit','recall','delay','halt','suspend','investigation',
    'probe','violation','plummet','tank','selloff','correction','slowdown',
    'defaults','fire','exits','sebi','npa','stressed','impairment','losses',
    'liability','writeoff','shortage','inflation','tariff','sanction','ban',
    'delist','outflow','weakness','pressure','contraction','headwind',
    'uncertainty','volatile','drops','falls','slides','tumbles','slips'])

def score_sentiment(text):
    words = re.findall(r'[a-z]+', text.lower())
    pos = sum(1 for w in words if w in POS)
    neg = sum(1 for w in words if w in NEG)
    total = pos + neg
    if not total:
        return {"label": "Neutral", "score": 0}
    s = round((pos - neg) / total, 3)
    return {"label": "Positive" if s > 0.1 else "Negative" if s < -0.1 else "Neutral", "score": s}

def clean_html(text):
    return re.sub(r'<[^>]+>', '', text or '').strip()

def source_from_link(link):
    m = re.search(r'https?://(?:www\.)?([^/]+)', link or '')
    if m:
        h = m.group(1)
        h = re.sub(r'\.(com|in|co\.in|net|org|io)$', '', h)
        return h[:25]
    return ''

def parse_date(s):
    try:
        d = dateparser.parse(s or '')
        if d and d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except:
        return None

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}

# ── News RSS Sources ─────────────────────────────────────────────────────────
RSS_SOURCES = [
    # Economic Times - Markets
    "https://economictimes.indiatimes.com/markets/stocks/news/rssfeeds/2146843.cms",
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://economictimes.indiatimes.com/industry/rssfeeds/13352306.cms",
    # Business Standard
    "https://www.business-standard.com/rss/markets-106.rss",
    "https://www.business-standard.com/rss/companies-101.rss",
    # Moneycontrol
    "https://www.moneycontrol.com/rss/marketsindia.xml",
    "https://www.moneycontrol.com/rss/business.xml",
    # LiveMint
    "https://www.livemint.com/rss/markets",
    "https://www.livemint.com/rss/companies",
    # Financial Express
    "https://www.financialexpress.com/market/feed/",
]

def fetch_all_rss():
    """Fetch all RSS sources and return combined article pool"""
    all_items = []
    for url in RSS_SOURCES:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=12)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            for entry in feed.entries:
                title   = clean_html(entry.get('title', ''))
                summary = clean_html(entry.get('summary', '') or entry.get('description', ''))
                link    = entry.get('link', '')
                pub_str = entry.get('published', '') or entry.get('updated', '')
                pub_dt  = parse_date(pub_str)
                if title:
                    all_items.append({
                        'title':   title,
                        'summary': summary[:250] + ('…' if len(summary) > 250 else ''),
                        'link':    link,
                        'source':  source_from_link(link),
                        'pubDate': pub_dt.isoformat() if pub_dt else None,
                        'pub_dt':  pub_dt,
                    })
            time.sleep(0.3)  # polite delay
        except Exception as e:
            print(f"    RSS error ({url[:50]}...): {e}")
    print(f"  Total pool: {len(all_items)} articles from {len(RSS_SOURCES)} sources")
    return all_items

def fetch_nse_announcements(symbol_clean):
    """Fetch official NSE corporate announcements (free, no auth)"""
    url = f"https://www.nseindia.com/api/corporate-announcements?index=equities&symbol={symbol_clean}"
    try:
        s = requests.Session()
        # NSE needs a session cookie first
        s.get("https://www.nseindia.com", headers=HEADERS, timeout=10)
        time.sleep(0.5)
        resp = s.get(url, headers=HEADERS, timeout=10)
        data = resp.json()
        items = []
        for ann in (data if isinstance(data, list) else [])[:5]:
            subject = ann.get('subject', '') or ann.get('desc', '')
            dt_str  = ann.get('bcast_date', '') or ann.get('an_dt', '')
            pub_dt  = parse_date(dt_str)
            if subject:
                items.append({
                    'title':   f"[NSE] {subject}",
                    'summary': ann.get('attchmntText', '')[:200],
                    'link':    f"https://www.nseindia.com/companies-listing/corporate-filings-announcements",
                    'source':  'nseindia',
                    'pubDate': pub_dt.isoformat() if pub_dt else None,
                    'pub_dt':  pub_dt,
                })
        return items
    except:
        return []

def match_articles(pool, search_terms):
    """Filter pool articles that mention any of the search terms"""
    matched = []
    seen = set()
    for item in pool:
        text = (item['title'] + ' ' + item['summary']).lower()
        for term in search_terms:
            if term.lower() in text:
                key = item['title'][:60]
                if key not in seen:
                    seen.add(key)
                    matched.append(item)
                break
    return matched

def main():
    with open('tickers.json') as f:
        config = json.load(f)
    tickers = config.get('tickers', [])
    print(f"📰 Fetching Indian stock news for {len(tickers)} stocks\n")

    # Step 1: Fetch all RSS sources once (efficient - one pool for all stocks)
    print("Fetching RSS feeds...")
    pool = fetch_all_rss()
    print()

    results = []
    for t in tickers:
        symbol   = t['symbol']
        name     = t.get('name', symbol)
        exch     = t.get('exchange', 'NSE')
        # search_terms: company name + any aliases
        terms    = t.get('search_terms', [name])
        if isinstance(terms, str):
            terms = [terms]
        # Always add the base name
        if name not in terms:
            terms.insert(0, name)

        # Clean symbol for NSE API (remove .NS/.BO)
        sym_clean = symbol.replace('.NS', '').replace('.BO', '')

        print(f"  [{sym_clean}] {name}")

        # Match from RSS pool
        matched = match_articles(pool, terms)

        # Also fetch NSE announcements
        nse_items = fetch_nse_announcements(sym_clean)
        if nse_items:
            print(f"    + {len(nse_items)} NSE announcements")

        all_items = matched + nse_items

        # Remove duplicates, sort by date
        seen = set()
        unique = []
        for item in all_items:
            k = item['title'][:50]
            if k not in seen:
                seen.add(k)
                unique.append(item)

        unique.sort(key=lambda x: x.get('pub_dt') or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

        # Score sentiment and clean up
        articles = []
        for item in unique[:20]:
            sent = score_sentiment(item['title'] + ' ' + item['summary'])
            articles.append({
                'title':     item['title'],
                'summary':   item['summary'],
                'link':      item['link'],
                'source':    item['source'],
                'pubDate':   item['pubDate'],
                'sentiment': sent,
            })

        print(f"    → {len(articles)} articles")
        results.append({
            "symbol":   symbol,
            "name":     name,
            "exchange": exch,
            "articles": articles,
        })

    all_articles = [a for r in results for a in r['articles']]
    pos = sum(1 for a in all_articles if a['sentiment']['label'] == 'Positive')
    neg = sum(1 for a in all_articles if a['sentiment']['label'] == 'Negative')
    neu = sum(1 for a in all_articles if a['sentiment']['label'] == 'Neutral')

    out = {
        "fetchedAt":    datetime.now(timezone.utc).isoformat(),
        "tickerCount":  len(tickers),
        "articleCount": len(all_articles),
        "overview":     {"positive": pos, "negative": neg, "neutral": neu},
        "stocks":       results,
    }

    os.makedirs('docs', exist_ok=True)
    with open('docs/data.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"\n✅ docs/data.json written — {len(all_articles)} articles | +{pos} ={neu} -{neg}")

if __name__ == '__main__':
    main()
