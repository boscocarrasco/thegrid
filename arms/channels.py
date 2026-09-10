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


class Channel:
    """Base: shared plumbing, arms override `initial` and `step`."""
    name = "?"
    addressing = "id"          # "id" or "xy"
    stateless = False          # True => the transcript is rebuilt every step

    def __init__(self, crop_ttl: int = 3):
        self.crop_ttl = crop_ttl
        self.live_crops = []   # (step_emitted, eid, description)

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

    # ---- crop ageing (arms B and C) ----

    def age_crops(self, step_no):
        """Returns descriptions of crops that have just aged out.

        The context is append-only, so an image already sent cannot be taken
        back mid-conversation. Ageing is therefore realised at the next
        compaction boundary (runner restarts the session with the aged
        transcript); what this returns is the textual replacement that goes
        into that transcript.
        """
        keep, aged = [], []
        for (s, eid, desc) in self.live_crops:
            if step_no - s >= self.crop_ttl:
                aged.append((eid, desc))
            else:
                keep.append((s, eid, desc))
        self.live_crops = keep
        return aged


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


ARMS = {"A": ArmA, "B": ArmB, "C": ArmC, "D": ArmD}
