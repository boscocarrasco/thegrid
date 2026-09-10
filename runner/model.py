"""Model channel: a persistent `claude` process driven over stream-json.

Why the CLI and not `POST /v1/messages`: this container has no
ANTHROPIC_API_KEY (see DECISIONS D2.1). The CLI is host-authenticated and
reports per-call `usage` — input, output, cache-creation and cache-read
tokens — plus `total_cost_usd`, which is exactly the accounting the brief
wants. Stripped of its default preamble (D2.2) it is a bare model call with
~1.1 k tokens of fixed overhead, identical across arms.

The process is kept alive across steps so the conversation is genuinely
append-only and the provider's prefix cache is reused. `cache_read_input_tokens`
on step 2+ is the evidence that it is.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from queue import Queue, Empty


@dataclass
class Reply:
    text: str
    ok: bool = True
    error: str = ""
    ttft_ms: float = 0.0
    decode_ms: float = 0.0
    total_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cache_create: int = 0
    tokens_cache_read: int = 0
    cost_usd: float = 0.0
    raw_usage: dict = field(default_factory=dict)


class ModelError(RuntimeError):
    pass


class ModelSession:
    """One conversation. Send content blocks, get text back."""

    def __init__(self, system_prompt: str, model: str = "sonnet",
                 cwd: str = None, timeout_s: float = 240.0):
        self.system_prompt = system_prompt
        self.model = model
        self.timeout_s = timeout_s
        self.cwd = cwd or os.getcwd()
        self.turns = 0
        self.cost_usd = 0.0
        self.proc = None
        self._q = Queue()
        self._threads = []
        self._stderr = []
        self._start()

    # ---------------------------------------------------------------- proc

    def _start(self):
        cmd = [
            "claude", "-p",
            "--input-format", "stream-json",
            "--output-format", "stream-json",
            "--include-partial-messages",
            "--verbose",
            "--system-prompt", self.system_prompt,
            "--tools", "",
            "--strict-mcp-config",
            "--setting-sources", "",
            "--disable-slash-commands",
            "--no-session-persistence",
            "--permission-prompts", "none",
            "--model", self.model,
        ]
        env = os.environ.copy()
        env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1, cwd=self.cwd, env=env,
        )
        t = threading.Thread(target=self._pump_stdout, daemon=True)
        t.start()
        self._threads.append(t)
        t2 = threading.Thread(target=self._pump_stderr, daemon=True)
        t2.start()
        self._threads.append(t2)

    def _pump_stdout(self):
        try:
            for line in self.proc.stdout:
                line = line.strip()
                if line:
                    self._q.put((time.time(), line))
        except Exception:
            pass
        finally:
            self._q.put((time.time(), None))

    def _pump_stderr(self):
        try:
            for line in self.proc.stderr:
                self._stderr.append(line.rstrip())
                if len(self._stderr) > 200:
                    del self._stderr[:100]
        except Exception:
            pass

    # ---------------------------------------------------------------- ask

    @staticmethod
    def is_rate_limit(err: str) -> bool:
        e = (err or "").lower()
        return ("session limit" in e or "rate limit" in e
                or "usage limit" in e or "429" in e or "overloaded" in e)

    def ask(self, content_blocks) -> Reply:
        """content_blocks: list of Anthropic content blocks (text / image)."""
        if self.proc is None or self.proc.poll() is not None:
            return Reply("", ok=False,
                         error=f"model process dead: {' | '.join(self._stderr[-4:])}")
        msg = {"type": "user",
               "message": {"role": "user", "content": content_blocks}}
        t_send = time.time()
        try:
            self.proc.stdin.write(json.dumps(msg) + "\n")
            self.proc.stdin.flush()
        except Exception as e:
            return Reply("", ok=False, error=f"write failed: {e}")

        first_token_at = None
        text_parts = []
        usage = {}
        cost_before = self.cost_usd
        got_result = False
        deadline = t_send + self.timeout_s

        while time.time() < deadline:
            try:
                ts, line = self._q.get(timeout=max(0.2, deadline - time.time()))
            except Empty:
                break
            if line is None:
                return Reply("", ok=False,
                             error=f"model stream closed: "
                                   f"{' | '.join(self._stderr[-4:])}")
            try:
                ev = json.loads(line)
            except Exception:
                continue
            et = ev.get("type")

            if et == "stream_event":
                se = ev.get("event", {})
                if se.get("type") == "content_block_delta" and first_token_at is None:
                    first_token_at = ts
            elif et == "assistant":
                m = ev.get("message", {})
                for b in m.get("content", []):
                    if b.get("type") == "text":
                        text_parts.append(b.get("text", ""))
                if m.get("usage"):
                    usage = m["usage"]
                if first_token_at is None:
                    first_token_at = ts
            elif et == "result":
                self.cost_usd = float(ev.get("total_cost_usd") or self.cost_usd)
                if ev.get("usage"):
                    usage = ev["usage"] or usage
                if ev.get("is_error"):
                    return Reply("".join(text_parts), ok=False,
                                 error=str(ev.get("result"))[:400])
                got_result = True
                break

        t_end = time.time()
        if not got_result:
            return Reply("".join(text_parts), ok=False,
                         error="timeout waiting for model result")

        self.turns += 1
        ttft = ((first_token_at or t_end) - t_send) * 1000.0
        return Reply(
            text="".join(text_parts).strip(),
            ttft_ms=ttft,
            decode_ms=max(0.0, (t_end - (first_token_at or t_end)) * 1000.0),
            total_ms=(t_end - t_send) * 1000.0,
            tokens_in=int(usage.get("input_tokens") or 0),
            tokens_out=int(usage.get("output_tokens") or 0),
            tokens_cache_create=int(usage.get("cache_creation_input_tokens") or 0),
            tokens_cache_read=int(usage.get("cache_read_input_tokens") or 0),
            cost_usd=max(0.0, self.cost_usd - cost_before),
            raw_usage=usage,
        )

    def close(self):
        try:
            if self.proc and self.proc.poll() is None:
                self.proc.stdin.close()
                self.proc.terminate()
                self.proc.wait(timeout=10)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        self.proc = None


# ------------------------------------------------------------------ helpers

def text_block(s: str) -> dict:
    return {"type": "text", "text": s}


def image_block(b64: str) -> dict:
    return {"type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": b64}}


def count_text_tokens(s: str) -> int:
    """Cheap, deterministic estimate used only to attribute *which part* of the
    prompt the observation occupies. Totals always come from provider usage."""
    return max(1, int(len(s) / 3.7))
