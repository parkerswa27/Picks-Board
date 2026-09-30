#!/usr/bin/env python3
"""
merge.py — the only script allowed to write data.json and record.json.

Neither model touches those files directly (see "Avoiding write conflicts"
in model-instructions.md -- that section is real again as of 9/23/26: the repo
had been carrying the v1 spec under that name, which never had it). Each model
writes its own scratch file; this script combines them.

Usage:

  # Publish today's picks -> data.json
  python3 merge.py publish \
      --betting betting_output.json \
      --props props_output.json \
      --out data.json

  # Close out a graded day -> append one entry to record.json
  python3 merge.py grade --date 2026-09-22 \
      --betting-graded betting_graded_2026-09-22.json \
      --props-graded props_graded_2026-09-22.json \
      --record record.json

  # Backfill parlay stake/units onto days already in record.json (idempotent)
  python3 merge.py parlay-units --record record.json

Scratch file shapes expected:
  betting_output.json        -> { "betting_model": [ ...picks with tier/confidence/edge... ] }
  props_output.json          -> { "player_props": { "picks": [...] }, "parlays": [...] }
  betting_graded_<date>.json -> { "betting_model": { "wins", "losses", "pushes", "units", "picks": [...] } }
  props_graded_<date>.json   -> { "player_props": { "wins", "losses", "pushes", "units", "picks": [...] }, "parlays": [...] }
  (or the graders' raw output {"fully_graded", "picks": [...]} -- totals are computed here,
   and a day that is not fully_graded is refused)

Adjust field names below if your models' scratch files differ — this is a
starting point, not a fixed contract.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def load(path):
    p = Path(path)
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)


def publish(args):
    betting = load(args.betting)
    props = load(args.props)
    if betting is None or props is None:
        print(
            f"Missing scratch file — betting={args.betting!r} "
            f"({'ok' if betting else 'MISSING'}), props={args.props!r} "
            f"({'ok' if props else 'MISSING'}). Not writing {args.out}.",
            file=sys.stderr,
        )
        sys.exit(1)

    combined = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "betting_model": betting.get("betting_model", []),
        "player_props": props.get("player_props", {"picks": [], "parlays": []}),
    }
    if "parlays" in props and "parlays" not in combined["player_props"]:
        combined["player_props"]["parlays"] = props["parlays"]

    with open(args.out, "w") as f:
        json.dump(combined, f, indent=2)
    print(f"Wrote {args.out}")

    # The graders read archive/board_<date>.json -- what the site actually showed that
    # day. Writing it here means no run has to remember a separate copy step.
    dates = {d for d in (betting.get("date"), props.get("date")) if d}
    if len(dates) == 1:
        snap = Path(args.out).resolve().parent / "archive" / f"board_{dates.pop()}.json"
        snap.parent.mkdir(exist_ok=True)
        with open(snap, "w") as f:
            json.dump(combined, f, indent=2)
        print(f"Wrote {snap}")
    else:
        print(f"  ! scratch files disagree on / lack a date ({dates or 'none'}) — "
              f"archive snapshot NOT written; grading will have nothing to read", file=sys.stderr)


PICK_KEYS = {
    "betting_model": ("sport", "matchup", "market", "pick", "tier", "stake", "odds", "result", "note", "basis", "locked",
                      "model_gap_pts", "neutral_site"),
    "player_props": ("player", "market", "pick", "tier", "stake", "odds", "result", "note", "basis"),
}


def net_units(p):
    """Spec "Unit sizing": a win nets stake x payout at the pick's own odds, a loss costs
    the stake, a push is 0."""
    stake, res = float(p.get("stake", 0)), p["result"]
    if res == "push":
        return 0.0
    if res == "loss":
        return -stake
    o = int(p["odds"])
    return stake * (o / 100 if o > 0 else 100 / -o)


def parlay_rows(date, graded_parlays, record_path):
    """Graded parlays -> record rows, with stake and units (spec "Parlay units", 9/30/26).
    Stake comes from the board the site actually published (archive/board_<date>.json),
    matched by position and odds -- the graders don't carry it. A parlay that was never
    sized (no stake on the published board: every parlay before 9/28) gets NO stake/units
    keys rather than a backdated one. An estimated "~" price is not placeable, so it is
    0 units win or lose. Returns (rows, problem)."""
    snap = Path(record_path).resolve().parent / "archive" / f"board_{date}.json"
    board = load(snap) or {}
    pub = board.get("player_props", {}).get("parlays") or board.get("parlays") or []
    rows = []
    for i, p in enumerate(graded_parlays):
        row = {k: p[k] for k in ("legs", "odds", "result", "note") if k in p}
        src = pub[i] if i < len(pub) else None
        if src is not None and src.get("odds") != p.get("odds"):
            return None, f"PARLAY ODDS MISMATCH — parlay {i} graded at {p.get('odds')} but {snap.name} published {src.get('odds')}"
        stake = (src or {}).get("stake")
        if stake is not None:
            row["stake"] = stake
            if str(p["odds"]).startswith("~"):
                row["units"] = 0.0
            elif p["result"] == "win" and "note" in p:
                # a void leg dropped out: the ticket paid a reduced price that the stored odds
                # don't show, so the payout can't be computed from this row
                return None, f"VOID-LEG PARLAY WIN — parlay {i} ({p['odds']}) won with a void leg; the reduced price is not in the stored odds, so its units must be set by hand"
            else:
                row["units"] = round(net_units({"stake": stake, "odds": p["odds"], "result": p["result"]}), 2)
        rows.append(row)
    return rows, None


def section(graded, name):
    """Accept either shape:
      * grader output (board_betting.py / board_props.py --grade):
          {"date", "fully_graded", "picks": [...], ...}  -> totals computed here
      * already-summed: {name: {"wins", "losses", "pushes", "units", "picks"}}
    Returns (section, problem) -- problem is a reason this day can't close yet."""
    if name in graded and "wins" in graded[name]:
        return graded[name], None
    if "picks" not in graded:
        return None, "unrecognised graded-file shape"
    if not graded.get("fully_graded"):
        left = graded.get("ungraded") or graded.get("unresolved") or "?"
        return None, f"not fully graded (outstanding: {left})"
    picks = [{k: p[k] for k in PICK_KEYS[name] if k in p} for p in graded["picks"]]
    return {
        "wins": sum(p["result"] == "win" for p in picks),
        "losses": sum(p["result"] == "loss" for p in picks),
        "pushes": sum(p["result"] == "push" for p in picks),
        "units": round(sum(net_units(p) for p in picks), 2),
        "picks": picks,
    }, None


def grade(args):
    betting = load(args.betting_graded)
    props = load(args.props_graded)

    if betting is not None and props is not None:
        bsec, bwhy = section(betting, "betting_model")
        psec, pwhy = section(props, "player_props")
        if bwhy or pwhy:
            print(f"{args.date}: not closing this day — betting: {bwhy or 'ok'}, "
                  f"props: {pwhy or 'ok'}. Will retry on a future run.")
            return

    if betting is None or props is None:
        print(
            f"{args.date}: not closing this day — "
            f"betting graded={'ok' if betting else 'MISSING'}, "
            f"props graded={'ok' if props else 'MISSING'}. "
            f"Will retry on a future run once both exist."
        )
        return

    record = load(args.record) or {"start_date": args.date, "days": []}

    if any(d["date"] == args.date for d in record["days"]):
        print(f"{args.date}: already recorded in {args.record}, skipping.")
        return

    if args.date < record.get("start_date", args.date):
        print(
            f"{args.date}: earlier than start_date {record['start_date']} — "
            f"refusing to backfill a day the site never published."
        )
        return

    parlays, why = parlay_rows(args.date, props.get("parlays", betting.get("parlays", [])), args.record)
    if why:
        # Not a pending day: re-running will refuse it again until someone fixes the data.
        print(f"!! {args.date}: MANUAL CHECK NEEDED — day NOT closed: {why}. "
              f"Retrying will not fix this; see model-instructions.md \"Parlay units (9/30/26)\".")
        return

    day = {
        "date": args.date,
        "betting_model": bsec,
        "player_props": psec,
        "parlays": parlays,
    }
    record["days"].append(day)

    with open(args.record, "w") as f:
        json.dump(record, f, indent=2)
    print(f"{args.date}: appended to {args.record}")


def parlay_units(args):
    """Backfill stake/units onto parlays already in record.json (days closed before
    parlay_rows existed). Recomputes from each day's own graded rows + its archived
    board; touches nothing but the parlays lists. Idempotent."""
    record = load(args.record)
    changed = 0
    for day in record["days"]:
        rows, why = parlay_rows(day["date"], day.get("parlays", []), args.record)
        if why:
            sys.exit(f"{day['date']}: {why} -- record.json not written")
        if rows != day.get("parlays", []):
            day["parlays"] = rows
            changed += 1
        for r in rows:
            u = f"{r['units']:+.2f}u" if "units" in r else "no stake (unsized)"
            print(f"  {day['date']}  {r['odds']:>7}  {r['result']:<5} {u}")
    total = sum(r.get("units", 0) for d in record["days"] for r in d.get("parlays", []))
    with open(args.record, "w") as f:
        json.dump(record, f, indent=2)
    print(f"{changed} day(s) updated; parlay units total {total:+.2f}u")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pub = sub.add_parser("publish", help="Combine today's scratch files into data.json")
    p_pub.add_argument("--betting", required=True)
    p_pub.add_argument("--props", required=True)
    p_pub.add_argument("--out", required=True)
    p_pub.set_defaults(func=publish)

    p_grade = sub.add_parser("grade", help="Append one graded day to record.json")
    p_grade.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_grade.add_argument("--betting-graded", required=True)
    p_grade.add_argument("--props-graded", required=True)
    p_grade.add_argument("--record", required=True)
    p_grade.set_defaults(func=grade)

    p_pu = sub.add_parser("parlay-units", help="Backfill parlay stake/units onto record.json days")
    p_pu.add_argument("--record", required=True)
    p_pu.set_defaults(func=parlay_units)

    args = parser.parse_args()
    args.func(args)
