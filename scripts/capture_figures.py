#!/usr/bin/env python3.12
"""Produce the figures the report/artifact uses, from the live desktop.

Every image here is a real capture taken through the same code path the
experiment uses — `observer.screen` — not a mock-up. Written to
results/figures/.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw  # noqa: E402

from executor.actions import Executor  # noqa: E402
from observer import delta as D, screen, table as tbl  # noqa: E402
from tasks import suite, workspace as ws  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "results", "figures")
os.makedirs(OUT, exist_ok=True)
meta = {}


def save(im, name, note=""):
    p = os.path.join(OUT, name)
    im.save(p, optimize=True)
    meta[name] = {"size": list(im.size), "bytes": os.path.getsize(p),
                  "tokens": screen.image_tokens(im.size), "note": note}
    print(f"  {name}: {im.size} {os.path.getsize(p)//1024}kB "
          f"~{screen.image_tokens(im.size)} tok")


def label_strip(im, text, h=26):
    """Put a caption bar under a crop so the figure is self-explanatory."""
    out = Image.new("RGB", (im.width, im.height + h), "#111318")
    out.paste(im, (0, 0))
    d = ImageDraw.Draw(out)
    d.text((6, im.height + 7), text[:110], fill="#cfd6e4")
    return out


def fig_editor():
    """The desktop as the agent sees it, plus what the tree says about it."""
    print("editor figure...")
    ws.reset()
    ws.launch_editor(os.path.join(ws.WORK, "notes/alpha.txt"))
    screen.wait_stable()
    a = screen.anchor_capture()
    im = screen.grab().resize(screen.ANCHOR_SIZE, Image.LANCZOS)
    save(im, "fig1_anchor.png", "anchor capture, arm B/C send this once")
    t = tbl.snapshot()
    with open(os.path.join(OUT, "fig1_table.txt"), "w") as f:
        f.write(t.render())
    meta["fig1_table.txt"] = {"elements": len(t),
                              "chars": len(t.render())}
    print(f"  table: {len(t)} elements")


def fig_vdelta():
    """The task that separates B from C, and the crops arm B actually sends."""
    print("vdelta figure...")
    t = suite.BY_ID["vdelta_rows"]
    t.setup(1)
    time.sleep(2)
    screen.wait_stable()
    before = tbl.snapshot()

    btn = [e for e in before.elements if e.name == "Load"]
    save(screen.grab().resize(screen.ANCHOR_SIZE, Image.LANCZOS),
         "fig2_before.png", "before the click: the rows do not exist yet")

    ex = Executor()
    ex.click(btn[0].id, live_table=before)
    time.sleep(1.5)
    screen.wait_stable()
    after = tbl.snapshot()
    save(screen.grab().resize(screen.ANCHOR_SIZE, Image.LANCZOS),
         "fig2_after.png", "after the click: one row is red, the tree cannot say which")

    changes = D.diff(before, after)
    added = [c for c in changes if c.verb == "added"]

    # what arm B sends: one labelled crop per added element
    crops = []
    for ch in added:
        el = after.get(ch.eid)
        if el is None:
            continue
        c = screen.crop_for(el.bbox, ch.eid)
        im = Image.open(os.path.join(OUT, "_tmp.png")) if False else None
        import base64
        import io
        im = Image.open(io.BytesIO(base64.b64decode(c["b64"])))
        crops.append((label_strip(im, f'#{ch.eid} "{el.name}"  {c["tokens"]} tok'),
                      c["tokens"]))
    if crops:
        w = max(c[0].width for c in crops)
        h = sum(c[0].height + 6 for c in crops)
        sheet = Image.new("RGB", (w, h), "#0b0d11")
        y = 0
        for im, _ in crops:
            sheet.paste(im, (0, y))
            y += im.height + 6
        save(sheet, "fig3_arm_b_crops.png",
             f"the {len(crops)} crops arm B sends; arm C sends none of this")
        meta["fig3_arm_b_crops.png"]["crop_tokens_total"] = sum(c[1] for c in crops)

    # what arm C sends: text only
    with open(os.path.join(OUT, "fig3_arm_c_text.txt"), "w") as f:
        f.write(D.render_changes(changes))
    print("  arm C text written")


def fig_delta_example():
    """A plain before/after delta on the editor, to show the verbs."""
    print("delta figure...")
    ws.reset()
    ws.launch_editor(os.path.join(ws.WORK, "notes/alpha.txt"))
    screen.wait_stable()
    t0 = tbl.snapshot(apps={"mousepad"})
    ex = Executor()
    ex.key("alt+f")
    time.sleep(1.0)
    screen.wait_stable()
    t1 = tbl.snapshot(apps={"mousepad"})
    ch = D.diff(t0, t1)
    with open(os.path.join(OUT, "fig4_delta.txt"), "w") as f:
        f.write(D.render_changes(ch))
    save(screen.grab().crop((80, 60, 700, 460)),
         "fig4_menu.png", "the File menu open; the delta below is what B/C send")
    print(f"  {len(ch)} changes")


def main():
    fig_editor()
    fig_vdelta()
    fig_delta_example()
    ws.kill_apps()
    with open(os.path.join(OUT, "figures.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"\nwrote {len(meta)} artefacts to {OUT}")


if __name__ == "__main__":
    main()
