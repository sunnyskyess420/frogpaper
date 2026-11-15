"""Audit the FrogPaper dropdown option tables.

One command that reports the numbers the dropdown improvement plan keeps
quoting: option counts, duplicates, cross-list overlap, casing, near-duplicates,
colour-combination validity and (when a database is available) real usage.

    python tools/option_audit.py                 # report only
    python tools/option_audit.py --write-docs    # also refresh docs/option-baseline.md
    python tools/option_audit.py --json          # machine-readable

Exit status is 1 when a hard defect is present (duplicates, cross-list overlap,
bad casing, stray whitespace, colour words that only exist in the parse
vocabulary), so it can run in CI unchanged.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import app_prompt_data as data  # noqa: E402

DEFAULT_DB = REPO_ROOT / "frogpaper.db"
DOC_PATH = REPO_ROOT / "docs" / "option-baseline.md"

# Words that must never come back: shipped typos and obvious mis-filings.
BANNED_WORDS = ("unset haze",)
# Terms the plan calls out as belonging to another list.
MISFILED = {
    "lighting": ("arctic aurora", "sunset savanna", "rain", "snow"),
    "mood": (
        "cottagecore",
        "dark academia",
        "cyberpunk edge",
        "solarpunk optimism",
        "vaporwave nostalgia",
        "lo-fi calm",
        "gothic elegance",
    ),
}
LOW_CONTROL_MOODS = ("numb", "resigned", "raw", "vulnerable", "contemplative")


def lists() -> dict[str, list[str]]:
    return data.THEME_VARIABLE_OPTIONS


def real_options(options: list[str]) -> list[str]:
    return [o for o in options if o]


def find_duplicates(options: list[str]) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    dupes: list[tuple[str, str]] = []
    for option in options:
        key = option.strip().lower()
        if key in seen:
            dupes.append((seen[key], option))
        else:
            seen[key] = option
    return dupes


def find_cross_overlap(table: dict[str, list[str]]) -> list[tuple[str, str, str]]:
    hits: list[tuple[str, str, str]] = []
    names = list(table)
    for i, first in enumerate(names):
        first_set = {o.lower() for o in table[first]}
        for second in names[i + 1:]:
            shared = first_set & {o.lower() for o in table[second]}
            shared.discard("")
            for value in sorted(shared):
                hits.append((first, second, value))
    return hits


def find_near_duplicates(options: list[str], threshold: float = 0.75) -> list[tuple[str, str]]:
    """Pairs that differ too little to justify two entries."""
    pairs: list[tuple[str, str]] = []
    opts = real_options(options)
    for i, first in enumerate(opts):
        for second in opts[i + 1:]:
            a, b = first.lower(), second.lower()
            if a == b:
                continue
            tokens_a, tokens_b = set(a.split()), set(b.split())
            union = tokens_a | tokens_b
            score = len(tokens_a & tokens_b) / len(union) if union else 0.0
            contained = (a in b or b in a) and abs(len(a) - len(b)) <= 8
            if score >= threshold or contained:
                pairs.append((first, second))
    return pairs


def casing_anomalies(options: list[str]) -> list[str]:
    """Entries that start with a capital.

    Only the leading character matters: the house style is lower-case-leading,
    while proper nouns inside a phrase ("ancient Chinese palace garden") and
    names such as "3D render" are intentional.
    """
    return [o for o in real_options(options) if o[:1].isupper()]


def whitespace_anomalies(options: list[str]) -> list[str]:
    return [o for o in options if o != o.strip() or "  " in o]


def colour_report() -> dict:
    families = real_options(data.COLOR_FAMILIES)
    variations = real_options(data.COLOR_VARIATIONS)
    combos = [(f, v) for f in families for v in variations]
    blocked = [(f, v) for f, v in combos if not data.is_valid_color_combo(f, v)]
    return {
        "families": len(families),
        "variations": len(variations),
        "combinations": len(combos),
        "blocked": len(blocked),
        "blocked_samples": [f"{v} {f}" for f, v in blocked[:12]],
        "legacy_families": list(data.LEGACY_COLOR_FAMILIES),
        "legacy_variations": list(data.LEGACY_COLOR_VARIATIONS),
        "parse_only_words": sorted(
            {v for v in data.LEGACY_COLOR_VARIATIONS if v not in data.COLOR_VARIATIONS}
            | {f for f in data.LEGACY_COLOR_FAMILIES if f not in data.COLOR_FAMILIES}
        ),
    }


def usage_from_db(db_path: Path) -> dict[str, Counter]:
    """Per-field value counts from the prompt_params table (may be empty)."""
    usage: dict[str, Counter] = {name: Counter() for name in lists()}
    if not db_path.exists():
        return usage
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        rows = con.execute("select params_json from prompt_params").fetchall()
        con.close()
    except sqlite3.Error:
        return usage
    for (blob,) in rows:
        try:
            params = json.loads(blob) if blob else {}
        except (TypeError, ValueError):
            continue
        for field in usage:
            value = params.get(field)
            if isinstance(value, str) and value.strip():
                usage[field][value.strip().lower()] += 1
    return usage


def collect(db_path: Path = DEFAULT_DB) -> dict:
    table = lists()
    usage = usage_from_db(db_path)
    events: dict = {}
    try:
        import image_events
        events = image_events.summary(db_path)
    except Exception:  # pragma: no cover - optional
        pass
    fields = {}
    for name, options in table.items():
        used = usage[name]
        offered = {o.lower() for o in real_options(options)}
        fields[name] = {
            "count": len(real_options(options)),
            "duplicates": find_duplicates(options),
            "casing": casing_anomalies(options),
            "whitespace": whitespace_anomalies(options),
            "banned": [o for o in options if o.lower() in BANNED_WORDS],
            "misfiled": [o for o in options if o.lower() in MISFILED.get(name, ())],
            "low_control": [o for o in options if o.lower() in LOW_CONTROL_MOODS] if name == "mood" else [],
            "near_duplicates": find_near_duplicates(options),
            "used_distinct": len(used),
            "never_used": sorted(offered - set(used)),
            "off_list": dict(sorted(((v, c) for v, c in used.items() if v not in offered),
                                    key=lambda kv: -kv[1])),
        }
    return {
        "fields": fields,
        "cross_overlap": find_cross_overlap(table),
        "colour": colour_report(),
        "usage_rows": sum(usage["subject"].values()),
        "events": events,
        "db": str(db_path),
    }


def hard_defects(report: dict) -> list[str]:
    problems: list[str] = []
    for name, info in report["fields"].items():
        if info["duplicates"]:
            problems.append(f"{name}: duplicate entries {info['duplicates']}")
        if info["casing"]:
            problems.append(f"{name}: inconsistent casing {info['casing']}")
        if info["whitespace"]:
            problems.append(f"{name}: stray whitespace {info['whitespace']}")
        if info["banned"]:
            problems.append(f"{name}: banned strings {info['banned']}")
        if info["misfiled"]:
            problems.append(f"{name}: misfiled terms {info['misfiled']}")
    if report["cross_overlap"]:
        problems.append(f"cross-list overlap {report['cross_overlap']}")
    return problems


def render_text(report: dict) -> str:
    out: list[str] = []
    out.append("FrogPaper dropdown audit")
    out.append("=" * 60)
    out.append(f"prompt_params rows on record: {report['usage_rows']}  ({report['db']})")
    if report.get("events"):
        summary = ", ".join(f"{k} {v}" for k, v in sorted(report["events"].items()))
        out.append(f"image_events rows: {summary}")
    out.append("")
    out.append(f"{'dropdown':<12}{'options':>8}{'used':>7}{'never':>7}{'dupes':>7}{'near':>6}{'off-list':>9}")
    for name, info in report["fields"].items():
        out.append(
            f"{name:<12}{info['count']:>8}{info['used_distinct']:>7}"
            f"{len(info['never_used']):>7}{len(info['duplicates']):>7}"
            f"{len(info['near_duplicates']):>6}{len(info['off_list']):>9}"
        )
    out.append("")

    for name, info in report["fields"].items():
        if info["casing"]:
            out.append(f"[{name}] casing: {', '.join(info['casing'])}")
        if info["misfiled"]:
            out.append(f"[{name}] misfiled: {', '.join(info['misfiled'])}")
        if info["low_control"]:
            out.append(f"[{name}] not visibly renderable: {', '.join(info['low_control'])}")
        if info["banned"]:
            out.append(f"[{name}] banned: {', '.join(info['banned'])}")
        if info["near_duplicates"]:
            pairs = ", ".join(f"{a} ~ {b}" for a, b in info["near_duplicates"][:8])
            out.append(f"[{name}] near-duplicates ({len(info['near_duplicates'])}): {pairs}")
        if info["off_list"]:
            top = ", ".join(f"{v} x{c}" for v, c in list(info["off_list"].items())[:6])
            out.append(f"[{name}] typed by hand: {top}")
        if info["never_used"] and report["usage_rows"]:
            sample = ", ".join(info["never_used"][:10])
            out.append(f"[{name}] never used ({len(info['never_used'])}): {sample}")
    if report["cross_overlap"]:
        out.append("")
        out.append("cross-list overlap:")
        for first, second, value in report["cross_overlap"]:
            out.append(f"  - {value!r} in {first} and {second}")

    colour = report["colour"]
    out.append("")
    out.append(
        f"colour: {colour['families']} families x {colour['variations']} variations "
        f"= {colour['combinations']} combos ({colour['blocked']} blocked by the validity matrix)"
    )
    if colour["blocked_samples"]:
        out.append(f"  blocked e.g. {', '.join(colour['blocked_samples'])}")
    out.append(f"  parse-only legacy words: {len(colour['parse_only_words'])}")

    problems = hard_defects(report)
    out.append("")
    if problems:
        out.append("FAIL")
        for problem in problems:
            out.append(f"  - {problem}")
    else:
        out.append("PASS: no duplicates, no cross-list overlap, casing consistent")
    return "\n".join(out)


def render_markdown(report: dict) -> str:
    lines = [
        "# Dropdown option baseline",
        "",
        "Generated by `python tools/option_audit.py --write-docs`. Re-run it after any",
        "edit to `app_prompt_data.py` and diff this file to see what moved.",
        "",
        f"`prompt_params` rows on record: **{report['usage_rows']}** ({report['db']})",
        "",
        "| Dropdown | Options | Distinct used | Never used | Duplicates | Near-duplicates | Typed off-list |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, info in report["fields"].items():
        lines.append(
            f"| {name} | {info['count']} | {info['used_distinct']} | {len(info['never_used'])} | "
            f"{len(info['duplicates'])} | {len(info['near_duplicates'])} | {len(info['off_list'])} |"
        )
    colour = report["colour"]
    lines += [
        "",
        "## Colour",
        "",
        f"- {colour['families']} families x {colour['variations']} variations = "
        f"{colour['combinations']} combinations, {colour['blocked']} blocked as meaningless.",
        f"- Parse-only legacy words kept resolvable: {len(colour['parse_only_words'])}.",
    ]
    if colour["blocked_samples"]:
        lines.append(f"- Blocked examples: {', '.join(colour['blocked_samples'])}")
    lines += ["", "## Open items", ""]
    problems = hard_defects(report)
    if problems:
        lines += [f"- {problem}" for problem in problems]
    else:
        lines.append("- None: no duplicates, no cross-list overlap, casing consistent.")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite database to read usage from")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument("--write-docs", action="store_true", help=f"refresh {DOC_PATH.relative_to(REPO_ROOT)}")
    args = parser.parse_args(argv)

    report = collect(args.db)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(render_text(report))

    if args.write_docs:
        DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
        DOC_PATH.write_text(render_markdown(report), encoding="utf-8")
        print(f"\nwrote {DOC_PATH.relative_to(REPO_ROOT)}")

    return 1 if hard_defects(report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
