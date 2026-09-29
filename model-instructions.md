# Model output spec

Paste the relevant section below into your model's instructions (or into the
Claude Code scheduled-task prompt) so its output matches what the site
expects in `data.json`.

## Betting model

**Selection is by edge, not a hard confidence floor.** Pull straight from
`bets.db` — never re-price. A pick can be under 50% confidence and still be
the card's best play if the edge is real; don't drop it and don't flip the
card to the other side just to clear a floor.

**`confidence` is always the model's honest win probability.** Never adjust
it to make a pick look more presentable. Sub-50% picks still get published —
they tier as Lean, not dropped.

**Tiers:**
- Top Play — confidence ≥ 65%
- Medium — confidence 55–65%
- Lean — everything else that clears the edge bar, including sub-50% picks

**SUPPRESS set.** If a market gets cut from core (per the ledger), add it to
SUPPRESS the same day — it can't be published, let alone as a Top Play, while
excluded. Revisit the SUPPRESS set periodically against fresh results; a cut
market isn't necessarily cut forever.

**Data hygiene:** exclude games already in progress at generation time —
picks on in-progress games aren't picks. Screen out known data artifacts
(missing/unconfirmed starters, pitchers with too few starts to trust, etc.)
even when they'd otherwise carry the biggest raw edge on the board.

Output each pick as:
```json
{ "tier": "top", "matchup": "NYY @ BOS", "market": "Moneyline", "pick": "NYY -135", "confidence": 0.68, "edge": 4.2 }
```
`tier` is one of `"top"`, `"medium"`, `"lean"`. `edge` is a plain signed number (points), never a string.

## Player prop model

**Quality over quantity.** Aim for 10+ individual picks per sport, but if
fewer than 10 legs actually qualify (e.g. games already started, or only a
weaker confidence tier remains), publish what qualifies and don't pad with
excluded-tier legs just to hit the count. Fewer clean picks beats a padded
card.

**Calibration correction is standing behavior, not a per-day ask.** If your
own graded history shows a systematic gap between a confidence tier's stated
number and its actual hit rate, apply that correction by default before
`confidence` goes into the file — a number that's known to run hot isn't
honest just because it's the model's raw output. Recompute the offset
periodically as the graded sample grows; don't freeze it at whatever the
first measurement was.

**`confidence` and `edge` must be plain numbers** — `confidence` a 0–1
probability, `edge` a signed number like `3.1`. If the underlying database
stores something else (e.g. a 1–10 card score), convert it before writing
the file. Put any extra reasoning or the raw market number in a separate
field if you want to keep it — never in `edge` or `confidence` themselves,
or the site's formatter will silently blank that row.

**Exclude in-progress games** at generation time, same as the betting model.

**Parlays:** single book only, so it's actually placeable as one ticket. No
leg reused between the 3-leg and 4-leg parlay. Same-game legs are allowed —
see "Parlay legs — same-game allowed" below, which supersedes the old
different-games-only rule.

Output individual picks as:
```json
{ "sport": "MLB", "player": "A. Judge", "market": "Total Bases O/U 1.5", "pick": "Over", "tier": "medium", "confidence": 0.61, "edge": 3.1 }
```
`tier` is one of `"top"`, `"medium"`, `"lean"` — see Unit sizing below for what each is worth and how to set thresholds for this model.

Output each parlay as:
```json
{
  "legs": 3,
  "odds": "+450",
  "selections": [
    "A. Judge — Total Bases Over 1.5",
    "M. Betts — Hits Over 0.5",
    "S. Ohtani — Strikeouts Under 6.5"
  ]
}
```

## Parlay legs — same-game allowed

Parlay legs may come from the same game — this applies everywhere, not
just single-game NFL days. There is no "different games" restriction.

When legs share a game, price the parlay using the book's actual Same
Game Parlay odds for that combination, not by multiplying the individual
legs' standalone prices. Correlated legs are priced differently by the
book than independent ones; computing a naive product overstates the
payout and misrepresents what's actually placeable. If DraftKings
declines that specific combination as an SGP, don't publish it.

**Exception (9/24/26):** when DraftKings' SGP price simply isn't available
to us (PropLine's free tier redacts SGP quotes), a parlay the spec requires
may be published at an **estimate** — the product of the legs' own DK
prices — shown as `"~+559"` with `"odds_basis": "estimate: product of
single-leg DK prices, not a DK SGP quote"`. It ignores same-game
correlation, so it is not a placeable price; the `~` stays on it through
grading.

## Unit sizing

Every published pick carries a `tier`, and stake follows tier directly:

- Top / high confidence — **1.5u**
- Medium — **1.0u**
- Lean / low confidence — **0.75u**

This now applies to **both** models — player props need a `tier` field too,
not just the betting model. Don't force props into the betting model's
65%/55% confidence cutoffs, though — prop confidence runs lower across the
board (see the calibration note above), so those thresholds would leave
almost everything in Lean. Set thresholds that make sense for the props
model's own calibrated confidence range, and keep them consistent day to day
so the units figure stays comparable across dates.

When grading a day for `record.json`, each pick's contribution to that day's
`units` total is its stake at its tier, resolved at its own odds — a win
nets stake × implied payout, a loss costs the full stake, a push is 0. Sum
those per section to get the day's `units` figure; don't set it by hand
separately from the graded picks.

## Avoiding write conflicts

**Neither model writes to `data.json` or `record.json` directly.** Two
independent scripts each regenerating the full file will eventually race —
whichever finishes last silently wins, and the other's work disappears with
no error. Instead:

- The betting model writes only to its own scratch file — `betting_output.json`, shaped as `{ "betting_model": [...] }`.
- The player prop model writes only to its own scratch file — `props_output.json`, shaped as `{ "player_props": {...}, "parlays": [...] }`.
- A single **merge step** — run once, after both scratch files are fresh for the day — reads both, adds a fresh `updated_at`, and writes the combined `data.json`. This merge step is the only process allowed to write `data.json`.
- The same rule applies to grading: each model writes its own day's graded results to a scratch file (`betting_graded_<date>.json`, `props_graded_<date>.json`). The merge step combines them into one `record.json` day entry — and only appends that day once **both** scratch files exist and are fully graded (rule 5 above still applies: no partial days).

When you wire up the scheduled task later, its prompt should run the betting
model, the prop model, and the merge step in that fixed order, in one
session — not two independent triggers.

## Coverage requirements

These sit on top of the normal edge-based selection — they don't replace it.
A pick published only to satisfy a coverage rule below, rather than because
it independently cleared the normal threshold, must carry
`"basis": "coverage floor"` so it stays distinguishable from genuine
edge-based picks in both `data.json` and `record.json`. `confidence` still
reports the honest number either way — coverage rules relax whether a pick
gets published, never what its stated probability is.

- **MLB:** at least 40% of the day's game slate should have a published
  pick, down to Lean tier if needed. Note: this only works if enough games
  reach the pricing stage in the first place. If the pre-pricing screen
  (survey.py's starter-confirmation check, etc.) is itself eliminating most
  of the slate before the model ever prices it, lowering the publish
  threshold won't fix the coverage number — that's a separate bottleneck
  worth checking directly.
- **NFL:** TNF, MNF, and SNF always get a published pick, regardless of
  whether anything clears the normal bar that week. Separately, 40% of
  Saturday/Sunday NFL games should have a pick.
- **CFB:** 40% of each day's games should have a pick — Saturday and any
  weeknight (Thu/Fri etc.) CFB slate alike (extended from Saturday-only 9/25/26).
- **NFL player props, single-game days:** on any day where the slate is
  exactly one NFL game, publish at least 6 player props for that game and
  at least one 3-leg parlay built from it.
  - **The 6 is a target, not a quota (9/28/26).** If fewer than 6 legs clear
    the rules, publish what clears and report it in the run report as
    `NFL props: N of 6, shortfall`. A shortfall is never filled by bending
    the anytime-TD floor or cap, the gap window, or any other rule.
  - **Anytime TD floor and cap (9/28/26):** an anytime-TD leg needs model
    probability ≥ 25% **and** a DraftKings price no longer than +300. Both
    must hold (`NFL_TD_MIN_PROB`, `NFL_TD_MAX_PRICE` in `board_props.py`).
    9/28 MNF published 5 of 6 under these rules (Odunze +475 at 25.0% and
    Cooper, Moore, Wicks excluded).
  - **Parlay leg search:** every valid 3-leg combination of the published
    props (one leg per player, one per team + stat category) is considered;
    the one with the highest joint model probability publishes. If no valid
    combination exists, no parlay publishes.

## NFL / CFB / NBA betting: spreads, as price reads

**Spreads only** for CFB, NBA and NFL — no moneylines. There is no graded
betting history for these sports yet, so there is no calibrated edge model
(MLB's `EDGE_BAR` and the props tier thresholds only exist because of real
graded samples; the CFB spread sweep in `bets.db` is explicitly NO_EDGE).
Until that history exists, CFB (and NBA) picks are **price reads**; NFL
picks come from the nfl_eff model under the documented exception below.
Either way they are published only where a coverage rule requires a pick
(TNF/SNF/MNF, the 40% Saturday/Sunday NFL and daily CFB floors, and
games in `requested_games.json`). Price reads work like this:

- Line: DraftKings' main spread (the alternate pair priced closest to even).
- Side: the one with the higher no-vig probability (the shorter price); a
  dead-even price goes to the side laying points.
- `confidence` = that no-vig probability; `edge` = `0.0`;
  `"basis": "price read — no model edge"`; `pick` reads `"Team -4.5 (-115)"`.
- Tier Lean, 0.75u — a zero-edge pick is never sized up by its price.
- Floor denominator: the day's games DraftKings actually prices (unpriced
  FCS games can't be picked, so counting them makes the floor unreachable).
- Floor fill order: highest confidence first (every edge is 0.0).
- NBA has no coverage rule yet, so it publishes nothing until one is set.
- Published, counted toward coverage, carried forward if started, and graded
  into `record.json` (PropLine final scores, margin + line; exact = push)
  exactly like every other pick.

## NFL spread model: published below breakeven (documented exception, 9/24/26)

**Every other model in this pipeline publishes only once it clears breakeven
on a validated holdout. The NFL spread model does not, and publishes anyway.**
This is a deliberate, one-time exception by Parker, recorded here so nobody
reads "NFL has a real model now" as "NFL has an edge now". It has not been
shown to have one; the backtest says it doesn't.

Model: `nfl_power/nfl_eff.py` — opponent-adjusted offense/defense EPA/play and
success rate from nflverse play-by-play (ridge fit toward a carried prior), a
3-season rolling home-field term, no market data in the fit, walk-forward.
Splits: TUNE 2000–14 (hyperparameters, on margin RMSE), TEST 2015–22 excl.
2020, HOLDOUT 2023–25; graded at a uniform −110 (breakeven 52.38%) because the
line source changed from sharp (~2% hold, 2006–22) to retail (4.7%, 2023+).

Backtest, reported in full (9/24/26):

| Split | Games | Cover% (95% CI) | ROI @ −110 | Model RMSE | Market RMSE |
|---|---|---|---|---|---|
| TUNE 2000–14 (in-sample for b; context only) | 3,879 | 50.1% (48.5–51.7) | −4.4% | 13.82 | 13.55 |
| TEST 2015–22 excl. 2020 | 1,848 | 50.2% (47.9–52.4) | −4.2% | 13.10 | 12.73 |
| HOLDOUT 2023–25 | 836 | 47.2% (43.9–50.6) | −9.8% | 13.24 | 12.72 |

Re-run 9/28/26 from the frozen parameters: identical. HOLDOUT by season: 2023
45.0%, 2024 50.2%, 2025 46.5%.

**Calibration of the published confidence (9/28/26).** `cover_logit` (P(model
side covers) = logistic(a0 + a1·|model − line|), a0 −0.066, a1 +0.031) is fit
on TUNE. Out of sample it does not hold: refit on TEST the slope is −0.033, on
HOLDOUT −0.003 — confidence rises with disagreement while actual cover falls.
Its Brier score is no better than a constant 0.5 on TEST (0.2508 vs 0.2500) or
HOLDOUT (0.2504 vs 0.2500). HOLDOUT, predicted vs actual: 0.53–0.55 bin 0.538
vs 0.379 (n=29); 0.55+ bin 0.566 vs 0.444 (n=18). "Slightly hot" understated it.

**Cover by model-vs-line disagreement (diagnostic context, 9/28/26):**

| Disagreement | TEST n | TEST cover | HOLDOUT n | HOLDOUT cover |
|---|---|---|---|---|
| 0–1 pts | 517 | 52.4% | 236 | 44.1% |
| 1–2 | 472 | 50.0% | 199 | 52.3% |
| 2–3 | 315 | 50.8% | 158 | 43.7% |
| 3–5 | 360 | 48.9% | 163 | 50.9% |
| 5+ | 184 | 45.7% | 80 | 43.8% |

No bucket is consistently above breakeven; 5+ is the worst in both splits.

Larger model-vs-market disagreements covered *worse* (5+ pts: 45.7% TEST,
43.8% holdout) — the opposite of a real edge. The market was more accurate in
every split. The schedule-bias check passed in the configuration the model
runs (adjusted-rating correlation with opponent defense −0.065 overall,
+0.017 from week 14), so this is a working model that doesn't beat the line,
not a broken one.

Rules that still apply to its picks:
- `confidence` = the model's own calibrated P(cover), fit on TUNE only
  (≈ 0.48–0.54). Never adjusted upward; a 0.497 publishes as 0.497. Out of
  sample even this runs slightly hot at large edges.
- `edge` = confidence minus DK's no-vig probability for that side, in points.
- Every pick is **Lean, 0.75u** until a real graded NFL sample exists to set
  tiers against — no NFL edge bar has been validated.
- `"basis": "nfl_eff model — below breakeven in backtest (documented
  exception)"` on every pick, in `data.json` and `record.json`.
- Coverage rules still decide which games get a pick; the model decides the
  side and the confidence.
- **Weekend floor fill order (9/28/26):** floor games are filled by the
  **smallest** model-vs-line disagreement (`model_gap_pts`), tagged
  `"basis": "coverage floor"` with the model caveat moved to `note`. This
  avoids the 5+ bucket the old highest-confidence order selected. It is a
  judgment call, not a tuned parameter, and not a claimed edge — the table
  above shows no bucket beats breakeven.
- **`model_gap_pts`** (|model margin − line|, points) is on every NFL model
  pick and kept in `record.json` with its outcome.
- **Neutral sites:** the model reads nflverse's schedule (`location ==
  "Neutral"`) and uses HFA 0 there, exactly as the backtest did. A game
  missing from the schedule is a loud `!!` price read, never a silent home site.
  (The CFB Model column does the same from `cfb.db`'s neutral flag.)
- **Fail loudly:** a missing parameter in `nfl_eff_tuned.json` (`cover_logit`
  included — `--tune` now writes it, TUNE only) or a failed nflverse
  `--refresh` prints `!! NFL model unavailable` and that run's NFL picks are
  price reads. A failed refresh stops only the NFL model, not the daily run.
- **Season:** nflverse convention — January/February games belong to the prior
  season (`nfl_eff.nfl_season`).

**Standing rules (Parker, 9/28/26):**
- Don't tune on 2023–2025 again. HOLDOUT has been looked at; any future change
  is judged on 2026+ games only.
- Every NFL spread pick is logged with `model_gap_pts` and its graded outcome,
  so 2026 is the clean forward test.

## NHL same-day composite: unvalidated, no backtest (documented exception, 9/29/26)

**This is not a model. It has never been tested against a single game.** Parker
asked for NHL picks on opening night (9/29/26, 5 games) before any NHL
pipeline existed, so this is a same-day heuristic published as an explicit,
dated exception — the same category as the CFB price reads and the NFL
below-breakeven exception, and weaker than both: nothing here was fit, tuned
or backtested, because there is nothing yet to backtest against.

What it is (`nhl_power/nhl_composite.py`, wired into `board_betting.py`):
- Home margin, goals/game = 0.5 × (xG diff/game, home − away) + 0.5 × (points %
  converted to goals/game, home − away) + 0.5 × (projected starting goalie's
  GSAx/60, home − away) + home ice.
- Each team term is a recency-weighted average of 2021-22 through 2025-26:
  weights 0.40 / 0.25 / 0.15 / 0.10 / 0.10, newest first.
- Data: MoneyPuck team + goalie season summaries (all situations, score/venue-
  adjusted xG), NHL standings at each season's end, NHL current rosters.
- **Every weight is a guess**: the 0.5/0.5 xG-vs-points blend, the season
  weights, the goalie term's 0.5 discount, the goalie shrink (GP/(GP+40)).
  Two numbers are measured, not guessed, and neither is a fitted model: home ice
  (+0.221 goals/game, league home goal diff 2021-26) and the points %→goals
  conversion (−3.28 + 5.90 × pts%, across 160 team-seasons).
- **Goalies are projected, not confirmed**: the NHL API posts no starters, so
  the term uses the current-roster goalie with the most 2025-26 games, and
  says so in each pick's `note`.
- Team history does not see offseason roster moves beyond that goalie term.

How it publishes:
- **Side** = the composite's side. That is the only thing the composite decides.
- **`confidence`** = DraftKings' no-vig probability for that side. It is the
  market's number, not the composite's; there is no calibration to trust.
- **`edge` = 0.0.** Tier **Lean, 0.75u.**
- **`"basis": "same-day composite — unvalidated, no backtest"`**: a tag distinct
  from "price read", "coverage floor" and the NFL model basis, so these picks
  are never mistaken for a tested model in `data.json`, `record.json` or on the site.
- **Coverage:** 60% of the slate (Parker 9/29/26), filled by the games where the
  composite is most one-sided (largest |margin|). That order is a judgment
  call, not a tuned parameter.
- **Scope:** tonight only (`NHL_DATES = {"2026-09-29"}`). Graded from PropLine
  final scores, moneyline on the winner, like every other pick.

**Retirement.** This heuristic is retired, not upgraded, once a real walk-forward
NHL model — historical seasons ingested, TUNE/TEST/HOLDOUT splits, reported the
way the NFL model is — exists and is validated. That model supersedes it
entirely. Until then, nobody should read "the board has NHL picks" as "the
board has an NHL model". As of 9/29/26 no such pipeline exists in either repo;
it has not been started here.

## Lean-tier picks

Lean-tier picks are real picks, not a lower-priority afterthought. They get
published in `data.json` and graded into `record.json` exactly like Top and
Medium picks — nothing in the pipeline should filter, hide, deprioritize, or
silently drop a Lean pick at any stage.

## Player prop data source

Player props are priced from DraftKings only, via **PropLine** (`pip install
propline`), requesting `bookmakers="draftkings"` and the specific prop
markets by name — a `get_odds` call with no `markets` returns only
h2h/spreads/totals. The key comes from the `PROPLINE_API_KEY` environment
variable only (exported in `~/.zshenv` so non-interactive scheduled runs see
it) — never in a committed file.

PropLine's response is the-odds-api-shaped (player in `description`, side in
`name`, plus `price` / `point`), confirmed 9/24/26 against the Odds API cache
with identical DK prices. Keep only `Over`/`Under` outcomes with a `point`;
DK also lists "N+" ladder outcomes with no point under the same market key.
The Odds API path (`bookmakers=draftkings`, never `regions=`) remains as a
fallback: `props_card.py --source oddsapi`.

## Track record (`record.json`)

This file is **append-only history**, separate from `data.json`. `start_date`
is fixed at the date the site actually went live — **2026-09-22** — and it
never moves earlier, even if a model has fully graded data for a day before
that. A day that existed only in a database before the site published
anything to anyone doesn't belong in the public record; backfilling it would
credit a track record for picks nobody could see. This applies to both
models equally, even if one of them has gradable data and the other doesn't
for the same date.

Each daily run should:

1. Grade the **previous** day's picks once their games have finished (win / loss / push), using final results from `bets.db` / `props.db`.
2. Append one new entry to the `days` array for that date — never overwrite or edit a previous day's entry once it's written.
3. `wins` / `losses` / `pushes` and `units` are per-day totals for that section; the site sums across all days itself, so don't maintain a running cumulative total in the file.
4. Parlays are graded independently — a parlay's win/loss doesn't change the win/loss tally of its individual legs, even if a leg also appears as a standalone pick that same day.
5. Only grade games that have actually finished. If a day isn't fully graded yet (postponements, late games), leave it out of `record.json` until it is — don't publish partial or estimated results.
6. **Cancelled with no makeup date = void (9/28/26).** An MLB game Cancelled with no `rescheduleDate`/`resumeDate` (e.g. rained out on the season's last day) will never be played: betting picks and prop legs on it grade as a **push** (0 units) with a void note. Both graders apply this automatically; a dated `"void"` entry in `prop_overrides.json` records a manual, box-score-verified void. Postponed and suspended games are *not* void — they stay ungraded until made up (rule 5).

Schema:

```json
{
  "start_date": "2026-09-22",
  "days": [
    {
      "date": "2026-09-22",
      "betting_model": {
        "wins": 5, "losses": 3, "pushes": 0, "units": 2.4,
        "picks": [
          { "matchup": "NYY @ BOS", "market": "Moneyline", "pick": "NYY -135", "tier": "top", "stake": 1.5, "result": "win" }
        ]
      },
      "player_props": {
        "wins": 7, "losses": 3, "pushes": 0, "units": 1.8,
        "picks": [
          { "player": "A. Judge", "market": "Total Bases O/U 1.5", "pick": "Over", "tier": "medium", "stake": 1.0, "result": "win" }
        ]
      },
      "parlays": [
        { "legs": 3, "odds": "+568", "result": "loss" }
      ]
    }
  ]
}
```

`result` is one of `"win"`, `"loss"`, `"push"`. `stake` is optional but
recommended on each pick — it makes the day's `units` figure auditable
against the tier table above instead of just trusting a hand-computed total.

```json
{
  "updated_at": "2026-09-22T14:00:00Z",
  "betting_model": [
    { "tier": "top", "matchup": "NYY @ BOS", "market": "Moneyline", "pick": "NYY -135", "confidence": 0.68, "edge": 4.2 }
  ],
  "player_props": {
    "picks": [
      { "sport": "MLB", "player": "A. Judge", "market": "Total Bases O/U 1.5", "pick": "Over", "tier": "medium", "confidence": 0.61, "edge": 3.1 }
    ],
    "parlays": [
      { "legs": 3, "odds": "+450", "selections": ["...", "...", "..."] },
      { "legs": 4, "odds": "+900", "selections": ["...", "...", "...", "..."] }
    ]
  }
}
```
