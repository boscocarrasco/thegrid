"""The element table: a snapshot of every actionable element on screen.

Elements come from AT-SPI2 over D-Bus. Each carries a stable id, role, name,
state, absolute bbox, an explicit click point, and its parent's id.

Stable ids are the load-bearing part. If an element's id changes when the app
repaints, every delta downstream becomes noise, so ids are derived in four
tiers, preferring whatever survives a repaint *and* a move:

  1. the toolkit's own accessible-id, when the app sets one
  2. (parent_id, role, name, nth-duplicate) — survives moves and repaints
  3. (parent_id, role, child-index) — survives repaints, not sibling inserts
  4. (parent_id, role, quantised position within parent) — last resort

Tier 4 is the one the spec describes; tiers 1-3 exist because they are strictly
more stable and the spec's requirement is stability, not a particular hash.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi  # noqa: E402

from observer import enrich as _ENRICH  # noqa: E402

# Roles the agent can actually act on. Containers are walked but not listed
# unless they are scrollable or carry text.
ACTIONABLE_ROLES = {
    "push button", "toggle button", "check box", "radio button",
    "menu item", "check menu item", "radio menu item", "menu",
    "text", "entry", "password text", "combo box", "list item",
    "table cell", "page tab", "link", "slider", "spin button",
    "tree item", "icon", "list box", "document frame", "document text",
    "document spreadsheet", "paragraph", "table column header",
    "table row header", "tool bar", "scroll bar",
}

# Roles whose pixels carry information the tree cannot describe. Arm C uses
# this set to decide when it is forced to fall back to a crop.
VISUAL_ROLES = {
    "canvas", "image", "chart", "drawing area", "video", "animation",
    "icon", "embedded", "glass pane",
}

# States worth reporting; the full AT-SPI state set is far too noisy.
TRACKED_STATES = ("enabled", "sensitive", "checked", "selected", "focused",
                  "expanded", "showing", "visible", "editable", "pressed")

_MAX_NODES = 1200
_MAX_DEPTH = 18


@dataclass
class Element:
    id: str
    role: str
    name: str
    states: tuple
    bbox: tuple           # absolute (x, y, w, h)
    click: tuple          # absolute (x, y) — explicit, not always bbox centre
    parent: Optional[str]
    text: str = ""        # literal text the tree reports, if any
    app: str = ""
    visual: bool = False  # pixels carry info the tree cannot describe
    # --- round-2 enrichment; all inert unless snapshot(enrich=True) ---
    block: Optional[str] = None       # id of the block this belongs to
    reachable: bool = True            # can it be clicked *now*
    blocked_by: str = ""              # if not, the id of what blocks it
    keys: str = ""                    # direct accelerator, e.g. ctrl+s
    key_path: str = ""                # menu path, e.g. alt+f,s
    ambiguous: bool = False           # shares role+name with disjoint twins
    ambiguity_group: str = ""
    ambiguity_reason: str = ""    # "same-name" or "peer-set"
    merged_ids: tuple = ()            # duplicates folded into this entry
    menu_keys: tuple = ()             # (item name, combo) inside a closed menu
    _acc: object = field(default=None, repr=False, compare=False)

    def to_dict(self):
        d = asdict(self)
        d.pop("_acc", None)
        return d

    def key(self):
        """What a `changed` comparison looks at."""
        return (self.role, self.name, self.text, self.states, self.bbox)


def _short(s: str, n: int = 10) -> str:
    return hashlib.sha1(s.encode("utf-8", "replace")).hexdigest()[:n]


def _states_of(acc) -> tuple:
    try:
        ss = acc.get_state_set()
    except Exception:
        return ()
    out = []
    for name in TRACKED_STATES:
        try:
            st = getattr(Atspi.StateType, name.upper())
        except AttributeError:
            continue
        try:
            if ss.contains(st):
                out.append(name)
        except Exception:
            pass
    return tuple(out)


def _bbox_of(acc):
    try:
        comp = acc.get_component_iface()
        if comp is None:
            return None
        e = comp.get_extents(Atspi.CoordType.SCREEN)
        if e.width <= 0 or e.height <= 0:
            return None
        return (int(e.x), int(e.y), int(e.width), int(e.height))
    except Exception:
        return None


_TEXT_ROLES = ("text", "entry", "password text", "paragraph",
               "table cell", "document text", "label", "spin button")


def _text_of(acc, role: str) -> str:
    """Literal text the tree reports. Only for roles where it is the payload.

    Note the static call: `acc.get_text_iface()` hands back the Accessible
    itself, and `Accessible.get_text()` is the *name* getter with a different
    signature, so the bound form silently yields nothing. Everything about the
    text-only delta path depends on this being the static Atspi.Text call.
    """
    if role not in _TEXT_ROLES:
        return ""
    try:
        n = Atspi.Text.get_character_count(acc)
        if n <= 0:
            return ""
        return Atspi.Text.get_text(acc, 0, min(n, 400))
    except Exception:
        return ""


def _click_point(acc, role: str, bbox) -> tuple:
    """Explicit click point.

    The geometric centre is wrong for a row with a checkbox, a tab with a close
    button, or a very wide menu item, so bias left for wide list-like rows and
    otherwise use the centre.
    """
    x, y, w, h = bbox
    if role in ("table cell", "list item", "tree item", "menu item",
                "check menu item", "radio menu item") and w > 240:
        return (x + min(60, w // 4), y + h // 2)
    if role == "page tab" and w > 120:
        return (x + w // 3, y + h // 2)
    return (x + w // 2, y + h // 2)


def _accessible_id(acc) -> str:
    for meth in ("get_accessible_id",):
        try:
            v = getattr(acc, meth)()
            if v:
                return str(v)
        except Exception:
            pass
    return ""


# Roles whose *name* is a document title rather than an identity: a frame is
# called "Untitled 1 - Mousepad" until you type, and then "*Untitled 1 -
# Mousepad". Chaining ids through such a name re-keys every descendant on the
# first keystroke, which is precisely the instability the table must not have,
# so these roles are identified structurally instead.
VOLATILE_NAME_ROLES = {
    "frame", "window", "dialog", "alert", "file chooser", "application",
    "page tab", "page tab list", "scroll pane", "panel", "filler",
    "document frame", "document text", "document spreadsheet", "root pane",
    "layered pane", "internal frame", "viewport",
}


class _IdAssigner:
    """Assigns tier-1..4 ids, keeping a per-parent duplicate counter."""

    def __init__(self):
        self._dupes = {}

    def assign(self, acc, role, name, parent_id, child_index, bbox, parent_bbox):
        aid = _accessible_id(acc)
        if aid:
            return "e" + _short(f"1|{parent_id}|{role}|{aid}")

        if name and role not in VOLATILE_NAME_ROLES:
            base = f"2|{parent_id}|{role}|{name}"
            n = self._dupes.get(base, 0)
            self._dupes[base] = n + 1
            return "e" + _short(f"{base}|{n}")

        if child_index is not None:
            return "e" + _short(f"3|{parent_id}|{role}|{child_index}")

        if bbox and parent_bbox:
            rx = (bbox[0] - parent_bbox[0]) // 8
            ry = (bbox[1] - parent_bbox[1]) // 8
            return "e" + _short(f"4|{parent_id}|{role}|{rx}|{ry}")

        return "e" + _short(f"4|{parent_id}|{role}|?")


class ElementTable:
    """An immutable snapshot: ordered list of Elements plus an id index."""

    def __init__(self, elements, app_names=(), truncated=False):
        self.elements = elements
        self.by_id = {e.id: e for e in elements}
        self.app_names = tuple(app_names)
        self.truncated = truncated
        # Round-2 enrichment. Absent unless observer.enrich.apply has run, so
        # an unenriched table renders exactly as it did in round 1.
        self.enriched = False
        self.blocks = {}
        self.blockers = []
        self.n_blocked = 0
        self.n_shortcuts = 0
        self.merged_away = 0
        self.ambiguous_groups = 0
        self.ambiguous_same_name = 0
        self.ambiguous_peer_sets = 0
        self.enrich_ms = {}
        self.dropped_enrichment = ""

    def __len__(self):
        return len(self.elements)

    def get(self, eid):
        return self.by_id.get(eid)

    def to_dicts(self):
        return [e.to_dict() for e in self.elements]

    def _row(self, e, hide_blocked: bool = False) -> str:
        x, y, w, h = e.bbox
        st = ",".join(s for s in e.states
                      if s in ("enabled", "checked", "selected", "focused",
                               "expanded", "editable"))
        txt = f' text="{e.text[:80]}"' if e.text else ""
        row = (f'#{e.id} {e.role} "{e.name[:48]}"{txt} '
               f'bbox=[{x},{y},{w},{h}] click=[{e.click[0]},{e.click[1]}] {st}')
        if not self.enriched:
            return row
        if e.keys:
            row += f" keys={e.keys}"
        if e.key_path and e.key_path != e.keys:
            row += f" menu={e.key_path}"
        if not e.reachable and not hide_blocked:
            row += f" BLOCKED-BY={e.blocked_by}"
        if e.ambiguous:
            row += f" AMBIGUOUS({e.ambiguity_group})"
        return row

    def render(self, max_rows: int = 400) -> str:
        """The full table as the model sees it at anchor time.

        Unenriched this is a flat list, exactly as round 1 emitted it. Enriched
        it is grouped into blocks, because a flat list of two hundred rows makes
        the model rebuild the structure of the screen from scratch on every
        step — which is half of what the step gap was.
        """
        if not self.enriched or not self.blocks:
            lines = [self._row(e) for e in self.elements[:max_rows]]
            if len(self.elements) > max_rows:
                lines.append(
                    f"... {len(self.elements) - max_rows} more elements omitted")
            return "\n".join(lines)

        order, seen = [], set()
        for e in self.elements:
            b = e.block
            if b not in seen:
                seen.add(b)
                order.append(b)
        lines, shown = [], 0
        for bid in order:
            members = [e for e in self.elements if e.block == bid]
            blk = self.blocks.get(bid)
            head = blk.label() if blk else "[ungrouped]"
            # When the whole block is behind a modal, say so once on the header
            # rather than on every row: same information, a fraction of the
            # tokens, and the grouping is what makes that possible.
            all_blocked = bool(members) and not any(e.reachable for e in members)
            if all_blocked:
                head += f"  — NOT ACTIONABLE, blocked by {members[0].blocked_by}"
            lines.append(head)
            for e in members:
                if shown >= max_rows:
                    break
                lines.append("  " + self._row(e, hide_blocked=all_blocked))
                shown += 1
                if e.menu_keys:
                    inner = ", ".join(f"{n}={c}" for n, c in e.menu_keys)
                    lines.append(f"    inside (no click needed): {inner}")
            if shown >= max_rows:
                break
        if len(self.elements) > shown:
            lines.append(f"... {len(self.elements) - shown} more elements omitted")
        return "\n".join(lines)


def _is_listable(role: str, name: str, text: str, states: tuple) -> bool:
    if role in ACTIONABLE_ROLES:
        return True
    if role in VISUAL_ROLES:
        return True
    return False


def snapshot(screen_w=1920, screen_h=1080, apps=None, enrich=False,
             drop=None) -> ElementTable:
    """Walk every application on the AT-SPI bus and build the element table.

    With `enrich=False` this is exactly the round-1 table, byte for byte, which
    is what lets arm B remain a valid control. With `enrich=True` the walk also
    records every container it passes and which block each element falls in,
    and `observer.enrich.apply` runs the four round-2 rules over the result.
    """
    Atspi.init()
    try:
        desktop = Atspi.get_desktop(0)
    except Exception:
        return ElementTable([], (), False)

    out = []
    app_names = []
    ids = _IdAssigner()
    budget = [_MAX_NODES]
    nodes = {}        # every walked accessible, containers included
    block_of = {}     # listed element id -> nearest block container id

    def walk(acc, parent_id, parent_bbox, depth, child_index, app_name,
             block_id=None):
        if budget[0] <= 0 or depth > _MAX_DEPTH:
            return
        try:
            role = acc.get_role_name()
            name = acc.get_name() or ""
        except Exception:
            return
        try:
            states = _states_of(acc)
        except Exception:
            states = ()

        bbox = _bbox_of(acc)
        # Off-screen or zero-area elements are not observable, so they are not
        # in the table; "showing" is what AT-SPI uses for actually-on-screen.
        on_screen = bool(
            bbox
            and bbox[0] < screen_w and bbox[1] < screen_h
            and bbox[0] + bbox[2] > 0 and bbox[1] + bbox[3] > 0
            and "showing" in states
        )

        eid = ids.assign(acc, role, name, parent_id, child_index, bbox, parent_bbox)
        text = _text_of(acc, role)

        if enrich:
            nodes[eid] = (role, name, bbox, parent_id, acc)
            # A block is the nearest enclosing container the tree already
            # declares. Nesting works out on its own: a dialog inside a frame
            # takes over as the block for everything under it.
            if on_screen and role in _ENRICH.BLOCK_ROLE_SET:
                block_id = eid

        if on_screen and _is_listable(role, name, text, states):
            budget[0] -= 1
            out.append(Element(
                id=eid, role=role, name=name, states=states, bbox=bbox,
                click=_click_point(acc, role, bbox), parent=parent_id,
                text=text, app=app_name, visual=(role in VISUAL_ROLES), _acc=acc,
            ))
            if enrich:
                block_of[eid] = block_id

        try:
            n = acc.get_child_count()
        except Exception:
            n = 0
        if n > 300:
            n = 300
        for i in range(n):
            if budget[0] <= 0:
                return
            try:
                c = acc.get_child_at_index(i)
            except Exception:
                continue
            if c is not None:
                walk(c, eid, bbox or parent_bbox, depth + 1, i, app_name,
                     block_id)

    try:
        ndesk = desktop.get_child_count()
    except Exception:
        ndesk = 0
    for i in range(ndesk):
        try:
            app = desktop.get_child_at_index(i)
            if app is None:
                continue
            aname = app.get_name() or f"app{i}"
        except Exception:
            continue
        if apps and aname not in apps:
            continue
        app_names.append(aname)
        walk(app, None, None, 0, None, aname)

    # Deterministic order: top-to-bottom, left-to-right. Makes the rendered
    # table byte-identical for identical screens, which the cache depends on.
    out.sort(key=lambda e: (e.app, e.bbox[1], e.bbox[0], e.role, e.id))
    t = ElementTable(out, app_names, truncated=(budget[0] <= 0))
    if enrich:
        _ENRICH.apply(t, nodes, block_of, drop=drop)
    return t
