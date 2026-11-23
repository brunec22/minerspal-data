#!/usr/bin/env python3
"""Orders hashrate/api/v2/crypto/supported-cryptos.json so the app's first match per ticker
is the real (mined) coin: market-cap rank ascending, unranked last, plus a few mined coins
pinned ahead of higher-ranked tokens sharing their ticker.

Before this, LTC resolved to "Binance-Peg Litecoin", KAS to "Wrapped Kaspa", DOGE to
"SPACE DOGE"... which gave wrong prices/profits and 404s on crypto.com (slow fallbacks).
Run after editing the list:  python3 tools/sort_supported_cryptos.py
"""
import json
import pathlib

FILE = pathlib.Path(__file__).resolve().parent.parent / "hashrate/api/v2/crypto/supported-cryptos.json"
PINNED = {  # ticker -> slug of the mined coin
    "beam": "beam", "clam": "clams", "exp": "expanse", "game": "gamecredits",
    "iron": "iron-fish", "spr": "spreadcoin", "uno": "unobtanium", "via": "viacoin",
}

def main():
    cryptos = json.loads(FILE.read_text())
    cryptos.sort(key=lambda c: (c.get("rank") is None, c.get("rank") or 0))
    def pinned(c):
        return PINNED.get(c["ticker"].lower()) == (c.get("slugs") or [None])[0]
    ordered = [c for c in cryptos if pinned(c)] + [c for c in cryptos if not pinned(c)]
    FILE.write_text(json.dumps(ordered, separators=(",", ":"), ensure_ascii=False))
    print(f"{len(ordered)} cryptos written")

if __name__ == "__main__":
    main()
