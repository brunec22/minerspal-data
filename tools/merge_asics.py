#!/usr/bin/env python3
"""Merges tools/asic_additions.json (2025-2026 models, source: asicminervalue.com model pages,
collected Nov 2026) into hashrate/api/v2/mining-equipment/asics.json without changing the schema.
Only algorithms the app knows (supported-algos.json) are merged; existing models are left untouched."""
import json, re, uuid
from datetime import datetime

ASICS = "hashrate/api/v2/mining-equipment/asics.json"
ALGOS = "hashrate/api/v2/algo/supported-algos.json"
UNIT = {"h/s": 1, "kh/s": 1e3, "mh/s": 1e6, "gh/s": 1e9, "th/s": 1e12, "ph/s": 1e15, "ksol/s": 1e3, "sol/s": 1}
NS = uuid.UUID("0b7d0c1e-55a4-4f63-8f0e-1c9f2b8a7d31")
CANON = {"kheavyhash": "KHeavyHash", "ethash": "EtHash"}  # spelling already used in asics.json

asics = json.load(open(ASICS))
known_algos = {a["name"].lower() for a in json.load(open(ALGOS))}
have = {((x.get("brand") or "") + " " + x["name"]).lower().replace(".", "") for x in asics}
added = []
for x in json.load(open("tools/asic_additions.json")):
    algo = CANON.get(x["algo"].lower(), x["algo"])
    if algo.lower() not in known_algos or x["unit"].lower() not in UNIT:
        continue
    key = (x["brand"] + " " + x["model"]).lower().replace(".", "")
    if key in have:
        continue
    try:
        hr = float(x["hash"].replace(",", "")) * UNIT[x["unit"].lower()]
        watts = int(float(x["watts"].replace(",", "")))
    except ValueError:
        continue
    price = re.sub(r"[^\d.]", "", x.get("price") or "")
    have.add(key)
    added.append({
        "id": str(uuid.uuid5(NS, key)), "name": x["model"], "brand": x["brand"], "type": "asic",
        "releaseDate": datetime.strptime(x["release"], "%b %Y").strftime("%Y-%m-01T00:00:00Z"),
        "algoPerfList": [{"algoName": algo, "longHashrate": hr, "powerConsumptionWatts": watts}],
        "price": float(price) if price else None, "imageUrl": None})
asics = sorted(added + asics, key=lambda x: x.get("releaseDate") or "", reverse=True)
json.dump(asics, open(ASICS, "w"), indent=1)
print(f"added {len(added)} ASICs, total {len(asics)}")
