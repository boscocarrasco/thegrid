#!/usr/bin/env python3.12
"""Do block identities survive a repaint, the way element ids do?

The same argument as `test_id_stability.py`, one level up. A block is a set of
elements that appears and disappears as a unit, and the enriched table groups
by it, names it and marks it fixed or variable. If a block's identity churns
when the application repaints, then every grouping the model is shown is noise,
and worse than the flat list it replaced — the model would be told the screen
restructured itself when nothing happened.

Four scenarios, matching the id test:

  1. idle       — two snapshots with nothing happening
  2. repaint    — a forced full-screen expose (xrefresh)
  3. content    — typing into the editor; the chrome's blocks must hold
  4. move       — the window is dragged; blocks keep their ids and their kind

And two assertions the id test has no analogue for:

  5. membership — an element does not wander between blocks while the screen
                  is unchanged
  6. kind       — a block does not flip between fixed and variable

Run:  /usr/bin/python3.12 tests/test_block_stability.py
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from observer import screen, table  # noqa: E402


def snap(apps=None):
    screen.wait_stable(timeout=3.0, quiet=0.25)
    return table.snapshot(apps=apps, enrich=True)


def blocks_of(t):
    return {bid: (b.role, b.name, b.kind) for bid, b in t.blocks.items()}


def compare(a, b, label):
    ba, bb = blocks_of(a), blocks_of(b)
    lost = set(ba) - set(bb)
    new = set(bb) - set(ba)
    kept = set(ba) & set(bb)
    churn = (len(lost) + len(new)) / max(len(ba), 1)
    flipped = [bid for bid in kept if ba[bid][2] != bb[bid][2]]
    ok = churn <= 0.05 and not flipped
    print(f"  [{label}] before={len(ba)} after={len(bb)} kept={len(kept)} "
          f"lost={len(lost)} new={len(new)} churn={churn:.1%} "
          f"kind-flips={len(flipped)} -> {'PASS' if ok else 'FAIL'}")
    for bid in list(lost)[:4]:
        print(f"      lost  {bid} {ba[bid]}")
    for bid in list(new)[:4]:
        print(f"      new   {bid} {bb[bid]}")
    for bid in flipped[:4]:
        print(f"      flip  {bid} {ba[bid][2]} -> {bb[bid][2]}")
    return ok


def membership(a, b, label):
    """Elements present in both snapshots must sit in the same block."""
    common = set(a.by_id) & set(b.by_id)
    moved = [i for i in common if a.by_id[i].block != b.by_id[i].block]
    ok = len(moved) <= max(1, len(common) // 50)
    print(f"  [{label}] shared elements={len(common)} "
          f"changed block={len(moved)} -> {'PASS' if ok else 'FAIL'}")
    for i in moved[:4]:
        e = b.by_id[i]
        print(f"      {i} {e.role} {e.name[:28]!r}: "
              f"{a.by_id[i].block} -> {e.block}")
    return ok


def main():
    from executor.actions import Executor
    ex = Executor()

    from tasks import workspace as ws
    work = ws.reset()
    ws.launch_editor(work + "/notes/alpha.txt")
    time.sleep(2.0)

    results = {}

    ex.key("alt+f")
    time.sleep(0.9)

    t0 = snap(apps={"mousepad"})
    print(f"baseline: {len(t0)} elements in {len(t0.blocks)} blocks")
    for bid, b in t0.blocks.items():
        print(f"    {bid} {b.role:14s} {b.name[:26]!r:28s} {b.kind:8s} n={b.n}")
    if len(t0.blocks) < 2:
        print("FAIL: too few blocks to test anything")
        return 1

    t1 = snap(apps={"mousepad"})
    results["idle"] = compare(t0, t1, "idle")
    results["idle_membership"] = membership(t0, t1, "idle-membership")

    r = subprocess.run(["xrefresh"], capture_output=True)
    if r.returncode != 0:
        subprocess.run(["xdotool", "search", "--name", "Mousepad",
                        "windowunmap", "%1"], capture_output=True)
        time.sleep(0.4)
        subprocess.run(["xdotool", "search", "--name", "Mousepad",
                        "windowmap", "%1"], capture_output=True)
    time.sleep(0.8)
    t2 = snap(apps={"mousepad"})
    results["repaint"] = compare(t0, t2, "repaint")

    ex.key("Escape")
    time.sleep(0.6)
    t0b = snap(apps={"mousepad"})
    ex.key("ctrl+a")
    ex.type("hello block stability test 12345")
    time.sleep(0.6)
    t3 = snap(apps={"mousepad"})
    results["content"] = compare(t0b, t3, "content")
    results["content_membership"] = membership(t0b, t3, "content-membership")

    subprocess.run(["xdotool", "search", "--name", "Mousepad",
                    "windowmove", "%@", "420", "260"], capture_output=True)
    time.sleep(1.2)
    t4 = snap(apps={"mousepad"})
    if t4.elements and t3.elements and \
            t4.elements[0].bbox[:2] == t3.elements[0].bbox[:2]:
        print("  [move] window did not actually move -> SKIP (not asserted)")
    else:
        results["move"] = compare(t3, t4, "move")
        results["move_membership"] = membership(t3, t4, "move-membership")

    # A modal dialog must create a block and mark everything behind it blocked.
    ex.key("ctrl+shift+s")
    time.sleep(1.6)
    t5 = snap(apps={"mousepad"})
    has_blocker = bool(t5.blockers)
    blocked = t5.n_blocked
    print(f"  [modal] blockers={len(t5.blockers)} elements blocked={blocked} "
          f"-> {'PASS' if has_blocker and blocked else 'FAIL'}")
    results["modal"] = bool(has_blocker and blocked)
    ex.key("Escape")

    ws.kill_apps()

    print("\n" + "=" * 60)
    for k, v in results.items():
        print(f"  {k:20} {'PASS' if v else 'FAIL'}")
    allok = all(results.values())
    print("RESULT:", "PASS" if allok else "FAIL")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
