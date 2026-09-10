#!/usr/bin/env python3.12
"""Positive and negative controls for the verifiers that decide every result.

A verifier is the one component whose silent failure is invisible: it does not
add noise to a result, it inverts one. `calc_total` shipped a check for a total
no correct answer produces (DECISIONS D6.1), and for the whole first version of
the report that read as a task LibreOffice was too hard to complete.

So each verifier is exercised twice, without a desktop:

  * **positive control** — build the end state the task asks for, byte for
    byte, and assert the verifier accepts it. This is what catches a check
    that cannot be satisfied.
  * **negative control** — leave the workspace at its starting state and
    assert the verifier rejects it. This is what catches a check that passes
    anything.

Only the verifiers that read the filesystem are covered. The four browser tasks
read live page state over CDP and need a running Chromium, so they are listed
as uncovered rather than faked — a stub that pretends to be a browser would
test the stub.

    /usr/bin/python3.12 tests/test_verifiers.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tasks import suite  # noqa: E402
from tasks import workspace as ws  # noqa: E402

# The end state each task asks for, written straight to disk. Anything not
# listed keeps whatever the starting workspace had.
CORRECT_END_STATE = {
    "files_save_as": {"archive/alpha-copy.txt": "alpha one\nalpha two\nalpha three\n"},
    "files_new_note": {"notes/shopping.txt": "bread\nmilk\nolives\n"},
    "files_rename": {"notes/gamma-final.txt": "gamma line\n",
                     "__remove__": ["notes/gamma.txt"]},
    "text_append": {"notes/beta.txt": "beta line\nAPPROVED\n"},
    "text_replace": {"inbox/report-draft.txt": "QUARTERLY REPORT\nrevenue: 1560\n"
                                               "costs: 830\nheadcount: 12\n"},
    "text_delete_line": {"notes/todo.txt": "buy milk\nwrite report\n"},
    "text_uppercase": {"notes/quiet.txt": "THE MEETING IS AT NOON\n"},
    "calc_total": {"data/values-total.csv": "item,qty,price\npens,10,1.5\n"
                                            "pads,4,3.25\nink,2,7\n,,11.75\n"},
    "calc_add_row": {"data/values-plus.csv": "item,qty,price\npens,10,1.5\n"
                                             "pads,4,3.25\nink,2,7\ntape,6,2\n"},
    "calc_count_eng": {"data/eng-count.txt": "2\n"},
    "cross_report_summary": {"archive/summary.txt": "revenue: 1240\ncosts: 830\n"},
    "cross_inventory_note": {"notes/inventory-note.txt": "3\n"},
    # long tasks
    "long_three_notes": {"notes/n1.txt": "alpha\n",
                         "notes/n2.txt": "bravo\n",
                         "notes/n3.txt": "charlie\n"},
    "long_ledger_edits": {"notes/ledger.txt":
                          "ITEM ONE: 111\nITEM TWO: 222\nITEM THREE: 333\n"
                          "ITEM FOUR: 444\nITEM FIVE: 500\n"},
    "long_region_transfer": {"archive/regions.txt": "41\n52\n63\n74\n"},
}

# Verifiers that need a live browser, and therefore a live desktop.
NEEDS_BROWSER = {"web_form", "visual_chart", "visual_shapes", "visual_badge",
                 "vdelta_rows", "vdelta_bars", "long_onboarding_form"}

# The starting workspace, as tasks/workspace.py builds it. Reproduced through
# that module rather than copied, so a fixture change cannot silently diverge.
STARTING_FILES = ws._fixtures()

# Two tasks seed an extra file through `reset(extra_files=...)` at setup time.
EXTRA_SETUP_FILES = {
    "text_delete_line": {"notes/todo.txt": "buy milk\nCANCELLED: old task\n"
                                           "write report\n"},
    "text_uppercase": {"notes/quiet.txt": "the meeting is at noon\n"},
}


def build_workspace(root, task_id, apply_end_state):
    """Lay out a workspace: the starting fixtures, then optionally the answer."""
    files = dict(STARTING_FILES)
    files.update(EXTRA_SETUP_FILES.get(task_id, {}))
    if apply_end_state:
        end = dict(CORRECT_END_STATE[task_id])
        for rel in end.pop("__remove__", []):
            files.pop(rel, None)
        files.update(end)
    for rel, content in files.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
    return root


def run_case(task, apply_end_state):
    """Point the verifiers at a temporary workspace and run one."""
    root = tempfile.mkdtemp(prefix="grid-verify-")
    original = suite.WORK
    try:
        build_workspace(root, task.id, apply_end_state)
        suite.WORK = root
        return task.verify()
    finally:
        suite.WORK = original
        shutil.rmtree(root, ignore_errors=True)


def main():
    tasks = [t for t in suite.SUITE if t.id not in NEEDS_BROWSER]
    missing = [t.id for t in tasks if t.id not in CORRECT_END_STATE]
    if missing:
        print(f"FAIL  no end state defined for {missing}")
        return 1

    failures = []
    print(f"{'task':<24} {'accepts correct':<16} rejects unsolved")
    print("-" * 62)
    for task in tasks:
        ok_pos, why_pos = run_case(task, apply_end_state=True)
        ok_neg, why_neg = run_case(task, apply_end_state=False)

        if not ok_pos:
            failures.append(f"{task.id}: rejects the correct end state — {why_pos}")
        if ok_neg:
            failures.append(f"{task.id}: accepts an untouched workspace")

        print(f"{task.id:<24} {'PASS' if ok_pos else 'FAIL':<16} "
              f"{'PASS' if not ok_neg else 'FAIL'}")

    print()
    print(f"not covered (need a live browser): {', '.join(sorted(NEEDS_BROWSER))}")
    print()
    if failures:
        for f in failures:
            print(f"  {f}")
        print(f"RESULT: FAIL ({len(failures)} problems)")
        return 1
    print(f"RESULT: PASS ({len(tasks)} verifiers, positive and negative)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
