#!/usr/bin/env python3
"""Regenerates reward-estimation data from WhatToMine.

Outputs (in hashrate/api/v2/reward-estimation/):
  reward-estimations.json  {TICKER: {"hashes": H/s, "reward24h": coins/day, "updatedAt": "yyyy-MM-dd'T'HH:mm:ssZ"}}
                           (exact schema the app's GitHubRewardEstimationFetcher decodes)
  whattomine-units.json    {"updatedAt": ..., "coins": {TICKER: {"id", "algorithm", "unit", "unitLabel"}}}
                           Used by the app's live WhatToMine batch fetcher: WhatToMine's ?hr= parameter is
                           expressed in each coin's display unit, which its JSON API does not expose.
Units are read from each coin page ("... for 212.00 kh/s @ 1,350W") and cached; pages are only
re-read for new coins or once a week. Stdlib only.
"""
import html, json, os, re, sys, time, urllib.request
import concurrent.futures as cf
from datetime import datetime, timezone

OUT = "hashrate/api/v2/reward-estimation"
UA = {"User-Agent": "Mozilla/5.0 (compatible; MinersPalData/1.0; +https://github.com/brunec22/minerspal-data)"}
UNIT = {"h/s": 1, "kh/s": 1e3, "mh/s": 1e6, "gh/s": 1e9, "th/s": 1e12, "ph/s": 1e15, "eh/s": 1e18,
        "sol/s": 1, "ksol/s": 1e3, "msol/s": 1e6, "g/s": 1, "gps": 1}
# When WhatToMine lists one ticker under several algorithms, the one MinersPal users mine most.
PREFERRED_ALGO = {"DGB": "SHA-256", "XTM": "SHA3x", "QUAI": "KawPow", "MEWC": "MeowPow", "EPIC": "ProgPow"}
QUERY_HR = 1_000_000  # big multiplier so WhatToMine's 6-decimal rounding never zeroes small rewards


def get(url, as_json=True, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                data = r.read()
            return json.loads(data) if as_json else data.decode("utf-8", "replace")
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(2 + i * 3)


def page_unit(coin_id):
    s = html.unescape(get(f"https://whattomine.com/coins/{coin_id}", as_json=False))
    m = re.search(r"for [\d,.]+ ([A-Za-z/]+) @", s)
    if not m or m.group(1).lower() not in UNIT:
        return None
    return m.group(1)


def num(s):
    try:
        return float(str(s).replace(",", "").replace("$", ""))
    except Exception:
        return None


def main():
    now = datetime.now(timezone.utc)
    stamp_units = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    stamp = now.strftime("%Y-%m-%dT%H:%M:%S+0000")
    units_path = os.path.join(OUT, "whattomine-units.json")
    try:
        cache = json.load(open(units_path))
    except Exception:
        cache = {"coins": {}}
    by_id = {str(v["id"]): v for v in cache.get("coins", {}).values()}
    refresh_all = now.weekday() == 0 and now.hour < 2 or os.environ.get("REFRESH_UNITS") == "1"

    coins = get("https://whattomine.com/calculators.json")["coins"]
    active = [c for c in coins.values() if c.get("listed") and c.get("status") == "Active" and not c.get("lagging") and c.get("tag")]
    chosen = {}
    for c in active:
        t = c["tag"].upper()
        pref = PREFERRED_ALGO.get(t)
        if t not in chosen or (pref and c.get("algorithm") == pref):
            chosen[t] = c

    def unit_for(c):
        cached = by_id.get(str(c["id"]))
        if cached and not refresh_all:
            return cached["unitLabel"]
        try:
            return page_unit(c["id"])
        except Exception as e:
            print(f"unit {c['tag']}: {e}", file=sys.stderr)
            return cached["unitLabel"] if cached else None

    with cf.ThreadPoolExecutor(4) as ex:
        labels = dict(zip(chosen, ex.map(unit_for, chosen.values())))

    def est_for(t):
        c, label = chosen[t], labels.get(t)
        if not label:
            return t, None
        try:
            r = get(f"https://whattomine.com/coins/{c['id']}.json?hr={QUERY_HR}&p=0&fee=0&cost=0&hcost=0&span_br=&span_d=24")
        except Exception as e:
            print(f"coin {t}: {e}", file=sys.stderr)
            return t, None
        est = num(r.get("estimated_rewards"))
        if est is None or est <= 0:
            return t, None
        return t, {"hashes": int(QUERY_HR * UNIT[label.lower()]), "reward24h": round(est, 10), "updatedAt": stamp}

    with cf.ThreadPoolExecutor(4) as ex:
        results = dict(ex.map(est_for, list(chosen)))
    rewards = {t: v for t, v in sorted(results.items()) if v}
    if len(rewards) < 20:
        sys.exit(f"Only {len(rewards)} estimations, keeping previous files")

    units = {"updatedAt": stamp_units, "coins": {
        t: {"id": chosen[t]["id"], "algorithm": chosen[t].get("algorithm"),
            "unit": UNIT[labels[t].lower()], "unitLabel": labels[t]}
        for t in sorted(chosen) if labels.get(t)}}
    os.makedirs(OUT, exist_ok=True)
    json.dump(rewards, open(os.path.join(OUT, "reward-estimations.json"), "w"), indent=1)
    json.dump(units, open(units_path, "w"), indent=1)
    print(f"{len(rewards)} reward estimations, {len(units['coins'])} units", file=sys.stderr)


if __name__ == "__main__":
    main()
