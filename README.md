# minerspal-data

Public JSON feeds for the MinersPal app, served by GitHub Pages at
`https://brunec22.github.io/minerspal-data/`. Paths match what the app decodes; do not rename
files or change their schema without an app update.

| Path | Updated by |
| --- | --- |
| `minersPal/api/news/news.json` | `news.yml` every 2 h (public crypto RSS feeds) |
| `minersPal/api/news/dev-news.json` | `news.yml` (staging feed: more sources, 7 days; simulator/dev builds) |
| `hashrate/api/v2/reward-estimation/reward-estimations.json` | `rewards.yml` every 2 h (WhatToMine) |
| `hashrate/api/v2/reward-estimation/whattomine-units.json` | `rewards.yml` (hashrate unit per coin for the app's live WhatToMine fetcher) |
| `hashrate/api/v2/mining-equipment/gpus.json` | `gpus.yml` weekly (WhatToMine GPU pages) |
| `hashrate/api/v2/mining-equipment/asics.json` | manual: `python3 tools/merge_asics.py` after editing `tools/asic_additions.json` |
| `hashrate/api/v2/algo/supported-algos.json` | manual + additive from `gpus.yml` |
| `hashrate/api/v2/crypto/supported-cryptos.json`, `s2crypto/api/v1/supportedCurrencies.json`, `hashrate/api/v2/images/pool-images/` | static |

Initial content was seeded from the previous MinersPal data host (thiagoam.github.io).
Every workflow can also be run by hand from the Actions tab (Run workflow).
