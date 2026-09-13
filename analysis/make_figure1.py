#!/usr/bin/env python3
"""Figure 1 - Recorded source divergence by topic.

Reads the coded claim dataset and renders a horizontal bar chart of the
divergence rate per topic (conflicted claims / multi-source claims).

Because the denominator is now reported, topics with no multi-source claims
at all are drawn as "no multi-source claims" instead of as a 0% bar.

Usage:
    python3 make_figure1.py                       # data/claims_coded.csv -> figures/figure1_divergence.png
    python3 make_figure1.py data/claims_coded.csv out.png

Works on either the English mirror or the Chinese original: the topic labels are
matched on the Chinese key, so pass the English file and the Chinese file yields
the same chart.
"""
from __future__ import annotations

import csv
import os
import math
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Chinese topic labels in the dataset -> English labels for the report
EN = {
    "责任与定性": "Attribution &\ncharacterization",
    "Responsibility and framing": "Attribution &\ncharacterization",
    "动机": "Motive",
    "时间线": "Timeline",
    "遏制与检测": "Containment\n& detection",
    "规模": "Scale",
    "技术手段": "Technical\nmechanism",
    "影响范围": "Impact scope",
    "对齐训练": "Alignment\ntraining",
}


def main(csv_path: str, out: str):
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        rows = list(reader)

    # The same script runs on the English mirror and the Chinese original.
    if "主题" in fields:
        k_topic, k_conflict = "主题", "冲突状态"
    else:
        k_topic, k_conflict = "topic", "conflict_status"

    by_topic = defaultdict(list)
    for r in rows:
        by_topic[r[k_topic]].append(r)

    data = []
    for topic, rs in by_topic.items():
        n = len(rs)
        cf = sum(1 for r in rs if r[k_conflict].strip()[:2].upper() == "C1")
        sg = sum(1 for r in rs if r[k_conflict].strip()[:2].upper() == "C2")
        multi = n - sg
        rate = (cf / multi * 100) if multi else 0.0
        data.append((rate, EN.get(topic, topic), n, cf, multi))
    # contested first, then the rest; topics with no denominator last
    data.sort(key=lambda x: (x[4] == 0, x[0]))

    labels = [d[1] for d in data]
    rates = [d[0] for d in data]
    ns = [d[2] for d in data]
    cf = [d[3] for d in data]
    multi = [d[4] for d in data]

    total = len(rows)
    total_cf = sum(1 for r in rows if r[k_conflict].strip()[:2].upper() == "C1")
    total_sg = sum(1 for r in rows if r[k_conflict].strip()[:2].upper() == "C2")
    overall = total_cf / (total - total_sg) * 100

    fig, ax = plt.subplots(figsize=(10.5, 5.4), dpi=220)
    y = list(range(len(labels)))

    for i, (r, m) in enumerate(zip(rates, multi)):
        if m == 0:
            ax.barh(i, 2, color="#c9ced6", height=0.62, zorder=3)
            ax.text(4.0, i, "no multi-source claims", va="center", ha="left",
                    fontsize=10.5, style="italic", color="#6b7686")
        else:
            ax.barh(i, r, color="#c2410c", height=0.62, zorder=3)
            ax.text(r + 2.4, i, f"{r:.1f}%", va="center", ha="left",
                    fontsize=11.5, fontweight="bold", color="#c2410c")
        ax.text(-1.6, i, f"{cf[i]}/{multi[i]}", va="center", ha="right",
                fontsize=10, color="#5a6473")

    ax.axvline(overall, color="#5a6473", linestyle="--", linewidth=1.2, zorder=2)
    ax.text(overall + 1.2, len(labels) - 0.35,
            f"all multi-source claims: {total_cf}/{total - total_sg} = {overall:.1f}%",
            fontsize=9.5, color="#5a6473", ha="left", va="center")

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=11)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Recorded divergence rate  (conflicted claims / multi-source claims)",
                  fontsize=11)
    ax.set_title("Divergence concentrates on \"why\" and \"whose fault\" — not on \"how\"",
                 fontsize=13.5, fontweight="bold", pad=14)

    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", color="#e3e7ec", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)

    fig.text(0.5, -0.02,
             f"n = {total} coded factual claims from 11 sources, all read at origin; "
             f"{total_sg} of them ({total_sg / total * 100:.0f}%) rest on a single source "
             f"and are excluded from every denominator.",
             ha="center", fontsize=8.6, color="#6b7686")

    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    print(f"saved {out}")
    for r, lab, n, c, m in sorted(data, key=lambda x: (x[4] == 0, -x[0])):
        print(f"  {lab.replace(chr(10),' '):26s} {r:5.1f}%  claims={n} conflicts={c} multi={m}")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        here, "..", "data", "claims_coded.csv")
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        here, "..", "figures", "figure1_divergence.png")
    main(src, dst)
