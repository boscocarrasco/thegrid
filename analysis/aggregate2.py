#!/usr/bin/env python3.12
"""Round-2 tables. Everything in RESULTS2.md is generated here, never typed.

Two things differ from round 1's `aggregate.py`, both because of what round 1
could not resolve:

**Paired.** Every arm runs every task at every repetition index, so a
comparison is made on the within-pair difference at `(task, rep)` rather than
on means between arms. Most of the variance in this harness comes from the
task, and pairing removes it. Unpaired means are still reported, as secondary.

**Variance is a result, not a diagnostic.** For every cell the spread across
repetitions is reported next to the mean. Where it is large that is a
statement about how underpowered the experiment is, and it belongs in the
report rather than in a footnote.

    /usr/bin/python3.12 analysis/aggregate2.py results/raw2/*.jsonl > RESULTS2.md
"""
from __future__ import annotations

import glob
import json
import random
import statistics as st
import sys
from collections import defaultdict

BOOT = 5000
RNG = random.Random(20260911)


# ------------------------------------------------------------------ loading

def load(paths):
    rows = []
    for p in paths:
        for line in open(p):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def usable(rows):
    """Runs that measured something.

    A run stopped by the provider's quota is not a failure of the arm, and a
    harness error is not a failure of the task. Both are excluded here and
    counted separately, because silently scoring them as losses would bias
    every table toward whichever arm happened to run while the quota was open.
    """
    return [r for r in rows
            if r.get("terminated") not in ("rate_limited", "harness_error",
                                           "model_error")]


def cell(r):
    """What distinguishes one experimental condition from another."""
    return (r["arm"], r.get("image_window"), bool(r.get("task_object")),
            r.get("dropped_enrichment") or "", r.get("token_budget"))


# ------------------------------------------------------------- statistics

def boot_ci(vals, stat=st.mean, n=BOOT, alpha=0.05):
    vals = [v for v in vals if v is not None]
    if not vals:
        return (float("nan"),) * 3
    if len(vals) == 1:
        return (vals[0], vals[0], vals[0])
    point = stat(vals)
    draws = []
    k = len(vals)
    for _ in range(n):
        draws.append(stat([vals[RNG.randrange(k)] for _ in range(k)]))
    draws.sort()
    lo = draws[int(alpha / 2 * n)]
    hi = draws[int((1 - alpha / 2) * n) - 1]
    return point, lo, hi


def overlaps(a, b):
    return not (a[2] < b[1] or b[2] < a[1])


def pair_key(r):
    """What makes two runs comparable: same tier, same task, same repetition.

    `run_tag` is in the key deliberately. Tiers overlap on tasks — the budget
    sweeps re-run five tasks the control tier already ran — so keying on
    (task, rep) alone would pair a run truncated at an 8,000-token ceiling
    against an unconstrained run of the same task, and would silently drop
    every duplicate but the last. Both are wrong in the same direction: they
    mix conditions and then report the mixture as a controlled difference.
    """
    return (r.get("run_tag"), r["task"], r.get("rep"))


def paired(rows_a, rows_b, field, across=False):
    """Differences at matching (run_tag, task, rep). Returns (diffs, n, orphan).

    Pairing is what makes an N of five informative here: the same task at the
    same repetition index, run on two arms, differs by the arm and by decoding
    noise, and nothing else. Comparing arm means instead would drown that in
    the spread between tasks, which is an order of magnitude larger.

    `across=True` drops run_tag from the key, and is only correct where the tag
    *is* the condition being manipulated: the ablation arms ran in their own
    tier, and experiment 4's image window and task object are one tag each.
    There the two sides differ by the manipulated variable and by when they
    ran, which is a weaker control than a tier that interleaves its arms — so
    every table that uses it says so.
    """
    key = (lambda r: (r["task"], r.get("rep"))) if across else pair_key
    idx_a = {key(r): r for r in rows_a}
    idx_b = {key(r): r for r in rows_b}
    keys = sorted(set(idx_a) & set(idx_b))
    diffs = []
    for k in keys:
        va, vb = idx_a[k].get(field), idx_b[k].get(field)
        if va is None or vb is None:
            continue
        diffs.append(float(vb) - float(va))
    orphan = len(set(idx_a) ^ set(idx_b))
    return diffs, len(diffs), orphan


def fresh(r):
    return (r.get("tokens_in", 0) + r.get("tokens_out", 0)
            + r.get("tokens_cache_create", 0))


def fmt(p, lo, hi, dp=2):
    if p != p:
        return "—"
    return f"{p:.{dp}f} [{lo:.{dp}f}, {hi:.{dp}f}]"


def spread(vals):
    """Standard deviation across repetitions, as a number the report shows."""
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return float("nan")
    return st.pstdev(vals)


# ------------------------------------------------------------------ tables

MENU_GROUP = ["text_replace", "calc_add_row", "files_rename",
              "menu_replace_all", "menu_save_as_subdir",
              "menu_calc_insert_column", "menu_files_new_folder"]

CONTROL_GROUP = ["files_new_note", "files_save_as", "text_append",
                 "text_delete_line", "text_uppercase", "calc_total",
                 "calc_count_eng", "web_form", "visual_chart",
                 "visual_shapes", "visual_badge", "cross_report_summary",
                 "cross_inventory_note", "vdelta_rows", "vdelta_bars"]

DEFECT_THREE = ["text_replace", "calc_add_row", "files_rename"]


def by_arm(rows):
    d = defaultdict(list)
    for r in rows:
        d[r["arm"]].append(r)
    return d


def header(rows, all_rows):
    excluded = [r for r in all_rows if r not in rows]
    rl = [r for r in all_rows if r.get("terminated") == "rate_limited"]
    waited = sum(r.get("rate_limit_wait_s", 0) or 0 for r in all_rows)
    print("# RESULTS2 — round 2, generated from results/raw2/")
    print()
    print("Every table in this file is produced by `analysis/aggregate2.py` "
          "from the raw run records. Nothing here is typed by hand.")
    print()
    print(f"- usable runs: **{len(rows)}**")
    print(f"- excluded (rate limit, harness or model error): {len(excluded)}"
          f" — of which {len(rl)} rate-limited")
    print(f"- total time spent waiting out provider rate limits: "
          f"{waited / 60:.1f} min")
    est = sum(r.get("cost_usd", 0) or 0 for r in rows)
    print(f"- **estimated** cost of the usable runs: ${est:.2f} — computed "
          f"from token counts and the published rate, not observed spend; "
          f"this runs on a subscription and there is no bill to read")
    print()


def table_headline(rows):
    print("## 1. Headline, by arm")
    print()
    print("| Arm | n | success | steps | fresh tokens | image tokens "
          "| est. $ | grounding fails |")
    print("|---|---|---|---|---|---|---|---|")
    for arm, rs in sorted(by_arm(rows).items()):
        print(f"| {arm} | {len(rs)} "
              f"| {fmt(*boot_ci([1.0 if r['success'] else 0.0 for r in rs]), 3)} "
              f"| {fmt(*boot_ci([r['steps'] for r in rs]), 2)} "
              f"| {fmt(*boot_ci([fresh(r) for r in rs]), 0)} "
              f"| {fmt(*boot_ci([r.get('image_tokens', 0) for r in rs]), 0)} "
              f"| {fmt(*boot_ci([r.get('cost_usd', 0) for r in rs]), 4)} "
              f"| {fmt(*boot_ci([r.get('grounding_failures', 0) for r in rs]), 2)} |")
    print()
    print("All dollar figures are **estimated** from tokens, not observed.")
    print()


def table_paired(rows, base, treat, task_ids, label):
    a = [r for r in rows if r["arm"] == base and r["task"] in task_ids]
    b = [r for r in rows if r["arm"] == treat and r["task"] in task_ids]
    if not a or not b:
        print(f"*{label}: not run ({base} n={len(a)}, {treat} n={len(b)}).*")
        print()
        return None
    print(f"### {label}")
    print()
    print(f"| metric | {base} mean | {treat} mean | paired diff "
          f"({treat} − {base}) | pairs | verdict |")
    print("|---|---|---|---|---|---|")
    out = {}
    for field, dp in (("steps", 2), ("success", 3), ("model_calls", 2),
                      ("cost_usd", 4)):
        va = [float(r[field]) for r in a if r.get(field) is not None]
        vb = [float(r[field]) for r in b if r.get(field) is not None]
        diffs, npairs, orphan = paired(a, b, field)
        if not diffs:
            continue
        d = boot_ci(diffs)
        verdict = ("no detectable difference at this N"
                   if d[1] <= 0 <= d[2] else
                   (f"**{treat} lower**" if d[0] < 0 else f"**{treat} higher**"))
        print(f"| {field} | {st.mean(va):.{dp}f} | {st.mean(vb):.{dp}f} "
              f"| {fmt(*d, dp)} | {npairs} | {verdict} |")
        out[field] = d
    print()
    return out


def table_variance(rows, task_ids, label):
    print(f"### Variance across repetitions — {label}")
    print()
    print("Spread within a cell is how underpowered the experiment is, so it "
          "is reported rather than smoothed away.")
    print()
    print("| arm | task | n | mean steps | sd steps | successes |")
    print("|---|---|---|---|---|---|")
    groups = defaultdict(list)
    for r in rows:
        if r["task"] in task_ids:
            groups[(r["arm"], r["task"])].append(r)
    for (arm, task), rs in sorted(groups.items()):
        steps = [r["steps"] for r in rs]
        sd = spread(steps)
        print(f"| {arm} | {task} | {len(rs)} | {st.mean(steps):.1f} "
              f"| {'—' if sd != sd else f'{sd:.1f}'} "
              f"| {sum(1 for r in rs if r['success'])}/{len(rs)} |")
    print()


def table_by_task(rows):
    print("## Per task")
    print()
    arms = sorted({r["arm"] for r in rows})
    print("| task | " + " | ".join(f"{a} succ" for a in arms) + " | "
          + " | ".join(f"{a} steps" for a in arms) + " |")
    print("|---" * (1 + 2 * len(arms)) + "|")
    tasks = sorted({r["task"] for r in rows})
    for t in tasks:
        succ, steps = [], []
        for a in arms:
            rs = [r for r in rows if r["task"] == t and r["arm"] == a]
            if rs:
                succ.append(f"{sum(1 for r in rs if r['success'])}/{len(rs)}")
                steps.append(f"{st.mean([r['steps'] for r in rs]):.1f}")
            else:
                succ.append("—")
                steps.append("—")
        print(f"| {t} | " + " | ".join(succ) + " | " + " | ".join(steps) + " |")
    print()


def table_ambiguity(rows):
    rs = [r for r in rows if r.get("crops_ambiguity") is not None
          and r["arm"] in ("C+", "B+")]
    if not rs:
        return
    print("## Which ambiguity rule fired")
    print()
    print("The registered prediction (P2.2) is about the same-name rule from "
          "§5.2 of the design document. The peer-set rule was added after "
          "reading the tree and before running anything, and is the weaker "
          "claim. They are counted separately so a result is never credited "
          "to the rule that did not fire.")
    print()
    print("| arm | task | runs | crops forced by ambiguity | same-name | peer-set |")
    print("|---|---|---|---|---|---|")
    g = defaultdict(list)
    for r in rs:
        g[(r["arm"], r["task"])].append(r)
    for (arm, task), v in sorted(g.items()):
        tot = sum(r.get("crops_ambiguity", 0) for r in v)
        sn = sum(r.get("crops_amb_same_name", 0) for r in v)
        ps = sum(r.get("crops_amb_peer_set", 0) for r in v)
        if not tot:
            continue
        print(f"| {arm} | {task} | {len(v)} | {tot} | {sn} | {ps} |")
    print()


def table_enrich_cost(rows):
    rs = [r for r in rows if r.get("enrich_ms")]
    if not rs:
        return
    print("## What the enrichment costs")
    print()
    print("Measured per step inside the observer, and reported whether or not "
          "the number is flattering (PREDICTIONS.md §8).")
    print()
    phases = ("merge_ms", "blocks_ms", "ambiguity_ms", "reach_ms",
              "shortcuts_ms", "total_ms")
    print("| arm | runs | steps | " + " | ".join(
        p.replace("_ms", "") + " ms/step" for p in phases) + " |")
    print("|---" * (3 + len(phases)) + "|")
    g = defaultdict(list)
    for r in rs:
        g[r["arm"]].append(r)
    for arm, v in sorted(g.items()):
        steps = sum(max(r["steps"], 1) for r in v)
        cells = []
        for p in phases:
            tot = sum((r["enrich_ms"] or {}).get(p, 0.0) for r in v)
            cells.append(f"{tot / max(steps, 1):.2f}")
        print(f"| {arm} | {len(v)} | {steps} | " + " | ".join(cells) + " |")
    print()
    # observation-token overhead, against the unenriched control
    base = [r for r in rows if r["arm"] == "B"]
    trt = [r for r in rows if r["arm"] == "B+"]
    if base and trt:
        diffs, n, _ = paired(base, trt, "observation_tokens")
        if diffs:
            d = boot_ci(diffs)
            mb = st.mean([r["observation_tokens"] for r in base])
            print(f"Observation tokens, B+ against B, paired on "
                  f"{n} (task, rep) pairs: **{d[0]:+,.0f}** "
                  f"[{d[1]:+,.0f}, {d[2]:+,.0f}] against a B mean of "
                  f"{mb:,.0f} — **{100 * d[0] / mb:+.1f}%**.")
            print()


def table_budget(rows):
    rs = [r for r in rows if r.get("token_budget")]
    if not rs:
        print("## Budget sweep")
        print()
        print("**Not run.** No runs in `results/raw2/` carry an enforced "
              "token budget. The question is not answered this round and no "
              "post-hoc reclassification is substituted for it: round 1 "
              "showed the two give different answers.")
        print()
        return
    print("## Budget sweep — enforced during execution, on fresh tokens")
    print()
    print("Budgeting is on fresh tokens (input + cache-write + output). A "
          "cache read is neither work the provider redid nor a cost paid at "
          "full rate; charging it would bill the append-only arms for the "
          "very thing that makes them cheap, and would let anyone pick the "
          "winner by picking the denominator.")
    print()
    print("| ceiling | arm | n | success | stopped by the budget | steps |")
    print("|---|---|---|---|---|---|")
    g = defaultdict(list)
    for r in rs:
        g[(r["token_budget"], r["arm"])].append(r)
    for (bud, arm), v in sorted(g.items()):
        cut = sum(1 for r in v if r.get("terminated") == "token_budget")
        print(f"| {bud:,} | {arm} | {len(v)} "
              f"| {fmt(*boot_ci([1.0 if r['success'] else 0.0 for r in v]), 3)} "
              f"| {cut}/{len(v)} ({100 * cut / max(len(v), 1):.0f}%) "
              f"| {st.mean([r['steps'] for r in v]):.1f} |")
    print()

    ceilings = sorted({r["token_budget"] for r in rs})
    print("### Paired within `(task, rep)`, at each ceiling")
    print()
    print("The same task and the same repetition seed, one row per pair. A "
          "positive success difference means the enriched tool wins at that "
          "ceiling.")
    print()
    print("| ceiling | pairs | success B+ − A | steps B+ − A | verdict |")
    print("|---|---|---|---|---|")
    crossing = []
    for bud in ceilings:
        sub = [r for r in rs if r["token_budget"] == bud]
        a = [r for r in sub if r["arm"] == "A"]
        b = [r for r in sub if r["arm"] == "B+"]
        if not a or not b:
            continue
        dsucc, n, _ = paired(a, b, "success")
        dstep, _, _ = paired(a, b, "steps")
        if not dsucc:
            continue
        ds, lo, hi = boot_ci(dsucc)
        step_ci = boot_ci(dstep) if dstep else (0.0, 0.0, 0.0)
        win = "B+ ahead" if lo > 0 else ("A ahead" if hi < 0 else
                                         "no detectable difference")
        crossing.append((bud, ds, lo, hi, win))
        print(f"| {bud:,} | {n} | {fmt(ds, lo, hi, 3)} "
              f"| {fmt(*step_ci)} | {win} |")
    print()

    if len(crossing) >= 2:
        print("### Where the curves cross")
        print()
        signs = [("+" if d > 0 else "−" if d < 0 else "0") for _, d, _, _, _ in crossing]
        flips = [i for i in range(1, len(signs)) if signs[i] != signs[i - 1]]
        if flips:
            for i in flips:
                lo_b, hi_b = crossing[i - 1][0], crossing[i][0]
                print(f"The point estimate changes sign between "
                      f"**{lo_b:,} and {hi_b:,} fresh tokens** "
                      f"({crossing[i-1][1]:+.3f} → {crossing[i][1]:+.3f}). "
                      f"Whether that is a real crossing depends on the "
                      f"intervals in the table above, not on the point "
                      f"estimates: read a crossing as established only where "
                      f"the two intervals sit on opposite sides of zero.")
        else:
            print(f"The point estimate keeps the same sign "
                  f"({' → '.join(f'{d:+.3f}' for _, d, _, _, _ in crossing)}) "
                  f"across every ceiling measured "
                  f"({', '.join(f'{b:,}' for b, _, _, _, _ in crossing)} fresh "
                  f"tokens). **No crossing is observed in the measured "
                  f"range.** A crossing may exist outside it; the ceilings "
                  f"that were not run are named in REPORT2.md.")
        print()
        both = [c for c in crossing if c[2] > 0 or c[3] < 0]
        if not both:
            print("At no measured ceiling does the difference clear zero, so "
                  "this round answers *below what budget does the tool win* "
                  "with **no budget in the measured range, at this N** — "
                  "which is not the same as the arms being equal.")
            print()


def table_constraints(rows):
    rs = [r for r in rows if r.get("constraint_results")]
    if not rs:
        return
    print("## Constraints, checked one at a time")
    print()
    print("What separates *failed the task* from *forgot a constraint*. The "
          "violation rate counts only constraints on runs that did something "
          "— a run that never started cannot be said to have forgotten "
          "anything.")
    print()
    print("| arm | task object | task | runs | task success | constraint "
          "violations | rate |")
    print("|---|---|---|---|---|---|---|")
    g = defaultdict(list)
    for r in rs:
        g[(r["arm"], bool(r.get("task_object")), r["task"])].append(r)
    for (arm, tobj, task), v in sorted(g.items()):
        checked = viol = 0
        for r in v:
            cr = {k: val for k, val in r["constraint_results"].items()
                  if not k.startswith("_")}
            checked += len(cr)
            viol += sum(1 for val in cr.values() if not val)
        print(f"| {arm} | {'on' if tobj else 'off'} | {task} | {len(v)} "
              f"| {sum(1 for r in v if r['success'])}/{len(v)} "
              f"| {viol}/{checked} "
              f"| {100 * viol / max(checked, 1):.0f}% |")
    print()


def table_image_window(rows):
    rs = [r for r in rows if r.get("peak_live_image_tokens")]
    if not rs:
        return
    print("## The image window")
    print()
    print("| arm | window | runs | peak live images | peak live image tokens "
          "| re-anchors | compactions | success |")
    print("|---|---|---|---|---|---|---|---|")
    g = defaultdict(list)
    for r in rs:
        g[(r["arm"], r.get("image_window"))].append(r)
    for (arm, win), v in sorted(g.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0)):
        print(f"| {arm} | {win} | {len(v)} "
              f"| {st.mean([r['peak_live_images'] for r in v]):.1f} "
              f"| {st.mean([r['peak_live_image_tokens'] for r in v]):,.0f} "
              f"| {st.mean([r.get('reanchors', 0) for r in v]):.1f} "
              f"| {st.mean([r.get('compactions', 0) for r in v]):.1f} "
              f"| {sum(1 for r in v if r['success'])}/{len(v)} |")
    print()


LONG_FOUR = ["long_march_export", "long_notes_digest",
             "long_ledger_edits", "long_region_transfer"]

ABLATIONS = [("B+nb", "blocks"), ("B+nr", "reachability"), ("B+nk", "shortcuts")]


def _tag(rows, tag):
    return [r for r in rows if r.get("run_tag") == tag]


def table_ablation(rows):
    """Which of the three enrichments carries the effect."""
    base = [r for r in rows if r["arm"] == "B+" and r["task"] in MENU_GROUP
            and not r.get("token_budget")]
    arms = {a for a, _ in ABLATIONS} & {r["arm"] for r in rows}
    if not arms or not base:
        print("## Ablation — which enrichment does the work")
        print()
        print("**Not run.** No records for `B+nb`, `B+nr` or `B+nk`.")
        print()
        return
    print("## Ablation — which enrichment does the work")
    print()
    print("Each arm computes the whole enrichment and then withholds one "
          "thing, so the cost of computing it is identical across arms and "
          "only what the model sees changes. A **positive** step difference "
          "means removing that enrichment made the agent spend more steps — "
          "that enrichment was doing work.")
    print()
    print("*Paired on `(task, rep)` across tiers.* The ablation arms ran in "
          "their own tier rather than interleaved with `B+`, so these pairs "
          "share the task, the seed and every setting, but not the hour they "
          "ran in. That is a weaker control than the interleaved comparisons "
          "above, and the intervals should be read with that in mind.")
    print()
    print("| withheld | arm | pairs | steps vs B+ | success vs B+ | verdict |")
    print("|---|---|---|---|---|---|")
    for arm, what in ABLATIONS:
        sub = [r for r in rows if r["arm"] == arm and r["task"] in MENU_GROUP]
        if not sub:
            continue
        ds, n, _ = paired(base, sub, "steps", across=True)
        su, _, _ = paired(base, sub, "success", across=True)
        if not ds:
            continue
        d = boot_ci(ds)
        s = boot_ci(su) if su else (0.0, 0.0, 0.0)
        verdict = ("**carries work**" if d[1] > 0 else
                   ("**costs steps when present**" if d[2] < 0 else
                    "no detectable difference at this N"))
        print(f"| {what} | `{arm}` | {n} | {fmt(*d)} | {fmt(*s, 3)} "
              f"| {verdict} |")
    print()
    print("| arm | menu-group success | menu-group steps |")
    print("|---|---|---|")
    for arm in ["B+"] + [a for a, _ in ABLATIONS]:
        sub = [r for r in rows if r["arm"] == arm and r["task"] in MENU_GROUP
               and not r.get("token_budget")]
        if not sub:
            continue
        print(f"| {arm} | {sum(1 for r in sub if r['success'])}/{len(sub)} "
              f"| {st.mean([r['steps'] for r in sub]):.2f} |")
    print()


def table_long(rows):
    """Experiment 4 — the image window and the persistent task object."""
    cfg = {t: _tag(rows, t) for t in
           ("t4_long_full", "t4_long_wide", "t4_long_notobj", "t4_long_base")}
    if not cfg["t4_long_full"]:
        print("## Experiment 4 — long tasks, image window and task object")
        print()
        print("**Not run.** No records tagged `t4_long_*`.")
        print()
        return
    print("## Experiment 4 — long tasks, image window and task object")
    print()
    print("Four tasks of 40 allowed steps, five repetitions each. The three "
          "`B+` configurations differ by exactly one setting, and each setting "
          "is its own tier, so these are paired on `(task, rep)` across tiers: "
          "same task, same seed, same everything but the manipulated variable "
          "and the hour it ran in.")
    print()
    print("| configuration | n | success | steps | peak live images "
          "| peak image tokens | re-anchors | compactions | est. $ |")
    print("|---|---|---|---|---|---|---|---|---|")
    label = {"t4_long_full": "B+ · window 2 · task object **on**",
             "t4_long_wide": "B+ · window **4** · task object on",
             "t4_long_notobj": "B+ · window 2 · task object **off**",
             "t4_long_base": "A · baseline (screenshot each step)"}
    for t in ("t4_long_full", "t4_long_wide", "t4_long_notobj", "t4_long_base"):
        v = cfg[t]
        if not v:
            continue
        print(f"| {label[t]} | {len(v)} "
              f"| {fmt(*boot_ci([1.0 if r['success'] else 0.0 for r in v]), 3)} "
              f"| {st.mean([r['steps'] for r in v]):.1f} "
              f"| {st.mean([r['peak_live_images'] for r in v]):.1f} "
              f"| {st.mean([r['peak_live_image_tokens'] for r in v]):,.0f} "
              f"| {st.mean([r.get('reanchors', 0) for r in v]):.1f} "
              f"| {st.mean([r.get('compactions', 0) for r in v]):.1f} "
              f"| ${st.mean([r['cost_usd'] for r in v]):.4f} |")
    print()
    print("| comparison | pairs | peak image tokens | steps | success |")
    print("|---|---|---|---|---|")
    for a, b, name in (
            ("t4_long_wide", "t4_long_full", "window 2 against window 4"),
            ("t4_long_notobj", "t4_long_full", "task object on against off"),
            ("t4_long_base", "t4_long_full", "B+ against the baseline A")):
        ra, rb = cfg[a], cfg[b]
        if not ra or not rb:
            continue
        tk, n, _ = paired(ra, rb, "peak_live_image_tokens", across=True)
        sp, _, _ = paired(ra, rb, "steps", across=True)
        su, _, _ = paired(ra, rb, "success", across=True)
        if not tk:
            continue
        print(f"| {name} | {n} | {fmt(*boot_ci(tk), 0)} "
              f"| {fmt(*boot_ci(sp))} | {fmt(*boot_ci(su), 3)} |")
    print()


def main():
    paths = sys.argv[1:] or sorted(glob.glob("results/raw2/*.jsonl"))
    if not paths:
        print("no input files", file=sys.stderr)
        return 1
    all_rows = load(paths)
    rows = usable(all_rows)

    # The budget sweep is a different experiment run on the same tasks: its
    # runs are cut off at a token ceiling by design. Pooling them into the
    # step-gap tables would report truncated runs as if they were ordinary
    # ones, so everything except the budget table reads the unbudgeted runs.
    free = [r for r in rows if not r.get("token_budget")]

    header(rows, all_rows)
    table_headline(free)

    print("## 2. Experiment 1 — does the enrichment close the step gap?")
    print()
    print(f"Unbudgeted runs only ({len(free)} of {len(rows)} usable). The "
          f"{len(rows) - len(free)} runs carrying an enforced token ceiling "
          f"belong to the budget sweep and are reported there.")
    print()
    present = {r["arm"] for r in free}
    rows, budgeted = free, rows
    for base, treat in (("B", "B+"), ("A", "B+"), ("A", "B")):
        if base in present and treat in present:
            table_paired(rows, base, treat, MENU_GROUP,
                         f"{treat} against {base} — menu/dialog group")
    for base, treat in (("B", "B+"),):
        if base in present and treat in present:
            table_paired(rows, base, treat, DEFECT_THREE,
                         f"{treat} against {base} — the three round-1 defect tasks")
            table_paired(rows, base, treat, CONTROL_GROUP,
                         f"{treat} against {base} — control group (no harm test)")
    table_variance(rows, MENU_GROUP, "menu/dialog group")

    print("## 3. Experiment 2 — ambiguity forces a crop")
    print()
    for base, treat in (("C", "C+"), ("C+", "B")):
        if base in present and treat in present:
            table_paired(rows, base, treat, ["vdelta_rows", "vdelta_bars"],
                         f"{treat} against {base} — the vdelta pair")
    table_ambiguity(rows)

    table_budget(budgeted)
    table_long(rows)
    table_constraints(rows)
    table_ablation(rows)
    table_image_window(rows)
    table_enrich_cost(rows)
    table_by_task(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
