# An observation layer for computer-use agents — and a measurement of whether it helps

This repository contains two things:

1. **A minimal observation layer.** It reads the operating system's own
   accessibility tree into a table of on-screen elements with exact
   coordinates and stable ids, emits per-step *deltas* with verbs
   (`added` / `removed` / `changed` / `moved` / `state`), crops and labels the
   pixels of changed regions, and executes actions addressed by element id
   with validation at the instant of acting.

2. **An experiment that tests whether it is worth it**, comparing three
   observation channels under otherwise identical conditions.

The hypothesis under test: *an agent performs better and costs less if,
instead of a full screenshot every step, it receives a table of elements with
exact coordinates and thereafter only a list of what changed.*

Results are in **[RESULTS.md](RESULTS.md)** (generated from data, never typed
by hand) and **[REPORT.md](REPORT.md)**. Decisions taken autonomously are in
**[DECISIONS.md](DECISIONS.md)**; progress in **[PROGRESS.md](PROGRESS.md)**.

## The three arms

Everything is held constant — model, system prompt skeleton, task set, step
limit, executor, verifier, debounce, seeds — except the observation channel.
`arms/channels.py` is the entire independent variable.

| Arm | Start of task | Each step | Action addressing |
|---|---|---|---|
| **A** baseline | task + full screenshot | full screenshot | pixel coordinates |
| **B** crop-priority | task + full element table + anchor screenshot | verb delta **+ a labelled pixel crop of every changed region** | element id |
| **C** text-priority | same as B | verb delta, **text only**; a crop only where the tree genuinely cannot describe the change | element id |
| **D** ablation (optional) | same as B | full table + full screenshot, no deltas | element id |

Arm B's crop rule follows the specification exactly: `added` yes, `state` yes,
`changed` non-textual yes, `changed` text-only no, `moved` no, `removed` no.
Arm C sends pixels only when the element is a visual role (canvas, image,
chart, video) or when the check that a bbox actually contains what the tree
claims fails.

In B, C and D the context is append-only, so the provider's prefix cache is
reused across steps. In A the screenshot is replaced each step, as the
standard loop does — that is the behaviour being compared, not a bug.

## Layout

```
observer/    element table from AT-SPI2, stable ids, verb deltas,
             labelled region crops, screen-stability debounce
executor/    XTEST actions; click(id) re-reads the element at the instant of
             acting and aborts on a stale belief
arms/        the three (four) observation channels — the independent variable
tasks/       task definitions, programmatic verifiers, deterministic reset
runner/      the shared agent loop, the model channel, the experiment driver
analysis/    aggregation into RESULTS.md with bootstrap intervals
tests/       the id-stability gate
scripts/     desktop bring-up and the environment gate check
```

## Requirements

Ubuntu 24.04 container, run as root. Python **3.12** specifically
(`/usr/bin/python3.12`) — the AT-SPI GObject bindings are built for it.

```bash
apt-get update && apt-get install -y --no-install-recommends \
  xdotool x11-utils x11-xserver-utils xauth xvfb dbus-x11 openbox \
  at-spi2-core gir1.2-atspi-2.0 python3-pyatspi python3-gi python3-gi-cairo \
  gir1.2-gtk-3.0 mousepad pcmanfm libreoffice-gtk3 libreoffice-calc \
  imagemagick fonts-dejavu-core x11-apps

/usr/bin/python3.12 -m pip install --break-system-packages \
  Pillow numpy python-xlib websocket-client
```

Chromium is expected at `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`
(the Playwright build present in this image); change `tasks/workspace.py:CHROMIUM`
to point elsewhere.

Model access goes through the `claude` CLI in headless mode, which must be
authenticated. There is no `ANTHROPIC_API_KEY` in this container — see
DECISIONS D2.1 for why that route was chosen and what it costs.

## Running it

```bash
# 1. bring up the virtual desktop (Xvfb + D-Bus + AT-SPI + openbox)
bash scripts/env_up.sh
set -a; source /tmp/grid-env/env.sh; set +a

# 2. gate check: the accessibility tree must actually populate
/usr/bin/python3.12 scripts/verify_env.py

# 3. gate check: element ids must survive a repaint
/usr/bin/python3.12 tests/test_id_stability.py

# 4. the experiment (interleaved, resumable, stops at 85% of budget)
/usr/bin/python3.12 runner/experiment.py --arms A,B,C --reps 3 --tag main

# 5. the tables
/usr/bin/python3.12 analysis/aggregate.py --raw results/raw/main.jsonl --out RESULTS.md
```

Useful flags on `runner/experiment.py`:

| Flag | Meaning |
|---|---|
| `--arms A,B,C,D` | which channels to run |
| `--tasks id,id` | subset of the suite (default: all) |
| `--reps N` | repetitions per (task, arm) |
| `--token-budget N` | per-run token ceiling, for the equal-budget comparison |
| `--deadline-utc T` | stop at a wall-clock time |
| `--max-usd X` | stop at 85 % of this spend |

Re-running the same `--tag` resumes: completed runs are skipped, and runs that
ended in a provider rate limit or a harness error are retried.

## What gets recorded

One JSON object per run in `results/raw/<tag>.jsonl`, never aggregated at
write time: `success` (from the programmatic verifier), `steps`,
`model_calls`, `wall_time_total_s`, `ttft_per_step_ms`,
`decode_time_per_step_ms`, `tokens_in` / `tokens_out` / `tokens_cached` /
`tokens_cache_create`, `observation_tokens`, `image_tokens`,
`grounding_failures`, `action_aborts`, `cost_usd`, plus the full step-by-step
action trace and the verifier's reason.

## Tasks

14 of the 16 defined tasks are run (DECISIONS D4.5). Every one ends in a
machine check of final state — a file's bytes, a CSV cell, page state read
over CDP. **No model judges success anywhere.** Coverage spans file
operations, text editing and formatting, spreadsheet work, a browser form, a
cross-application task, and three deliberately non-textual tasks (a bar chart,
a count of filled circles, colour-coded status badges) that exist to separate
arm B from arm C.

Each run starts from a deterministic reset: every application is killed, the
four applications' config/cache/session trees are wiped, the workspace
fixtures are rebuilt, and every window is forced to a fixed geometry.

## Scope

This measures the **observation channel only**. There is deliberately no
persistent graph, no memory between runs, no distilled procedures and no
routing to code.
