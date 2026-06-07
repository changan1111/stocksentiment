import json, re, feedparser, requests
from datetime import datetime, timezone
from dateutil import parser as dateparser

POS = set(['surge','rally','gain','beat','profit','growth','record','strong','bullish',
    'upgrade','buy','outperform','revenue','boost','soar','rise','positive','exceed',
    'optimistic','improve','recover','breakout','high','launch','win','success',
    'milestone','jump','advance','expand','increase','profitable','dividend',
    'acquisition','approval','breakthrough','orders','deal','partnership','raised',
    'targets','confident','delivers','rises','quarterly','multibagger','ipo',
    'listing','nifty','sensex','recommended','inflow','demand','exports','award',
    'returns','yield','bonus','buyback','split','momentum','robust','steady',
    'rebound','recovery','turnaround','merger','capex','investment'])

NEG = set(['fall','drop','crash','loss','miss','weak','bearish','downgrade','sell',
    'underperform','decline','plunge','slump','risk','warn','concern','cut',
    'reduce','negative','disappoint','fail','debt','layoff','resign','fine',
    'penalty','fraud','lawsuit','recall','delay','halt','suspend','investigation',
    'probe','violation','plummet','tank','selloff','correction','slowdown',
    'defaults','fire','exits','sebi','npa','stressed','impairment','hit',
    'losses','liability','writeoff','shortage','inflation','tariff','sanction',
    'ban','delist','outflow','weakness','pressure','contraction','headwind',
    'uncertainty','volatile'])

def score(text):
    words = re.findall(r'[a-z]+', text.lower())
    pos = sum(1 for w in words if w in POS)
    neg = sum(1 for w in words if w in NEG)
    total = pos + neg
    if not total:
        return {"label": "Neutral", "score": 0}
    s = round((pos - neg) / total, 3)
    return {"label": "Positive" if s > 0.1 else "Negative" if s < -0.1 else "Neutral", "score": s}

def source_from_link(link):
    m = re.search(r'https?://(?:www\.)?([^/]+)', link or '')
    if m:
        return re.sub(r'\.(com|in|co\.in|net|org)$', '', m.group(1))[:30]
    return ''

def fetch(symbol):
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=IN&lang=en-IN"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        r.raise_for_status()
        feed = feedparser.parse(r.content)
    except Exception as e:
        print(f"  ✗ {symbol}: {e}")
        return []
    articles = []
    for e in feed.entries[:20]:
        title   = e.get('title','').strip()
        summary = re.sub(r'<[^>]+>','', e.get('summary','')).strip()
        link    = e.get('link','')
        pub_str = e.get('published','')
        try:
            pub_dt = dateparser.parse(pub_str)
            if pub_dt and pub_dt.tzinfo is None:
                from datetime import timezone
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            pub_iso = pub_dt.isoformat() if pub_dt else None
        except:
            pub_iso = None
        articles.append({
            "title":     title,
            "summary":   summary[:250] + ('…' if len(summary)>250 else ''),
            "link":      link,
            "source":    source_from_link(link),
            "pubDate":   pub_iso,
            "sentiment": score(title + ' ' + summary),
        })
    print(f"  ✓ {symbol}: {len(articles)} articles")
    return articles

def main():
    with open('tickers.json') as f:
        config = json.load(f)
    tickers = config.get('tickers', [])
    print(f"Fetching: {[t['symbol'] for t in tickers]}")
    results = []
    for t in tickers:
        results.append({
            "symbol":   t['symbol'],
            "name":     t.get('name', t['symbol']),
            "exchange": t.get('exchange','NSE'),
            "articles": fetch(t['symbol']),
        })
    all_articles = [a for r in results for a in r['articles']]
    pos = sum(1 for a in all_articles if a['sentiment']['label']=='Positive')
    neg = sum(1 for a in all_articles if a['sentiment']['label']=='Negative')
    neu = sum(1 for a in all_articles if a['sentiment']['label']=='Neutral')
    out = {
        "fetchedAt":    datetime.now(timezone.utc).isoformat(),
        "tickerCount":  len(tickers),
        "articleCount": len(all_articles),
        "overview":     {"positive": pos, "negative": neg, "neutral": neu},
        "stocks":       results,
    }
    import os
    os.makedirs('docs', exist_ok=True)
    with open('docs/data.json','w',encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✅ Wrote docs/data.json — {len(all_articles)} articles")

if __name__ == '__main__':
    main()
