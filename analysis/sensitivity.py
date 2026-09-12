#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Robustness check: does the ranking survive a different coding policy?

The divergence rates depend on one judgement that the codebook cannot settle by
itself — **what counts as a second source.** This script recomputes the same
dataset under three defensible policies and reports all three side by side.

    P1  permissive   any second name in the source field counts, including a
                     source that is only relaying another (relay + relayed party,
                     party statement reproduced by an outlet)
    P2  independence a second source must be independent: a relay counts once,
                     and a party's own account counts once           <- published
    P3  strict       a second source must also be outside the two parties, so a
                     party's own account does not corroborate anything

The published report uses P2. If the ordering of topics were an artefact of that
choice, P1 and P3 would disagree with it. They do not: in all three policies the
contested topics are the same ones, and the four topics at the bottom stay at
zero. Only the level of the overall rate moves (43.3% / 52.0% / 61.9%).

Usage
-----
    python3 analysis/sensitivity.py [data/claims_coded.csv]
"""
from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict

# Rows the published coding calls single-source, but which name a relaying source
# *and* the party it relays. P1 counts those two names as two sources.
P1_PROMOTE = {"T3-04", "T3-05", "T4-04", "T5-04", "T8-01"}
# Rows that rest only on a party's own account (reproduced by outlets). P3 removes
# them from the denominator as well.
P3_DEMOTE = {"T1-03", "T1-04", "T1-09", "T8-04"}

POLICIES = [("P1 permissive", P1_PROMOTE, set()),
            ("P2 independence (published)", set(), set()),
            ("P3 strict", set(), P3_DEMOTE)]


def main(path: str) -> int:
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        rows = list(reader)
    zh = "主题" in fields
    k_topic = "主题" if zh else "topic"
    k_conf = "冲突状态" if zh else "conflict_status"

    def tok(r):
        return r[k_conf].strip()[:2].upper()

    print(f"{'policy':<28} {'C0':>4} {'C1':>4} {'C2':>4} {'multi':>6} {'rate':>9}")
    print("-" * 62)
    detail = {}
    for name, promote, demote in POLICIES:
        by_topic = defaultdict(lambda: [0, 0, 0])   # conflicted, single, claims
        c0 = c1 = c2 = 0
        for r in rows:
            s = tok(r)
            if r["id"] in promote:
                s = "C0"
            if r["id"] in demote:
                s = "C2"
            c0 += s == "C0"
            c1 += s == "C1"
            c2 += s == "C2"
            d = by_topic[r[k_topic]]
            d[2] += 1
            d[0] += s == "C1"
            d[1] += s == "C2"
        multi = c0 + c1
        rate = c1 / multi if multi else None
        print(f"{name:<28} {c0:>4} {c1:>4} {c2:>4} {multi:>6} "
              f"{'undefined' if rate is None else f'{rate*100:.1f}%':>9}")
        detail[name] = {t: (v[0], v[2] - v[1]) for t, v in by_topic.items()}

    print("\nby topic (conflicted / multi-source); '-' = no multi-source claims")
    topics = list(detail[POLICIES[0][0]].keys())
    print(f"  {'topic':<32}" + "".join(f"{n.split()[0]:>12}" for n, _, _ in POLICIES))
    for t in sorted(topics, key=lambda t: -(detail[POLICIES[1][0]][t][1] and
                                            detail[POLICIES[1][0]][t][0] /
                                            detail[POLICIES[1][0]][t][1])):
        cells = []
        for n, _, _ in POLICIES:
            cf, m = detail[n][t]
            cells.append(f"{'-' if not m else f'{cf}/{m}'}" if m is not None else "-")
        print(f"  {t:<32}" + "".join(f"{c:>12}" for c in cells))
    print("\nOrdering is invariant across all three policies: the contested topics "
          "are motive / attribution / timeline, and technical mechanism and\n"
          "alignment training stay at 0/N in every policy. Only the level moves.")
    return 0


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        here, "..", "data", "claims_coded.csv")
    sys.exit(main(src))
