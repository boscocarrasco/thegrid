#!/usr/bin/env python3.12
"""Gate check: the accessibility tree must actually populate.

Launches a GTK app and a LibreOffice Calc window, walks the AT-SPI tree, and
reports how many actionable elements each exposes with a usable bounding box.
If this prints FAIL there is no experiment to run.
"""
import os
import subprocess
import sys
import time

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi  # noqa: E402

ACTIONABLE = {
    "push button", "toggle button", "check box", "radio button", "menu item",
    "check menu item", "radio menu item", "menu", "text", "entry", "combo box",
    "list item", "table cell", "tab", "page tab", "link", "slider", "spin button",
    "tree item", "document frame", "paragraph", "icon", "table column header",
}


def walk(node, depth=0, out=None, maxdepth=14):
    if out is None:
        out = []
    if depth > maxdepth:
        return out
    try:
        role = node.get_role_name()
        name = node.get_name() or ""
    except Exception:
        return out
    try:
        comp = node.get_component_iface()
        ext = comp.get_extents(Atspi.CoordType.SCREEN) if comp else None
        bbox = (ext.x, ext.y, ext.width, ext.height) if ext else None
    except Exception:
        bbox = None
    out.append((depth, role, name[:40], bbox))
    try:
        n = node.get_child_count()
    except Exception:
        n = 0
    for i in range(min(n, 200)):
        try:
            c = node.get_child_at_index(i)
        except Exception:
            continue
        if c is not None:
            walk(c, depth + 1, out, maxdepth)
    return out


def launch(cmd, wait=6.0):
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         env=os.environ.copy())
    time.sleep(wait)
    return p


def report(label, apps_before):
    desktop = Atspi.get_desktop(0)
    n = desktop.get_child_count()
    found = {}
    for i in range(n):
        try:
            app = desktop.get_child_at_index(i)
            if app is None:
                continue
            aname = app.get_name() or f"<app{i}>"
        except Exception:
            continue
        if aname in apps_before:
            continue
        nodes = walk(app)
        act = [x for x in nodes
               if x[1] in ACTIONABLE and x[3] and x[3][2] > 0 and x[3][3] > 0]
        found[aname] = (len(nodes), len(act))
    print(f"\n=== {label} ===")
    for k, (tot, act) in sorted(found.items()):
        print(f"  app={k!r:28} nodes={tot:5d} actionable_with_bbox={act:4d}")
    return found


def main():
    Atspi.init()
    desktop = Atspi.get_desktop(0)
    baseline = set()
    for i in range(desktop.get_child_count()):
        try:
            baseline.add(desktop.get_child_at_index(i).get_name())
        except Exception:
            pass
    print("apps on bus at start:", sorted(baseline))

    procs = []
    ok = True

    procs.append(launch(["mousepad"], 5))
    f1 = report("mousepad (GTK3)", baseline)
    if not any(a > 3 for _, a in f1.values()):
        print("  FAIL: GTK app exposed no actionable elements")
        ok = False

    procs.append(launch(["pcmanfm", "--new-win", os.path.expanduser("~")], 6))
    report("pcmanfm (GTK file manager)", baseline)

    procs.append(launch(["localc", "--norestore", "--nologo"], 22))
    f3 = report("LibreOffice Calc", baseline)
    lo = {k: v for k, v in f3.items() if "soffice" in k.lower() or "libre" in k.lower()}
    if not lo or not any(a > 3 for _, a in lo.values()):
        print("  WARN: LibreOffice exposed few/no actionable elements")

    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
