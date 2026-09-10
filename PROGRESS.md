# PROGRESS.md

Wall clock started 2026-09-10 04:25 UTC. Budget 8 h / 40 USD (defaults — see
DECISIONS D0.1). The session was **rate-limited and idle from ~06:15 to
~12:20 UTC**, so elapsed time and time actually worked differ by about six
hours; budget is tracked against time worked (DECISIONS D4.1).

| # | Milestone | State | Notes |
|---|---|---|---|
| 1 | Environment up, AT-SPI tree populated | **done** | gate passed |
| 2 | Observer + stable-id test | **done** | test caught two real bugs |
| 3 | Executor with act-time validation | **done** | re-reads one element, not the tree |
| 4 | Agent loop with injectable observation channel | **done** | one loop, channel injected |
| 5 | Arms A / B / C (+ D implemented, not run) | **done** | A reimplemented, see D4.9 |
| 6 | Two tasks end-to-end on all three arms | **done** | pilot found 3 blocking bugs |
| 7 | Remaining tasks | **done** | 16 defined, 14 run (D4.5) |
| 8 | Full interleaved run | **in progress** | 3 arms × 14 tasks × 3 reps |
| 9 | Analysis + reports | pending | |

## Milestone 1 — environment (04:52 UTC)

`scripts/env_up.sh` brings up Xvfb `:99` at 1920×1080×24 / 96 dpi, a shared
D-Bus session bus, `at-spi-bus-launcher` + `at-spi2-registryd`, openbox, and
exports everything through `/tmp/grid-env/env.sh`.

`scripts/verify_env.py` is the gate. Result:

```
app='mousepad'   nodes= 322  actionable_with_bbox= 265
app='pcmanfm'    nodes= 193  actionable_with_bbox= 120
app='soffice'    nodes=2020  actionable_with_bbox= 753
RESULT: PASS
```

Model access was resolved in the same milestone (D2.1–D2.3): the `claude` CLI
in headless stream-json mode accepts image blocks, reports token usage split
into input / output / cache-write / cache-read, and a two-turn probe confirmed
the append-only prefix is genuinely cached (turn 2: `cache_read=1166`).

## Milestones 2–3 — observer and executor (05:55 UTC)

`tests/test_id_stability.py` passes on all four scenarios (idle, forced
repaint, content change, window move) at 0 % id churn, with a window move
emitting 7 `moved` rather than 7 `removed` + 7 `added`.

It caught two real bugs before anything was built on top:

* **ids chained through the parent's name.** Typing one character renames the
  frame `Untitled 1 - Mousepad` → `*Untitled 1 - Mousepad`, which re-keyed
  every descendant: 200 % churn. Title-bearing roles are now identified
  structurally.
* **text extraction silently returned empty**, because `get_text_iface()`
  hands back the Accessible whose `get_text()` is the *name* getter with a
  different signature. The entire text-only delta path — all of arm C — was
  quietly dead.

## Milestones 4–6 — loop, arms, tasks, pilot (12:40 UTC)

Piloting two tasks across three arms before spending budget was worth it; it
found three blocking faults:

* Chromium never launched (needs `--no-sandbox` as root), so every browser
  task would have scored zero for all arms.
* The CDP verifier got 403 from DevTools until the websocket `Origin` header
  was suppressed.
* Act-time validation re-walked the whole tree twice per step (~1.4 s each
  with Calc open); it now re-reads the single named element.

## Milestone 8 — full run (in progress, started 13:02 UTC)

3 arms × 14 tasks × 3 reps = 126 runs, interleaved, resumable, with a
15:00 UTC deadline and an 85 %-of-spend stop.

**Arm A was reimplemented partway through and its earlier runs discarded**
(D4.9): the first version accumulated every screenshot in one append-only
conversation, giving the baseline full prefix caching, when the brief requires
the screenshot to be *replaced* each step. Under the corrected version the
baseline records `cache_read = 0` on every run — the destroyed cache that the
whole comparison is about. The 14 superseded runs are archived in
`results/raw/discarded_armA_v1.jsonl` and excluded from analysis.

Spend on the experiment so far: ~$1.4 of the $40 budget.
