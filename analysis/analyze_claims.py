#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Source-divergence analysis over the coded claim dataset.

Reads the coded claim dataset (English or Chinese column headers - auto-detected)
and reports, per topic:

    divergence rate = conflicted claims / multi-source claims

Single-source claims are EXCLUDED from the denominator, because a claim with only
one source cannot be in conflict with anything. Including them would silently
deflate every rate.

Usage
-----
    python3 analyze_claims.py [dataset.csv] [--outdir DIR]

Default dataset: ../data/claims_coded.csv   (English mirror)
Use ../data/claims_coded_zh_original.csv for the Chinese original.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict

# Column header vocabulary, so the same script runs on either language.
COLS = {
    "en": {"id": "id", "topic": "topic", "claim": "claim",
           "source_type": "source_type", "date": "date",
           "verifiability": "verifiability", "conflict": "conflict_status"},
    "zh": {"id": "id", "topic": "主题", "claim": "陈述",
           "source_type": "来源类型", "date": "日期",
           "verifiability": "可核实性", "conflict": "冲突状态"},
}

# Canonical values, keyed by the token that appears in both languages.
CONFLICT = {
    "C0": ("no conflict (multi-source agreement)", "无冲突（多源一致）"),
    "C1": ("conflict (sources disagree)", "有冲突（来源说法不一致）"),
    "C2": ("single source (undecidable)", "单源（无法判断）"),
}
VERIF = {
    "V1": ("verifiable", "可核实"),
    "V2": ("partially verifiable", "部分可核实"),
    "V3": ("not verifiable", "不可核实"),
    "V4": ("structurally unverifiable", "结构性不可核实"),
}
TOPIC_EN = {
    "时间线": "Timeline", "技术手段": "Technical mechanism", "规模": "Scale",
    "责任与定性": "Responsibility and framing", "动机": "Motive",
    "遏制与检测": "Containment and detection", "对齐训练": "Alignment training",
    "影响范围": "Impact scope",
}


def token(value: str) -> str:
    """'C1有冲突' / 'C1 conflict' -> 'C1'."""
    return value.strip()[:2].upper()


def detect_lang(fieldnames: list[str]) -> str:
    """Chinese if any Chinese header (or a *_zh suffixed header) is present."""
    zh_markers = ("主题", "冲突状态", "陈述", "来源类型",
                  "topic_zh", "claim_zh", "conflict_status_zh")
    return "zh" if any(f in fieldnames for f in zh_markers) else "en"


def label(tok: str, table: dict, lang: str) -> str:
    return table.get(tok, ("?", "?"))[1 if lang == "zh" else 0]


def pct(rate: float | None) -> str:
    """Format a rate, or 'undefined' when the denominator is empty."""
    return "undefined" if rate is None else f"{rate * 100:.1f}%"


def num(rate: float | None) -> str:
    return "" if rate is None else f"{rate:.4f}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", nargs="?", default=None)
    ap.add_argument("--outdir", default=None,
                    help="where to write the CSV/JSON outputs (default: alongside the dataset)")
    args = ap.parse_args(argv)

    here = os.path.dirname(os.path.abspath(__file__))
    path = args.dataset or os.path.join(here, "..", "data", "claims_coded.csv")
    path = os.path.abspath(path)
    outdir = os.path.abspath(args.outdir or os.path.dirname(path))
    os.makedirs(outdir, exist_ok=True)

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        lang = detect_lang(reader.fieldnames or [])
        col = COLS[lang]
        rows = list(reader)

    total = len(rows)
    if total == 0:
        print("empty dataset", file=sys.stderr)
        return 2

    print("=" * 78)
    print(f"Source-divergence analysis  |  {os.path.basename(path)}")
    print(f"header language: {lang}  |  claims: {total}")
    print("=" * 78)

    # ---------- overall ----------
    c = Counter(token(r[col["conflict"]]) for r in rows)
    conflicted = c.get("C1", 0)
    single = c.get("C2", 0)
    multi = total - single
    overall = conflicted / multi if multi else None

    print("\n[OVERALL]")
    for k in ("C0", "C1", "C2"):
        print(f"  {label(k, CONFLICT, lang):34s} {c.get(k,0):3d}  "
              f"({c.get(k,0)/total*100:5.1f}%)")
    print(f"  {'divergence rate among multi-source claims':34s} "
          f"{conflicted}/{multi} = {pct(overall)}")
    print(f"  -> {single}/{total} claims ({single/total*100:.1f}%) rest on a single "
          f"source and are excluded from every denominator")

    # ---------- by topic ----------
    by_topic = defaultdict(list)
    for r in rows:
        by_topic[r[col["topic"]]].append(r)

    ranked = []
    for topic, rs in by_topic.items():
        n = len(rs)
        cf = sum(1 for r in rs if token(r[col["conflict"]]) == "C1")
        sg = sum(1 for r in rs if token(r[col["conflict"]]) == "C2")
        m = n - sg
        ranked.append((cf / m if m else None, topic, n, cf, sg, m))
    # contested topics first (by rate), topics with no denominator last
    ranked.sort(key=lambda x: (x[0] is None, -(x[0] or 0.0)))

    print("\n[BY TOPIC]")
    print(f"  {'topic':<30} {'n':>4} {'conf':>5} {'1src':>5} {'multi':>6} {'rate':>7}")
    print("  " + "-" * 62)
    for rate, topic, n, cf, sg, m in ranked:
        name = TOPIC_EN.get(topic, topic)
        note = "  <- no multi-source claims" if rate is None else ""
        print(f"  {name:<30} {n:>4} {cf:>5} {sg:>5} {m:>6} {pct(rate):>9}{note}")

    # ---------- by verifiability ----------
    v = Counter(token(r[col["verifiability"]]) for r in rows)
    print("\n[BY VERIFIABILITY]")
    for k in ("V1", "V2", "V3", "V4"):
        if v.get(k):
            print(f"  {label(k, VERIF, lang):34s} {v[k]:3d}  ({v[k]/total*100:5.1f}%)")

    # ---------- cross-tab: verifiability of CONFLICTED claims ----------
    cv = Counter(token(r[col["verifiability"]]) for r in rows
                 if token(r[col["conflict"]]) == "C1")
    print("\n[CROSS] verifiability of the conflicted claims")
    for k, n in cv.most_common():
        print(f"  {label(k, VERIF, lang):34s} {n:3d}")
    # a conflicted claim whose own source is unverifiable is worth flagging
    hard = cv.get("V3", 0) + cv.get("V4", 0)
    if hard:
        print(f"  -> {hard}/{conflicted} conflicts involve claims resting on "
              f"unverifiable sourcing")

    # ---------- outputs ----------
    p1 = os.path.join(outdir, "analysis_by_topic.csv")
    with open(p1, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["topic", "claims", "conflicted", "single_source",
                    "multi_source", "divergence_rate"])
        for rate, topic, n, cf, sg, m in ranked:
            w.writerow([TOPIC_EN.get(topic, topic), n, cf, sg, m, num(rate)])

    p2 = os.path.join(outdir, "analysis_summary.csv")
    with open(p2, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerow(["claims_total", total])
        w.writerow(["conflicted_C1", conflicted])
        w.writerow(["single_source_C2", single])
        w.writerow(["no_conflict_C0", c.get("C0", 0)])
        w.writerow(["multi_source", multi])
        w.writerow(["divergence_rate_multi_source", num(overall)])
        w.writerow(["divergence_rate_all_claims", f"{conflicted/total:.4f}"])

    p3 = os.path.join(outdir, "analysis_summary.json")
    with open(p3, "w", encoding="utf-8") as f:
        json.dump({
            "dataset": os.path.basename(path),
            "header_language": lang,
            "claims_total": total,
            "conflicted": conflicted,
            "single_source": single,
            "multi_source": multi,
            "divergence_rate_multi_source": (
                None if overall is None else round(overall, 4)),
            "by_topic": [
                {"topic": TOPIC_EN.get(t, t), "claims": n, "conflicted": cf,
                 "single_source": sg, "multi_source": m,
                 "rate": None if r is None else round(r, 4)}
                for r, t, n, cf, sg, m in ranked
            ],
            "by_verifiability": {k: v[k] for k in ("V1", "V2", "V3", "V4") if v.get(k)},
        }, f, ensure_ascii=False, indent=2)

    print(f"\nwrote {os.path.basename(p1)} / {os.path.basename(p2)} / "
          f"{os.path.basename(p3)}  ->  {outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
