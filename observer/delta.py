"""Delta between two element tables, expressed with verbs.

Verbs and what they mean, following the spec:

    added    an id present now that was not present before
    removed  an id present before that is gone now
    changed  same id, different name/text  (subdivided: text-only or not)
    moved    same id, same content, different bbox
    state    same id, different state set

The `changed` split matters: a change that is only a string the tree already
reports literally, with the bbox unmoved, is the single case the spec says
needs no crop.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Change:
    verb: str                   # added|removed|changed|moved|state
    eid: str
    role: str = ""
    name: str = ""
    bbox: Optional[tuple] = None
    click: Optional[tuple] = None
    detail: str = ""            # human-readable payload
    text_only: bool = False     # only meaningful for verb == "changed"
    visual: bool = False        # element's pixels carry non-tree information
    tree_described: bool = True  # tree can fully describe this change

    def render(self) -> str:
        sig = {"added": "+", "removed": "-", "changed": "~",
               "moved": "~", "state": "!"}.get(self.verb, "?")
        parts = [f'{sig} {self.verb:<7} #{self.eid}']
        if self.role:
            parts.append(self.role)
        if self.name:
            parts.append(f'"{self.name[:48]}"')
        if self.bbox and self.verb in ("added", "moved"):
            x, y, w, h = self.bbox
            parts.append(f"bbox=[{x},{y},{w},{h}]")
        if self.click and self.verb == "added":
            parts.append(f"click=[{self.click[0]},{self.click[1]}]")
        if self.detail:
            parts.append(self.detail)
        return "  ".join(parts)


# Noise filter: things that change without meaning anything.
_NOISE_NAMES = ("caret", "cursor", "blink")


def _is_noise(ch: Change) -> bool:
    n = (ch.name or "").lower()
    if any(k in n for k in _NOISE_NAMES):
        return True
    # A pure "focused"/"showing" flicker on the same element with nothing else
    # changing is not information the agent can act on.
    if ch.verb == "state" and ch.detail in ("focused added", "focused removed"):
        return True
    return False


def diff(prev, curr, drop_noise: bool = True):
    """prev, curr: ElementTable. Returns list[Change]."""
    changes = []
    prev_ids = set(prev.by_id) if prev else set()
    curr_ids = set(curr.by_id)

    for eid in curr_ids - prev_ids:
        e = curr.by_id[eid]
        changes.append(Change(
            verb="added", eid=eid, role=e.role, name=e.name, bbox=e.bbox,
            click=e.click, visual=e.visual,
            detail=(f'text="{e.text[:80]}"' if e.text else ""),
            tree_described=not e.visual,
        ))

    for eid in prev_ids - curr_ids:
        e = prev.by_id[eid]
        changes.append(Change(verb="removed", eid=eid, role=e.role, name=e.name))

    for eid in curr_ids & prev_ids:
        a, b = prev.by_id[eid], curr.by_id[eid]
        if a.states != b.states:
            gained = [s for s in b.states if s not in a.states]
            lost = [s for s in a.states if s not in b.states]
            bits = []
            if lost:
                bits.append(" ".join(lost) + " removed")
            if gained:
                bits.append(" ".join(gained) + " added")
            changes.append(Change(
                verb="state", eid=eid, role=b.role, name=b.name,
                detail="; ".join(bits), visual=b.visual,
                # The tree names the flag in text, so C can describe it; B
                # still crops it because the flip is visual by definition.
                tree_described=not b.visual,
            ))

        name_changed = a.name != b.name
        text_changed = a.text != b.text
        if name_changed or text_changed:
            if text_changed:
                det = f'text="{b.text[:120]}"'
            else:
                det = f'name="{b.name[:80]}"'
            # Text-only: the payload is a string the tree reports literally and
            # the box has not moved. This is the one no-crop case.
            text_only = (not b.visual) and (a.bbox == b.bbox)
            changes.append(Change(
                verb="changed", eid=eid, role=b.role, name=b.name, bbox=b.bbox,
                detail=det, text_only=text_only, visual=b.visual,
                tree_described=(not b.visual),
            ))

        if a.bbox != b.bbox and not name_changed and not text_changed:
            x, y, w, h = b.bbox
            dx, dy = x - a.bbox[0], y - a.bbox[1]
            changes.append(Change(
                verb="moved", eid=eid, role=b.role, name=b.name, bbox=b.bbox,
                detail=f"d=[{dx:+d},{dy:+d}]", visual=b.visual,
            ))

    if drop_noise:
        changes = [c for c in changes if not _is_noise(c)]

    order = {"removed": 0, "added": 1, "state": 2, "changed": 3, "moved": 4}
    changes.sort(key=lambda c: (order.get(c.verb, 9), c.eid))
    return changes


def render_changes(changes, max_lines: int = 120) -> str:
    if not changes:
        return "(no change)"
    lines = [c.render() for c in changes[:max_lines]]
    if len(changes) > max_lines:
        lines.append(f"... {len(changes) - max_lines} further changes omitted")
    return "\n".join(lines)


# Which verbs carry a pixel crop, per the spec's table.
#   added            -> yes
#   state            -> yes
#   changed non-text -> yes
#   changed text     -> no
#   moved            -> no
#   removed          -> no
def wants_crop_priority(ch: Change) -> bool:
    """Arm B rule: crops are the norm."""
    if ch.verb == "added":
        return True
    if ch.verb == "state":
        return True
    if ch.verb == "changed":
        return not ch.text_only
    return False


def wants_crop_text_first(ch: Change) -> bool:
    """Arm C rule: text only, unless the tree genuinely cannot describe it.

    Three cases, exactly as the spec states them:
      * the element is a visual type (canvas, image, chart, video, icon),
      * the changed region has no tree element behind it (the caller emits
        such a region as a synthetic change with visual=True), or
      * the bbox-contains-what-the-tree-says check failed, which the caller
        signals by clearing `tree_described`.
    """
    if ch.verb in ("removed", "moved"):
        return False
    return bool(ch.visual or not ch.tree_described)
