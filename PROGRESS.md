# PROGRESS.md

Wall clock started 2026-09-10 04:25 UTC. Budget 8 h / 40 USD (defaults — see
DECISIONS D0.1). Hard stop at 85 %: **11:13 UTC or 34 USD**, whichever first.

| # | Milestone | State | Notes |
|---|---|---|---|
| 1 | Environment up, AT-SPI tree populated | **done** | gate passed, see below |
| 2 | Observer + stable-id test | pending | |
| 3 | Executor with act-time validation | pending | |
| 4 | Agent loop with injectable observation channel | pending | |
| 5 | Arms A / B / C | pending | |
| 6 | Two tasks end-to-end on all three arms | pending | |
| 7 | Remaining tasks | pending | |
| 8 | Full interleaved run | pending | |
| 9 | Analysis + reports | pending | |

## Milestone 1 — environment (done, 04:52 UTC)

`scripts/env_up.sh` brings up Xvfb `:99` at 1920×1080×24 / 96 dpi, a shared
D-Bus session bus, `at-spi-bus-launcher` + `at-spi2-registryd`, and exports
everything through `/tmp/grid-env/env.sh`.

`scripts/verify_env.py` is the gate. Result on this container:

```
app='mousepad'   nodes= 322  actionable_with_bbox= 265
app='pcmanfm'    nodes= 193  actionable_with_bbox= 120
app='soffice'    nodes=2020  actionable_with_bbox= 753
RESULT: PASS
```

The tree is genuinely populated, so the experiment is viable.

Model access was also resolved (DECISIONS D2.1–D2.3): the `claude` CLI in
headless stream-json mode accepts image content blocks, returns per-call token
usage including `cache_read_input_tokens`, and a two-turn probe confirmed the
append-only prefix is cached and reused (turn 2: `cache_read=1166`,
`cache_creation=76`). That is the mechanism arms B/C depend on, verified
before any of it was built on.
