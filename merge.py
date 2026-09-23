#!/usr/bin/env python3
"""
merge.py — the only script allowed to write data.json and record.json.

Neither model touches those files directly (see "Avoiding write conflicts"
in model-instructions.md). Each model writes its own scratch file; this
script combines them.

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

Scratch file shapes expected:
  betting_output.json        -> { "betting_model": [ ...picks with tier/confidence/edge... ] }
  props_output.json          -> { "player_props": { "picks": [...] }, "parlays": [...] }
  betting_graded_<date>.json -> { "betting_model": { "wins", "losses", "pushes", "units", "picks": [...] } }
  props_graded_<date>.json   -> { "player_props": { "wins", "losses", "pushes", "units", "picks": [...] }, "parlays": [...] }

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


def grade(args):
    betting = load(args.betting_graded)
    props = load(args.props_graded)

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

    empty_section = {"wins": 0, "losses": 0, "pushes": 0, "units": 0, "picks": []}
    day = {
        "date": args.date,
        "betting_model": betting.get("betting_model", empty_section),
        "player_props": props.get("player_props", empty_section),
        "parlays": props.get("parlays", betting.get("parlays", [])),
    }
    record["days"].append(day)

    with open(args.record, "w") as f:
        json.dump(record, f, indent=2)
    print(f"{args.date}: appended to {args.record}")


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

    args = parser.parse_args()
    args.func(args)
