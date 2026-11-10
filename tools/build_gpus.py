#!/usr/bin/env python3
"""Builds hashrate/api/v2/mining-equipment/gpus.json (HWHardware schema, type "gpu") from
WhatToMine's public GPU pages, and adds any GPU algorithms missing from
hashrate/api/v2/algo/supported-algos.json (additive only, same schema).

HWHardware: {"id","name","brand","type","releaseDate","algoPerfList":[{"algoName","longHashrate"(H/s),
"powerConsumptionWatts"}],"price","imageUrl"}. Stdlib only.
"""
import html, json, re, sys, time, uuid, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (compatible; MinersPalData/1.0; +https://github.com/brunec22/minerspal-data)"}
OUT = "hashrate/api/v2/mining-equipment/gpus.json"
ALGOS = "hashrate/api/v2/algo/supported-algos.json"
UNIT = {"h/s": 1, "kh/s": 1e3, "mh/s": 1e6, "gh/s": 1e9, "th/s": 1e12, "sol/s": 1, "ksol/s": 1e3, "g/s": 1}
NS = uuid.UUID("6f1c0b52-3a43-4a8e-9d4c-6b1f4d7e2a10")

# Approximate launch month per GPU family (WhatToMine does not publish launch dates).
RELEASES = [
    (r"RTX 5090|RTX 5080", "2025-01"), (r"RTX 5070 Ti|RTX 5070", "2025-03"), (r"RTX 5060 Ti", "2025-04"), (r"RTX 5060", "2025-05"),
    (r"RTX 4090", "2022-10"), (r"RTX 4080 Super|RTX 4070 Ti Super|RTX 4070 Super", "2024-01"), (r"RTX 4080", "2022-11"),
    (r"RTX 4070 Ti", "2023-01"), (r"RTX 4070", "2023-04"), (r"RTX 4060 Ti", "2023-05"), (r"RTX 4060", "2023-06"),
    (r"RTX 3090 Ti", "2022-03"), (r"RTX 3080 12GB", "2022-01"), (r"RTX 3090|RTX 3080 Ti", "2021-06"), (r"RTX 3080|RTX 3090", "2020-09"),
    (r"RTX 3070 Ti", "2021-06"), (r"RTX 3070", "2020-10"), (r"RTX 3060 Ti", "2020-12"), (r"RTX 3060", "2021-02"), (r"RTX 3050", "2022-01"),
    (r"RTX 20\d0 Super", "2019-07"), (r"RTX 20", "2018-09"), (r"GTX 16", "2019-03"), (r"GTX 1080 Ti", "2017-03"), (r"GTX 10", "2016-06"),
    (r"RTX A\d", "2021-04"), (r"CMP", "2021-03"),
    (r"RX 9070", "2025-03"), (r"RX 9060", "2025-06"), (r"RX 7900", "2022-12"), (r"RX 7800|RX 7700", "2023-09"), (r"RX 7600", "2023-05"),
    (r"RX 6950|RX 6750|RX 6650", "2022-05"), (r"RX 6900|RX 6800", "2020-11"), (r"RX 6700", "2021-03"), (r"RX 6600", "2021-08"),
    (r"RX 5[67]00", "2019-07"), (r"Radeon VII", "2019-02"), (r"Vega", "2017-08"), (r"RX 5[78]0", "2017-04"), (r"RX 4[78]0", "2016-06"),
    (r"Arc", "2022-10"), (r"RX 5500", "2019-12"), (r"R9 Fury|R9 380", "2015-06"),
]


def get(url):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return html.unescape(r.read().decode("utf-8", "replace"))
        except Exception:
            if i == 2:
                raise
            time.sleep(3)


def text_parts(s):
    s = re.sub(r"<script.*?</script>|<style.*?</style>", "", s, flags=re.S)
    return [p.strip() for p in re.sub(r"<[^>]+>", "|", s).split("|") if p.strip()]


def release(name):
    for pat, ym in RELEASES:
        if re.search(pat, name, re.I):
            return ym + "-01T00:00:00Z"
    return None


def main():
    algos = json.load(open(ALGOS))
    known = {a["name"].lower(): a["name"] for a in algos}
    known["cuckatoo31"] = "Cuckatoo31+"
    try:
        listing = get("https://whattomine.com/gpus")
    except Exception as e:
        # WhatToMine sometimes blocks CI runners (403); keep the committed gpus.json.
        print(f"GPU listing unavailable ({e}); keeping previous gpus.json", file=sys.stderr)
        return
    links, seen = [], set()
    for href, name in re.findall(r'href="(/gpus/(\d+-[a-z0-9-]+))"[^>]*>([^<]+)<', listing) and \
            [(m[0], m[2]) for m in re.findall(r'href="(/gpus/(\d+-[a-z0-9-]+))"[^>]*>([^<]+)<', listing)]:
        if href not in seen:
            seen.add(href); links.append((href, name.strip()))
    gpus, algo_tickers = [], {}
    for href, name in links:
        slug = href.split("/")[-1]
        brand = "NVIDIA" if "-nvidia-" in slug else "AMD" if "-amd-" in slug else "Intel" if "-intel-" in slug else None
        try:
            parts = text_parts(get("https://whattomine.com" + href))
        except Exception as e:
            print(f"{name}: {e}", file=sys.stderr); continue
        perf = {}
        for i in range(2, len(parts)):
            m = re.match(r"^([\d,.]+) ([A-Za-z/]+) @ ([\d,]+)W$", parts[i])
            if not m or m.group(2).lower() not in UNIT:
                continue
            algo_raw, coin = parts[i - 1], parts[i - 2]
            algo = known.get(algo_raw.lower(), algo_raw)
            t = re.search(r"\(([A-Z0-9]+)\)$", coin)
            if t:
                algo_tickers.setdefault(algo, set()).add(t.group(1))
            if algo in perf:
                continue
            hr = float(m.group(1).replace(",", "")) * UNIT[m.group(2).lower()]
            perf[algo] = {"algoName": algo, "longHashrate": hr, "powerConsumptionWatts": int(m.group(3).replace(",", ""))}
        if not perf:
            continue
        gpus.append({"id": str(uuid.uuid5(NS, slug)), "name": re.sub(r"^(GeForce|Radeon) ", "", name) if brand else name,
                     "brand": brand, "type": "gpu", "releaseDate": release(name),
                     "algoPerfList": list(perf.values()), "price": None, "imageUrl": None})
        time.sleep(0.7)
    if len(gpus) < 20:
        print(f"Only {len(gpus)} GPUs parsed, keeping previous gpus.json", file=sys.stderr)
        return
    json.dump(gpus, open(OUT, "w"), indent=1)
    added = 0
    for algo, tickers in sorted(algo_tickers.items()):
        entry = next((a for a in algos if a["name"].lower() == algo.lower()), None)
        if entry is None:
            algos.append({"name": algo, "cryptoTickers": sorted(tickers)}); added += 1
        else:
            for t in sorted(tickers):
                if t not in entry["cryptoTickers"]:
                    entry["cryptoTickers"].append(t)
    json.dump(algos, open(ALGOS, "w"), indent=1)
    print(f"{len(gpus)} GPUs, {added} new algos", file=sys.stderr)


if __name__ == "__main__":
    main()
