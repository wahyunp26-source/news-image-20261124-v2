# STATUS — news-image-20261124 v2 (BUILT, NOT SUBMITTED)

- Entry dir: `~/workspace/makefun/news-image-20261124-v2-entry/`
- Repo (to create on submit): https://github.com/wahyunp26-source/news-image-20261124-v2
- entry.png: 1024×1024, 207,380 B, sha256
  `538af5b8e55902b871427a81f4ddad0b9e674d4a9005f0c2c4155ec3f72871be`
  (revised 25 Nov ~09:30 WIB — see "Revision (Wahyu: perbaiki lagi dan rapikan)" below;
  previous render was 204,311 B, sha256 `263f4274…`)
- Quota: v1 used 1/3. v2 NOT submitted (parent handles bundle/submit after
  user approves preview). Force_Last: any v2 submit REPLACES v1.
- All code written FRESH in this session. v1's main.py / atlas_blob.py were
  NEVER read or copied. Only v1's entry.png was viewed (to see what to beat).
- Grader-style test VERIFIED (re-verified after the revision): read-only copy
  of the repo, run `python3 -P -s /bot/main.py` from a different CWD with
  MAKEFUN_OUTPUT_DIR set → exit 0, entry.png written. Two runs
  byte-identical (sha256 above). 1.7 s per run.
  Docker not available in this VM (not needed — process driver used).

## Revision (Wahyu 25 Nov 09:22: "coba perbaiki lagi dan rapikan") — targeted edits only, no rewrite

1. MAP pins (biggest flaw): the Europe/Middle East cluster was one dense red
   mass. FIXED with a real layout: label offsets computed by an offline
   repulsion relaxation (script /tmp/map_layout3.py) using main.py's exact
   int-truncated projection, min centre distance 13.5 px, then an integer
   repair pass — final min pairwise distance **13.6 px**, max offset 16 px,
   31/35 pins offset. Offset labels get a thin red leader line back to
   their true lat/lon point (marked by a small dot). Verified numerically
   AND by a 2x crop: all 35 pins are individually readable now.
   (Lesson: the first attempt's optimizer used round() while main.py uses
   int() — 6 pairs still touched at 11.7–12.5 px; re-ran with int anchors.)
2. HERO 3 (Hormuz): sun + flame merged into one orange blob. FIXED: sun
   moved up-left and shrunk (r=10, glow r=20, steps=3), flame shrunk
   (24×30, glow r=16) — verified in a 2x crop: two separate elements.
   Added 2 more mines (3 total bobbing in the strait).
3. MID 12 (Mexico): police car was a tiny blob. FIXED: redrawn ~3x bigger
   (92 px wide body + cabin + windows + red/blue light bar + "POLICIA"
   door text + wheels with hubs) — verified in a 3x crop: reads as a
   police car at 300 px.
4. HERO 1 chip: "HUANG RETURNS" contradicted the "slides 7%" headline.
   FIXED: chip now "SLIDES 7%", plus "-7%" written on the arrow head.
5. SCENE DETAIL: in-scene captions added — "MERKURY" on the corvette hull
   (hero 2), "NATO AWACS" under the plane (mid 6), "-7%" on the arrow
   (hero 1), 2 extra mines (hero 3). No clutter added; strict grid kept.
6. NEATNESS: full-res + 300 px views checked — no overlapping text/pins,
   no clipping, grid intact, masthead/stats/region bar unchanged.

## References (top-1s, full-res)

Measured at 1024×1024. Final winners (from make.fun bounty pages):
news19 #1 @superskie, news20 #1 @superskie, news21 #1 @superskie,
news22 #1 @bagarte, news23 R3 #1 @kevin. The saved full-res images I could
actually view were the DEV-phase leaders, not the final winners:
- news19 dev #1 hazel-harbor-63 ("Thursday 19 November 2026", 33 stories,
  score 0.9923) — VIEWED full-res.
- news20-top1.webp ("Friday 20 November 2026", 36 stories) — VIEWED full-res;
  title matches @superskie's winning title, treated as the winner with that
  caveat.
- news22 dev #1 ilyayaaa ("Sunday 22 November 2026", 35 stories, 6 regions,
  score 0.9911) — VIEWED full-res. NOTE: the task brief said
  v8-top3/top1.png was news23's #1 — WRONG, it is news22's #1.
- news21 final #1 @superskie + news22 final #1 @bagarte + news23 R3 #1
  @kevin: images NOT fetchable at full res (make.fun entry pages expose no
  image URL to the text fetcher; the leaderboard API fetch was blocked after
  one empty response — not retried). Used instead: v11 STATUS measurements
  of news23's leader (hero-2 drone rain ~7 trails, masthead 43 px caps).
- Common pattern (all three viewed): giant serif masthead (~43 px caps),
  3-story italic sub-headline, 6-stat strip, region bar, 3 heroes, 10 mids
  (2 rows of 5), 20–23 briefs, dotted map + numbered pins, DATE CHECK box,
  named sources, 27–39 stories, flat vector, ZERO real photos, muted palette
  (cream/navy/muted red/soft orange/sage). Hero decks 13–22 words, mid decks
  ~7–11 words, briefs ~8–12 words. Every story ONE complete sentence.
  Bottom is map + briefs (visual), never a numbered list.

Deck lengths measured (news22 #1): H1 21 words, H2 14, H3 11; mids 7–11;
briefs 8–12. (news19 #1): H1 ~21, H2 ~19, H3 ~15. v2 matches: heroes
18–21 words, mids 11–16, briefs 8–14.

## What v2 fixes vs v1 (v1: R1 36/7,302 → R2 1,614/9,063)

v1's R2 collapse is most plausibly factual self-contradiction, fixed here:
1. DATE CHECK contradicted itself: stat strip + story 4 were about the
   Poland missiles while DATE CHECK listed "missiles landing in Poland
   (19 Nov)" as left out — and the date was wrong (missiles landed 20 Nov).
   v2's DATE CHECK is self-consistent and names the left-out days correctly.
2. Delta outage was a 22 Nov story presented as 24 Nov (outage was Sunday
   22 Nov; by Tuesday operations were stabilised). DROPPED; replaced by the
   Huawei verdict (Tuesday, Brooklyn jury).
3. Grok lawsuit states were wrong ("Washington") — the suing states are
   Oregon + Virginia. FIXED (mid 7, verified 24 Nov).
4. Nvidia reinstatement (+31.5%) happened Monday 23 Nov, not Tuesday.
   v2's hero 1 is Tuesday's true development: shares slide ~7% a day after
   the record rally (verified: Reuters/CNN 24 Nov).
5. New Tuesday-true stories added (all verified 24 Nov): Huawei guilty,
   Houthi PIF Tower strike (2nd in 5 days, 11 hurt), Poland drone incursion
   (deliberate, 24 Nov), Sanofi–Insmed $41bn, Nepal 5.4 quake, Indonesia
   factory fire (24 dead), Ghalibaf no-talks vow, Tripoli demands answers,
   14 nations back ICJ ruling, NATO AWACS to Poland, Grok OR+VA suit.
6. Hero 1 is now a real scene (chip + big red down arrow + tickers), not the
   bare chart panel v1 had. The arrow polygon was rewritten after the first
   render showed a bowtie (concave scanline bug) — verified fixed in crop.
7. Middot "·" rendered as "?" in render 1 (missing U+00B7 in atlas) — fixed.

## Self-eval (honest)

- Layout matches the top-1 pattern on every structural point: masthead,
  stats, region bar, 3 heroes, 10 mids, 22 briefs, map + pins, DATE CHECK,
  sources. Facts are Tuesday-true and self-consistent — the two things v1
  got wrong.
- Verdict: TOP 50 CREDIBLE, TOP 15 PLAUSIBLE, TOP 1–7 UNLIKELY. Do not
  claim top 1. Gaps vs the winners: (1) scene detail density — winners'
  scenes carry more small storytelling elements (figures, flags, in-scene
  captions like "Officials' count"); v2's scenes are simpler, though each
  reads instantly at 300 px; (2) the map — my hand-drawn dot grid is
  coarser than winners' coastlines and the Europe/Middle East pin cluster
  is a dense red mass; (3) hero 3 (Hormuz) sun glow + flame merge into one
  orange blob; (4) mid 12 (Mexico) police car is a tiny blob, scene mostly
  bare courthouse; (5) no in-scene captions.
- REVISED VERDICT after the 25 Nov ~09:30 fix (commit 509b57e): gaps
  (2), (3), (4), (5) above are now CLOSED — pins are individually
  readable (min 13.6 px apart, verified), sun and flame are separate,
  the police car reads at 300 px, and 4 in-scene captions were added.
  Remaining gap is only (1): winners' scenes are still denser with small
  storytelling elements than ours. Verdict moves to TOP 50 CREDIBLE,
  TOP 15 MORE PLAUSIBLE THAN BEFORE — top 1–7 still unlikely, do not
  claim it. The R2-collapse mechanism itself remains unobservable.
- What v2 does NOT fix: it cannot fix the R2-collapse mechanism itself
  (unknown — the judge's Swiss pairings in R2 are unobservable); it only
  removes the visible defects that most plausibly caused it.

## Files

- main.py (fresh, stdlib-only runtime), assets_blob.py (67 lines, zlib+base64
  glyph atlases + map grid), gen_assets.py (build-time PIL atlas renderer),
  entry.png (local render), LICENSE (SPDX first line), README.md (3 badges),
  FONT_LICENSES.md, .makefun/owner.json.
- No vendor/makefun-frontend.ts: no such file exists in this kit (checked —
  kit has starter/main.ts only, no vendor dir) and v1's repo has none either;
  it is a main.ts/guide-comp requirement, not a Python-entry one. Flagged,
  not blocking.
