# Who Authorized This Intrusion? — code and data

Artifacts for the report **"Who Authorized This Intrusion? A Ten-Step Authorization
Chain, a Coded Audit of Source Disagreement, and One Format-Level Demonstration"**,
submitted to the *AI Incident Response Sprint*
(Apart Research × CeSIA), September 2026.

Everything here is re-runnable from the two files in `data/`. No network access is
needed, no private data is included, and the whole pipeline finishes in a few seconds.

---

## What this repository contains

| Path | What it is |
|---|---|
| `data/claims_coded.csv` | **The dataset.** 50 factual claims about the July 2026 OpenAI / Hugging Face incident, each coded on 8 fields. English. |
| `data/claims_coded_zh_original.csv` | The Chinese original the coding was performed in. Both files carry the same 50 rows and produce identical statistics. |
| `codebook/codebook.md` | The coding rules: what counts as a factual claim, what each field means, and how conflicts were decided. |
| `analysis/analyze_claims.py` | Computes the divergence rate overall and per topic. Auto-detects Chinese or English headers. |
| `analysis/make_figure1.py` | Renders Figure 1 of the report. |
| `analysis/sensitivity.py` | Robustness check: recomputes the same dataset under three coding policies (see *Robustness* below). |
| `analysis/out/` | Output of the analysis (CSV + JSON), committed so you can diff against your own run. |
| `data/primary_read.md` | The two Hugging Face primary documents, with the URL, retrieval time and SHA-256 of the copy each relay-carried claim was re-verified against. |
| `experiment/verify_bypass_paths.py` | The format-level demonstration, **and** the metadata-only HDF5 scanner as a standalone tool. |
| `experiment/results_final.json` | Raw output of the experiment, including the library versions it ran under. |
| `experiment/SAFETY.md` | Dual-use boundary statement: what this experiment deliberately does *not* do. |
| `figures/figure1_divergence.png` | Figure 1 as it appears in the report. |

---

## Reproduce in two commands

```bash
pip install -r requirements.txt

# 1) divergence rate, overall and per topic
python3 analysis/analyze_claims.py data/claims_coded.csv --outdir /tmp/out

# 2) Figure 1
python3 analysis/make_figure1.py data/claims_coded.csv figures/figure1_copy.png
```

Expected output of step 1:

```
[OVERALL]
  no conflict (multi-source agreement)  12  ( 24.0%)
  conflict (sources disagree)           13  ( 26.0%)
  single source (undecidable)           25  ( 50.0%)
  divergence rate among multi-source claims     13/25 = 52.0%
  -> 25/50 claims (50.0%) rest on a single source and are excluded from every denominator

[BY TOPIC]
  topic                             n  conf  1src  multi    rate
  Containment and detection         4     1     3      1    100.0%
  Motive                            6     4     1      5     80.0%
  Responsibility and framing        7     4     2      5     80.0%
  Timeline                          9     4     2      7     57.1%
  Technical mechanism               8     0     5      3      0.0%
  Alignment training                4     0     1      3      0.0%
  Impact scope                      4     0     3      1      0.0%
  Scale                             8     0     8      0 undefined  <- no multi-source claims
```

Note the denominators. Four topics read 0.0% on 3, 3, 1 and 1 multi-source claims,
and Scale has none, so its rate is printed as **undefined** rather than zero. Read the
ordering, not the decimals.

If your numbers differ from these, the divergence measure is not reproducing and
**you should not use it** — please open an issue.

### Robustness: the ranking does not depend on the coding policy

```bash
python3 analysis/sensitivity.py data/claims_coded.csv
```

The one judgement the codebook cannot settle by itself is *what counts as a second
source*. `sensitivity.py` recomputes everything under three defensible policies:

| policy | what a second source may be | overall rate |
|---|---|---|
| P1 permissive | any second name in the source field, relays included | 13/30 = **43.3%** |
| P2 independence *(published)* | an independent source; a relay counts once, a party's own account counts once | 13/25 = **52.0%** |
| P3 strict | also outside the two parties — a party's account corroborates nothing | 13/21 = **61.9%** |

The level moves; the ordering does not. Motive 4/5, attribution 4/5 and timeline 4/7 in
all three; technical mechanism and alignment training 0/N in all three; Scale has no
multi-source claims in any of them.

### The same script runs on the Chinese original

```bash
python3 analysis/analyze_claims.py data/claims_coded_zh_original.csv --outdir /tmp/zh
```

The language is detected from the headers. Both files yield **identical** statistics
(50 claims, 13 conflicted, 25 single-source, 25 multi-source, rate 0.5200; Scale
undefined). Run both and diff them — that is the cheapest check that the mirror is
faithful.

---

## The experiment

```bash
# run all vectors; writes results.json
python3 experiment/verify_bypass_paths.py --json results.json

# or use the detector on its own, against a file or a directory
python3 experiment/verify_bypass_paths.py --scan /path/to/some.h5
python3 experiment/verify_bypass_paths.py --scan /path/to/a/dataset_dir/
```

The scanner reads **metadata only**. It does not dereference external storage, does
not read the target of any declaration, and does not modify its input. Read
`experiment/SAFETY.md` before pointing it at anything.

Environment the committed results were produced under (recorded in
`results_final.json`): Python 3.11.15, macOS 12.7.6, h5py 3.16.0, datasets 5.0.1,
Jinja2 3.1.6, PyArrow 25.0.1.

---

## Method in one paragraph

Every **factual** statement about the incident was extracted from each source read —
statements of the form "X happened", not opinions or evaluations. Each claim was coded
on topic, source type, date, verifiability, and whether other sources agree. A claim is
**conflicted** (`C1`) only if two or more sources address the same fact and give
incompatible accounts; a claim with a single source is `C2` and is **excluded from the
denominator**, because it cannot be in conflict with anything. The headline number is
therefore `conflicted / (total − single_source)`, not `conflicted / total`.

**A `C0` requires two or more *independent* sources.** A source that merely relays
another — a commentator quoting a vendor's blog, a party's own statement reproduced in
a news article — counts once, not twice. Where a primary document could not be read
directly, the claim is coded at the level of the source that could be read, and the
`source_type` field says so.

Both choices are the point. Including single-source claims in the denominator would let
a thin record look *more* reliable than it is; and counting a party's own account twice
because two outlets repeated it would manufacture agreement that does not exist.
**Half of this dataset (25 of 50 claims) is single-source**, and that number is a
result, not a nuisance.

---

## Known limitations

These are stated in the report and repeated here so nobody has to dig them out:

1. **No inter-coder reliability.** Coding was done by a single coder. A second coder
   would move these ratios. This is the largest limitation of the method.
2. **The sample is not random.** It is the sources that were available to us — eleven
   documents, two of them Hugging Face primary documents retrieved at origin after the
   first coding pass — not an exhaustive set; selection may be biased.
3. **Conflicted ≠ wrong.** `C1` means sources contradict each other. It does not mean
   any source is inaccurate, and we do not adjudicate.
4. **Version and access dependence.** Official statements exist in several revisions; we
   coded the locally archived versions. The two Hugging Face primary documents became
   retrievable at origin only after the first coding pass, so part of the technical record
   was first coded through relays. All 15 relay-carried rows were then re-verified against
   the primary text: 13 confirmed as coded, 2 adjusted, and **no conflict code changed**,
   so no rate moved. The re-verification is Appendix E of the report.
5. **Divergence is not reliability.** Two sources can disagree without either being
   wrong, and agree without either being right. What is measured is recorded
   disagreement inside a non-random sample. If that disagreement is driven mainly by
   journalistic style rather than factual conflict, the measure's explanatory power
   drops. We did not test this.
6. **Small denominators.** Topic rates rest on 1 to 7 multi-source claims; Scale has
   none. Treat the ranking as the finding, not the decimals.
7. **Claims, not disputes.** One disagreement can produce several coded claims, and one
   fact can appear under two topics. A `claim_group_id` is the next version of this
   table.
7. **Inherited limitations.** METR states its data came from OpenAI under a negotiated
   redaction agreement and that much of the analysis was delegated to AI agents, which
   METR itself cannot fully verify. Downstream conclusions inherit this.
8. **The experiment tests the library layer, not the platform layer.** There may be
   defensive layers in between that we did not model.
9. **Experiment n = 1 per vector.** This is a format-level demonstration, not
   statistical measurement, and it tests library behaviour only — not any deployed
   control and not any vendor's remediation. Vector T3 was inconclusive and is reported
   as such, not as a pass.

---

## Citation

```bibtex
@misc{zhu2026authorized,
  author       = {Zhu, Jiangbo},
  title        = {Who Authorized This Intrusion? A Ten-Step Authorization Chain,
                  a Coded Audit of Source Disagreement, and One Format-Level
                  Demonstration},
  year         = {2026},
  howpublished = {AI Incident Response Sprint, Apart Research × CeSIA},
  note         = {Track 2: what happened, and what fails next}
}
```

## License

Code: MIT (`LICENSE`). Dataset and text: CC BY 4.0.
