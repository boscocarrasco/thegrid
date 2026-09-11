"""The observation channels. This file *is* the independent variable.

Everything else — model, system prompt skeleton, task set, step limit, decoding
settings, executor, verifier — is shared. An arm decides two things and nothing
else:

  * what the model is shown at the start of a task and at each step, and
  * whether an action names an element id or a pixel coordinate.

Arm A   full screenshot every step, model returns pixel coordinates.
Arm B   anchor shot + full table once; then verb deltas with a pixel crop of
        every changed region (crops are the norm).
Arm C   identical to B except the per-step delta is text only; a crop is sent
        only when the tree genuinely cannot describe the change.
Arm D   full screenshot every step *plus* the full table, no deltas. Separates
        "having the table" from "sending only what changed".
"""
from __future__ import annotations

from dataclasses import dataclass, field

from observer import delta as D
from observer import screen
from runner.model import text_block, image_block, count_text_tokens


ACTION_RULES_ID = """\
Reply with exactly two lines and nothing else:

WHY: <one short sentence>
ACT: <one action>

Actions available (address elements by id, never by coordinates):
  CLICK #id                 click the element with that id
  DOUBLECLICK #id           double-click it
  TYPE <text>               type text into whatever has focus
  KEY <combo>               press keys, e.g. KEY ctrl+s   KEY Return   KEY alt+f
  SCROLL #id <n>            scroll inside an element; n<0 up, n>0 down
  DONE                      the task is complete
  GIVEUP                    the task cannot be completed

Rules:
- An id looks like #e1a2b3c4d5. Use only ids you have been shown.
- One action per reply. Do not explain beyond the WHY line.
- A menu opens on CLICK; its items then appear as `added` in the next step.
- Prefer keyboard shortcuts (KEY ctrl+s) when they are unambiguous.
- Say DONE only once the change is actually saved/applied, not merely typed.
"""

ACTION_RULES_XY = """\
Reply with exactly two lines and nothing else:

WHY: <one short sentence>
ACT: <one action>

Actions available (address the screen by pixel coordinate):
  CLICK <x> <y>             click at that point
  DOUBLECLICK <x> <y>       double-click there
  TYPE <text>               type text into whatever has focus
  KEY <combo>               press keys, e.g. KEY ctrl+s   KEY Return   KEY alt+f
  SCROLL <x> <y> <n>        scroll at that point; n<0 up, n>0 down
  DONE                      the task is complete
  GIVEUP                    the task cannot be completed

Rules:
- Coordinates are in the coordinate space of the screenshot you are shown,
  whose size is given with each image. They are mapped to the real screen for
  you, so just read them off the image.
- One action per reply. Do not explain beyond the WHY line.
- A menu opens on CLICK; read the next screenshot to see its items.
- Prefer keyboard shortcuts (KEY ctrl+s) when they are unambiguous.
- Say DONE only once the change is actually saved/applied, not merely typed.
"""

SYSTEM_PROMPT = """\
You are driving a Linux desktop to complete a task. You act one step at a time.
After each action you are shown what happened and choose the next action.
Be efficient: take the shortest reliable route, and stop as soon as the task is
genuinely done. If something does not work twice in a row, try a different
route rather than repeating it.
"""


@dataclass
class Observation:
    """What gets appended to the conversation for one step."""
    blocks: list = field(default_factory=list)
    observation_tokens: int = 0   # text tokens belonging to the observation
    image_tokens: int = 0
    n_images: int = 0
    n_changes: int = 0
    note: str = ""


TASK_OBJECT_NOTE = """\
The block below is the task itself. It does not expire when the screen changes
and it is repeated verbatim every time the running history is replaced. Every
constraint in it must still hold when you say DONE.
"""


def render_task_object(task) -> str:
    """The task, kept apart from the screen log.

    A dominant failure mode on long tasks is that the agent loses an explicit
    constraint from the statement — "in CSV", "only the March rows", "without
    touching the original" — because it lives in a message that got buried.
    The screen log expires when the screen changes; the task does not, so it is
    stored separately and re-stated at every compaction.
    """
    lines = [TASK_OBJECT_NOTE, f"GOAL: {task.prompt}"]
    cons = getattr(task, "constraints", ()) or ()
    if cons:
        lines.append("CONSTRAINTS — all of these must hold at the end:")
        for i, c in enumerate(cons, 1):
            lines.append(f"  C{i}. {c}")
    return "\n".join(lines)


class Channel:
    """Base: shared plumbing, arms override `initial` and `step`."""
    name = "?"
    addressing = "id"          # "id" or "xy"
    stateless = False          # True => the transcript is rebuilt every step
    enrich = False             # round-2 layer-1 enrichment on the table
    ambiguity_crops = False    # ambiguity forces a crop
    task_object = False        # keep the statement apart from the screen log
    # Never more than this many full screenshots live in the context at once.
    # Re-anchoring appends a fresh screenshot without discarding the transcript,
    # which keeps the cache; once the window is full the next refresh has to be
    # a real compaction, which rebuilds and costs the cache but resets the
    # count. The window is therefore what decides how often the cache is paid
    # for, and it is the knob experiment 4 turns.
    image_window = 2

    def __init__(self, crop_ttl: int = 3):
        self.crop_ttl = crop_ttl
        self.live_crops = []       # (step_emitted, eid, description)
        self.last_compaction = 0
        self.compactions = 0
        self.reanchors = 0
        self.crops_aged = 0
        self.crops_emitted = 0
        self.crops_ambiguity = 0   # crops the ambiguity rule alone asked for
        self.crops_amb_same_name = 0
        self.crops_amb_peer_set = 0
        self.live_anchors = 1      # the initial observation carries one
        self.peak_live_images = 1
        self.peak_live_image_tokens = 0
        self._live_image_tokens = 0

    # ---- live-image accounting, used by the image window ----

    def _note_images(self, n_full, tokens):
        self.live_anchors += n_full
        self._live_image_tokens += tokens
        live = self.live_anchors + len(self.live_crops)
        self.peak_live_images = max(self.peak_live_images, live)
        self.peak_live_image_tokens = max(self.peak_live_image_tokens,
                                          self._live_image_tokens)

    def action_rules(self):
        return ACTION_RULES_ID if self.addressing == "id" else ACTION_RULES_XY

    # ---- helpers shared by every arm ----

    @staticmethod
    def _anchor():
        a = screen.anchor_capture()
        return a

    def initial(self, task, table):
        raise NotImplementedError

    def step(self, task, prev_table, curr_table, last_result, step_no):
        raise NotImplementedError

    # ---- crop ageing and compaction (arms B, C, D) ----

    # A compaction discards the accumulated transcript and starts again from a
    # consolidated description of where the agent is. It is what stops an
    # append-only context from growing without bound, and it is the mechanism
    # the first round of this experiment never exercised because tasks were
    # too short to trigger it.
    compactable = True
    reanchor_every = 8      # forced re-anchor interval, in steps
    min_gap = 4             # never compact twice in quick succession

    def age_crops(self, step_no):
        """Crops whose time is up, as (id, description) pairs.

        A crop stays visible for `crop_ttl` steps. Because the live context is
        append-only, an image already sent cannot be retracted mid-conversation
        — so ageing is realised at the next compaction, where the rebuilt
        transcript carries the crop's text description instead of its pixels.
        """
        keep, aged = [], []
        for (s, eid, desc) in self.live_crops:
            if step_no - s >= self.crop_ttl:
                aged.append((eid, desc))
            else:
                keep.append((s, eid, desc))
        self.live_crops = keep
        return aged

    def should_compact(self, step_no, prev_table, curr_table):
        """Compact at natural boundaries, or on the re-anchor interval.

        Natural boundaries are where the accumulated history has just stopped
        being worth anything — the application changed, or a dialog opened or
        closed. Compacting there is cheap in information even though it always
        costs the cache.
        """
        if not self.compactable:
            return False, ""
        if step_no - self.last_compaction < self.min_gap:
            return False, ""

        prev_apps = set(prev_table.app_names) if prev_table else set()
        curr_apps = set(curr_table.app_names)
        if prev_apps and curr_apps != prev_apps:
            return True, "application changed"

        def dialogs(t):
            return {e.id for e in t.elements
                    if e.role in ("dialog", "alert", "file chooser")}
        if prev_table is not None and dialogs(prev_table) != dialogs(curr_table):
            return True, "dialog opened or closed"

        if step_no - self.last_compaction >= self.reanchor_every:
            return True, "re-anchor interval"
        return False, ""

    def refresh(self, task, curr_table, history, step_no, prev_table):
        """Decide between doing nothing, re-anchoring, and compacting.

        A re-anchor appends a fresh table and screenshot to the transcript that
        is already there: the prefix is untouched, so the cache survives, but a
        second full screenshot is now live. A compaction throws the transcript
        away and starts from a consolidated summary: the cache is lost, and the
        image count resets to one.

        The image window is what chooses between them. Below it, refresh the
        cheap way; at it, pay for a compaction. With a window of two that means
        the cache is rebuilt on every other refresh; with four, every fourth.
        """
        do_it, why = self.should_compact(step_no, prev_table, curr_table)
        if not do_it:
            return None, ""
        natural = why in ("application changed", "dialog opened or closed")
        if not natural and self.live_anchors < self.image_window:
            return self.reanchor(task, curr_table, step_no, why), "reanchor"
        return self.compact(task, curr_table, history, step_no, why), "compaction"

    def reanchor(self, task, curr_table, step_no, reason):
        """A fresh table and screenshot appended to the existing transcript."""
        a = self._anchor()
        lines = []
        if self.task_object:
            lines += [render_task_object(task), ""]
        lines.append(f"[re-anchor at step {step_no}: {reason}. Everything above "
                     f"still stands; this is a fresh reading of the screen.]")
        lines.append("")
        lines.append(f"ELEMENTS ({len(curr_table)}):")
        lines.append(curr_table.render())
        lines.append("")
        lines.append(f"Fresh screenshot ({a['size'][0]}x{a['size'][1]}):")
        txt = "\n".join(lines)
        self.last_compaction = step_no
        self.reanchors += 1
        self._note_images(1, a["tokens"])
        return Observation(
            blocks=[text_block(txt), image_block(a["b64"])],
            observation_tokens=count_text_tokens(txt),
            image_tokens=a["tokens"], n_images=1,
            note=f"reanchor: {reason}",
        )

    def compact(self, task, curr_table, history, step_no, reason):
        """Build the re-anchor message that replaces the whole transcript.

        Per the spec this is the cheap moment to re-anchor, because the prefix
        has just been thrown away anyway: the agent gets the task again, a
        consolidated account of what it has already done, the text descriptions
        of any crops that have aged out, a fresh full element table and a fresh
        anchor screenshot.
        """
        aged = self.age_crops(step_no)
        a = self._anchor()
        if self.task_object:
            lines = [render_task_object(task), ""]
        else:
            lines = [f"TASK: {task.prompt}", ""]
        lines.append(f"[context compacted at step {step_no}: {reason}. The "
                     f"running history has been replaced by this summary and "
                     f"a fresh view of the screen.]")
        lines.append("")
        if history:
            lines.append("What you have done so far:")
            for n, res in history[-14:]:
                lines.append(f"  step {n}: {res}")
            lines.append("")
        if aged:
            lines.append("Regions you were shown earlier, now described in "
                         "text instead of pixels:")
            for eid, desc in aged[-10:]:
                lines.append(f"  {desc}")
            lines.append("")
        lines.append(f"ELEMENTS ({len(curr_table)}):")
        lines.append(curr_table.render())
        lines.append("")
        lines.append(f"Fresh anchor screenshot "
                     f"({a['size'][0]}x{a['size'][1]}) of the same "
                     f"{a['native'][0]}x{a['native'][1]} screen:")
        txt = "\n".join(lines)
        self.last_compaction = step_no
        self.compactions += 1
        self.crops_aged += len(aged)
        # The transcript is gone: exactly one image is live again.
        self.live_anchors = 0
        self._live_image_tokens = 0
        self._note_images(1, a["tokens"])
        return Observation(
            blocks=[text_block(txt), image_block(a["b64"])],
            observation_tokens=count_text_tokens(txt),
            image_tokens=a["tokens"], n_images=1,
            note=f"compaction: {reason}",
        )


# --------------------------------------------------------------------- A

class ArmA(Channel):
    """Baseline: the loop every computer-use agent runs today.

    The screenshot is *replaced* each step rather than accumulated: the model
    sees the history of what it did as text, and exactly one image — the
    current screen. That is what the standard loop does, and the brief is
    explicit that it must not be "fixed". The practical consequence is that
    the transcript has to be rebuilt every step (`stateless`), because an
    append-only conversation cannot retract an image it already sent. That
    rebuild is also why the baseline keeps re-paying for its prefix: the
    position where the previous screenshot used to sit changes on every step.
    """
    name = "A"
    addressing = "xy"
    stateless = True
    compactable = False        # it already rebuilds every step

    def __init__(self, crop_ttl: int = 3):
        super().__init__(crop_ttl)
        self.history = []       # [(step_no, action_result_text)]

    def _render(self, task, a, step_no, last_result):
        lines = [f"TASK: {task.prompt}", ""]
        if self.history:
            lines.append("What you have done so far:")
            for n, res in self.history:
                lines.append(f"  step {n}: {res}")
            lines.append("")
        lines.append(f"This is step {step_no}.")
        if step_no > 1:
            lines.append(f"Result of your last action: {last_result}")
        lines.append(f"Current screenshot ({a['size'][0]}x{a['size'][1]}). "
                     f"Give coordinates in that space.")
        return "\n".join(lines)

    def initial(self, task, table):
        a = self._anchor()
        txt = self._render(task, a, 1, "")
        return Observation(
            blocks=[text_block(txt), image_block(a["b64"])],
            observation_tokens=count_text_tokens(txt),
            image_tokens=a["tokens"], n_images=1, note="screenshot-only",
        )

    def step(self, task, prev_table, curr_table, last_result, step_no):
        self.history.append((step_no - 1, last_result[:120]))
        a = self._anchor()
        txt = self._render(task, a, step_no, last_result)
        return Observation(
            blocks=[text_block(txt), image_block(a["b64"])],
            observation_tokens=count_text_tokens(txt),
            image_tokens=a["tokens"], n_images=1, note="screenshot-replaced",
        )


# --------------------------------------------------------------------- B

class ArmB(Channel):
    """Tool, crop-priority: every changed region arrives as labelled pixels."""
    name = "B"
    addressing = "id"

    def initial(self, task, table):
        a = self._anchor()
        tt = table.render()
        txt = (f"TASK: {task.prompt}\n\n"
               f"Below is the complete table of on-screen elements, with exact "
               f"coordinates taken from the operating system, and an anchor "
               f"screenshot ({a['size'][0]}x{a['size'][1]}, showing the same "
               f"{a['native'][0]}x{a['native'][1]} screen) so you "
               f"can see what those ids look like.\n\n"
               f"ELEMENTS ({len(table)}):\n{tt}\n")
        self._note_images(0, a["tokens"])
        return Observation(
            blocks=[text_block(txt), image_block(a["b64"])],
            observation_tokens=count_text_tokens(txt),
            image_tokens=a["tokens"], n_images=1, note="anchor+table",
        )

    def step(self, task, prev_table, curr_table, last_result, step_no):
        changes = D.diff(prev_table, curr_table)
        head = (f"Step {step_no}. Result of last action: {last_result}\n"
                f"CHANGES ({len(changes)}):\n{D.render_changes(changes)}\n")
        blocks = [text_block(head)]
        img_tokens = 0
        n_img = 0
        for ch in changes:
            if not D.wants_crop_priority(ch):
                continue
            el = curr_table.get(ch.eid)
            if el is None:
                continue
            if n_img >= 6:          # hard cap: a full repaint must not explode
                break
            c = screen.crop_for(el.bbox, ch.eid)
            x, y, w, h = c["region"]
            lbl = (f'crop #{ch.eid} ({ch.verb}) {el.role} "{el.name[:40]}" '
                   f'at screen [{x},{y},{w},{h}]:')
            blocks.append(text_block(lbl))
            blocks.append(image_block(c["b64"]))
            img_tokens += c["tokens"]
            n_img += 1
            self.live_crops.append((step_no, ch.eid, lbl))
            self.crops_emitted += 1
        self._note_images(0, img_tokens)
        return Observation(
            blocks=blocks,
            observation_tokens=count_text_tokens(
                head + "".join(b["text"] for b in blocks if b["type"] == "text")),
            image_tokens=img_tokens, n_images=n_img, n_changes=len(changes),
            note="delta+crops",
        )


# --------------------------------------------------------------------- C

class ArmC(Channel):
    """Tool, text-priority: crops only where the tree genuinely cannot speak."""
    name = "C"
    addressing = "id"

    def initial(self, task, table):
        return ArmB.initial(self, task, table)

    def step(self, task, prev_table, curr_table, last_result, step_no):
        changes = D.diff(prev_table, curr_table)
        # The bbox-honesty check: if the tree declares text but the region has
        # no ink, the tree is lying and C is forced to send pixels.
        for ch in changes:
            el = curr_table.get(ch.eid)
            if el is None or ch.verb in ("removed", "moved"):
                continue
            if el.text or el.name:
                if not screen.verify_bbox(el.bbox, el.text or el.name):
                    ch.tree_described = False

        head = (f"Step {step_no}. Result of last action: {last_result}\n"
                f"CHANGES ({len(changes)}):\n{D.render_changes(changes)}\n")
        blocks = [text_block(head)]
        img_tokens = 0
        n_img = 0
        for ch in changes:
            if not D.wants_crop_text_first(ch):
                continue
            el = curr_table.get(ch.eid)
            if el is None or n_img >= 6:
                continue
            c = screen.crop_for(el.bbox, ch.eid)
            x, y, w, h = c["region"]
            why = "visual element" if ch.visual else "tree description unreliable"
            lbl = (f'crop #{ch.eid} ({ch.verb}, {why}) {el.role} '
                   f'"{el.name[:40]}" at screen [{x},{y},{w},{h}]:')
            blocks.append(text_block(lbl))
            blocks.append(image_block(c["b64"]))
            img_tokens += c["tokens"]
            n_img += 1
            self.live_crops.append((step_no, ch.eid, lbl))
            self.crops_emitted += 1
        return Observation(
            blocks=blocks,
            observation_tokens=count_text_tokens(
                head + "".join(b["text"] for b in blocks if b["type"] == "text")),
            image_tokens=img_tokens, n_images=n_img, n_changes=len(changes),
            note="delta+forced-crops",
        )


# --------------------------------------------------------------------- D

class ArmD(Channel):
    """Table + full screenshot every step, no deltas. Ablation only."""
    name = "D"
    addressing = "id"

    def initial(self, task, table):
        return ArmB.initial(self, task, table)

    def step(self, task, prev_table, curr_table, last_result, step_no):
        a = self._anchor()
        tt = curr_table.render()
        txt = (f"Step {step_no}. Result of last action: {last_result}\n"
               f"ELEMENTS ({len(curr_table)}):\n{tt}\n"
               f"Current screenshot ({a['size'][0]}x{a['size'][1]}):")
        return Observation(
            blocks=[text_block(txt), image_block(a["b64"])],
            observation_tokens=count_text_tokens(txt),
            image_tokens=a["tokens"], n_images=1, note="table+screenshot",
        )


# ------------------------------------------------------------- B+ and C+

class _Enriched(Channel):
    """Shared parts of the round-2 arms.

    The enrichment changes what the *table* says, not how the channel behaves,
    so B+ differs from B in exactly one place — `enrich = True`, which makes the
    runner ask the observer for blocks, reachability, shortcuts and the geometry
    merge. Everything else in the loop is untouched, which is what keeps B a
    valid control rather than a different experiment.
    """
    enrich = True
    task_object = True

    def preamble(self, task):
        return (render_task_object(task) if self.task_object
                else f"TASK: {task.prompt}")

    def initial_enriched(self, task, table):
        a = self._anchor()
        tt = table.render()
        extra = []
        if table.blocks:
            extra.append(f"The table is grouped into {len(table.blocks)} blocks "
                         f"— sets of elements that appear and disappear "
                         f"together. Each is marked fixed (chrome that does not "
                         f"change with the data) or variable (content).")
        if table.n_shortcuts:
            extra.append("Rows carry the keyboard accelerators the accessibility "
                         "tree declares. `keys=ctrl+s` means one KEY action "
                         "replaces opening the menu and clicking; an `inside` "
                         "line lists what a closed menu contains, so you do not "
                         "need to open it to find out.")
        if table.blockers:
            extra.append("A modal dialog is open. Blocks marked NOT ACTIONABLE "
                         "cannot be clicked until it closes — clicking them "
                         "wastes a step.")
        if table.ambiguous_groups:
            extra.append("Rows marked AMBIGUOUS are ones the tree cannot tell "
                         "apart; a pixel crop of each is sent when they change.")
        txt = (f"{self.preamble(task)}\n\n"
               f"Below is the complete table of on-screen elements, with exact "
               f"coordinates taken from the operating system, and an anchor "
               f"screenshot ({a['size'][0]}x{a['size'][1]}, showing the same "
               f"{a['native'][0]}x{a['native'][1]} screen) so you "
               f"can see what those ids look like.\n"
               + ("\n".join("- " + e for e in extra) + "\n" if extra else "")
               + f"\nELEMENTS ({len(table)}):\n{tt}\n")
        self._note_images(0, a["tokens"])
        return Observation(
            blocks=[text_block(txt), image_block(a["b64"])],
            observation_tokens=count_text_tokens(txt),
            image_tokens=a["tokens"], n_images=1, note="anchor+enriched-table",
        )

    def _tag_ambiguous(self, changes, curr_table):
        for ch in changes:
            el = curr_table.get(ch.eid)
            if el is not None and el.ambiguous:
                ch.ambiguous = True
                ch.ambiguity_reason = el.ambiguity_reason

    def _count_ambiguity_crop(self, ch, forced_by_ambiguity):
        if not forced_by_ambiguity:
            return
        self.crops_ambiguity += 1
        if ch.ambiguity_reason == "same-name":
            self.crops_amb_same_name += 1
        elif ch.ambiguity_reason == "peer-set":
            self.crops_amb_peer_set += 1


class ArmBPlus(_Enriched):
    """B with the layer-1 enrichment: blocks, reachability, shortcuts, merge."""
    name = "B+"
    addressing = "id"

    def initial(self, task, table):
        return self.initial_enriched(task, table)

    def step(self, task, prev_table, curr_table, last_result, step_no):
        return ArmB.step(self, task, prev_table, curr_table, last_result, step_no)


class ArmCPlus(_Enriched):
    """C with the enrichment and the rule that ambiguity forces a crop.

    Arm B crops every `added` element anyway, so the ambiguity rule changes
    nothing there; it is only in the text-first channel that it can decide
    anything, which is why the prediction about it is registered on C+.
    """
    name = "C+"
    addressing = "id"
    ambiguity_crops = True

    def initial(self, task, table):
        return self.initial_enriched(task, table)

    def step(self, task, prev_table, curr_table, last_result, step_no):
        changes = D.diff(prev_table, curr_table)
        self._tag_ambiguous(changes, curr_table)
        for ch in changes:
            el = curr_table.get(ch.eid)
            if el is None or ch.verb in ("removed", "moved"):
                continue
            if el.text or el.name:
                if not screen.verify_bbox(el.bbox, el.text or el.name):
                    ch.tree_described = False

        head = (f"Step {step_no}. Result of last action: {last_result}\n"
                f"CHANGES ({len(changes)}):\n{D.render_changes(changes)}\n")
        blocks = [text_block(head)]
        img_tokens = n_img = 0
        for ch in changes:
            text_first = D.wants_crop_text_first(ch)
            by_ambiguity = D.wants_crop_ambiguous(ch)
            if not (text_first or by_ambiguity):
                continue
            el = curr_table.get(ch.eid)
            if el is None or n_img >= 6:
                continue
            c = screen.crop_for(el.bbox, ch.eid)
            x, y, w, h = c["region"]
            if text_first:
                why = "visual element" if ch.visual else "tree description unreliable"
            else:
                why = f"ambiguous: {ch.ambiguity_reason}"
            lbl = (f'crop #{ch.eid} ({ch.verb}, {why}) {el.role} '
                   f'"{el.name[:40]}" at screen [{x},{y},{w},{h}]:')
            blocks.append(text_block(lbl))
            blocks.append(image_block(c["b64"]))
            img_tokens += c["tokens"]
            n_img += 1
            self.live_crops.append((step_no, ch.eid, lbl))
            self.crops_emitted += 1
            self._count_ambiguity_crop(ch, by_ambiguity and not text_first)
        self._note_images(0, img_tokens)
        return Observation(
            blocks=blocks,
            observation_tokens=count_text_tokens(
                head + "".join(b["text"] for b in blocks if b["type"] == "text")),
            image_tokens=img_tokens, n_images=n_img, n_changes=len(changes),
            note="delta+forced-crops+ambiguity",
        )


# Ablations for §4.4 of PREDICTIONS.md — each is B+ with one enrichment off.
class ArmBPlusNoBlocks(ArmBPlus):
    name = "B+nb"
    drop_enrichment = "blocks"


class ArmBPlusNoReach(ArmBPlus):
    name = "B+nr"
    drop_enrichment = "reachability"


class ArmBPlusNoKeys(ArmBPlus):
    name = "B+nk"
    drop_enrichment = "shortcuts"


ARMS = {"A": ArmA, "B": ArmB, "C": ArmC, "D": ArmD,
        "B+": ArmBPlus, "C+": ArmCPlus,
        "B+nb": ArmBPlusNoBlocks, "B+nr": ArmBPlusNoReach,
        "B+nk": ArmBPlusNoKeys}
