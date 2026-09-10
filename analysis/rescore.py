#!/usr/bin/env python3.12
"""Re-score runs a broken verifier mis-judged, without rewriting the raw data.

`calc_total`'s verifier looked for the string "48.5". No correct answer
produces that number: the task asks for the total of the price column,
1.5 + 3.25 + 7.0 = 11.75. Every run that did the task correctly was therefore
recorded as a failure.

The raw JSONL is evidence and is never edited. What makes the correction
possible without re-running anything is that the broken verifier embedded the
bytes the agent actually produced inside its own failure message. Those bytes
are recovered here and put through the *fixed* rule — `tasks.suite.calc_total_ok`,
the same predicate the live verifier now calls, so the two cannot drift.

A run is only re-scored when the recovered payload is provably complete. The
old message truncated the file at 120 characters; anything at or over that
limit may be missing the total and is left exactly as it was recorded, counted
as indeterminate rather than quietly resolved in either direction.

Run it standalone to see what it would change:

    /usr/bin/python3.12 analysis/rescore.py results/raw/*.jsonl
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from tasks.suite import calc_total_ok  # noqa: E402

# What the broken verifier wrote, and the truncation it applied.
_BROKEN_MESSAGE = re.compile(r"^total 48\.5 not found in (?P<payload>.+)$", re.S)
_TRUNCATED_AT = 120

TASK = "calc_total"


def _recover_payload(detail):
    """The CSV the agent produced, back out of the failure message it caused.

    Returns None when this run's message is not the broken verifier's, or when
    the payload cannot be read back exactly as it was written.
    """
    m = _BROKEN_MESSAGE.match(detail or "")
    if not m:
        return None
    try:
        payload = ast.literal_eval(m.group("payload"))
    except (ValueError, SyntaxError):
        return None
    if not isinstance(payload, str):
        return None
    return payload


def apply(rows):
    """Return (rows, changes). `rows` is a new list; the input is not mutated.

    `changes` records one entry per run the pass looked at, so the correction
    can be reported rather than silently applied.
    """
    out, changes = [], []
    for r in rows:
        if r.get("task") != TASK or r.get("success"):
            out.append(r)
            continue

        payload = _recover_payload(r.get("verify_detail", ""))
        if payload is None:
            # Not the broken message — e.g. the file was never created, which
            # the old verifier judged correctly.
            out.append(r)
            continue

        if len(payload) >= _TRUNCATED_AT:
            changes.append({"arm": r.get("arm"), "seed": r.get("seed"),
                            "outcome": "indeterminate",
                            "reason": "payload truncated in the recorded message"})
            out.append(r)
            continue

        ok, why = calc_total_ok(payload)
        if not ok:
            changes.append({"arm": r.get("arm"), "seed": r.get("seed"),
                            "outcome": "unchanged", "reason": why})
            out.append(r)
            continue

        fixed = dict(r)
        fixed["success"] = True
        fixed["verify_detail"] = "ok (re-scored: " + why + ")"
        fixed["rescored"] = {
            "was": False,
            "task": TASK,
            "reason": "verifier looked for 48.5; the task's total is 11.75",
        }
        changes.append({"arm": r.get("arm"), "seed": r.get("seed"),
                        "outcome": "false negative corrected",
                        "reason": "wrote the correct total 11.75"})
        out.append(fixed)
    return out, changes


def summarise(changes):
    """One line per outcome class, for the header of a generated report."""
    counts = {}
    for c in changes:
        counts[c["outcome"]] = counts.get(c["outcome"], 0) + 1
    return counts


def main():
    paths = sys.argv[1:] or ["results/raw/main.jsonl"]
    rows = []
    for p in paths:
        if not os.path.exists(p):
            continue
        with open(p) as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    _, changes = apply(rows)
    if not changes:
        print(f"{len(rows)} runs read, nothing to re-score")
        return 0
    for c in changes:
        print(f"  arm {c['arm']} seed {c['seed']}: {c['outcome']} — {c['reason']}")
    print(f"{len(rows)} runs read; " +
          ", ".join(f"{n} {k}" for k, n in sorted(summarise(changes).items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
