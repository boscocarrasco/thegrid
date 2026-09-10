"""Action execution over XTEST, with validation at the instant of acting.

The point of `click(id)` is that coordinates are resolved against a *fresh*
table at the moment of the click, not against whatever the model saw several
hundred milliseconds ago. If the element has vanished or changed state since,
the action aborts instead of landing somewhere arbitrary. Every abort is
counted: it is one of the metrics.
"""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field

from observer import table as tbl


@dataclass
class ActionResult:
    ok: bool
    kind: str
    detail: str = ""
    aborted: bool = False        # validation refused to act
    grounding_failure: bool = False   # acted, but hit nothing / changed nothing
    coords: tuple = None
    elapsed_s: float = 0.0
    extra: dict = field(default_factory=dict)


def _xdo(*args, timeout=10):
    return subprocess.run(["xdotool", *args], capture_output=True,
                          text=True, timeout=timeout)


class Executor:
    """Executes actions and keeps the counters the experiment reports."""

    def __init__(self, screen_w=1920, screen_h=1080):
        self.w, self.h = screen_w, screen_h
        self.action_aborts = 0
        self.grounding_failures = 0
        self.abort_log = []

    # ---------- primitives ----------

    def _click_xy(self, x, y, button=1, double=False):
        x = int(max(0, min(x, self.w - 1)))
        y = int(max(0, min(y, self.h - 1)))
        _xdo("mousemove", "--sync", str(x), str(y))
        if double:
            _xdo("click", "--repeat", "2", "--delay", "80", str(button))
        else:
            _xdo("click", str(button))
        return (x, y)

    # ---------- id-addressed actions (arms B, C, D) ----------

    def click(self, eid, expect_states=None, live_table=None, double=False):
        """Resolve `eid` against the table as it is *now*, then click.

        `expect_states` is what the model was told the element's state was; if
        it no longer holds, we abort rather than act on a stale belief.
        """
        t0 = time.time()
        cur = live_table if live_table is not None else tbl.snapshot(self.w, self.h)
        el = cur.get(eid)
        if el is None:
            self.action_aborts += 1
            self.abort_log.append({"reason": "element_gone", "id": eid})
            return ActionResult(False, "click", f"element #{eid} no longer present",
                                aborted=True, elapsed_s=time.time() - t0)
        if expect_states:
            missing = [s for s in expect_states if s not in el.states]
            if missing:
                self.action_aborts += 1
                self.abort_log.append({"reason": "state_changed", "id": eid,
                                       "missing": missing})
                return ActionResult(False, "click",
                                    f"#{eid} lost expected state(s) {missing}",
                                    aborted=True, elapsed_s=time.time() - t0)
        if "enabled" in el.states or "sensitive" in el.states or not el.states:
            pass
        else:
            self.action_aborts += 1
            self.abort_log.append({"reason": "not_enabled", "id": eid})
            return ActionResult(False, "click", f"#{eid} is not enabled",
                                aborted=True, elapsed_s=time.time() - t0)

        coords = self._click_xy(*el.click, double=double)
        return ActionResult(True, "click", f"#{eid} {el.role} \"{el.name[:40]}\"",
                            coords=coords, elapsed_s=time.time() - t0,
                            extra={"bbox": el.bbox})

    # ---------- coordinate-addressed action (arm A only) ----------

    def click_xy(self, x, y, live_table=None, double=False):
        """Arm A's action. A click that lands on no element is a grounding
        failure — that is the metric the whole tool is supposed to remove."""
        t0 = time.time()
        cur = live_table if live_table is not None else tbl.snapshot(self.w, self.h)
        hit = None
        best_area = None
        for e in cur.elements:
            bx, by, bw, bh = e.bbox
            if bx <= x < bx + bw and by <= y < by + bh:
                area = bw * bh
                if best_area is None or area < best_area:
                    best_area, hit = area, e
        coords = self._click_xy(x, y, double=double)
        if hit is None:
            self.grounding_failures += 1
            return ActionResult(True, "click_xy", f"({x},{y}) hit no element",
                                grounding_failure=True, coords=coords,
                                elapsed_s=time.time() - t0)
        return ActionResult(True, "click_xy",
                            f"({x},{y}) -> {hit.role} \"{hit.name[:40]}\"",
                            coords=coords, elapsed_s=time.time() - t0,
                            extra={"hit_id": hit.id})

    # ---------- shared actions ----------

    def type(self, text):
        t0 = time.time()
        _xdo("type", "--clearmodifiers", "--delay", "12", text, timeout=60)
        return ActionResult(True, "type", f"typed {len(text)} chars",
                            elapsed_s=time.time() - t0)

    def key(self, combo):
        t0 = time.time()
        for part in combo.split():
            _xdo("key", "--clearmodifiers", part)
            time.sleep(0.04)
        return ActionResult(True, "key", combo, elapsed_s=time.time() - t0)

    def scroll(self, eid, delta, live_table=None):
        t0 = time.time()
        cur = live_table if live_table is not None else tbl.snapshot(self.w, self.h)
        el = cur.get(eid)
        if el is None:
            self.action_aborts += 1
            self.abort_log.append({"reason": "element_gone", "id": eid})
            return ActionResult(False, "scroll", f"#{eid} no longer present",
                                aborted=True, elapsed_s=time.time() - t0)
        x, y = el.click
        _xdo("mousemove", "--sync", str(int(x)), str(int(y)))
        button = "4" if delta < 0 else "5"
        _xdo("click", "--repeat", str(min(abs(int(delta)), 15)), "--delay", "40", button)
        return ActionResult(True, "scroll", f"#{eid} by {delta}",
                            elapsed_s=time.time() - t0)

    def scroll_xy(self, x, y, delta):
        t0 = time.time()
        _xdo("mousemove", "--sync", str(int(x)), str(int(y)))
        button = "4" if delta < 0 else "5"
        _xdo("click", "--repeat", str(min(abs(int(delta)), 15)), "--delay", "40", button)
        return ActionResult(True, "scroll_xy", f"({x},{y}) by {delta}",
                            elapsed_s=time.time() - t0)
