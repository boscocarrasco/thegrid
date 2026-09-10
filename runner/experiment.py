#!/usr/bin/env python3.12
"""Experiment driver: interleaved, resumable, budget-aware.

Arms are run interleaved rather than in blocks, so any drift in the container
or the provider hits every arm equally. The run list is generated up front from
a fixed seed and executed in order; anything already present in the output
JSONL is skipped, so an interrupted run resumes where it stopped.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runner.loop import run_one          # noqa: E402
from tasks import suite as S             # noqa: E402
from tasks import workspace as ws        # noqa: E402


def desktop_alive():
    """Cheap check that Xvfb and the AT-SPI bus are both still there."""
    import subprocess
    if subprocess.run(["xdpyinfo"], capture_output=True).returncode != 0:
        return False
    try:
        import gi
        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi
        Atspi.init()
        Atspi.get_desktop(0).get_child_count()
        return True
    except Exception:
        return False


def build_plan(arms, task_ids, reps, plan_seed=20260910):
    """One entry per (task, arm, rep), ordered so arms interleave."""
    plan = []
    for rep in range(1, reps + 1):
        for tid in task_ids:
            for arm in arms:
                plan.append({"task": tid, "arm": arm, "rep": rep,
                             "seed": 1000 * rep + (hash(tid) % 997)})
    rng = random.Random(plan_seed)
    # Shuffle within each rep block: keeps arms interleaved but removes any
    # fixed task->position coupling that could interact with drift.
    out = []
    for rep in range(1, reps + 1):
        block = [p for p in plan if p["rep"] == rep]
        rng.shuffle(block)
        out.extend(block)
    return out


def already_done(path):
    done = set()
    if not os.path.exists(path):
        return done
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("terminated") in ("rate_limited", "harness_error"):
                continue          # retry those
            done.add((r["task"], r["arm"], r.get("rep", r.get("seed"))))
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="A,B,C")
    ap.add_argument("--tasks", default="", help="comma list; default = all")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--crop-ttl", type=int, default=3)
    ap.add_argument("--out", default="results/raw")
    ap.add_argument("--tag", default="main")
    ap.add_argument("--max-usd", type=float,
                    default=float(os.environ.get("MAX_API_SPEND_USD", "40")))
    ap.add_argument("--stop-frac", type=float, default=0.85)
    ap.add_argument("--deadline-utc", default="",
                    help="ISO time to stop at, e.g. 2026-09-10T15:30:00")
    ap.add_argument("--token-budget", type=int, default=None,
                    help="per-run token ceiling (equal-budget comparison)")
    ap.add_argument("--rate-limit-wait", type=int, default=0,
                    help="seconds to wait and retry when rate limited (0=stop)")
    args = ap.parse_args()

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    task_ids = ([t.strip() for t in args.tasks.split(",") if t.strip()]
                or [t.id for t in S.SUITE])
    plan = build_plan(arms, task_ids, args.reps)
    path = os.path.join(args.out, f"{args.tag}.jsonl")
    os.makedirs(args.out, exist_ok=True)
    done = already_done(path)

    deadline = None
    if args.deadline_utc:
        deadline = time.mktime(time.strptime(args.deadline_utc,
                                             "%Y-%m-%dT%H:%M:%S")) - time.timezone

    spend = 0.0
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                try:
                    spend += float(json.loads(line).get("cost_usd") or 0)
                except Exception:
                    pass

    stop_usd = args.max_usd * args.stop_frac
    print(f"plan: {len(plan)} runs ({len(task_ids)} tasks x {len(arms)} arms "
          f"x {args.reps} reps); {len(done)} already done; "
          f"spend so far ${spend:.2f}; stop at ${stop_usd:.2f}", flush=True)

    n_ok = n_run = 0
    for i, p in enumerate(plan, 1):
        key = (p["task"], p["arm"], p["rep"])
        if key in done:
            continue
        if spend >= stop_usd:
            print(f"STOP: reached 85% of spend budget (${spend:.2f})", flush=True)
            break
        if deadline and time.time() >= deadline:
            print("STOP: reached wall-clock deadline", flush=True)
            break

        if not desktop_alive():
            # A dead X server would silently score every remaining run as a
            # failure for whichever arm happened to be next, so stop rather
            # than record fiction.
            print("STOP: desktop is not alive (Xvfb or AT-SPI bus gone). "
                  "Re-run scripts/env_up.sh and resume.", flush=True)
            break

        task = S.BY_ID[p["task"]]
        t0 = time.time()
        rec = run_one(task, p["arm"], p["seed"], model=args.model,
                      crop_ttl=args.crop_ttl, out_dir=args.out,
                      run_tag=args.tag, token_budget=args.token_budget)
        rec_rep = p["rep"]
        # stamp the rep so resume can identify it
        with open(path, "r") as f:
            lines = f.readlines()
        if lines:
            last = json.loads(lines[-1])
            last["rep"] = rec_rep
            lines[-1] = json.dumps(last) + "\n"
            with open(path, "w") as f:
                f.writelines(lines)

        spend += rec["cost_usd"]
        n_run += 1
        n_ok += 1 if rec["success"] else 0
        print(f"[{i}/{len(plan)}] {p['arm']} {p['task']} rep{p['rep']} "
              f"-> {'OK ' if rec['success'] else 'FAIL'} "
              f"steps={rec['steps']} calls={rec['model_calls']} "
              f"${rec['cost_usd']:.4f} {time.time()-t0:.0f}s "
              f"term={rec['terminated']} | total ${spend:.2f}", flush=True)

        if rec["terminated"] == "rate_limited":
            if args.rate_limit_wait <= 0:
                print("STOP: rate limited by provider.", flush=True)
                break
            print(f"rate limited; sleeping {args.rate_limit_wait}s", flush=True)
            time.sleep(args.rate_limit_wait)

    ws.kill_apps()
    print(f"\ndone: {n_run} runs this session, {n_ok} succeeded, "
          f"total spend ${spend:.2f}", flush=True)


if __name__ == "__main__":
    main()
