# The Board — auto-updating picks site

A static site that shows your betting model and player prop picks. Claude Code
writes `data.json`, pushes it to GitHub, and the live site picks it up
automatically — no server, no hosting bill.

## 1. Put this on GitHub

```bash
cd picks-site
git init
git add .
git commit -m "Initial site"
gh repo create my-picks-board --private --source=. --push
# no gh CLI? create the repo on github.com, then:
# git remote add origin https://github.com/<you>/my-picks-board.git
# git branch -M main
# git push -u origin main
```

## 2. Turn on GitHub Pages

Repo → **Settings → Pages** → Source: `Deploy from a branch` → Branch: `main` / `root`.
Your site goes live at `https://<you>.github.io/my-picks-board/`.

> **Privacy note:** GitHub Pages for a private repo requires GitHub Pro/Team.
> On the free plan, use a **public** repo — the URL isn't listed anywhere or
> indexed by search engines, so in practice only people you send the link to
> will find it. If you want real access control (so it's not just
> security-through-obscurity), put the site behind **Cloudflare Pages +
> Cloudflare Access** instead (free tier, restrict by email address) — ask me
> and I can walk you through that swap.

## 3. Point Claude Code at it

After your models produce their picks each run, have Claude Code:
1. Write the results into `data.json` in this repo, matching the schema below.
2. Set `updated_at` to the current UTC timestamp.
3. `git add data.json && git commit -m "Update picks" && git push`

GitHub Pages rebuilds automatically on push (usually live within ~30–60 seconds).

### Data schema

See **model-instructions.md** for the full spec to hand to your models — it
defines the betting model's tiers (top / medium / lean) and the player prop
model's per-sport minimums and parlay requirements. Quick summary:

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
      { "legs": 3, "odds": "+450", "selections": ["...", "...", "..."] }
    ]
  }
}
```

- `tier` — `"top"`, `"medium"`, or `"lean"`; the site groups betting picks under each automatically.
- `sport` — groups player props into sections (MLB, NFL, etc.) on the page.
- `confidence` — 0 to 1, drawn as the small bar.
- `edge` — a signed percentage; green if ≥ 0, red if negative.
- `parlays` — each needs `legs`, `selections` (the leg count and array length should match), and optionally `odds`.
- Add or drop rows freely each run; the page just re-renders from whatever's in the file.

## 4. Make it run on a schedule, not by hand

Claude Code has built-in scheduled tasks, so it can run this every day without you opening it:

**Desktop app:** sidebar → **Schedule** → **+ New task** →
- Prompt: *"Run my betting model and player prop model, write the results into
  data.json in ~/path/to/my-picks-board following the schema in
  model-instructions.md, then git commit and push."*
- Frequency: e.g. daily at 9:00 AM local time.
- Since this edits files and runs git commands, say **yes** when it asks
  whether the task should run autonomously.

**CLI:** use the built-in cron tool / `/loop` from inside a Claude Code
session in this repo, with the same prompt.

That's the whole loop: schedule fires → model runs → `data.json` updates →
push → Pages rebuilds → you and your friends refresh the link and see today's
board.
