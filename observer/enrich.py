"""Layer-1 enrichment: blocks, reachability, shortcuts, geometry merge.

Round 1 measured a defect: on menu and dialog tasks the tool arms spend up to
2.5x the steps of the screenshot baseline (`PREDICTIONS.md` Fact 1). A flat
list of two hundred ids is a worse thing to navigate than a picture of a menu,
and the table was not telling the agent three things the tree already knows:

  * which elements belong together and appear or disappear as a unit (blocks),
  * which elements can actually be clicked right now (reachability),
  * that a three-level menu has a one-keystroke accelerator (shortcuts).

Two further rules come from §5.2 of the design document and are about honesty
rather than cost:

  * duplicates merge **by geometry, never by text** — same role and name is the
    same element only if the rectangles overlap or nest; and
  * elements that remain ambiguous after that — same role, same name, disjoint
    rectangles — **force a crop**, because the tree has already said everything
    it knows and it was not enough.

Every enrichment here is opt-in. With `enrich=False` the table is byte-identical
to the one round 1 produced, which is what lets arm B stay the control.
"""
from __future__ import annotations

import time

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi  # noqa: E402


# ---------------------------------------------------------------- blocks

# A block is a set of elements that appears and disappears as a unit. These are
# the container roles the tree already declares; all we ever did was flatten
# them. Order matters only for readability of the rendered table.
BLOCK_ROLES = (
    "menu bar", "tool bar", "status bar", "popup menu",
    "dialog", "alert", "file chooser",
    "page tab list", "list box", "table", "tree table", "tree",
    "document frame", "document text", "document spreadsheet",
    "scroll pane", "frame",
)
BLOCK_ROLE_SET = set(BLOCK_ROLES)

# Fixed: does not change with the data — navigation, menus, headers.
# Variable: carries content — the list of rows, the results table.
FIXED_BLOCK_ROLES = {"menu bar", "tool bar", "status bar", "popup menu",
                     "page tab list", "frame"}
VARIABLE_BLOCK_ROLES = {"list box", "table", "tree table", "tree",
                        "document frame", "document text",
                        "document spreadsheet", "scroll pane"}
# Everything else (dialog, alert, file chooser) is decided by what it holds:
# five or more entries of the same *data* role means it is showing data rather
# than controls. Restricting the test to data roles matters — a dialog with six
# check boxes is still a fixed block, and an earlier version that counted any
# repeated role called Mousepad's Find-and-Replace dialog variable.
_REPEAT_FOR_VARIABLE = 5
_DATA_ROLES = {"list item", "table cell", "tree item", "table row header"}

# Roles that can block the screen behind them when modal.
BLOCKER_ROLES = {"dialog", "alert", "file chooser"}


class Block:
    __slots__ = ("id", "role", "name", "kind", "n", "bbox")

    def __init__(self, bid, role, name, kind, n, bbox):
        self.id, self.role, self.name = bid, role, name
        self.kind, self.n, self.bbox = kind, n, bbox

    def label(self):
        nm = f' "{self.name[:34]}"' if self.name else ""
        return f"[{self.role}{nm} · {self.kind} · {self.n}]"


# ------------------------------------------------------------- shortcuts

# AT-SPI hands GTK key bindings back as three semicolon-separated fields:
#   "s;<Alt>f:s;<Primary>s"
#    ^ local mnemonic
#      ^ the full menu path, colon-separated
#                ^ the direct accelerator
# The third field is the prize: it collapses a three-click descent into one
# keystroke. The second is the fallback when there is no direct accelerator.
_MODS = {
    "primary": "ctrl", "control": "ctrl", "ctrl": "ctrl",
    "alt": "alt", "shift": "shift", "super": "super", "meta": "alt",
}

# Querying the Action interface is two D-Bus round trips per element, so the
# answers are cached: a menu's accelerator does not change while the app runs.
_KB_CACHE = {}
_KB_ROLES = {"menu", "menu item", "check menu item", "radio menu item",
             "push button", "toggle button"}


def _translate(chunk: str) -> str:
    """`<Primary><Shift>s` -> `ctrl+shift+s`."""
    mods, rest, i = [], "", 0
    while i < len(chunk):
        if chunk[i] == "<":
            j = chunk.find(">", i)
            if j < 0:
                break
            m = _MODS.get(chunk[i + 1:j].lower())
            if m and m not in mods:
                mods.append(m)
            i = j + 1
        else:
            rest = chunk[i:]
            break
    rest = rest.strip()
    if not rest:
        return ""
    return "+".join(mods + [rest])


def parse_binding(raw: str):
    """-> (accelerator, menu path). Either may be empty."""
    if not raw:
        return "", ""
    parts = raw.split(";")
    accel = _translate(parts[2]) if len(parts) > 2 else ""
    path = ""
    if len(parts) > 1 and parts[1]:
        steps = [_translate(p) for p in parts[1].split(":")]
        steps = [s for s in steps if s]
        if steps:
            path = ",".join(steps)
    return accel, path


_MENU_CACHE = {}
_MENU_MAX_ITEMS = 14          # per menu, in the rendered summary
_MENU_MAX_NODES = 220         # per menu, in the subtree walk


def menu_shortcuts(el):
    """Accelerators for a menu's contents, without opening the menu.

    The table lists only elements that are `showing`, and a menu's items are
    not showing until it is popped up. Exposing the accelerator only once the
    menu is open would be useless: the entire value of `KEY ctrl+s` is that it
    replaces the three clicks that get you there. The tree declares those items
    and their bindings whether or not the menu is on screen, so they are read
    from the closed menu and summarised on its row.

    That is a deliberate departure from "the table holds what is on screen",
    recorded in DECISIONS.md as D7.3. It is a summary attached to a visible
    element, not a set of clickable rows: nothing here gets an id, because
    nothing here can be clicked until the menu is open.
    """
    if el.role != "menu":
        return ()
    ck = (el.app, el.id)
    hit = _MENU_CACHE.get(ck)
    if hit is not None:
        return hit

    found, budget = [], [_MENU_MAX_NODES]

    def descend(acc, depth):
        if budget[0] <= 0 or depth > 4:
            return
        try:
            n = acc.get_child_count()
        except Exception:
            return
        for i in range(min(n, 60)):
            if budget[0] <= 0:
                return
            budget[0] -= 1
            try:
                c = acc.get_child_at_index(i)
                if c is None:
                    continue
                role = c.get_role_name()
                name = (c.get_name() or "").strip()
            except Exception:
                continue
            if role in ("menu item", "check menu item", "radio menu item",
                        "menu") and name:
                a, p = "", ""
                try:
                    na = Atspi.Action.get_n_actions(c)
                    for k in range(min(na, 3)):
                        a, p = parse_binding(
                            Atspi.Action.get_key_binding(c, k) or "")
                        if a or p:
                            break
                except Exception:
                    pass
                combo = a or p
                if combo:
                    found.append((name, combo))
            if role == "menu":
                descend(c, depth + 1)

    try:
        descend(el._acc, 0)
    except Exception:
        pass
    # Direct accelerators first: they are the ones that save the clicks.
    found.sort(key=lambda t: ("," in t[1], t[0]))
    out = tuple(found[:_MENU_MAX_ITEMS])
    if len(_MENU_CACHE) < 4000:
        _MENU_CACHE[ck] = out
    return out


def _key_binding(el):
    if el.role not in _KB_ROLES:
        return "", ""
    ck = (el.app, el.id)
    hit = _KB_CACHE.get(ck)
    if hit is not None:
        return hit
    out = ("", "")
    try:
        n = Atspi.Action.get_n_actions(el._acc)
        for i in range(min(n, 4)):
            a, p = parse_binding(Atspi.Action.get_key_binding(el._acc, i) or "")
            if a or p:
                out = (a, p)
                break
    except Exception:
        pass
    if len(_KB_CACHE) < 20000:
        _KB_CACHE[ck] = out
    return out


# -------------------------------------------------- geometry duplicate merge

def _overlaps(a, b) -> bool:
    """True if the rectangles overlap or one nests inside the other."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw <= bx or bx + bw <= ax
                or ay + ah <= by or by + bh <= ay)


# A spreadsheet exposes thousands of cells sharing a role; pairwise comparison
# inside one enormous group is the one place this pass could get expensive, so
# groups above this size are left alone. They are also exactly the groups where
# the names are empty and the rule would not fire anyway.
_MAX_GROUP = 40


def merge_duplicates(elements):
    """Collapse entries that are the same element seen twice.

    The rule that separates noise from information is the rectangle, never the
    text: a container that inherited its child's name, or the same button
    exposed by two stacked toolkits, occupies the same pixels. Two entries in
    different places are different things however identically they are named.

    The survivor is the *smallest* rectangle, which is the leaf — the thing
    that actually takes the click, not the panel wrapped around it.
    """
    groups = {}
    for e in elements:
        if not e.name.strip():
            continue
        groups.setdefault((e.app, e.role, e.name), []).append(e)

    dropped, merged_into = set(), {}
    for key, g in groups.items():
        if len(g) < 2 or len(g) > _MAX_GROUP:
            continue
        # union-find over "rectangles touch"
        parent = list(range(len(g)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                if _overlaps(g[i].bbox, g[j].bbox):
                    ri, rj = find(i), find(j)
                    if ri != rj:
                        parent[ri] = rj
        clusters = {}
        for i in range(len(g)):
            clusters.setdefault(find(i), []).append(i)
        for members in clusters.values():
            if len(members) < 2:
                continue
            els = [g[i] for i in members]
            keep = min(els, key=lambda e: e.bbox[2] * e.bbox[3])
            for e in els:
                if e is keep:
                    continue
                dropped.add(e.id)
                merged_into[e.id] = keep.id
            keep.merged_ids = tuple(sorted(e.id for e in els if e is not keep))
    return dropped, merged_into


def mark_ambiguous(elements):
    """Same role, same name, *disjoint* rectangles — the tree is out of words.

    Six rows all called `job-delta`, twelve buttons all called Download. Text
    repetition here is not a signal to compress, it is a signal to send pixels;
    the elements are flagged and the channels crop each one. This is the case
    that sank the text-only channel in round 1 (1/8), and the rule resolves it
    without a single pixel being consulted to make the decision.
    """
    groups = {}
    for e in elements:
        if not e.name.strip():
            continue
        groups.setdefault((e.app, e.role, e.name), []).append(e)
    n_groups = 0
    for key, g in groups.items():
        if len(g) < 2 or len(g) > _MAX_GROUP:
            continue
        disjoint = all(
            not _overlaps(g[i].bbox, g[j].bbox)
            for i in range(len(g)) for j in range(i + 1, len(g))
        )
        if not disjoint:
            continue
        n_groups += 1
        tag = f"{g[0].role}:{g[0].name[:24]}"
        for k, e in enumerate(g):
            e.ambiguous = True
            e.ambiguity_reason = "same-name"
            e.ambiguity_group = f"{tag} ({k + 1} of {len(g)})"
    return n_groups


# A peer set is 4-12 sibling rows of a data role, in one block, with disjoint
# rectangles, identical states, identical text and identical size, whose *only*
# varying attribute is the name.
_PEER_MIN, _PEER_MAX = 4, 12


def mark_peer_sets(elements):
    """The other way the tree runs out of words, and the one that is real here.

    §5.2 of the design document diagnoses round 1's 1/8 text-only result as six
    list items *sharing a name*. Reading the actual tree, that is not what
    happens: the six rows are called `job-alpha` … `job-foxtrot`, all distinct.
    They are indistinguishable on the axis the task asks about — which of them
    failed — because that is carried by a colour, and no attribute in the tree
    reports it. `mark_ambiguous` above never fires on this page.

    So the same principle needs its second instance: a run of sibling rows of a
    data role, in one block, alike in every attribute the tree exposes *except*
    the name. The tree has one axis of variation and the agent may need another.
    Like the same-name rule this decides structurally — nothing here consults a
    pixel to work out that pixels are needed.

    This rule was added after inspecting the tree and before running anything.
    That is a weaker claim than pre-registration and is declared as such in
    REPORT2.md; runs record which of the two rules fired, so the two are never
    conflated.
    """
    groups = {}
    for e in elements:
        if e.role not in _DATA_ROLES or e.ambiguous:
            continue
        groups.setdefault((e.app, e.role, e.block), []).append(e)
    n_groups = 0
    for g in groups.values():
        if not (_PEER_MIN <= len(g) <= _PEER_MAX):
            continue
        names = [e.name.strip() for e in g]
        if not all(names) or len(set(names)) != len(names):
            continue
        if len({e.states for e in g}) != 1 or len({e.text for e in g}) != 1:
            continue
        w0, h0 = g[0].bbox[2], g[0].bbox[3]
        if any(abs(e.bbox[2] - w0) > 2 or abs(e.bbox[3] - h0) > 2 for e in g):
            continue
        if any(_overlaps(g[i].bbox, g[j].bbox)
               for i in range(len(g)) for j in range(i + 1, len(g))):
            continue
        n_groups += 1
        for k, e in enumerate(g):
            e.ambiguous = True
            e.ambiguity_reason = "peer-set"
            e.ambiguity_group = (f"{e.role} peer set, alike but for the name "
                                 f"({k + 1} of {len(g)})")
    return n_groups


# ---------------------------------------------------------------- the pass

def apply(table, nodes, block_of, drop=None):
    """Run every enrichment over a freshly built table, in place.

    `nodes` maps every walked accessible's id to
    `(role, name, bbox, parent_id, acc)` — containers included, which the table
    itself does not list. `block_of` maps a listed element id to the id of its
    nearest block container.

    Returns a timing dict, because §8 of PREDICTIONS.md commits to reporting
    what the enrichment costs whether or not the number is flattering.
    """
    t = {}

    # --- duplicates, first: everything downstream should see the merged set
    t0 = time.perf_counter()
    dropped, merged_into = merge_duplicates(table.elements)
    if dropped:
        table.elements = [e for e in table.elements if e.id not in dropped]
        table.by_id = {e.id: e for e in table.elements}
    t["merge_ms"] = (time.perf_counter() - t0) * 1000.0
    table.merged_away = len(dropped)

    # --- blocks (before ambiguity: the peer-set rule is scoped to a block)
    t0 = time.perf_counter()
    counts, roles_in = {}, {}
    for e in table.elements:
        b = block_of.get(e.id)
        e.block = b
        if b is None:
            continue
        counts[b] = counts.get(b, 0) + 1
        roles_in.setdefault(b, {})
        roles_in[b][e.role] = roles_in[b].get(e.role, 0) + 1
    blocks = {}
    for bid, n in counts.items():
        role, name, bbox = nodes.get(bid, ("?", "", None, None, None))[:3]
        if role in FIXED_BLOCK_ROLES:
            kind = "fixed"
        elif role in VARIABLE_BLOCK_ROLES:
            kind = "variable"
        else:
            rep = max([v for r, v in roles_in.get(bid, {}).items()
                       if r in _DATA_ROLES] or [0])
            kind = "variable" if rep >= _REPEAT_FOR_VARIABLE else "fixed"
        blocks[bid] = Block(bid, role, name, kind, n, bbox)
    table.blocks = blocks
    t["blocks_ms"] = (time.perf_counter() - t0) * 1000.0

    # --- ambiguity: the registered same-name rule, then the peer-set rule
    t0 = time.perf_counter()
    table.ambiguous_same_name = mark_ambiguous(table.elements)
    table.ambiguous_peer_sets = mark_peer_sets(table.elements)
    table.ambiguous_groups = table.ambiguous_same_name + table.ambiguous_peer_sets
    t["ambiguity_ms"] = (time.perf_counter() - t0) * 1000.0

    # --- reachability
    t0 = time.perf_counter()
    blockers = []
    for nid, (role, name, bbox, parent_id, acc) in nodes.items():
        if role not in BLOCKER_ROLES:
            continue
        try:
            ss = acc.get_state_set()
            if not (ss.contains(Atspi.StateType.MODAL)
                    and ss.contains(Atspi.StateType.SHOWING)):
                continue
        except Exception:
            continue
        blockers.append((nid, role, name))

    def ancestors(eid):
        seen, cur = [], eid
        while cur is not None and cur not in seen and len(seen) < 40:
            seen.append(cur)
            rec = nodes.get(cur)
            cur = rec[3] if rec else None
        return seen

    n_blocked = 0
    if blockers:
        bset = {b[0] for b in blockers}
        label = {b[0]: f"{b[1]}{(' ' + repr(b[2][:30])) if b[2] else ''}"
                 for b in blockers}
        for e in table.elements:
            chain = set(ancestors(e.id))
            hit = chain & bset
            if hit:
                continue                      # inside the modal: reachable
            first = next(iter(bset))
            e.reachable = False
            e.blocked_by = f"#{first} ({label[first]})"
            n_blocked += 1
    table.blockers = [b[0] for b in blockers]
    table.n_blocked = n_blocked
    t["reach_ms"] = (time.perf_counter() - t0) * 1000.0

    # --- shortcuts
    t0 = time.perf_counter()
    n_keys = 0
    for e in table.elements:
        a, p = _key_binding(e)
        if a or p:
            e.keys, e.key_path = a, p
            n_keys += 1
        if e.role == "menu" and e.reachable:
            e.menu_keys = menu_shortcuts(e)
            n_keys += len(e.menu_keys)
    table.n_shortcuts = n_keys
    t["shortcuts_ms"] = (time.perf_counter() - t0) * 1000.0

    # --- ablation: compute everything, then withhold exactly one thing.
    # Computing it first and dropping it afterwards keeps the measured cost of
    # the enrichment identical across ablations, so what the ablation varies is
    # what the model is told and nothing else.
    if drop == "blocks":
        table.blocks = {}          # render falls back to the flat list
    elif drop == "reachability":
        for e in table.elements:
            e.reachable, e.blocked_by = True, ""
        table.n_blocked = 0
    elif drop == "shortcuts":
        for e in table.elements:
            e.keys, e.key_path, e.menu_keys = "", "", ()
        table.n_shortcuts = 0

    t["total_ms"] = sum(t.values())
    table.enrich_ms = t
    table.enriched = True
    table.dropped_enrichment = drop or ""
    return t
