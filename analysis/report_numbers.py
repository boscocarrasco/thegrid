#!/usr/bin/env python3.12
"""Pull the specific figures REPORT.md quotes, so the prose cannot drift.

Prints a compact block of every number the report cites, computed from the raw
JSONL. If a figure is not in this output, it does not belong in the report.
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, __file__.rsplit("/", 2)[0])

from analysis.aggregate import boot_ci, ci_str, load, overlaps, usable  # noqa


def arm_rows(rows):
    d = defaultdict(list)
    for r in rows:
        d[r["arm"]].append(r)
    return d


def q(rows, key):
    return boot_ci([r[key] for r in rows])


def ratio(a, b):
    return (a / b) if b else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", nargs="*", default=["results/raw/main.jsonl"])
    ap.add_argument("--eqb", nargs="*", default=["results/raw/eqbudget.jsonl"])
    args = ap.parse_args()

    rows = load(args.raw)
    good, dropped = usable(rows)
    g = arm_rows(good)

    print("=" * 70)
    print("COUNTS")
    print(f"  recorded={len(rows)} usable={len(good)} excluded={len(dropped)}")
    for a in sorted(g):
        succ = sum(1 for r in g[a] if r["success"])
        print(f"  arm {a}: n={len(g[a])} success={succ} "
              f"({100.0*succ/len(g[a]):.1f}%)")
    per = defaultdict(int)
    for r in good:
        per[(r["task"], r["arm"])] += 1
    print(f"  reps per (task,arm): min={min(per.values())} max={max(per.values())}")
    print(f"  tasks={len(set(r['task'] for r in good))}")
    print(f"  total spend on experiment=${sum(r['cost_usd'] for r in rows):.2f}")

    keys = ["success", "steps", "model_calls", "tokens_total", "image_tokens",
            "observation_tokens", "tokens_cached", "tokens_cache_create",
            "tokens_out", "cost_usd", "wall_time_total_s",
            "grounding_failures", "action_aborts"]
    print("\n" + "=" * 70)
    print("PER-ARM MEANS [95% bootstrap CI]")
    for a in sorted(g):
        print(f"\n  --- arm {a} (n={len(g[a])}) ---")
        for k in keys:
            nd = 4 if k == "cost_usd" else (3 if k in ("success", "grounding_failures", "action_aborts") else 1)
            print(f"    {k:24} {ci_str(q(g[a], k), nd)}")
        cache_tot = sum(r["tokens_cached"] + r["tokens_cache_create"]
                        + r["tokens_in"] for r in g[a])
        hit = sum(r["tokens_cached"] for r in g[a]) / cache_tot if cache_tot else 0
        print(f"    {'cache_hit_share':24} {100*hit:.1f}%")
        ncomp = sum(1 for r in g[a] if r["success"])
        if ncomp:
            print(f"    {'calls/completed':24} "
                  f"{sum(r['model_calls'] for r in g[a])/ncomp:.2f}")
            print(f"    {'cost/completed':24} "
                  f"${sum(r['cost_usd'] for r in g[a])/ncomp:.4f}")
            print(f"    {'tokens/completed':24} "
                  f"{sum(r['tokens_total'] for r in g[a])/ncomp:,.0f}")

    print("\n" + "=" * 70)
    print("PAIRWISE (mean ratio, and whether CIs overlap)")
    for x, y in (("A", "B"), ("A", "C"), ("B", "C")):
        if x not in g or y not in g:
            continue
        print(f"\n  {x} vs {y}")
        for k in keys:
            mx, my = q(g[x], k), q(g[y], k)
            ov = overlaps(mx, my)
            r = ratio(mx[0], my[0])
            print(f"    {k:24} {mx[0]:>12,.4f} vs {my[0]:>12,.4f}  "
                  f"ratio={r:>7.2f}x  {'OVERLAP' if ov else 'SEPARATED'}")

    print("\n" + "=" * 70)
    print("PER-STEP LATENCY")
    for a in sorted(g):
        tt = [st.mean(r["ttft_per_step_ms"]) for r in g[a] if r["ttft_per_step_ms"]]
        dc = [st.mean(r["decode_time_per_step_ms"]) for r in g[a]
              if r["decode_time_per_step_ms"]]
        obs = [r["observe_time_s"] / max(1, r["steps"]) * 1000 for r in g[a]]
        print(f"  arm {a}: ttft={ci_str(boot_ci(tt),0)}ms "
              f"decode={ci_str(boot_ci(dc),0)}ms "
              f"observe/step={ci_str(boot_ci(obs),0)}ms")

    print("\n" + "=" * 70)
    print("VISUAL vs NON-VISUAL (does B beat C where pixels matter?)")
    for label, pred in (("visual", lambda r: "visual" in r.get("tags", [])),
                        ("non-visual", lambda r: "visual" not in r.get("tags", []))):
        print(f"\n  {label}:")
        for a in sorted(g):
            rs = [r for r in g[a] if pred(r)]
            if not rs:
                continue
            sr = boot_ci([1.0 if r["success"] else 0.0 for r in rs])
            print(f"    arm {a}: n={len(rs)} success={ci_str(sr,3)} "
                  f"img_tokens={ci_str(boot_ci([r['image_tokens'] for r in rs]),0)} "
                  f"steps={ci_str(boot_ci([r['steps'] for r in rs]),1)}")

    print("\n" + "=" * 70)
    print("FAILURES BY TASK AND ARM")
    ft = defaultdict(list)
    for r in good:
        if not r["success"]:
            ft[(r["task"], r["arm"])].append(r["verify_detail"][:70])
    for (t, a), v in sorted(ft.items()):
        print(f"  {a} {t}: {len(v)}x  e.g. {v[0]}")

    print("\n" + "=" * 70)
    print("TERMINATION REASONS")
    tr = defaultdict(int)
    for r in good:
        tr[(r["arm"], r["terminated"])] += 1
    for k, v in sorted(tr.items()):
        print(f"  {k[0]} {k[1]:16} {v}")

    # ---- equal budget, if that sweep was run ----
    eq = load(args.eqb)
    eqgood, _ = usable(eq)
    if eqgood:
        print("\n" + "=" * 70)
        print("EQUAL-TOKEN-BUDGET SWEEP (separate run, raised step ceiling)")
        ge = arm_rows(eqgood)
        for a in sorted(ge):
            rs = ge[a]
            sr = boot_ci([1.0 if r["success"] else 0.0 for r in rs])
            print(f"  arm {a}: n={len(rs)} budget={rs[0].get('token_budget')} "
                  f"success={ci_str(sr,3)} "
                  f"steps={ci_str(boot_ci([r['steps'] for r in rs]),1)} "
                  f"tokens={ci_str(boot_ci([r['tokens_total'] for r in rs]),0)}")
            hitb = sum(1 for r in rs if r["terminated"] == "token_budget")
            print(f"           stopped by budget: {hitb}/{len(rs)}")
    else:
        print("\n(equal-budget sweep: no data)")


if __name__ == "__main__":
    main()
