"""Per-option usage report for the FrogPaper dropdowns.

Reads the `image_events` table written by Phase 1 — one row per option field per
generated image, plus favourite / wallpaper / delete events — and prints, for
every dropdown: uses, favourites, deletes, wallpaper sets, the source the image
came from, never-used options, and values typed by hand that are not in the list.

    python tools/option_report.py
    python tools/option_report.py --since 2026-11-01 --top 20
    python tools/option_report.py --field mood --top 0        # every option
    python tools/option_report.py --legacy                    # pre-Phase-1 database

A database that predates the event log has no `image_events` rows; `--legacy`
falls back to counting `prompt_params` alone, which gives uses but no
favourites, deletes or sources.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import app_prompt_data as data  # noqa: E402
import image_events  # noqa: E402

DEFAULT_DB = REPO_ROOT / "frogpaper.db"


def legacy_counts(db_path: Path, since: str | None) -> list[dict]:
    """Uses only, from `prompt_params` (databases written before Phase 1)."""
    if not db_path.exists():
        return []
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        query = "select params_json, updated_at from prompt_params"
        params: tuple = ()
        if since:
            query += " where updated_at >= ?"
            params = (since,)
        rows = con.execute(query, params).fetchall()
    except sqlite3.Error:
        return []
    finally:
        con.close()

    tally: dict[tuple, Counter] = defaultdict(Counter)
    for blob, _stamp in rows:
        try:
            params_dict = json.loads(blob) if blob else {}
        except (TypeError, ValueError):
            continue
        if not isinstance(params_dict, dict):
            continue
        source = params_dict.get("source") or "unknown"
        for field in image_events.FIELD_KEYS:
            value = (params_dict.get(field) or "").strip()
            tally[(field, value, source)]["uses"] += 1
    return [{"field": f, "value": v, "source": s, **counts} for (f, v, s), counts in tally.items()]


def report_field(name: str, options: list[str], rows: list[dict], top: int) -> list[str]:
    offered = {o.lower(): o for o in options if o}
    totals: Counter = Counter()
    per_source: dict[str, Counter] = defaultdict(Counter)
    source_names: dict[str, set] = defaultdict(set)

    for row in rows:
        if row["field"] != name:
            continue
        value = (row["value"] or "").lower()
        for key in ("uses", "favorites", "unfavorites", "deletes", "wallpaper_sets"):
            totals[key] += row.get(key) or 0
        for key in ("uses", "favorites", "deletes", "wallpaper_sets"):
            if row.get(key):
                per_source[value][key] += row[key]
        if row.get("source"):
            source_names[value].add(row["source"])

    out = [f"── {name} ── options {len(offered)} | picks {totals['uses']} | "
           f"favourites {totals['favorites']} | deletes {totals['deletes']} | "
           f"wallpapers {totals['wallpaper_sets']}"]
    if not totals["uses"] and not totals["deletes"]:
        out.append("   no recorded events yet")
        return out

    ranked = sorted(per_source.items(),
                    key=lambda kv: (-kv[1]["uses"], -kv[1]["deletes"], kv[0]))
    shown = ranked if top <= 0 else ranked[:top]
    for value, counts in shown:
        label = offered.get(value, f"{value}  (typed)")
        uses = counts["uses"]
        share = 100.0 * uses / totals["uses"] if totals["uses"] else 0.0
        extras = []
        if counts["favorites"]:
            extras.append(f"♥{counts['favorites']}")
        if counts["deletes"]:
            extras.append(f"✖{counts['deletes']}")
        if counts["wallpaper_sets"]:
            extras.append(f"▣{counts['wallpaper_sets']}")
        sources = sorted(source_names.get(value, ()))
        src_note = f"  [{' '.join(sources)}]" if len(sources) > 1 else ""
        tail = f"  {' '.join(extras)}" if extras else ""
        out.append(f"   {uses:>4}  {share:5.1f}%  {label}{tail}{src_note}")
    if top > 0 and len(ranked) > top:
        out.append(f"   ... {len(ranked) - top} more")

    used_values = set(per_source)
    never_used = sorted(v for k, v in offered.items() if k not in used_values)
    out.append(f"   never used: {len(never_used)}/{len(offered)}")
    if never_used:
        preview = ", ".join(never_used[:12])
        out.append(f"   e.g. {preview}{' ...' if len(never_used) > 12 else ''}")

    typed = [(v, c) for v, c in ranked if v not in offered]
    if typed:
        out.append("   typed by hand (not in the list):")
        for value, counts in typed[:10]:
            out.append(f"     {counts['uses']:>4}  {value}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--since", default=None, help="ISO date, e.g. 2026-11-01")
    parser.add_argument("--field", default=None, help="limit to one dropdown")
    parser.add_argument("--top", type=int, default=15, help="rows per dropdown; 0 = all")
    parser.add_argument("--legacy", action="store_true",
                        help="count prompt_params only (no favourites/deletes/sources)")
    args = parser.parse_args(argv)

    rows = image_events.counts(args.db, since=args.since)
    mode = "image_events"
    if args.legacy or not rows:
        rows = legacy_counts(args.db, args.since)
        mode = "prompt_params (legacy)"
        if not args.legacy and rows:
            print("note: no event rows yet, falling back to prompt_params — "
                  "uses only, no favourites/deletes/sources\n")

    picks = sum(r.get("uses") or 0 for r in rows)
    print(f"FrogPaper option report — source: {mode} — {picks} recorded picks"
          f" (one per field per image) from {args.db.name}"
          f"{f' since {args.since}' if args.since else ''}")
    print()

    fields = data.THEME_VARIABLE_OPTIONS
    if args.field:
        if args.field not in fields:
            print(f"unknown field {args.field!r}; choose from {', '.join(fields)}")
            return 2
        fields = {args.field: fields[args.field]}

    for name, options in fields.items():
        print("\n".join(report_field(name, options, rows, args.top)))
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
