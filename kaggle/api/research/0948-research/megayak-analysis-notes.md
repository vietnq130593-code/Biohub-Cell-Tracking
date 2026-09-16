# megayak — The 0.966 Notebooks Used A Patched Metric Bug (notes)

---

# Appendix - the 0.966 Notebooks Used A Patched Metric Bug

Everything above is the tracking pipeline that produced this submission. What
follows is the analysis, and it changes nothing about the submission: it runs
afterwards and only reads the ground-truth graphs under `train/`.

# The 0.966 Notebooks Used A Metric Bug That Was Patched On July 17

Six public notebooks on this competition carry scores of 0.963–0.966. Reproducing
them today does not give you 0.966, and this notebook shows why: they exploited a
property of the division metric that the organisers removed on 2026-07-17.

It then measures the thing that is actually blocking the division term now, on all
199 training videos, on CPU, in about thirty seconds.

**What is in here**

1. What the exploit was, and the commit that closed it
2. A gate audit over every ground-truth division in the training set — 151 of them
3. What that says about where the remaining division score is

Predictions are cached from my own GPU kernel; this notebook re-runs no inference,
so it forks and runs on CPU in minutes.

## 1. The exploit

The 0.963 and 0.966 notebooks differ in six lines. Two of them matter:

```
- MAX_COMPONENTS = 1400        + MAX_COMPONENTS = 3000
- FORKS = 5                    + FORKS = 20
```

Those feed an `augment_dataset()` step that appends synthetic rows to the
submission:

```python
hub_id = next_id                       # t = -1000, (z, y, x) = (-10000, -10000, -10000)
new_edges = [row(dataset, "edge", source_id=hub_id, target_id=root)
             for root in roots]        # roots = the largest MAX_COMPONENTS tracks

for index in range(FORKS):             # a chain of FORKS fake divisions
    new_edges += [
        row(dataset, "edge", source_id=previous_id,  target_id=divider_id),
        row(dataset, "edge", source_id=divider_id,   target_id=child_id),
        row(dataset, "edge", source_id=divider_id,   target_id=continuation_id),
    ]
```

One hub node outside the volume, wired to the root of every track, plus a chain of
fake forks. Nothing near a real cell.

**Why it worked.** The division metric at the time required, for a ground-truth
division to count as a true positive:

> - **Single connected component.** All the matched predicted nodes above lie in
>   one connected component of the predicted graph.
> - **Contains a predicted fork.** The component includes at least one predicted
>   dividing node (a predicted cell with two outgoing edges).

The hub merges every track into one weakly connected component, satisfying the
first clause for every division at once. The fake forks satisfy the second. So any
ground-truth division whose parent and both daughters were merely *detected*
scored as a true positive. The division Jaccard goes to roughly 1.0, and it is
weighted 0.1 — which is most of the distance from 0.866 to 0.966.

**Why it no longer works.**

```
2026-07-17  aa65e90  updating metric to patch weakly connected component exploit
2026-06-26  b7a6192  Initial public release
```

`metrics.md` now reads, in as many words:

> Merely sharing a weakly connected component is not sufficient.

The rule is local: the fork must be the matched parent or its immediate successor,
and the two daughters must land on two distinct direct-child branches of that fork.
A hub at t = -1000 is not the immediate predecessor of anything real.

Those leaderboard entries are fossils of the old metric. The scores stand; the
method does not reproduce.

## 2. So what is blocking divisions now?

The division term is worth up to 0.100 and almost nobody is collecting it. Rather
than guess, this section replays the safe-division gates of the public
post-processing stack against **every ground-truth division in the training set**
and counts how many survive.

It reads only the 199 `.geff` ground-truth graphs — a few hundred bytes each. No
images, no model, no GPU.

### Gate-by-gate survival

Each gate is applied in the order the post-processing applies it. The number is how
many of the real divisions are still alive after that gate.

### The two gates that do the damage

`divergence` asks that the two grandchildren be at least 2.25 µm further apart than
the sisters were, one frame later. `symmetry` rejects a fork whose two
parent-to-daughter distances differ by more than 60% of their mean.

Both are described in the source as precision filters. Against real divisions they
behave like coin flips.

## 3. What this does and does not buy you

Opening both gates roughly triples how many real divisions are even *reachable*.
That is a necessary condition, not a sufficient one — I tested it end to end on
held-out videos with the official metric and the score went **down**:

| arm | forks proposed | division TP/FP/FN | adj edge Jaccard | score |
|---|---|---|---|---|
| gates as shipped (2.25 / 0.6) | 145 | 1 / 1 / 6 | 0.9383 | **0.9508** |
| gates open (−999 / off) | 541 | 0 / 19 / 7 | 0.9341 | 0.9341 |
| middle (0.0 / 1.2) | 541 | 0 / 17 / 7 | 0.9354 | 0.9354 |

Opening the gates takes the candidate pool from 141 to 1,586 in one video, and
`cap_skipped` goes from 0 to 43. The per-frame budget is about five slots and the
ranking key is `parent_dist + 0.15 * sister_dist` sorted ascending — pure geometry,
tightest pair first. Tightest pairs are duplicate detections, not divisions. The
budget gets spent before a real division is reached, and the one true positive that
existed is lost.

**So the binding constraint is the ranking, not the gates.** Anything that scores a
candidate fork on evidence rather than on how close the two points are should
recover this, and the gates have to come open at the same time or there is nothing
to rank.

One more thing worth knowing if you are tuning divisions: the offline division
metric in the widely-forked public stack is **not** the official one. Its
true-positive rule is weakly-connected-component reachability — the very thing
`metrics.md` now rules out. On the same predictions it reported a division Jaccard
of 0.2500 where `division_metrics.py` says **0.1250**. If you have been tuning
safe-division thresholds against it, you have been steering by a compass that reads
double.

## Summary

- The 0.963–0.966 public notebooks scored that way through a weakly-connected-component
  property of the division metric, removed in commit `aa65e90` on 2026-07-17. Those
  numbers are not reproducible under the current metric.
- Of 151 real divisions in the training set, the shipped gate stack leaves 35
  reachable. The divergence threshold of 2.25 µm sits at the median of the real
  distribution and the symmetry threshold of 0.6 at roughly its 60th percentile.
- Opening those gates alone makes things worse, because the fork budget is spent by
  a geometry-only ranker. The division term is a ranking problem.
- The offline division metric in the common public stack reports roughly double the
  official value. Check yours against `division_metrics.py` before trusting a sweep.

Ground truth read directly from the competition `train/*.geff` files. Everything
above runs on CPU.