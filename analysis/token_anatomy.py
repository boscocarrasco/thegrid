#!/usr/bin/env python3.12
"""Why does each arm spend what it spends?

Two questions the headline table poses but does not answer:

  * arm C spends more total tokens than arm B, although its per-step payload is
    strictly smaller (it sends no crops); and
  * arm A spends 4x fewer total tokens than arm B, although it sends a full
    screenshot every step and B sends one only at anchors.

Both are answered by decomposing the total rather than comparing it. The
decomposition is arithmetic on the recorded usage, not a model: for a
conversation of n steps whose prompt grows by p_k tokens at step k, an
append-only arm re-reads the whole prefix every step, so its billed input is
sum_k (sum_{j<k} p_j) — quadratic in n — while an arm that rebuilds its
transcript pays only sum_k p_k, linear in n.

Run:
    /usr/bin/python3.12 analysis/token_anatomy.py --raw results/raw/*.jsonl
"""
from __future__ import annotations

import argparse
import os
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis import rescore  # noqa: E402
from analysis.aggregate import boot_ci, ci_str, load, usable  # noqa: E402

ARMS = ["A", "B", "C", "D"]


def by_arm(rows):
    d = defaultdict(list)
    for r in rows:
        d[r["arm"]].append(r)
    return d


def mean(xs):
    xs = [x for x in xs if x is not None]
    return st.mean(xs) if xs else float("nan")


def hr(t):
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


def decompose(g):
    """Where every token of the total actually sits."""
    hr("1. ANATOMY OF tokens_total, PER TASK")
    print(f"{'arm':<4}{'total':>10}{'cache_read':>12}{'cache_write':>12}"
          f"{'input':>9}{'output':>9}{'read %':>9}")
    for a in ARMS:
        rs = g.get(a)
        if not rs:
            continue
        tot = mean([r["tokens_total"] for r in rs])
        rd = mean([r["tokens_cached"] for r in rs])
        wr = mean([r["tokens_cache_create"] for r in rs])
        ip = mean([r["tokens_in"] for r in rs])
        op = mean([r["tokens_out"] for r in rs])
        print(f"{a:<4}{tot:>10,.0f}{rd:>12,.0f}{wr:>12,.0f}"
              f"{ip:>9,.0f}{op:>9,.0f}{100*rd/tot:>8.1f}%")
    print("\n  tokens_total = cache_read + cache_write + input + output.")
    print("  Cache reads are billed at ~10% of fresh input, so a big total is")
    print("  not automatically a big bill — see section 4.")


def growth(g):
    """Is the total linear or quadratic in the number of steps?"""
    hr("2. HOW THE TOTAL GROWS WITH STEPS")
    print("  Fitting tokens_total = a + b*n and a + b*n + c*n^2 per arm,")
    print("  n = steps. R^2 says which shape the data actually has.\n")
    print(f"{'arm':<4}{'n runs':>8}{'tok/step':>11}{'linear R2':>12}"
          f"{'quadratic R2':>15}{'shape':>14}")
    for a in ARMS:
        rs = g.get(a)
        if not rs or len(rs) < 8:
            continue
        xs = [r["steps"] for r in rs]
        ys = [r["tokens_total"] for r in rs]
        r2l = _r2(xs, ys, deg=1)
        r2q = _r2(xs, ys, deg=2)
        per = mean([y / max(1, x) for x, y in zip(xs, ys)])
        shape = "quadratic" if (r2q - r2l) > 0.03 else "linear"
        print(f"{a:<4}{len(rs):>8}{per:>11,.0f}{r2l:>12.3f}{r2q:>15.3f}"
              f"{shape:>14}")
    print("\n  Pooling every task in one fit is a poor model for the tool arms:")
    print("  their per-step payload scales with the element table, which differs")
    print("  by an order of magnitude between a text editor and LibreOffice.")
    print("  Fitting *within* each task, where the table size is fixed, isolates")
    print("  the growth shape:\n")
    print(f"{'arm':<4}{'tasks fitted':>14}{'median linear R2':>19}"
          f"{'median quad R2':>17}{'median gain':>13}")
    for a in ARMS:
        rs = g.get(a)
        if not rs:
            continue
        per_task = defaultdict(list)
        for r in rs:
            per_task[r["task"]].append(r)
        ls, qs = [], []
        for t, v in per_task.items():
            if len(v) < 4 or len(set(x["steps"] for x in v)) < 3:
                continue
            xs = [x["steps"] for x in v]
            ys = [x["tokens_total"] for x in v]
            rl, rq = _r2(xs, ys, 1), _r2(xs, ys, 2)
            if rl == rl and rq == rq:
                ls.append(rl)
                qs.append(rq)
        if ls:
            gain = st.median([q - l for q, l in zip(qs, ls)])
            print(f"{a:<4}{len(ls):>14}{st.median(ls):>19.3f}"
                  f"{st.median(qs):>17.3f}{gain:>13.3f}")
    print("\n  An append-only arm re-reads its whole prefix every step, so its")
    print("  billed input is the sum of prefixes: quadratic in step count.")
    print("  An arm that rebuilds its transcript pays each prefix once: linear.")


def _r2(xs, ys, deg=1):
    import numpy as np
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    if len(set(xs)) <= deg:
        return float("nan")
    coef = np.polyfit(x, y, deg)
    pred = np.polyval(coef, x)
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return 1 - ss_res / ss_tot if ss_tot else float("nan")


def per_step_payload(g):
    """What each arm adds to the context on a single step."""
    hr("3. PER-STEP PAYLOAD (what the arm appends each step)")
    print(f"{'arm':<4}{'obs tok/step':>14}{'img tok/step':>14}"
          f"{'out tok/step':>14}{'steps':>9}")
    for a in ARMS:
        rs = g.get(a)
        if not rs:
            continue
        obs = mean([r["observation_tokens"] / max(1, r["steps"]) for r in rs])
        img = mean([r["image_tokens"] / max(1, r["steps"]) for r in rs])
        out = mean([r["tokens_out"] / max(1, r["steps"]) for r in rs])
        stp = mean([r["steps"] for r in rs])
        print(f"{a:<4}{obs:>14,.0f}{img:>14,.0f}{out:>14,.0f}{stp:>9.1f}")


def cost_vs_tokens(g):
    hr("4. TOKENS ARE NOT THE BILL")
    print(f"{'arm':<4}{'tokens/task':>13}{'cost/task':>12}"
          f"{'$ per 100k tok':>17}{'fresh tok/task':>16}")
    for a in ARMS:
        rs = g.get(a)
        if not rs:
            continue
        tot = mean([r["tokens_total"] for r in rs])
        cost = mean([r["cost_usd"] for r in rs])
        fresh = mean([r["tokens_in"] + r["tokens_cache_create"] + r["tokens_out"]
                      for r in rs])
        print(f"{a:<4}{tot:>13,.0f}{cost:>12.4f}"
              f"{1e5 * cost / tot:>17.4f}{fresh:>16,.0f}")
    print("\n  'fresh' = input + cache-write + output: what the provider had to")
    print("  process. It tracks cost far better than the raw total does.")


def c_vs_b(rows):
    """Why C spends more than B, when its payload is strictly smaller."""
    hr("5. WHY C > B  (C sends less per step, yet spends more)")
    b = [r for r in rows if r["arm"] == "B"]
    c = [r for r in rows if r["arm"] == "C"]

    print(f"{'':<26}{'B':>12}{'C':>12}{'C/B':>9}")
    for label, f in (
            ("steps / task", lambda r: r["steps"]),
            ("output tok / task", lambda r: r["tokens_out"]),
            ("output tok / step", lambda r: r["tokens_out"] / max(1, r["steps"])),
            ("obs tok / step", lambda r: r["observation_tokens"] / max(1, r["steps"])),
            ("image tok / task", lambda r: r["image_tokens"]),
            ("cache_read / task", lambda r: r["tokens_cached"]),
            ("total / task", lambda r: r["tokens_total"]),
    ):
        mb, mc = mean([f(r) for r in b]), mean([f(r) for r in c])
        print(f"{label:<26}{mb:>12,.1f}{mc:>12,.1f}{mc/mb if mb else 0:>9.2f}")

    # Control for steps: compare only runs that took the same number of steps.
    hr("5b. SAME TASK, SAME STEP COUNT — is C still dearer?")
    pair = defaultdict(lambda: {"B": [], "C": []})
    for r in rows:
        if r["arm"] in ("B", "C"):
            pair[(r["task"], r["steps"])][r["arm"]].append(r)
    matched = [(k, v) for k, v in pair.items() if v["B"] and v["C"]]
    if matched:
        db = [mean([x["tokens_total"] for x in v["B"]]) for _, v in matched]
        dc = [mean([x["tokens_total"] for x in v["C"]]) for _, v in matched]
        ob = [mean([x["tokens_out"] for x in v["B"]]) for _, v in matched]
        oc = [mean([x["tokens_out"] for x in v["C"]]) for _, v in matched]
        print(f"  matched (task, step-count) cells: {len(matched)}")
        print(f"  total tokens   B {mean(db):>10,.0f}   C {mean(dc):>10,.0f}"
              f"   C/B {mean(dc)/mean(db):.2f}")
        print(f"  output tokens  B {mean(ob):>10,.0f}   C {mean(oc):>10,.0f}"
              f"   C/B {mean(oc)/mean(ob):.2f}")
        print("\n  If C is dearer at equal step count, the extra is not step")
        print("  count: it is what C writes and re-reads per step.")
    else:
        print("  no matched cells")

    # How much of C's excess is the blind group alone?
    hr("5d. HOW MUCH OF C'S EXCESS IS THE BLIND GROUP?")
    vb = [r for r in b if "vdelta" in r.get("tags", [])]
    vc = [r for r in c if "vdelta" in r.get("tags", [])]
    ob = [r for r in b if "vdelta" not in r.get("tags", [])]
    oc = [r for r in c if "vdelta" not in r.get("tags", [])]
    tb_all, tc_all = mean([r["tokens_total"] for r in b]), mean([r["tokens_total"] for r in c])
    excess = tc_all - tb_all
    tb_o, tc_o = mean([r["tokens_total"] for r in ob]), mean([r["tokens_total"] for r in oc])
    print(f"  C - B over every task            {excess:>12,.0f} tokens/task")
    print(f"  C - B excluding the blind group  {tc_o - tb_o:>12,.0f} tokens/task")
    print(f"  runs in the blind group          {len(vc):>12} of {len(c)}")
    if excess:
        share = 100 * (excess - (tc_o - tb_o)) / excess
        print(f"  share of the excess explained by that group  {share:>8.1f}%")
    print("\n  Outside the group where C cannot see, C is not the dearer arm.")

    # Where does C spend its extra steps?
    hr("5c. WHERE C'S EXTRA STEPS GO, BY TASK GROUP")
    for label, pred in (("mid-task appearance change",
                         lambda r: "vdelta" in r.get("tags", [])),
                        ("everything else",
                         lambda r: "vdelta" not in r.get("tags", []))):
        bb = [r for r in b if pred(r)]
        cc = [r for r in c if pred(r)]
        if not bb or not cc:
            continue
        print(f"  {label}:")
        print(f"     steps   B {mean([r['steps'] for r in bb]):>6.1f}"
              f"   C {mean([r['steps'] for r in cc]):>6.1f}")
        print(f"     tokens  B {mean([r['tokens_total'] for r in bb]):>10,.0f}"
              f"   C {mean([r['tokens_total'] for r in cc]):>10,.0f}")
        print(f"     success B {mean([r['success'] for r in bb]):>6.3f}"
              f"   C {mean([r['success'] for r in cc]):>6.3f}")


def a_vs_b(rows):
    """Why A spends fewer tokens than B, despite a screenshot every step."""
    hr("6. WHY A < B  (a screenshot every step, yet fewer tokens)")
    a = [r for r in rows if r["arm"] == "A"]
    b = [r for r in rows if r["arm"] == "B"]
    print(f"{'':<30}{'A':>12}{'B':>12}{'A/B':>9}")
    for label, f in (
            ("steps / task", lambda r: r["steps"]),
            ("image tok / task", lambda r: r["image_tokens"]),
            ("obs tok / task", lambda r: r["observation_tokens"]),
            ("cache_read / task", lambda r: r["tokens_cached"]),
            ("cache_write / task", lambda r: r["tokens_cache_create"]),
            ("input (uncached) / task", lambda r: r["tokens_in"]),
            ("total / task", lambda r: r["tokens_total"]),
            ("fresh / task", lambda r: r["tokens_in"] + r["tokens_cache_create"]
                                       + r["tokens_out"]),
            ("cost / task", lambda r: r["cost_usd"]),
    ):
        ma, mb = mean([f(r) for r in a]), mean([f(r) for r in b])
        print(f"{label:<30}{ma:>12,.2f}{mb:>12,.2f}{ma/mb if mb else 0:>9.2f}")

    ra = mean([r["tokens_cached"] for r in a])
    rb = mean([r["tokens_cached"] for r in b])
    ta = mean([r["tokens_total"] for r in a])
    tb = mean([r["tokens_total"] for r in b])
    print(f"\n  Gap in total:      {tb - ta:>10,.0f} tokens")
    print(f"  Gap in cache_read: {rb - ra:>10,.0f} tokens "
          f"({100*(rb-ra)/(tb-ta):.1f}% of the gap)")
    print("\n  Arm A rebuilds its transcript every step to drop the previous")
    print("  screenshot, so it never re-reads a prefix and its total stays")
    print("  linear. Arm B appends, so every step re-reads everything before")
    print("  it. The gap is almost entirely re-read tokens, which are the")
    print("  cheapest kind — which is why A's *cost* is higher despite this.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", nargs="*", required=True)
    ap.add_argument("--no-rescore", action="store_true")
    args = ap.parse_args()

    rows = load(args.raw)
    if not args.no_rescore:
        rows, _ = rescore.apply(rows)
    good, _ = usable(rows)
    g = by_arm(good)

    print(f"token anatomy over {len(good)} usable runs")
    decompose(g)
    growth(g)
    per_step_payload(g)
    cost_vs_tokens(g)
    c_vs_b(good)
    a_vs_b(good)
    print()


if __name__ == "__main__":
    main()
