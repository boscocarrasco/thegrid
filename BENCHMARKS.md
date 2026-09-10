# Running this against third-party benchmarks

Everything in `RESULTS.md` was measured on a task suite I wrote myself. That is
the weakest part of the evidence: I chose the tasks, and two of them were
designed after seeing which comparison failed to discriminate. An external
benchmark removes that degree of freedom.

This document is a plan, not a result. **Nothing here has been run** — the
container this work was done in cannot run any of it (see §4).

---

## 1. OSWorld — the obvious target, and a near-perfect fit

[OSWorld](https://github.com/xlang-ai/OSWorld) (NeurIPS 2024) is 369 tasks on
real Ubuntu, Windows and macOS, each with a scripted initial state and an
execution-based verifier. It is the benchmark the design document already
names as the external comparison.

It fits this work unusually well for three reasons.

**It already uses the same accessibility API.** OSWorld obtains its
accessibility tree through `pyatspi` on GNOME/Ubuntu and serialises it to XML.
That is the same AT-SPI2 source `observer/table.py` walks, so the observation
layer is a drop-in replacement for a component the benchmark already has,
not a foreign attachment.

**It already ships the baseline this experiment needs.** `--observation_type`
accepts four values:

| value | what the agent gets | maps to |
|---|---|---|
| `screenshot` | raw screen capture | **arm A** |
| `a11y_tree` | the full accessibility tree, every step | close to **arm D**, text-only |
| `screenshot_a11y_tree` | both, every step | **arm D** |
| `som` | set-of-marks: screenshot with numbered boxes | — |

There is no delta option. `a11y_tree` re-sends the *entire* tree on every
step, which is exactly the cost profile arm D showed to be the worst of both
worlds. So the interesting contribution is a fifth observation type —
`a11y_delta` — that sends the table once and then verb deltas, which is arms
B and C.

**The agent interface is small.** An agent implements two methods:

```python
class Agent:
    def reset(self): ...
    def predict(self, instruction: str, obs: dict) -> (response, actions): ...
```

`obs` is a dict keyed by the observation type (`obs["screenshot"]`,
`obs["a11y_tree"]`, …). Actions are returned either as `pyautogui` Python
source or as `computer_13`, OSWorld's enumerated action set.

### What would have to be written

1. **An observation provider.** Port `observer/table.py`, `observer/delta.py`
   and `observer/screen.py` into the benchmark VM and expose the result as a
   new `observation_type`. The element table and crops are already computed
   from AT-SPI and X11 respectively, both of which exist inside an OSWorld
   Ubuntu VM.
2. **An adapter for the action format.** This is the real work. Arms B/C act
   by element id; OSWorld expects `pyautogui` code or `computer_13`. The
   adapter resolves an id against the live table and emits
   `pyautogui.click(x, y)` — which is what `executor/actions.py` already does
   internally, minus the XTEST call. Act-time validation has to move into the
   adapter, since OSWorld executes the code itself.
3. **Four agents**, one per arm, all wrapping the same `runner/loop.py` logic
   with the channel injected, so the arms stay comparable to each other as
   well as to OSWorld's own numbers.

### The comparison worth running

| Configuration | Question it answers |
|---|---|
| `screenshot` (OSWorld default) | how the baseline scores — comparable to published leaderboards |
| `a11y_tree` (OSWorld default) | does the full tree beat a screenshot on their tasks |
| `a11y_delta` = arm B | **does table-once-plus-deltas beat both** |
| `a11y_delta` = arm C | does text-priority hold up on tasks I did not choose |

Publishable claim if it holds: *the same accessibility data, sent as a delta
instead of a full tree, at N % of the tokens and no loss of success rate.*

---

## 2. OSWorld 2.0 — the right target for compaction

[OSWorld 2.0](https://github.com/xlang-ai/OSWorld-V2) is 108 **long-horizon**
tasks, graded against weighted checkpoints rather than pass/fail. The scale
difference is the point: a task averages ~318 tool calls, against ~30 in
OSWorld 1.0.

This matters directly. §2.8 of `REPORT.md` reports that compaction fires and
cuts tokens 43 % but does not reduce cost, and says plainly that 17-step tasks
cannot show whether it pays off at 50 or 100 steps. **A 318-call task is where
that question gets answered** — and where an uncompacted append-only context
would stop fitting in the window at all, which is the regime the whole
compaction mechanism exists for.

If the observation layer has a strongest case, it is here, and it is untested.

---

## 3. Others, and why they rank lower

| Benchmark | Fit | Note |
|---|---|---|
| [Windows Agent Arena](https://github.com/microsoft/WindowsAgentArena) | medium | 154 tasks, Windows 11. Would require a UIA backend instead of AT-SPI — a real port, though the table/delta/crop design is toolkit-agnostic. Runs Windows in Docker + QEMU + KVM, parallelised on Azure ML. |
| [OS-Harm](https://github.com/tml-epfl/os-harm) | low | Built on OSWorld but measures *safety*, not efficiency. Free reuse of the OSWorld harness if it is already standing. |
| WebArena / Mind2Web | low | Browser-only. The CDP path would carry it, but it tests none of the desktop coverage that motivates AT-SPI. |

---

## 4. The blocker: this container cannot run any of them

Checked directly:

```
egrep -c '(vmx|svm)' /proc/cpuinfo   ->  0
ls /dev/kvm                          ->  does not exist
```

OSWorld's Docker provider requires KVM; its own documentation makes that check
the first setup step. Windows Agent Arena needs QEMU + KVM. Neither can start
here, so none of this was attempted rather than attempted and fudged.

Three ways out, in order of cost:

1. **AWS provider.** OSWorld supports `--provider_name aws` alongside VMware,
   VirtualBox and Docker. This is the least-effort path: no local
   virtualisation required, and it parallelises.
2. **A host with nested virtualisation.** Any bare-metal Linux box, or a cloud
   VM type that exposes KVM. Then `--provider_name docker` with
   `run_multienv.py --num_envs N`.
3. **VMware locally**, which is what the OSWorld authors use and document most
   thoroughly.

Cost is the other constraint. OSWorld is 369 tasks; at four arms and three
repetitions that is 4,428 runs. Measured cost here was ~$0.06–0.17 per task
depending on the arm, so a full sweep is order **$300–700**, against the
$22.96 this whole study spent. A defensible first pass is one repetition on a
stratified subset — OSWorld ships per-application task splits — with the full
sweep reserved for whichever arms survive.

---

## 5. Prior work that already occupies this ground

**[A11y-Compressor](https://arxiv.org/abs/2605.00551)** (ACL 2026 SRW) does
something adjacent and reports OSWorld numbers: it converts the linearised
accessibility tree into a compact structured representation, reporting
**input tokens down to 22 % of the original and success up 5.1 points**.

This is the number to beat, and it reframes the contribution. A11y-Compressor
compresses *the tree that is sent every step*. This layer's claim is
different — send the table **once**, then only what changed — and the two are
composable rather than competing: a compressed table plus deltas should beat
either alone.

It also means an honest framing of any OSWorld result has to compare against
A11y-Compressor, not just against `a11y_tree`. Their 22 % is the bar.

---

## 6. Recommended order

1. Stand up OSWorld on AWS with the stock `screenshot` and `a11y_tree` agents,
   and reproduce a published number. Until that reproduces, nothing measured
   on top of it means anything.
2. Add the `a11y_delta` observation type and the id→`pyautogui` adapter.
3. One repetition, stratified subset, four arms. Compare against both OSWorld
   defaults and the A11y-Compressor figures.
4. Only if that holds: OSWorld 2.0, where compaction finally has a horizon
   long enough to matter.
