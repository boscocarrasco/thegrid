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

Round 1 covered only the verifiers that read the filesystem, and listed the
seven that read live page state over CDP as uncovered rather than faked. Round 2
covers those too, the only honest way available: the real page is launched, the
correct answer is submitted into it over CDP, and the real verifier is asked. A
stub that pretended to be a browser would have tested the stub.

Those cases need a live desktop (DISPLAY, the AT-SPI bus, Chromium). Without
one they are reported as skipped, never as passed.

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
    # round 2: menus and dialogs
    "menu_replace_all": {"notes/log.txt":
                         "PROJECT LOG\nfinal: opening notes\n"
                         "second line mentions final twice: final\n"
                         "closing line\n"},
    "menu_save_as_subdir": {"archive/minutes.txt": "beta line\n"},
    "menu_calc_insert_column": {"data/values-tagged.csv":
                                "code,item,qty,price\n,pens,10,1.5\n"
                                ",pads,4,3.25\n,ink,2,7\n"},
    "menu_files_new_folder": {"inbox/2026-Q1/report-draft.txt":
                              "QUARTERLY REPORT\nrevenue: 1240\n"
                              "costs: 830\nheadcount: 12\n",
                              "__remove__": ["inbox/report-draft.txt"]},
    # round 2: long tasks with separately checkable constraints
    "long_march_export": {"data/ledger.csv": suite.LEDGER_CSV,
                          "data/march.csv":
                          "date,region,amount\n2026-03-02,north,340\n"
                          "2026-03-08,south,215\n2026-03-19,east,455\n"},
    "long_notes_digest": {"notes/digest.txt":
                          "alpha: alpha one\nbeta: beta line\n"
                          "gamma: gamma line\n"},
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
    "menu_replace_all": {"notes/log.txt": suite.MENU_REPLACE_SRC},
    "long_march_export": {"data/ledger.csv": suite.LEDGER_CSV},
}

# What a correct agent would have put into each browser page, expressed as the
# javascript that puts it there. Executed over the same CDP channel the verifier
# reads back through, against the real page the task serves.
BROWSER_ANSWER = {
    "web_form": """
        document.getElementById('company').value='Northwind';
        document.getElementById('contact').value='ops@northwind.example';
        document.getElementById('country').value='es';
        document.getElementById('submit').click();
    """,
    "visual_chart": """
        document.getElementById('ans').value='Q3';
        document.getElementById('go').click();
    """,
    "visual_shapes": """
        document.getElementById('ans').value='4';
        document.getElementById('go').click();
    """,
    "visual_badge": """
        document.getElementById('ans').value='charlie';
        document.getElementById('go').click();
    """,
    "vdelta_rows": """
        document.getElementById('load').click();
        document.getElementById('ans').value='job-delta';
        document.getElementById('go').click();
    """,
    "vdelta_bars": """
        document.getElementById('go1').click();
        document.getElementById('ans').value='west';
        document.getElementById('go').click();
    """,
    "long_onboarding_form": """
        document.getElementById('company').value='Northwind';
        document.getElementById('vat').value='ES123456';
        document.getElementById('contact').value='Rosa Klein';
        document.getElementById('email').value='rosa@northwind.example';
        document.getElementById('phone').value='600111222';
        document.getElementById('city').value='Valencia';
        document.getElementById('postcode').value='46001';
        document.getElementById('country').value='es';
        document.getElementById('submit').click();
    """,
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


def desktop_available():
    if not os.environ.get("DISPLAY"):
        return False
    try:
        import subprocess
        return subprocess.run(["xdpyinfo"], capture_output=True,
                              timeout=10).returncode == 0
    except Exception:
        return False


def run_browser_case(task, submit_answer):
    """The only honest control for a CDP verifier: use the real page.

    The task's own setup serves and opens the page. For the positive control
    the correct answer is typed into it over CDP — the same channel the
    verifier reads back through, so nothing about the page is simulated. For
    the negative control the page is left exactly as it loaded.
    """
    import time
    task.setup(1)
    time.sleep(2.0)
    if submit_answer:
        js = BROWSER_ANSWER[task.id]
        # vdelta pages need the load click to settle before the answer lands.
        for chunk in [c.strip() for c in js.strip().split(";") if c.strip()]:
            val, err = suite._cdp_eval(chunk + ";")
            if val is None and err and "cdp" in err.lower():
                return None, err
            time.sleep(0.35)
        time.sleep(1.0)
    return task.verify()


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

    # ---- the CDP verifiers, against a real browser ----
    browser = [t for t in suite.SUITE if t.id in NEEDS_BROWSER]
    if not desktop_available():
        print()
        print("SKIPPED (no live desktop): "
              f"{', '.join(sorted(NEEDS_BROWSER))}")
        print("  These are not counted as passing.")
        skipped = len(browser)
    else:
        skipped = 0
        print()
        print(f"{'browser task':<24} {'accepts correct':<16} rejects unsolved")
        print("-" * 62)
        for task in browser:
            neg, why_neg = run_browser_case(task, submit_answer=False)
            pos, why_pos = run_browser_case(task, submit_answer=True)
            if pos is None:
                failures.append(f"{task.id}: CDP unavailable — {why_pos}")
                print(f"{task.id:<24} {'ERROR':<16} ERROR")
                continue
            if not pos:
                failures.append(
                    f"{task.id}: rejects the correct end state — {why_pos}")
            if neg:
                failures.append(f"{task.id}: accepts an untouched page")
            print(f"{task.id:<24} {'PASS' if pos else 'FAIL':<16} "
                  f"{'PASS' if not neg else 'FAIL'}")
        try:
            ws.kill_apps()
        except Exception:
            pass
    print()
    if failures:
        for f in failures:
            print(f"  {f}")
        print(f"RESULT: FAIL ({len(failures)} problems)")
        return 1
    total = len(tasks) + (len(browser) - skipped)
    note = f" ({skipped} skipped, no desktop)" if skipped else ""
    print(f"RESULT: PASS ({total} verifiers, positive and negative){note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
