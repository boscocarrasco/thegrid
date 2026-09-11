"""One agent loop, shared by every arm.

The arm is injected as an observation channel. Nothing else about the loop —
model, system prompt skeleton, step limit, executor, verifier, debounce, seed —
varies between arms, because any other difference would invalidate the whole
comparison.
"""
from __future__ import annotations

import json
import os
import random
import re
import time
import traceback

from arms.channels import ARMS, SYSTEM_PROMPT
from executor.actions import Executor
from observer import screen, table as tbl
from runner.model import ModelSession, text_block, count_text_tokens
from tasks import workspace as ws

SCREEN_W, SCREEN_H = 1920, 1080

# Exponential backoff for provider rate limits, in seconds. The last value
# repeats until the per-run ceiling is reached.
RATE_LIMIT_BACKOFF = (30, 60, 120, 300, 600, 900)

_ACT_RE = re.compile(r"^\s*ACT:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


class Action:
    def __init__(self, kind, **kw):
        self.kind = kind
        self.__dict__.update(kw)

    def __repr__(self):
        d = {k: v for k, v in self.__dict__.items() if k != "kind"}
        return f"{self.kind}{d if d else ''}"


def parse_action(text, addressing):
    """Extract the single action from the model's reply."""
    m = _ACT_RE.search(text or "")
    raw = (m.group(1) if m else (text or "").strip().splitlines()[-1:] or [""])
    if isinstance(raw, list):
        raw = raw[0]
    raw = raw.strip()
    if not raw:
        return Action("malformed", raw=text[:200])

    up = raw.upper()
    if up.startswith("DONE"):
        return Action("done")
    if up.startswith("GIVEUP"):
        return Action("giveup")
    if up.startswith("TYPE"):
        return Action("type", text=raw[4:].lstrip())
    if up.startswith("KEY"):
        return Action("key", combo=raw[3:].strip())

    if addressing == "id":
        m2 = re.match(r"(DOUBLECLICK|CLICK)\s+#?([A-Za-z0-9]+)", raw, re.I)
        if m2:
            return Action("click", eid=m2.group(2),
                          double=m2.group(1).upper() == "DOUBLECLICK")
        m3 = re.match(r"SCROLL\s+#?([A-Za-z0-9]+)\s+(-?\d+)", raw, re.I)
        if m3:
            return Action("scroll", eid=m3.group(1), delta=int(m3.group(2)))
    else:
        m2 = re.match(r"(DOUBLECLICK|CLICK)\s+\(?\s*(-?\d+)\s*[, ]\s*(-?\d+)",
                      raw, re.I)
        if m2:
            return Action("click_xy", x=int(m2.group(2)), y=int(m2.group(3)),
                          double=m2.group(1).upper() == "DOUBLECLICK")
        m3 = re.match(r"SCROLL\s+\(?\s*(-?\d+)\s*[, ]\s*(-?\d+)\s*[, ]?\s*(-?\d+)",
                      raw, re.I)
        if m3:
            return Action("scroll_xy", x=int(m3.group(1)), y=int(m3.group(2)),
                          delta=int(m3.group(3)))
    return Action("malformed", raw=raw[:200])


def why_of(obs):
    """The reason a refresh gave, as recorded in its note."""
    return (obs.note or "").split(":", 1)[-1].strip()


def run_one(task, arm_name, seed, model="sonnet", crop_ttl=3,
            step_limit=None, token_budget=None, out_dir="results/raw",
            run_tag="", compaction=True, image_window=None, task_object=None,
            rate_limit_max_wait_s=3600.0):
    """Execute one (task, arm, seed) run and return its JSONL record."""
    random.seed(seed)
    rec = {
        "run_tag": run_tag,
        "task": task.id, "arm": arm_name, "seed": seed, "model": model,
        "tags": list(task.tags),
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "success": False, "steps": 0, "model_calls": 0,
        "wall_time_total_s": 0.0,
        "ttft_per_step_ms": [], "decode_time_per_step_ms": [],
        "tokens_in": 0, "tokens_out": 0, "tokens_cached": 0,
        "tokens_cache_create": 0,
        "observation_tokens": 0, "image_tokens": 0,
        "grounding_failures": 0, "action_aborts": 0,
        "cost_usd": 0.0,
        "observe_time_s": 0.0, "act_time_s": 0.0, "debounce_s": 0.0,
        "steps_detail": [], "verify_detail": "", "error": "",
        "compactions": 0, "crops_emitted": 0, "crops_aged": 0,
        "compaction_log": [],
        "step_limit": step_limit or task.max_steps,
        "token_budget": token_budget,
        "terminated": "", "crop_ttl": crop_ttl,
        # ---- round 2 ----
        "reanchors": 0,
        "enrich_ms": {},              # per-phase cost of the layer-1 enrichment
        "crops_ambiguity": 0,         # crops the ambiguity rule alone asked for
        "crops_amb_same_name": 0,     # ... by the registered same-name rule
        "crops_amb_peer_set": 0,      # ... by the peer-set rule
        "peak_live_images": 0,
        "peak_live_image_tokens": 0,
        "image_window": None,
        "task_object": False,
        "enriched": False,
        "dropped_enrichment": "",
        "constraint_results": {},     # per-constraint verdicts, long tasks
        "rate_limit_waits": [],       # (attempt, seconds waited)
        "rate_limit_wait_s": 0.0,
    }
    t_run0 = time.time()
    channel = ARMS[arm_name](crop_ttl=crop_ttl)
    if not compaction:
        # Control condition: the same arm with the one mechanism that bounds
        # its context switched off, so its cost can be attributed.
        channel.compactable = False
    if image_window is not None:
        channel.image_window = int(image_window)
    if task_object is not None:
        channel.task_object = bool(task_object)
    rec["compaction_enabled"] = bool(compaction and channel.compactable)
    rec["image_window"] = channel.image_window
    rec["task_object"] = bool(channel.task_object)
    rec["enriched"] = bool(getattr(channel, "enrich", False))
    rec["dropped_enrichment"] = getattr(channel, "drop_enrichment", "") or ""
    ex = Executor(SCREEN_W, SCREEN_H)
    sess = None

    try:
        task.setup(seed)
        screen.wait_stable(timeout=6.0, quiet=0.35)

        system = SYSTEM_PROMPT + "\n" + channel.action_rules()
        sess = ModelSession(system, model=model)

        enrich = bool(getattr(channel, "enrich", False))
        drop = getattr(channel, "drop_enrichment", None)

        def observe():
            return tbl.snapshot(SCREEN_W, SCREEN_H, enrich=enrich, drop=drop)

        t0 = time.time()
        cur = observe()
        obs = channel.initial(task, cur)
        rec["observe_time_s"] += time.time() - t0
        rec["initial_table_size"] = len(cur)
        prev_tbl = None

        limit = step_limit or task.max_steps
        last_result = "(nothing yet — this is the first step)"
        anchor_scale = (SCREEN_W / 1280.0, SCREEN_H / 720.0)
        history = []   # (step, result) — what survives a compaction

        for step in range(1, limit + 1):
            rec["observation_tokens"] += obs.observation_tokens
            rec["image_tokens"] += obs.image_tokens

            # ---- compaction: the only thing that bounds an append-only
            # context. Rebuilding the session is exactly the cache
            # invalidation the design document says compaction costs; the
            # transcript that replaces it carries a consolidated summary, the
            # text descriptions of aged-out crops, a fresh table and a fresh
            # anchor screenshot.
            if (not getattr(channel, "stateless", False)) and step > 1:
                fresh, kind = channel.refresh(task, cur, history, step, prev_tbl)
                if fresh is not None:
                    obs = fresh
                    if kind == "compaction":
                        # Only a compaction rewrites the prefix, so only a
                        # compaction pays for the cache. A re-anchor appends.
                        sess.close()
                        sess = ModelSession(system, model=model)
                        rec["compactions"] += 1
                    else:
                        rec["reanchors"] = rec.get("reanchors", 0) + 1
                    rec["compaction_log"].append(
                        {"step": step, "reason": why_of(fresh), "kind": kind})
                    rec["observation_tokens"] += obs.observation_tokens
                    rec["image_tokens"] += obs.image_tokens

            if getattr(channel, "stateless", False) and step > 1:
                # The baseline replaces its screenshot each step, and an
                # append-only conversation cannot retract an image it already
                # sent — so the transcript is rebuilt. This is the cache
                # invalidation the standard loop actually pays for, and it is
                # the behaviour under comparison, not a defect to work around.
                sess.close()
                sess = ModelSession(system, model=model)
                rec["session_rebuilds"] = rec.get("session_rebuilds", 0) + 1

            # The provider quota is an external constraint, not a property of
            # the arm, so a rate limit is waited out rather than counted. Each
            # wait is written into this run's record: runs lost to rate limits
            # and not flagged would bias every table toward whichever arm
            # happened to be running when the quota was free.
            reply = sess.ask(obs.blocks)
            rec["model_calls"] += 1
            attempt = 0
            while (not reply.ok and ModelSession.is_rate_limit(reply.error)
                   and rec["rate_limit_wait_s"] < rate_limit_max_wait_s):
                attempt += 1
                wait = min(RATE_LIMIT_BACKOFF[min(attempt - 1,
                                                  len(RATE_LIMIT_BACKOFF) - 1)],
                           rate_limit_max_wait_s - rec["rate_limit_wait_s"])
                rec["rate_limit_waits"].append(
                    {"attempt": attempt, "wait_s": round(wait, 1),
                     "step": step, "error": (reply.error or "")[:120]})
                rec["rate_limit_wait_s"] += wait
                time.sleep(wait)
                reply = sess.ask(obs.blocks)
                rec["model_calls"] += 1
            if not reply.ok and ModelSession.is_rate_limit(reply.error):
                # Backoff exhausted: the quota has been shut for longer than
                # this run is allowed to wait. Still not a task failure.
                rec["error"] = (f"rate limited after "
                                f"{rec['rate_limit_wait_s']:.0f}s of backoff: "
                                f"{reply.error[:160]}")
                rec["terminated"] = "rate_limited"
                break
            if not reply.ok:
                rec["error"] = f"model call failed: {reply.error}"
                rec["terminated"] = "model_error"
                break

            rec["ttft_per_step_ms"].append(round(reply.ttft_ms, 1))
            rec["decode_time_per_step_ms"].append(round(reply.decode_ms, 1))
            rec["tokens_in"] += reply.tokens_in
            rec["tokens_out"] += reply.tokens_out
            rec["tokens_cached"] += reply.tokens_cache_read
            rec["tokens_cache_create"] += reply.tokens_cache_create
            rec["cost_usd"] += reply.cost_usd

            act = parse_action(reply.text, channel.addressing)
            rec["steps"] = step

            if token_budget is not None:
                # Budget on *fresh* tokens: input + cache-write + output. A
                # cache read is neither work the provider redid nor a cost the
                # user pays at full rate, so charging it here would bill the
                # append-only arms for the very thing that makes them cheap
                # and would decide the comparison by choice of denominator.
                spent = (rec["tokens_in"] + rec["tokens_out"]
                         + rec["tokens_cache_create"])
                if spent > token_budget:
                    rec["terminated"] = "token_budget"
                    rec["steps_detail"].append(
                        {"step": step, "action": repr(act),
                         "note": "stopped: token budget exhausted"})
                    break

            if act.kind in ("done", "giveup"):
                rec["terminated"] = act.kind
                rec["steps_detail"].append({"step": step, "action": act.kind,
                                            "reply": reply.text[:200]})
                break

            # ---- act, with validation at the instant of acting ----
            t1 = time.time()
            # The table the model was shown is the one its id refers to; the
            # executor re-reads that single element's live geometry and state
            # at the instant of acting, so a second full tree walk here would
            # cost ~1.4s per step and add nothing.
            live = cur
            if act.kind == "click":
                r = ex.click(act.eid, live_table=live, double=act.double)
            elif act.kind == "click_xy":
                r = ex.click_xy(int(act.x * anchor_scale[0]),
                                int(act.y * anchor_scale[1]),
                                live_table=live, double=act.double)
            elif act.kind == "scroll":
                r = ex.scroll(act.eid, act.delta, live_table=live)
            elif act.kind == "scroll_xy":
                r = ex.scroll_xy(int(act.x * anchor_scale[0]),
                                 int(act.y * anchor_scale[1]), act.delta)
            elif act.kind == "type":
                r = ex.type(act.text)
            elif act.kind == "key":
                r = ex.key(act.combo)
            else:
                r = None
            rec["act_time_s"] += time.time() - t1

            if r is None:
                last_result = ("your reply could not be parsed as an action; "
                               "reply with exactly one ACT: line")
                detail = {"step": step, "action": "malformed",
                          "reply": reply.text[:200]}
            else:
                last_result = ("ok — " if r.ok else "FAILED — ") + r.detail
                detail = {"step": step, "action": repr(act), "ok": r.ok,
                          "detail": r.detail, "aborted": r.aborted,
                          "grounding_failure": r.grounding_failure}
            rec["steps_detail"].append(detail)
            history.append((step, last_result[:120]))

            # ---- observe: debounce, snapshot, delta ----
            t2 = time.time()
            st = screen.wait_stable(timeout=4.0, quiet=0.3)
            rec["debounce_s"] += st["waited_s"]
            prev = cur
            prev_tbl = cur
            cur = observe()
            if enrich and cur.enrich_ms:
                # PREDICTIONS.md §8 commits to reporting what the enrichment
                # costs whether or not the number is flattering, so the timing
                # is accumulated per run rather than inferred from totals.
                for k, v in cur.enrich_ms.items():
                    rec["enrich_ms"][k] = rec["enrich_ms"].get(k, 0.0) + v
            obs = channel.step(task, prev, cur, last_result, step + 1)
            rec["observe_time_s"] += time.time() - t2
        else:
            rec["terminated"] = "step_limit"

        rec["crops_emitted"] = channel.crops_emitted
        rec["crops_aged"] = channel.crops_aged
        rec["crops_ambiguity"] = channel.crops_ambiguity
        rec["crops_amb_same_name"] = channel.crops_amb_same_name
        rec["crops_amb_peer_set"] = channel.crops_amb_peer_set
        rec["peak_live_images"] = channel.peak_live_images
        rec["peak_live_image_tokens"] = channel.peak_live_image_tokens
        rec["grounding_failures"] = ex.grounding_failures
        rec["action_aborts"] = ex.action_aborts
        rec["abort_log"] = ex.abort_log[:20]

    except Exception:
        rec["error"] = traceback.format_exc()[-1200:]
        rec["terminated"] = rec["terminated"] or "harness_error"
    finally:
        if sess:
            try:
                rec["cost_usd"] = max(rec["cost_usd"], sess.cost_usd)
            except Exception:
                pass
            sess.close()

    # ---- programmatic verification of final state ----
    try:
        ok, why = task.verify()
        rec["success"] = bool(ok)
        rec["verify_detail"] = why
    except Exception as e:
        rec["success"] = False
        rec["verify_detail"] = f"verifier raised: {e}"

    # Per-constraint verdicts, where the task declares a decomposition. This is
    # what separates "failed the task" from "forgot a constraint" — without it
    # the task-object hypothesis has nothing to be measured against.
    if getattr(task, "verify_constraints", None):
        try:
            rec["constraint_results"] = {k: bool(v) for k, v
                                         in task.verify_constraints().items()}
        except Exception as e:
            rec["constraint_results"] = {"_error": str(e)[:160]}

    rec["wall_time_total_s"] = round(time.time() - t_run0, 2)
    rec["tokens_total"] = (rec["tokens_in"] + rec["tokens_out"]
                           + rec["tokens_cached"] + rec["tokens_cache_create"])
    rec["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{run_tag or 'runs'}.jsonl")
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec
