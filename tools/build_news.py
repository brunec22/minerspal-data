#!/usr/bin/env python3
"""Builds minersPal/api/news/news.json (+ dev-news.json) from public crypto RSS feeds.

Schema (decoded by MinersPal NewsManager / GitHubNews):
{"results":[{"slug","title","description","published_at","created_at","url","source"}],
 "updatedAt":"YYYY-MM-DDTHH:MM:SSZ"}
Dates are UTC "yyyy-MM-dd'T'HH:mm:ss'Z'". URLs are plain https links.

news.json     = production feed (last 72 h, max 60 items, mining stories boosted)
dev-news.json = staging feed used by simulator/dev builds (all sources, last 7 days,
                max 150 items, plus a test item) so feed changes can be checked
                before they reach users.
Stdlib only, so it runs on a bare GitHub Actions runner.
"""
import email.utils, hashlib, html, json, os, re, sys, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph", "https://cointelegraph.com/rss"),
    ("Decrypt", "https://decrypt.co/feed"),
    ("The Block", "https://www.theblock.co/rss.xml"),
    ("Bitcoin Magazine", "https://bitcoinmagazine.com/.rss/full/"),
    ("CryptoSlate", "https://cryptoslate.com/feed/"),
    ("CryptoPotato", "https://cryptopotato.com/feed/"),
    ("NewsBTC", "https://www.newsbtc.com/feed/"),
    ("Bitcoinist", "https://bitcoinist.com/feed/"),
    ("U.Today", "https://u.today/rss"),
    ("Hashrate Index", "https://hashrateindex.com/blog/rss/"),
]
DEV_ONLY_FEEDS = []  # add experimental feeds here to try them in dev-news.json first

MINING_WORDS = re.compile(r"\b(min(e|er|ers|ing)|hashrate|hash rate|asic|antminer|whatsminer|difficulty|halving|pool|gpu|proof[- ]of[- ]work|pow)\b", re.I)
UA = "Mozilla/5.0 (compatible; MinersPalNews/1.0; +https://github.com/brunec22/minerspal-data)"
NS = {"atom": "http://www.w3.org/2005/Atom", "content": "http://purl.org/rss/1.0/modules/content/",
      "dc": "http://purl.org/dc/elements/1.1/", "media": "http://search.yahoo.com/mrss/"}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def clean_text(s, limit=None):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s*(The post .* appeared first on .*|Read more.*|Continue reading.*)$", "", s)
    if limit and len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
    return s


def clean_url(u):
    u = (u or "").strip()
    m = re.match(r"^\[(https?://[^\]]+)\]\((https?://[^)]+)\)$", u)  # markdown link -> plain
    if m:
        u = m.group(2)
    u = re.sub(r"[?&]utm_[^=&]+=[^&]*", "", u).rstrip("?&")
    return u if u.startswith("https://") or u.startswith("http://") else None


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        d = email.utils.parsedate_to_datetime(s)
    except Exception:
        d = None
    if d is None:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def items_from(source, raw):
    root = ET.fromstring(raw)
    out = []
    for it in root.iter("item"):
        title = clean_text(it.findtext("title"))
        link = clean_url(it.findtext("link"))
        desc = it.findtext("description") or it.findtext("content:encoded", namespaces=NS) or ""
        date = parse_date(it.findtext("pubDate") or it.findtext("dc:date", namespaces=NS))
        if title and link and date:
            out.append(dict(title=title, url=link, description=clean_text(desc, 260), date=date, source=source))
    for it in root.iter("{http://www.w3.org/2005/Atom}entry"):
        title = clean_text(it.findtext("atom:title", namespaces=NS))
        l = it.find("atom:link", NS)
        link = clean_url(l.get("href") if l is not None else None)
        date = parse_date(it.findtext("atom:published", namespaces=NS) or it.findtext("atom:updated", namespaces=NS))
        desc = it.findtext("atom:summary", namespaces=NS) or ""
        if title and link and date:
            out.append(dict(title=title, url=link, description=clean_text(desc, 260), date=date, source=source))
    return out


def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:80] or hashlib.sha1(s.encode()).hexdigest()[:12]


def to_json_items(items):
    res, seen = [], set()
    for x in items:
        key = re.sub(r"[^a-z0-9]", "", x["title"].lower())[:70]
        if key in seen or x["url"] in seen:
            continue
        seen.add(key); seen.add(x["url"])
        ts = x["date"].strftime("%Y-%m-%dT%H:%M:%SZ")
        res.append({"slug": slugify(x["title"]), "title": x["title"], "description": x["description"],
                    "published_at": ts, "created_at": ts, "url": x["url"], "source": x["source"]})
    return res


def main(out_dir):
    now = datetime.now(timezone.utc)
    collected, dev_collected, ok = [], [], 0
    for source, url in FEEDS + DEV_ONLY_FEEDS:
        try:
            its = items_from(source, fetch(url))
            ok += 1
            print(f"{source}: {len(its)} items", file=sys.stderr)
        except Exception as e:
            print(f"{source}: FAILED {e}", file=sys.stderr)
            continue
        its = [i for i in its if i["date"] <= now + timedelta(minutes=10)]
        dev_collected += its
        if (source, url) in FEEDS:
            collected += its
    if ok < 3:
        sys.exit("Fewer than 3 feeds reachable, keeping the previous news.json")

    def rank(x):  # newest first; mining stories get a 6 h boost
        return x["date"] + (timedelta(hours=6) if MINING_WORDS.search(x["title"] + " " + x["description"]) else timedelta())

    prod = sorted([x for x in collected if now - x["date"] <= timedelta(hours=72)], key=rank, reverse=True)[:60]
    prod = sorted(prod, key=lambda x: x["date"], reverse=True)
    dev = sorted([x for x in dev_collected if now - x["date"] <= timedelta(days=7)], key=lambda x: x["date"], reverse=True)[:150]
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    news = {"results": to_json_items(prod), "updatedAt": stamp}
    dev_items = to_json_items(dev)
    dev_items.insert(0, {"slug": "minerspal-dev-feed", "title": "[DEV] MinersPal staging news feed",
                         "description": f"Staging feed generated {stamp}. Production users read news.json.",
                         "published_at": stamp, "created_at": stamp,
                         "url": "https://github.com/brunec22/minerspal-data", "source": "MinersPal"})
    devnews = {"results": dev_items, "updatedAt": stamp}
    if len(news["results"]) < 5:
        sys.exit("Too few news items, keeping the previous news.json")
    os.makedirs(out_dir, exist_ok=True)
    json.dump(news, open(os.path.join(out_dir, "news.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(devnews, open(os.path.join(out_dir, "dev-news.json"), "w"), ensure_ascii=False, indent=1)
    print(f"news.json: {len(news['results'])} items, dev-news.json: {len(dev_items)} items", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "minersPal/api/news")
