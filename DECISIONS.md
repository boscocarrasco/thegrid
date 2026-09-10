# DECISIONS.md

Every decision taken autonomously, with a one-line justification. Newest at the
bottom of each section.

## D0 — Budget

**D0.1 `MAX_WALL_CLOCK_HOURS` and `MAX_API_SPEND_USD` are unset in this
container, so the defaults from the brief apply: 8 h and 40 USD.**
The brief specifies those fallbacks explicitly; wall clock starts at the first
command of the session (2026-09-10 04:25 UTC), so the 85 % stop line is
≈11:13 UTC / 34 USD.

## D1 — Environment

**D1.1 Project interpreter is `/usr/bin/python3.12`, not the `python3` on
`PATH` (3.11).** The image ships a 3.11 that shadows the system interpreter,
but the Debian `gir1.2-atspi-2.0` / `python3-gi` bindings are compiled for
3.12 — `import gi` fails on 3.11 and works on 3.12, and without AT-SPI there
is no experiment.

**D1.2 Desktop is Xvfb `:99` at 1920×1080×24, DPI pinned to 96, `-noreset`.**
The spec requires fixed resolution and scale so coordinates never change
meaning between runs; `-noreset` stops the server from wiping state when the
last client exits between tasks.

**D1.3 One shared D-Bus session bus is created by `scripts/env_up.sh` and
exported through `/tmp/grid-env/env.sh`.** AT-SPI is a bus protocol: the
observer and the applications must sit on the same session bus or the tree
comes back empty, and `dbus-run-session` per-process would give each its own.

**D1.4 GUI applications are mousepad (GTK3 editor), pcmanfm (GTK3 file
manager), LibreOffice Calc (gtk3 VCL plugin) and Chromium.** They are the
lightest real GTK/Qt apps that cover the coverage classes the brief demands
(files, text, spreadsheet, browser) and all four populate AT-SPI; heavier
choices (GNOME Files, gedit) pull a full desktop session into the image.

**D1.5 `SAL_USE_VCLPLUGIN=gtk3` + `OOO_FORCE_DESKTOP=gnome` are forced for
LibreOffice.** Under the default `gen` VCL plugin LibreOffice exposes almost
nothing over AT-SPI; with the gtk3 plugin the gate check sees 753 actionable
elements.

## D2 — Model access

**D2.1 Model calls go through the `claude` CLI in headless
(`--print`) mode rather than a raw `POST /v1/messages`.** No
`ANTHROPIC_API_KEY` exists in this container and the Anthropic endpoint
returns 401 without one; the CLI is authenticated by the host and returns
per-call `usage` (input, output, `cache_creation_input_tokens`,
`cache_read_input_tokens`) plus `total_cost_usd`, which is exactly the
accounting the brief asks for.

**D2.2 The CLI is stripped to a bare model call with
`--system-prompt … --tools "" --strict-mcp-config --setting-sources ""
--disable-slash-commands`.** The default Claude Code preamble costs ~41 k
tokens per call (~$0.038); stripped it costs ~1.1 k (~$0.0045), which both
fits the 40 USD budget and stops the harness's own prompt from swamping the
observation tokens being measured. The residual ~1.1 k is identical across
arms, so it cannot bias the comparison, and it is recorded per run.

**D2.3 Temperature is not settable through the CLI, so it is held constant by
construction instead of being pinned to a value.** All arms go through the
identical call path with identical decoding settings; the brief's requirement
is that temperature not differ *between arms*, which is satisfied. Recorded as
a threat to validity because it is not 0.

**D1.6 openbox runs as the window manager and every app window is forced to a
fixed geometry by `tasks/workspace.py`.** Without a WM, GTK windows never take
focus and dialogs pile up at 0,0, so neither coordinates nor focus are
reproducible between runs — which would confound arm comparisons.

**D1.7 Reproducible initial state comes from a scripted wipe
(`tasks.workspace.reset`), not a container snapshot.** No snapshot/fork
primitive is available in this container; instead the reset kills every app,
deletes the four applications' config/cache/session trees and rebuilds the
workspace fixtures. It was needed immediately: mousepad's "restore previous
session?" modal blocked the second run of the very first test.

## D3 — Observer and experiment design

**D3.1 Element ids are derived in four tiers (toolkit accessible-id →
parent+role+name → parent+role+child-index → parent+role+quantised position),
not from the spec's position hash alone.** The requirement is stability; the
earlier tiers survive both repaints and moves, and the position hash is kept
only as the last-resort tier.

**D3.2 Roles whose name is a document title (frame, dialog, page tab,
panel, …) are identified structurally, never by name.** Found by the stability
test: typing one character renames the frame from `Untitled 1 - Mousepad` to
`*Untitled 1 - Mousepad`, and because ids chain through the parent this
re-keyed *every* descendant — 200 % churn. This was a real bug the test
caught, and it is exactly the failure mode the brief warns makes everything
downstream noise.

**D3.3 Only elements with `showing` state and a non-empty on-screen bbox enter
the table.** Closed menus expose ~219 menu items over AT-SPI; listing them
would put items on the table that the agent cannot click and would swamp the
delta.

**D3.4 The anchor capture is downscaled to 1280×720 (~1228 image tokens).**
Matches the 1–1.5 k per-capture figure the design doc assumes and is the
resolution class standard computer-use loops use; crops are sent at native
resolution since they are small (a typical button crop is ~16 tokens).

## D4 — Experiment execution

**D4.1 Model calls share this session's provider quota, and the session was
rate-limited for roughly six hours mid-build (06:15–12:20 UTC).** The wall
clock is therefore reported two ways: elapsed since the first command (~8 h)
and time actually spent working (~2.5 h). Budget decisions are taken against
the second, because the suspension was involuntary idle time, not work; both
numbers are stated in the report so the reader can apply whichever they mean.

**D4.2 A run that hits the provider rate limit is recorded as
`terminated=rate_limited` and excluded from the statistics, not scored as a
failure.** The quota is a property of the container, not of the observation
channel, so counting it as a loss would penalise whichever arm happened to be
scheduled when it struck.

**D4.3 The driver aborts if Xvfb or the AT-SPI bus has died, rather than
continuing.** The X server did die during the suspension, and a dead desktop
silently scores every subsequent run as a failure for whichever arm is next —
fabricated data, which is worse than a short run.

**D4.4 Act-time validation re-reads the single named element over AT-SPI
instead of re-walking the whole tree.** A full walk costs ~1.4 s with
LibreOffice open and the loop did two per step; re-reading one element is two
D-Bus round trips, and it is also what the design actually calls for — a cheap
*local* check. It additionally re-points the click if the element moved while
the model was deciding.

**D4.5 The suite run is 14 of the 16 tasks.** `calc_count_eng` and
`cross_inventory_note` were dropped because each LibreOffice run costs ~2–3
minutes and the pair would have added ~40 minutes without adding a coverage
class: every class the brief requires (files, text/format, spreadsheet,
browser form, cross-application, non-textual) is still covered by the
remaining 14. Both tasks and their verifiers remain in `tasks/suite.py`.

**D4.6 Repetitions are 3, not 5.** The brief permits dropping to 3 under
budget pressure and forbids going lower; 5 reps × 3 arms × 14 tasks would not
fit the remaining wall clock after the six-hour suspension. This is stated in
the report and is the main reason several comparisons come back as "no
difference detectable at this N".

**D4.7 Arm D was not run.** It is optional in the brief and the budget did not
stretch to a fourth arm; the code path (`arms.channels.ArmD`) is implemented
and exercised, but no D data exists, so the "where does the advantage come
from" question is answered only partially. Said plainly in the report.

**D4.8 A changed screen region with no tree element behind it is not detected.**
Arm C's forced-crop rule covers the two cases that do fire (visual roles, and
a failed bbox-honesty check) but not the third; implementing XDamage-style
uncovered-region detection was cut for time. Recorded as a limitation, and it
biases *against* C only where a task's information lives in an unexposed
region.

**D4.9 Arm A was reimplemented mid-experiment to *replace* its screenshot each
step, and the 14 runs made under the first version were discarded (archived in
`results/raw/discarded_armA_v1.jsonl`, excluded from all analysis).** The first
version appended each new screenshot to one append-only conversation, so the
baseline accumulated every screenshot it had ever seen and enjoyed full prefix
caching. The brief specifies the opposite — "en A, la captura se reemplaza cada
paso, como hace el bucle estándar; no lo 'arregles'" — and the difference is
not cosmetic: under the corrected version the baseline records
`cache_read = 0` on every run, because rebuilding the transcript to drop the
previous image invalidates the prefix. That destroyed cache is the mechanism
the whole comparison is about, so measuring it wrongly would have answered the
wrong question. Arms B and C were unaffected and their completed runs were
kept.

## D5 — Rigour work done with the remaining budget

The brief says surplus budget should go to measurement rigour, not scope. The
main sweep left ~$33 and several hours, and two gaps in the report were worth
more than any new feature.

**D5.1 Arm D was run after all (48 runs, $6.59), reversing D4.7.** With budget
left it was the only way to answer "where does the advantage come from". It
changed the answer materially: the table alone is *not* the mechanism — arm D
matches the baseline's success rate at 3.0× arm B's cost per completed task,
so the deltas, not the table, supply the economics.

**D5.2 Two new tasks (`vdelta_rows`, `vdelta_bars`) were added because the
original three non-textual tasks did not test what they were built to test.**
All three were answerable from the anchor screenshot alone, so arm B emitted
zero crops on them and B/C were identical by construction. The new pair puts
the decisive fact in an element that appears *during* the task and whose
meaning is carried only by appearance (a red row background; a bar's pixel
width). Verified before spending: after the triggering click, arm B's rule
emits 6 crops and arm C's emits 0. Result: B 6/6, C 0/6.

**D5.3 The new tasks give their rows explicit ARIA `list`/`listitem` roles.**
The first version used plain `<div>`s, which Chromium does not expose over
AT-SPI at all, so *neither* tool arm saw the rows and the tasks tested nothing.
That is the unimplemented uncovered-region case (D4.8) rather than the B-vs-C
question, so the tasks were changed to isolate the intended variable. The
limitation it exposed is stated in the report rather than papered over.

**D5.4 The equal-budget comparison is reported three ways — raw tokens, fresh
tokens, and money — because the winner changes with the denominator.** Raw
totals charge the append-only arms full price for tokens served from cache,
which reverses the conclusion. Reporting only one of the three would have
amounted to choosing the result.

**D5.5 Both universally-failing tasks (`calc_total`, `cross_report_summary`)
are retained.** They discriminate nothing and depress every arm equally, but
dropping tasks after seeing which ones failed is how results get manufactured.

## D6 — Corrections made after the reports were first published

**D6.1 `calc_total`'s verifier was wrong, and the 11 runs it mis-scored are
corrected at analysis time rather than by editing the raw data.** The verifier
searched the saved CSV for the string `48.5`. The total the task asks for is
the price column, 1.5 + 3.25 + 7.0 = **11.75**, so the check could not be
satisfied by a correct answer — it was unsatisfiable, not strict. Eleven of the
twelve runs wrote `,,11.75` into the CSV and saved it exactly as instructed and
were all recorded as failures; the twelfth (arm D, seed 3293) never created the
file and is a genuine failure. The first version of REPORT.md read the 0/12 as
LibreOffice's Save-As dialog defeating every arm, which is the opposite of what
the runs did.

Three things follow, in order of how much they matter:

* **The raw JSONL is not edited.** It is the evidence, and a results file that
  can be rewritten when a number is inconvenient is worth nothing. The fix is
  `analysis/rescore.py`, which recovers the bytes each agent produced — the
  broken verifier embedded them verbatim in its own failure message — and puts
  them through the corrected rule. `aggregate.py --no-rescore` reproduces the
  original, wrong figures exactly, and RESULTS.md states the correction and its
  per-arm counts in its own section.
* **The rule lives in one place.** `tasks.suite.calc_total_ok` is called both
  by the live verifier and by the re-scoring pass, so the two cannot drift. A
  run is re-scored only where the recovered payload is provably complete; the
  old message truncated at 120 characters, and anything at that limit is left
  as recorded and reported as indeterminate rather than resolved by guesswork.
* **No comparison changes direction.** The bug hit A +3, B +3, C +3, D +2, so
  it depressed every arm in proportion. Absolute success rates rise by 4–6
  points (A 0.833→0.896, B 0.812→0.875, C 0.708→0.771, D 0.833→0.875), the
  equal-budget tables shift with them, and every conclusion in REPORT.md
  survives unchanged.

**D6.2 The verifiers were not themselves verified; `tests/test_verifiers.py`
now does it, with positive and negative controls.** This bug was found by
reading the code, not by anything in the repository. `tests/test_id_stability.py`
guarded the observer, but nothing guarded the component that decides what counts
as success — the one whose silent failure looks exactly like a difficult task.

Each verifier is now exercised twice against a temporary workspace, no desktop
required: the correct end state is written to disk byte for byte and the
verifier must accept it (this is what catches an unsatisfiable check), and the
untouched starting workspace must be rejected (this is what catches a check
that passes anything). Confirmed against the original rule: the positive
control fails on it, so the test would have caught D6.1 on the first day.

Twelve of the eighteen verifiers are covered. The six browser tasks read live
page state over CDP and need a running Chromium, so they are reported as
uncovered rather than stubbed — a fake browser would only test the fake. That
gap is real: `vdelta_rows` and `vdelta_bars` carry the sharpest result in the
experiment and their verifiers have no control behind them.
