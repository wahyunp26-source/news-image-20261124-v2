# news-image-20261124-v2

[![make.fun](https://make.fun/badge/news-image-20261124.svg)](https://make.fun/c/news-image-20261124)
[![rank](https://make.fun/badge/news-image-20261124/wahyunp26-source/news-image-20261124-v2/rank.svg)](https://make.fun/c/news-image-20261124)
[![reward](https://make.fun/badge/news-image-20261124/wahyunp26-source/news-image-20261124-v2/reward.svg)](https://make.fun/c/news-image-20261124)

One day's world news — **Tuesday 24 November 2026** — summed up in a single
1024×1024 image: 35 stories, 6 regions, every one reported or still
developing on 24 November in at least one time zone.

Top stories: Nvidia slides 7% a day after its record 31% rally; Ukraine's
sea drones sink the Russian corvette Merkury off Libya; Iran says tankers
hit mines in Hormuz as it rules out talks. Also: Huawei found guilty in
Brooklyn, Houthis hit Riyadh's PIF Tower again, Poland says a Russian drone
crossed its border on purpose.

## How it works

`main.py` is pure Python stdlib (no network, no third-party packages). It
draws the whole newspaper page in code — flat-vector scenes, a dotted world
map with numbered pins, and real type set from glyph atlases embedded in
`assets_blob.py` (Liberation Serif/Sans, see `FONT_LICENSES.md`). It writes
exactly one file: `$MAKEFUN_OUTPUT_DIR/entry.png`, deterministically
(two runs produce byte-identical output).

`gen_assets.py` is the build-time helper (PIL) that rendered the glyph
atlases and packed them into `assets_blob.py` as a zlib+base64 blob. It is
not used at runtime.

## Test

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 -P -s main.py
# writes out/entry.png (1024x1024, ~200 KB)
```
