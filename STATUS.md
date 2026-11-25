# STATUS — news-image-20261124 v2 (BUILT, NOT SUBMITTED)

- Entry dir: `~/workspace/makefun/news-image-20261124-v2-entry/`
- Repo (to create on submit): https://github.com/wahyunp26-source/news-image-20261124-v2
- entry.png: 1024×1024, 212,089 B, sha256
  `b71204b7b1444e8adcb7784fd8c85e771718ac9e16bcc2563af251dac018eec9`
  (rebuilt from REAL top-1 refs 25 Nov ~10:05 WIB — see "Rebuild (Wahyu:
  referensi top 1 beneran)" below; previous render was 207,380 B, sha256
  `538af5b8…`)
- Quota: v1 used 1/3. v2 NOT submitted (parent handles bundle/submit after
  user approves preview). Force_Last: any v2 submit REPLACES v1.
- All code written FRESH in this session. v1's main.py / atlas_blob.py were
  NEVER read or copied. Only v1's entry.png was viewed (to see what to beat).
- Grader-style test VERIFIED (re-verified after the revision): read-only copy
  of the repo, run `python3 -P -s /bot/main.py` from a different CWD with
  MAKEFUN_OUTPUT_DIR set → exit 0, entry.png written. Two runs
  byte-identical (sha256 above). 1.7 s per run.
  Docker not available in this VM (not needed — process driver used).

## Rebuild (Wahyu 25 Nov ~09:52: "itu yakin udah ngambil referensi top 1 sebelumnya?") — from REAL winners, targeted edits only, no rewrite

Parent verified the doubt was CORRECT: the first v2 build never saw the
final winners — news21/22/23 #1 images were not fetchable via the text
fetcher or the leaderboard API (all finalists have source_withheld=true,
repo_url=""). This rebuild downloaded the REAL final winners at full res
via the submissions artifact endpoint into ~/workspace/makefun/top1-refs/:
news19 #1 superskie (86.4%), news20 #1 superskie (87.2%), news21 #1
superskie (86.1%), news22 #1 bagarte (85.4%), news23 R3 leader kevin
(provisional). All five VIEWED at full res + measured (see below).
The old "top1.png" reference was news22 DEV-phase #1 (ilyayaaa) — NOT a
final winner; ignored now.

Winner devices added (all confirmed across the 5 refs):
1. THE DAY IN UTC TIMELINE STRIP (the single biggest structural gap —
   v2 had none): red label box + 5 beats. Times VERIFIED 25 Nov by search:
   quake 01:32 UTC (NCS 07:02:47 IST), Sanofi deal 05:30 UTC (Sanofi
   release 06:30 Paris), Houthi tower hit Tuesday morning (Riyadh),
   Huawei verdict in US court hours ("Afternoon" phase label, as winners
   use "Overnight"/"Evening"), US markets close 21:00 UTC.
2. THE DAY IN NUMBERS label box: v2's stat strip already had the same six
   numbers; it now carries the winners' red label box ("THE DAY / IN /
   NUMBERS") and shorter captions ("TANKERS HIT IN HORMUZ", "HURT IN
   RIYADH STRIKE").
3. HERO RED LABEL BARS (kevin's device): full-width red bars above each
   hero illustration — "NVIDIA SLIDES 7%", "WARSHIP SUNK OFF LIBYA",
   "TANKERS HIT IN HORMUZ". The small in-scene hero chips were removed
   (duplication); "-7%" on the arrow and "MERKURY" hull caption kept.
4. STATUS BADGES on every kicker row (winners' device): outlined chips
   CONFIRMED (green) / OFFICIAL (amber) / CLAIM (red) + source — this is
   now where each story names its outlet. Hero 3 is CLAIM · AL JAZEERA
   (Iran's claim); mid 6 is OFFICIAL · WARSAW. Mid kickers shortened to
   winners' style ("4 BROOKLYN", "5 RIYADH"...) so chips fit.
5. DECKS tightened to winners' lengths and inline "(Reuters)" sources
   REMOVED from hero/mid decks (attribution moved to the badges): hero
   decks 14–20 words, mid decks 13 words, all 2 lines (measured with the
   real fonts — first render had 4 mid decks at 3 lines overlapping the
   next row + badge/kicker collisions on mids 7 and 12 + footer colliding
   with the right-side text; all fixed and re-measured: worst mid
   kicker+badge 174/185 px, footer ends 743 px vs right text at 808).
6. FOOTER now carries the winners' legend: "CONFIRMED 2+ outlets ·
   OFFICIAL authority's word · CLAIM one side says · Sources: ... ·
   Drawn illustrations, not photos."

Measured winner decks (full-res): heroes 14–21 words, mids 7–13 words,
briefs 8–12 words. v2 now: heroes 14/18/19 words, mids 13 words, briefs
8–14 words. Timeline facts all verified Tuesday-true; story facts/dates
unchanged from the corrected v2.

Grader-style test RE-VERIFIED after the rebuild: read-only repo copy,
`python3 -P -s` from a different CWD with MAKEFUN_OUTPUT_DIR set → exit
0, two runs byte-identical (sha256 above).

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

## Beat-top-1 fix round (25 Nov ~10:11–10:40, commit 9ac673d, NOT submitted)

Wahyu's bar: BETTER than top 1, not just equal. The 3 fixes were the
floor; every element had to be at least as good as the winners', at least
one visibly better.

### What changed (main.py only, 146 insertions, 91 deletions)
1. **Timeline: 7 beats, all timed** (kevin 5, bagarte 6, superskie19 7):
   Overnight Drone enters Poland · 01:32 Nepal 5.4 quake · 05:30 Sanofi
   $41bn deal · 07:30 UAE bus crash kills 11 · Morning Houthi hits
   Riyadh · Afternoon Huawei guilty · 21:00 Nvidia slides 7%.
   Every hour verified against sources (see the verification comment in
   main.py): Houthi exact hour NOT published (Morning, winners' own
   convention); Huawei no clock time (Afternoon); Poland drone crossed
   ~21:49 UTC Mon (Overnight beat); Trump–Rutte is Wed, factory fire was
   Sat — neither is a Tuesday beat.
2. **THE DAY IN NUMBERS: vertical panel on the right** (bagarte's device,
   cleaner here): navy panel x=830, w=166, y=172–588; white serif numbers,
   one-line captions, dividers between items, red rule under the header.
   The horizontal stats strip is GONE. Heroes narrowed to 252 px so the
   panel fits; scenes are 120 tall now (the strip removal freed 44 px) —
   the Nvidia arrow finally fits inside its scene.
3. **Grok courtroom redraw** (was the thinnest mid on the page — one laptop
   + triangle on bare purple): wood panels + scales-of-justice emblem
   top-right, judge's bench, document stack with red filed edge, two
   laptops (X and GROK screens), gavel + block — 12+ elements.
4. **Mid badges are status-only** (bagarte + kevin both do this on mids;
   heroes keep status + source). `_kicker` gained a `badge_src` param.
   Hero 1 kicker shortened ("SANTA CLARA", badge src "REUTERS") — the
   old "SANTA CLARA, US · MARKETS + CONFIRMED · REUTERS" was 282 px in a
   252 px column.
5. **Map 380x190 (was 290x145), 31% larger; repulsion re-run** (MIN_D 16,
   MAX_OFF 32): min pin distance 15.3 px (was 14.1), max offset 25.5 px
   (was 23.1), 31/35 labels offset. Briefs moved x 330 -> 428.
   At 2x zoom every pin number is individually readable; at 300 px the
   Europe/ME cluster is still dense — but so are bagarte's and kevin's.
   Ours adds leader lines back to true positions, which neither winner has.
6. **Overflow bugs caught by viewing the render** (the narrowed 150 px
   mid row 1 exposed them): scene_gaza's last building painted 32 px over
   the numbers panel (visible artifact in the first render); scene_riyadh
   skyline painted 48 px into the next scene; scene_poland city lights
   painted 28 px into the next scene. All three skylines are now
   width-relative (fractions of w). Odesa's last building fixed 1 px.
   The panel is clean in the final render.

### Verification
- Grader-style test PASSED: read-only repo copy, `python3 -P -s`,
  different CWD, MAKEFUN_OUTPUT_DIR set, exit 0, byte-identical across
  3 runs. entry.png 219,151 B, sha256 f854736b821fe6a4755aea424fb5f081f2e38c6a58edfbfd315fdf36028bb3c8.
- Full-res render viewed + crops viewed (heroes, mids row 1, panel, map):
  no text overflow, no collisions, no clipped labels. All 35 stories
  present, all dated Tuesday 24 Nov 2026.
- Commit 9ac673dae27fb26cd6f611ffb0a2257d11f99957 (master -> main).

### Honest verdict vs the winners (parent's own, no softening)
- Elements where v2 is now BETTER than the winners: timeline (7 beats,
  most of any winner), numbers panel (cleaner than bagarte's — dividers,
  red rule, one-line captions; his is a bare list), map (bigger + leader
  lines to true positions), grok courtroom (denser than any single mid
  scene in the winners' pages).
- Elements where v2 is at PARITY: heroes (bold scenes, red label bars,
  three annotation layers), mid scenes generally (detail-dense, all
  legible at 300 px), masthead + region bar + DATE CHECK.
- Elements where v2 still LAGS: the map's Europe/ME cluster is still a
  dense red zone at 300 px (same as the winners, but not better);
  mid 6's radar dome touches its number circle; mid 7's scales emblem is
  small and crowded by its number circle; winners' scenes carry slightly
  more small storytelling captions (in-scene labels) than ours overall.
- Bottom line: this is the closest v2 has ever been to the winners, and
  on the four elements Wahyu named it is at or above them. Whether that
  is enough for top 50 — let alone top 1–7 — is UNKNOWABLE from design
  alone: v1 went R1 rank 36 -> R2 rank 1,614 with the SAME entry, so the
  pairwise judge swings harder than any design difference. No rank
  prediction is made. Submit decision is Wahyu's (quota 1/3 used, 2 left;
  R3 judged 25 Nov 19:00, final R4 26 Nov 07:00).
