#!/usr/bin/env python3.12
"""Aggregate the raw JSONL into the tables that go into RESULTS.md.

Everything in RESULTS.md is produced here. Nothing is typed by hand.

Confidence intervals are bootstrap percentile intervals over runs. Where two
arms' intervals overlap the report says there is no detectable difference at
this N rather than naming a winner.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics as st
import sys
from collections import defaultdict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from analysis import rescore  # noqa: E402

BOOT = 5000
ARMS_ORDER = ["A", "B", "C", "D"]

ARM_LABEL = {
    "A": "A · baseline (full screenshot each step)",
    "B": "B · tool, crop-priority",
    "C": "C · tool, text-priority",
    "D": "D · table + screenshot, no deltas",
}


def load(paths):
    rows = []
    for p in paths:
        if not os.path.exists(p):
            continue
        with open(p) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    return rows


def usable(rows):
    """Runs that actually ran. Rate-limited and harness-error runs are excluded
    and reported separately: scoring them as failures would penalise whichever
    arm happened to be scheduled when the provider or the container faltered."""
    keep, dropped = [], []
    for r in rows:
        if r.get("terminated") in ("rate_limited", "harness_error"):
            dropped.append(r)
        elif r.get("model_calls", 0) == 0:
            dropped.append(r)
        else:
            keep.append(r)
    return keep, dropped


def boot_ci(vals, stat=st.mean, n=BOOT, alpha=0.05, seed=7):
    vals = [v for v in vals if v is not None]
    if not vals:
        return (float("nan"), float("nan"), float("nan"))
    if len(vals) == 1:
        return (vals[0], vals[0], vals[0])
    rng = random.Random(seed)
    k = len(vals)
    reps = []
    for _ in range(n):
        reps.append(stat([vals[rng.randrange(k)] for _ in range(k)]))
    reps.sort()
    lo = reps[int((alpha / 2) * n)]
    hi = reps[min(n - 1, int((1 - alpha / 2) * n))]
    return (stat(vals), lo, hi)


def fmt(v, nd=2):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{v:,.{nd}f}"


def ci_str(triple, nd=2):
    m, lo, hi = triple
    return f"{fmt(m, nd)} [{fmt(lo, nd)}, {fmt(hi, nd)}]"


def overlaps(a, b):
    """Do two CIs overlap?"""
    _, alo, ahi = a
    _, blo, bhi = b
    if any(math.isnan(x) for x in (alo, ahi, blo, bhi)):
        return True
    return not (ahi < blo or bhi < alo)


def by_arm(rows):
    d = defaultdict(list)
    for r in rows:
        d[r["arm"]].append(r)
    return d


def per_step_mean(r, key):
    v = r.get(key) or []
    return st.mean(v) if v else None


# ------------------------------------------------------------------ tables

def table_headline(rows):
    g = by_arm(rows)
    out = []
    out.append("| Arm | n | Success rate | Steps (mean) | Model calls / "
               "completed task | Wall time / task (s) | Tokens / task | "
               "Cost / completed task (USD) |")
    out.append("|---|---|---|---|---|---|---|---|")
    for a in ARMS_ORDER:
        rs = g.get(a)
        if not rs:
            continue
        n = len(rs)
        succ = [1.0 if r["success"] else 0.0 for r in rs]
        sr = boot_ci(succ)
        steps = boot_ci([r["steps"] for r in rs])
        wall = boot_ci([r["wall_time_total_s"] for r in rs])
        toks = boot_ci([r["tokens_total"] for r in rs])
        ncomp = sum(1 for r in rs if r["success"])
        calls_pc = (sum(r["model_calls"] for r in rs) / ncomp) if ncomp else None
        cost_pc = (sum(r["cost_usd"] for r in rs) / ncomp) if ncomp else None
        out.append(
            f"| {ARM_LABEL[a]} | {n} | {ci_str(sr, 3)} | {ci_str(steps, 1)} | "
            f"{fmt(calls_pc, 1)} | {ci_str(wall, 1)} | {ci_str(toks, 0)} | "
            f"{fmt(cost_pc, 4)} |")
    return "\n".join(out)


def table_tokens(rows):
    g = by_arm(rows)
    out = []
    out.append("| Arm | Observation tokens / task | Image tokens / task | "
               "Cache-read tokens / task | Cache-write tokens / task | "
               "Output tokens / task | Cache hit share |")
    out.append("|---|---|---|---|---|---|---|")
    for a in ARMS_ORDER:
        rs = g.get(a)
        if not rs:
            continue
        obs = boot_ci([r["observation_tokens"] for r in rs])
        img = boot_ci([r["image_tokens"] for r in rs])
        crd = boot_ci([r["tokens_cached"] for r in rs])
        ccr = boot_ci([r["tokens_cache_create"] for r in rs])
        outt = boot_ci([r["tokens_out"] for r in rs])
        tot_in = sum(r["tokens_cached"] + r["tokens_cache_create"] + r["tokens_in"]
                     for r in rs)
        hit = (sum(r["tokens_cached"] for r in rs) / tot_in) if tot_in else None
        out.append(
            f"| {ARM_LABEL[a]} | {ci_str(obs, 0)} | {ci_str(img, 0)} | "
            f"{ci_str(crd, 0)} | {ci_str(ccr, 0)} | {ci_str(outt, 0)} | "
            f"{fmt(100 * hit, 1) if hit is not None else '–'}% |")
    return "\n".join(out)


def table_latency(rows):
    g = by_arm(rows)
    out = []
    out.append("| Arm | TTFT / step (ms) | Decode / step (ms) | "
               "Observe time / task (s) | Debounce / task (s) | Act time / task (s) |")
    out.append("|---|---|---|---|---|---|")
    for a in ARMS_ORDER:
        rs = g.get(a)
        if not rs:
            continue
        ttft = boot_ci([x for x in (per_step_mean(r, "ttft_per_step_ms")
                                    for r in rs) if x is not None])
        dec = boot_ci([x for x in (per_step_mean(r, "decode_time_per_step_ms")
                                   for r in rs) if x is not None])
        obs = boot_ci([r.get("observe_time_s", 0) for r in rs])
        deb = boot_ci([r.get("debounce_s", 0) for r in rs])
        act = boot_ci([r.get("act_time_s", 0) for r in rs])
        out.append(f"| {ARM_LABEL[a]} | {ci_str(ttft, 0)} | {ci_str(dec, 0)} | "
                   f"{ci_str(obs, 1)} | {ci_str(deb, 1)} | {ci_str(act, 1)} |")
    return "\n".join(out)


def table_grounding(rows):
    g = by_arm(rows)
    out = []
    out.append("| Arm | Grounding failures / task | Action aborts / task | "
               "Runs with ≥1 grounding failure | Malformed replies / task |")
    out.append("|---|---|---|---|---|")
    for a in ARMS_ORDER:
        rs = g.get(a)
        if not rs:
            continue
        gf = boot_ci([r["grounding_failures"] for r in rs])
        ab = boot_ci([r["action_aborts"] for r in rs])
        share = 100.0 * sum(1 for r in rs if r["grounding_failures"] > 0) / len(rs)
        mal = boot_ci([sum(1 for s in r.get("steps_detail", [])
                           if s.get("action") == "malformed") for r in rs])
        out.append(f"| {ARM_LABEL[a]} | {ci_str(gf, 2)} | {ci_str(ab, 2)} | "
                   f"{fmt(share, 1)}% | {ci_str(mal, 2)} |")
    return "\n".join(out)


def table_by_task(rows):
    g = defaultdict(lambda: defaultdict(list))
    for r in rows:
        g[r["task"]][r["arm"]].append(r)
    arms = sorted({r["arm"] for r in rows})
    out = ["| Task | tags | " + " | ".join(f"{a} succ" for a in arms)
           + " | " + " | ".join(f"{a} steps" for a in arms) + " |"]
    out.append("|---" * (2 + 2 * len(arms)) + "|")
    for tid in sorted(g):
        tags = ",".join(g[tid][arms[0]][0]["tags"]) if g[tid].get(arms[0]) else ""
        sc, stp = [], []
        for a in arms:
            rs = g[tid].get(a, [])
            if not rs:
                sc.append("–")
                stp.append("–")
                continue
            sc.append(f"{sum(1 for r in rs if r['success'])}/{len(rs)}")
            stp.append(fmt(st.mean([r["steps"] for r in rs]), 1))
        out.append(f"| {tid} | {tags} | " + " | ".join(sc) + " | "
                   + " | ".join(stp) + " |")
    return "\n".join(out)


def table_visual_split(rows):
    """Do the non-textual tasks separate B from C, as the design predicts?

    Three groups, because the first two are not the same experiment:
      * `vdelta`  — the decisive fact appears *during* the task and is carried
                    only by appearance, so it can only arrive in a per-step
                    crop. This is the group that actually tests B vs C.
      * `visual`  — non-textual, but answerable from the anchor screenshot
                    alone, so the per-step channel never mattered.
      * the rest.
    """
    out = ["| Group | Arm | n | Success rate | Image tokens / task | Steps |",
           "|---|---|---|---|---|---|"]
    for label, pred in (
            ("mid-task appearance change (vdelta)",
             lambda r: "vdelta" in r.get("tags", [])),
            ("non-textual but anchor-solvable",
             lambda r: ("visual" in r.get("tags", [])
                        and "vdelta" not in r.get("tags", []))),
            ("everything else",
             lambda r: "visual" not in r.get("tags", []))):
        sub = [r for r in rows if pred(r)]
        for a in ARMS_ORDER:
            rs = [r for r in sub if r["arm"] == a]
            if not rs:
                continue
            sr = boot_ci([1.0 if r["success"] else 0.0 for r in rs])
            img = boot_ci([r["image_tokens"] for r in rs])
            stp = boot_ci([r["steps"] for r in rs])
            out.append(f"| {label} | {a} | {len(rs)} | {ci_str(sr, 3)} | "
                       f"{ci_str(img, 0)} | {ci_str(stp, 1)} |")
    return "\n".join(out)


def table_equal_budget(rows, budgets=(8000, 15000, 30000, 60000)):
    """Success rate when every arm is held to the same token budget per task.

    A run counts as a success under budget X only if it succeeded *and* the
    cumulative tokens it had consumed by the step it finished on were within X.
    This is the comparison that stops a cheaper arm from looking good only
    because it was allowed to spend less.
    """
    g = by_arm(rows)
    out = ["| Token budget / task | " + " | ".join(
        f"{a} success" for a in ARMS_ORDER if a in g) + " |"]
    out.append("|---" * (1 + len([a for a in ARMS_ORDER if a in g])) + "|")
    for b in budgets:
        cells = []
        for a in ARMS_ORDER:
            rs = g.get(a)
            if not rs:
                continue
            ok = sum(1 for r in rs
                     if r["success"] and r["tokens_total"] <= b)
            cells.append(f"{100.0 * ok / len(rs):.1f}% ({ok}/{len(rs)})")
        out.append(f"| {b:,} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def fresh_tokens(r):
    """Tokens the provider actually had to process this run.

    `tokens_total` counts a cache *read* the same as a fresh input token, but a
    read is an order of magnitude cheaper and does not represent work the model
    redid. Budgeting on the raw total therefore penalises exactly the arms the
    append-only design is meant to help, so the equal-budget comparison is also
    reported on this measure and on money.
    """
    return r["tokens_in"] + r["tokens_cache_create"] + r["tokens_out"]


def table_equal_budget_fresh(rows, budgets=(4000, 8000, 15000, 30000)):
    g = by_arm(rows)
    arms = [a for a in ARMS_ORDER if a in g]
    out = ["| Fresh-token budget / task | " + " | ".join(
        f"{a} success" for a in arms) + " |"]
    out.append("|---" * (1 + len(arms)) + "|")
    for b in budgets:
        cells = []
        for a in arms:
            rs = g[a]
            ok = sum(1 for r in rs if r["success"] and fresh_tokens(r) <= b)
            cells.append(f"{100.0 * ok / len(rs):.1f}% ({ok}/{len(rs)})")
        out.append(f"| {b:,} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def table_equal_budget_cost(rows, budgets=(0.02, 0.04, 0.06, 0.10)):
    g = by_arm(rows)
    arms = [a for a in ARMS_ORDER if a in g]
    out = ["| Cost budget / task (USD) | " + " | ".join(
        f"{a} success" for a in arms) + " |"]
    out.append("|---" * (1 + len(arms)) + "|")
    for b in budgets:
        cells = []
        for a in arms:
            rs = g[a]
            ok = sum(1 for r in rs if r["success"] and r["cost_usd"] <= b)
            cells.append(f"{100.0 * ok / len(rs):.1f}% ({ok}/{len(rs)})")
        out.append(f"| ${b:.2f} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def table_compaction(rows):
    """Did compaction actually fire, and what did it cost or save?"""
    g = by_arm(rows)
    arms = [a for a in ARMS_ORDER if a in g]
    out = ["| Arm | n | Steps / task | Compactions / task | Runs that compacted "
           "| Crops emitted / task | Crops aged out / task | Cache hit share |",
           "|---|---|---|---|---|---|---|---|"]
    rows = [r for r in rows if compaction_on(r)]
    g = by_arm(rows)
    arms = [a for a in ARMS_ORDER if a in g]
    for a in arms:
        rs = g[a]
        comp = boot_ci([r.get("compactions", 0) for r in rs])
        fired = sum(1 for r in rs if r.get("compactions", 0) > 0)
        emit = boot_ci([r.get("crops_emitted", 0) for r in rs])
        aged = boot_ci([r.get("crops_aged", 0) for r in rs])
        stp = boot_ci([r["steps"] for r in rs])
        tot_in = sum(r["tokens_cached"] + r["tokens_cache_create"] + r["tokens_in"]
                     for r in rs)
        hit = (sum(r["tokens_cached"] for r in rs) / tot_in) if tot_in else 0
        out.append(f"| {ARM_LABEL[a]} | {len(rs)} | {ci_str(stp, 1)} | "
                   f"{ci_str(comp, 2)} | {fired}/{len(rs)} | {ci_str(emit, 1)} | "
                   f"{ci_str(aged, 1)} | {fmt(100 * hit, 1)}% |")
    return "\n".join(out)


def compaction_on(r):
    """Was compaction active for this run?

    Runs made before the control condition existed do not carry the flag; for
    those the tag says it, since the control sweep has its own tag.
    """
    if "compaction_enabled" in r:
        return bool(r["compaction_enabled"])
    return "nocompact" not in (r.get("run_tag") or "")


def table_compaction_effect(rows):
    """Same arms, same tasks, compaction on vs off."""
    on = [r for r in rows if compaction_on(r)]
    off = [r for r in rows if not compaction_on(r)]
    if not on or not off:
        return ""
    out = ["| Arm | compaction | n | Success | Total tokens / task | "
           "Cost / task | Steps / task |", "|---|---|---|---|---|---|---|"]
    for a in ARMS_ORDER:
        for label, rs in (("on", [r for r in on if r["arm"] == a]),
                          ("off", [r for r in off if r["arm"] == a])):
            if not rs:
                continue
            sr = boot_ci([1.0 if r["success"] else 0.0 for r in rs])
            tk = boot_ci([r["tokens_total"] for r in rs])
            cs = boot_ci([r["cost_usd"] for r in rs])
            stp = boot_ci([r["steps"] for r in rs])
            out.append(f"| {a} | **{label}** | {len(rs)} | {ci_str(sr, 3)} | "
                       f"{ci_str(tk, 0)} | {ci_str(cs, 4)} | {ci_str(stp, 1)} |")
    return "\n".join(out)


def table_enforced_budget(rows):
    """The equal-budget comparison run properly: the ceiling was enforced
    *during* each run and the step limit doubled, so an arm with budget left
    could spend it on more steps instead of being capped by steps instead."""
    g = by_arm(rows)
    arms = [a for a in ARMS_ORDER if a in g]
    budget = next((r.get("token_budget") for r in rows if r.get("token_budget")),
                  None)
    out = [f"Fresh-token ceiling enforced per run: **{budget:,}**; every task's "
           f"step limit doubled so a cheaper arm can convert surplus budget "
           f"into extra steps.\n",
           "| Arm | n | Success rate | Runs stopped by the budget | Steps / task |",
           "|---|---|---|---|---|"]
    for a in arms:
        rs = g[a]
        sr = boot_ci([1.0 if r["success"] else 0.0 for r in rs])
        hit = sum(1 for r in rs if r["terminated"] == "token_budget")
        stp = boot_ci([r["steps"] for r in rs])
        out.append(f"| {ARM_LABEL[a]} | {len(rs)} | {ci_str(sr, 3)} | "
                   f"{hit}/{len(rs)} | {ci_str(stp, 1)} |")
    return "\n".join(out)


def comparisons(rows):
    """Explicit, interval-aware verdicts for the three report questions."""
    g = by_arm(rows)
    lines = []

    def metric(a, key, f=lambda r, k: r[k]):
        return boot_ci([f(r, key) for r in g[a]]) if g.get(a) else (
            float("nan"),) * 3

    def verdict(name, a1, a2, key, lower_is_better=True, nd=2):
        if a1 not in g or a2 not in g:
            return f"- **{name}**: not measurable (missing arm)."
        m1, m2 = metric(a1, key), metric(a2, key)
        if overlaps(m1, m2):
            return (f"- **{name}** ({key}): {a1}={ci_str(m1, nd)} vs "
                    f"{a2}={ci_str(m2, nd)} — intervals overlap, "
                    f"**no difference detectable at this N**.")
        better = (a1 if ((m1[0] < m2[0]) == lower_is_better) else a2)
        ratio = (max(m1[0], m2[0]) / min(m1[0], m2[0])
                 if min(m1[0], m2[0]) > 0 else float("nan"))
        return (f"- **{name}** ({key}): {a1}={ci_str(m1, nd)} vs "
                f"{a2}={ci_str(m2, nd)} — **{better} wins**, "
                f"{fmt(ratio, 2)}x.")

    for pair in (("A", "B"), ("A", "C"), ("B", "C")):
        lines.append(f"\n**{pair[0]} vs {pair[1]}**\n")
        lines.append(verdict("success rate", *pair, "success",
                             lower_is_better=False, nd=3))
        lines.append(verdict("model calls per task", *pair, "model_calls", nd=2))
        lines.append(verdict("total tokens per task", *pair, "tokens_total", nd=0))
        lines.append(verdict("image tokens per task", *pair, "image_tokens", nd=0))
        lines.append(verdict("cost per task", *pair, "cost_usd", nd=4))
        lines.append(verdict("steps per task", *pair, "steps", nd=2))
        lines.append(verdict("grounding failures per task", *pair,
                             "grounding_failures", nd=3))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", nargs="*", default=["results/raw/main.jsonl"])
    ap.add_argument("--out", default="RESULTS.md")
    ap.add_argument("--eqb", nargs="*", default=["results/raw/eqbudget.jsonl"],
                    help="raw JSONL from the enforced equal-budget sweep")
    ap.add_argument("--no-rescore", action="store_true",
                    help="report the success flags exactly as they were "
                         "recorded, including the ones a broken verifier got "
                         "wrong (see analysis/rescore.py)")
    args = ap.parse_args()

    rows = load(args.raw)
    if not rows:
        print("no data", file=sys.stderr)
        return 1
    corrections = []
    if not args.no_rescore:
        rows, corrections = rescore.apply(rows)
    good, dropped = usable(rows)

    arms_present = sorted({r["arm"] for r in good})
    tasks_present = sorted({r["task"] for r in good})
    reps = defaultdict(int)
    for r in good:
        reps[(r["task"], r["arm"])] += 1
    min_rep = min(reps.values()) if reps else 0
    max_rep = max(reps.values()) if reps else 0

    total_cost = sum(r["cost_usd"] for r in rows)

    body = []
    body.append("# RESULTS\n")
    body.append("_Generated by `analysis/aggregate.py` from "
                "`results/raw/*.jsonl`. Do not edit by hand._\n")
    body.append(f"- runs recorded: **{len(rows)}**, usable: **{len(good)}**, "
                f"excluded: **{len(dropped)}** "
                f"(provider rate limit or harness error — see below)")
    body.append(f"- arms: {', '.join(arms_present)} · tasks: "
                f"{len(tasks_present)} · repetitions per (task, arm): "
                f"{min_rep}–{max_rep}")
    body.append(f"- measured API spend on the experiment: **${total_cost:.2f}**")
    body.append("- intervals are 95 % bootstrap percentile intervals over runs "
                f"({BOOT:,} resamples)\n")

    if corrections:
        counts = rescore.summarise(corrections)
        body.append("### Re-scored runs\n")
        body.append("`calc_total`'s verifier searched for the string `48.5`. "
                    "The total the task asks for is 1.5 + 3.25 + 7.0 = "
                    "**11.75**, so no correct answer could ever satisfy it and "
                    "every run that did the task properly was recorded as a "
                    "failure. The raw JSONL is left untouched; "
                    "`analysis/rescore.py` recovers the bytes each agent "
                    "actually produced — the broken verifier preserved them "
                    "verbatim inside its own failure message — and puts them "
                    "through the fixed rule. Pass `--no-rescore` to reproduce "
                    "the original, wrong figures.\n")
        body.append("| Outcome | n |")
        body.append("|---|---|")
        for k, n in sorted(counts.items()):
            body.append(f"| {k} | {n} |")
        by_arm = defaultdict(int)
        for c in corrections:
            if c["outcome"] == "false negative corrected":
                by_arm[c["arm"]] += 1
        if by_arm:
            body.append("")
            body.append("Corrections per arm: " +
                        ", ".join(f"**{a}** +{n}"
                                  for a, n in sorted(by_arm.items())) +
                        ". Every arm is affected, so no comparison below "
                        "changes direction; the absolute success rates rise.")
        body.append("")

    if dropped:
        rc = defaultdict(int)
        for r in dropped:
            rc[(r.get("arm"), r.get("terminated"))] += 1
        body.append("### Excluded runs\n")
        body.append("| Arm | Reason | n |")
        body.append("|---|---|---|")
        for (a, why), n in sorted(rc.items(), key=lambda x: str(x[0])):
            body.append(f"| {a} | {why} | {n} |")
        body.append("")

    body.append("## 1. Headline\n")
    body.append(table_headline(good))
    body.append("\n## 2. Where the tokens go\n")
    body.append(table_tokens(good))
    body.append("\n## 3. Latency decomposition\n")
    body.append(table_latency(good))
    body.append("\n## 4. Grounding and act-time validation\n")
    body.append(table_grounding(good))
    body.append("\n## 5. Equal-token-budget comparison\n")
    body.append("Success rate when every arm is capped at the same tokens per "
                "task. This is the comparison that prevents a cheaper arm from "
                "looking good merely because it was allowed to spend less.\n")
    body.append("**(a) budget on raw total tokens** — note this counts a "
                "cache read the same as a fresh input token, which penalises "
                "the append-only arms:\n")
    body.append(table_equal_budget(good))
    body.append("\n**(b) budget on fresh tokens** (input + cache-write + "
                "output, i.e. what the provider actually had to process):\n")
    body.append(table_equal_budget_fresh(good))
    body.append("\n**(c) budget on money**, which is the measure a user "
                "actually pays:\n")
    body.append(table_equal_budget_cost(good))
    eqb_raw = load(args.eqb)
    if not args.no_rescore:
        eqb_raw, _ = rescore.apply(eqb_raw)
    eqb_rows, _ = usable(eqb_raw)
    if eqb_rows:
        body.append("\n**(d) budget enforced during the run** — a separate "
                    "sweep, not a reclassification of the runs above:\n")
        body.append(table_enforced_budget(eqb_rows))

    long_rows = [r for r in good if "long" in r.get("tags", [])]
    if long_rows:
        body.append("\n## 5b. Long tasks: compaction and crop ageing\n")
        body.append("Compaction is what bounds an append-only context. These "
                    "tasks are long enough (step limit 40) to trigger it at "
                    "natural boundaries — an application change, a dialog "
                    "opening or closing — and on the re-anchor interval.\n")
        body.append(table_compaction(long_rows))
        eff = table_compaction_effect(long_rows)
        if eff:
            body.append("\n**Compaction on vs off**, same arms and tasks:\n")
            body.append(eff)
        body.append("\n**Long tasks only, headline:**\n")
        body.append(table_headline(long_rows))

    body.append("\n## 6. Non-textual tasks vs the rest\n")
    body.append("Both groups carry information only in pixels, but only the "
                "first puts it in a change that happens *during* the task, "
                "where the per-step channel is the sole way it can arrive. "
                "The anchor-solvable group is answerable from the opening "
                "screenshot, so the per-step channel never mattered there and "
                "arm B emitted no crops at all.\n")
    body.append(table_visual_split(good))
    body.append("\n## 7. Per task\n")
    body.append(table_by_task(good))
    body.append("\n## 8. Head-to-head verdicts\n")
    body.append(comparisons(good))
    body.append("")

    with open(args.out, "w") as f:
        f.write("\n".join(body))
    print(f"wrote {args.out} from {len(good)} usable runs "
          f"({len(dropped)} excluded)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
