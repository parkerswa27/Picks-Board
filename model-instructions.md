# Model output spec

Paste the relevant section below into your model's instructions (or into the
Claude Code scheduled-task prompt) so its output matches what the site
expects in `data.json`.

## Betting model

Every pick gets exactly one tier:

- **Top Play** — highest-conviction bets. Confidence ≥ 65%.
- **Medium Confidence** — solid opinions, not your biggest bets. Confidence 55–65%.
- **Lean** — lower-conviction directional calls, still worth surfacing. Confidence 50–55%.

Don't limit yourself to a handful of top plays — surface every game that
clears the 50% floor, sorted into its tier, so the board reflects the full
slate rather than just the best 3–4 bets.

Output each pick as:
```json
{ "tier": "top", "matchup": "NYY @ BOS", "market": "Moneyline", "pick": "NYY -135", "confidence": 0.68, "edge": 4.2 }
```
`tier` is one of `"top"`, `"medium"`, `"lean"`.

## Player prop model

For **each sport with games on today's slate**:
- Produce **at least 10 individual player prop picks** (different players and/or markets — don't repeat the same player+market twice just to hit the count).
- Tag every pick with its `sport`.

Then, across the day's full prop pool, build:
- **One 3-leg parlay** — 3 different props, no two legs from the same player+market.
- **One 4-leg parlay** — same rule, 4 different props.

Output individual picks as:
```json
{ "sport": "MLB", "player": "A. Judge", "market": "Total Bases O/U 1.5", "pick": "Over", "confidence": 0.61, "edge": 3.1 }
```

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

## Full `data.json` shape

```json
{
  "updated_at": "2026-09-22T14:00:00Z",
  "betting_model": [
    { "tier": "top", "matchup": "NYY @ BOS", "market": "Moneyline", "pick": "NYY -135", "confidence": 0.68, "edge": 4.2 }
  ],
  "player_props": {
    "picks": [
      { "sport": "MLB", "player": "A. Judge", "market": "Total Bases O/U 1.5", "pick": "Over", "confidence": 0.61, "edge": 3.1 }
    ],
    "parlays": [
      { "legs": 3, "odds": "+450", "selections": ["...", "...", "..."] },
      { "legs": 4, "odds": "+900", "selections": ["...", "...", "...", "..."] }
    ]
  }
}
```

Drop this file into your scheduled-task prompt or model system prompt as-is —
the site (`app.js`) is already built to read this exact shape.
