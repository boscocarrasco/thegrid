#!/usr/bin/env python3.12
"""Do element ids survive a repaint?

If they do not, every delta downstream is noise and the whole experiment is
measuring nothing. Four scenarios, in increasing order of nastiness:

  1. idle       — two snapshots with nothing happening
  2. repaint    — a forced full-screen expose (xrefresh)
  3. content    — typing into the editor; the chrome must keep its ids
  4. move       — dragging the window; ids must survive, emitting `moved`
                  rather than a storm of removed+added

Run:  /usr/bin/python3.12 tests/test_id_stability.py
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from observer import delta, screen, table  # noqa: E402


def snap(apps=None):
    screen.wait_stable(timeout=3.0, quiet=0.25)
    return table.snapshot(apps=apps)


def compare(a, b, label, allow_content_ids=()):
    ids_a, ids_b = set(a.by_id), set(b.by_id)
    lost = ids_a - ids_b
    new = ids_b - ids_a
    lost = {i for i in lost if i not in allow_content_ids}
    new = {i for i in new if i not in allow_content_ids}
    kept = len(ids_a & ids_b)
    total = max(len(ids_a), 1)
    churn = (len(lost) + len(new)) / total
    ok = churn <= 0.05
    print(f"  [{label}] before={len(ids_a)} after={len(ids_b)} "
          f"kept={kept} lost={len(lost)} new={len(new)} churn={churn:.1%} "
          f"-> {'PASS' if ok else 'FAIL'}")
    if lost:
        for i in list(lost)[:5]:
            e = a.by_id[i]
            print(f"      lost  #{i} {e.role} {e.name[:32]!r} {e.bbox}")
    if new:
        for i in list(new)[:5]:
            e = b.by_id[i]
            print(f"      new   #{i} {e.role} {e.name[:32]!r} {e.bbox}")
    return ok


def main():
    from executor.actions import Executor
    ex = Executor()

    from tasks import workspace as ws
    work = ws.reset()
    ws.launch_editor(work + "/notes/alpha.txt")
    p = None

    results = {}

    # Open a menu so the table under test is a realistic size: at rest the
    # editor only exposes six menus and the text area, which is too thin a
    # surface to conclude anything from.
    ex.key("alt+f")          # File menu
    time.sleep(0.9)

    t0 = snap(apps={"mousepad"})
    print(f"baseline: {len(t0)} elements")
    if len(t0) < 10:
        print("FAIL: editor exposed too few elements to test anything")
        return 1

    # 1. idle
    t1 = snap(apps={"mousepad"})
    results["idle"] = compare(t0, t1, "idle")

    # 2. forced repaint
    r = subprocess.run(["xrefresh"], capture_output=True)
    if r.returncode != 0:
        # fall back: unmap/remap another window to force an expose
        subprocess.run(["xdotool", "search", "--name", "Mousepad",
                        "windowunmap", "%1"], capture_output=True)
        time.sleep(0.4)
        subprocess.run(["xdotool", "search", "--name", "Mousepad",
                        "windowmap", "%1"], capture_output=True)
    time.sleep(0.8)
    t2 = snap(apps={"mousepad"})
    results["repaint"] = compare(t0, t2, "repaint")

    # 3. content change — chrome ids must hold
    ex.key("Escape")         # close the menu before typing
    time.sleep(0.6)
    t0 = snap(apps={"mousepad"})
    ex.key("ctrl+a")
    ex.type("hello repaint stability test 12345")
    time.sleep(0.6)
    t3 = snap(apps={"mousepad"})
    # ids whose *content* legitimately changed are allowed to differ only if
    # their id is derived from the text; that is exactly what we are testing,
    # so nothing is whitelisted here.
    results["content"] = compare(t0, t3, "content")
    d = delta.diff(t0, t3)
    print("      delta verbs:",
          {v: sum(1 for c in d if c.verb == v)
           for v in ("added", "removed", "changed", "moved", "state")})

    # 4. window move — must produce `moved`, not removed+added
    subprocess.run(["xdotool", "search", "--name", "Mousepad",
                    "windowmove", "%@", "420", "260"], capture_output=True)
    time.sleep(1.2)
    t4 = snap(apps={"mousepad"})
    d4 = delta.diff(t3, t4)
    verbs = {v: sum(1 for c in d4 if c.verb == v)
             for v in ("added", "removed", "changed", "moved", "state")}
    if verbs["moved"] == 0 and verbs["added"] == 0 and verbs["removed"] == 0:
        # The window manager refused the move; a test that asserts nothing
        # must not report PASS.
        print("  [move] window did not actually move -> SKIP (not asserted)")
        print("      delta verbs:", verbs)
    else:
        results["move"] = compare(t3, t4, "move")
        print("      delta verbs:", verbs)
        moved_dominates = verbs["moved"] >= verbs["added"] + verbs["removed"]
        print(f"      moved dominates add/remove: "
              f"{'PASS' if moved_dominates else 'FAIL'}")
        results["move_verb"] = moved_dominates

    ws.kill_apps()

    print("\n" + "=" * 60)
    for k, v in results.items():
        print(f"  {k:12} {'PASS' if v else 'FAIL'}")
    allok = all(results.values())
    print("RESULT:", "PASS" if allok else "FAIL")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
