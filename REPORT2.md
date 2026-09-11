# REPORT2 — round 2

What was measured, what came out, which predictions failed, what could not be
measured at all, and what threatens the validity of the rest.

Every number here comes from `RESULTS2.md`, which `analysis/aggregate2.py`
generates from `results/raw2/*.jsonl`. Nothing in either file is typed by hand.
Round 1's raw data was not touched.

**All dollar figures are estimates.** This runs on a subscription through the
`claude` CLI; there is no bill to read. `cost_usd` is computed from token counts
and the published rate. It is useful for comparing arms with each other, which
is all it is used for, and it is not observed spend.

---

## 0. What ran, and what did not

| Tier | What | Planned | Ran |
|---|---|---|---|
| T1 | Exp 1 core — A, B, B+ × menu/dialog group (7) × 5 | 105 | **105** |
| T2 | Exp 2 — C, C+ × vdelta (2) × 5 | 20 | **20** (2 re-run after a rate limit) |
| T3 | Exp 1 control — A, B, B+ × control group | 225 | **110** of the reduced 8-task version (120) |
| T4 | Exp 4 — image window and task object on long tasks | 80 | **0** |
| T5 | Exp 3 — the budget sweep, enforced, three ceilings | 300 | **0** |
| T6 | Ablation, conditional on P1.1 | 105 | **0** |

**235 usable runs, 2 excluded, estimated cost $25.44.**

The reason T4–T6 did not run is a **provider suspension that cost about three
hours of wall clock**, landing in the middle of T2. The backoff waited it out
and wrote every wait into the affected runs' records — **168.5 minutes of
logged backoff across three runs**, one of which sat at the full one-hour
per-run ceiling. Two runs exhausted that ceiling and are marked `rate_limited`,
which excludes them from every statistic rather than scoring them as task
failures; both were re-run afterwards and their replacements are in the data.
Nothing was learned during the suspension and a third of the budget went with
it.

That is also what triggered the **pre-registered reduction** of T3.
`PREDICTIONS.md` §11 said the control group falls back to eight named tasks if
T1 and T2 together take more than three hours. They took five. The eight tasks
were fixed before any round-2 run existed, by a rule that reads only task ids
and application names, and they are written out entry by entry in §3.1 of that
document. T3 then hit its own wall-clock deadline at 110 of 120 runs, so the
fifth repetition is partial on some tasks; per-cell counts are in `RESULTS2.md`.

**Nothing below substitutes a number for an experiment that did not run.** In
particular there is no post-hoc reclassification standing in for the budget
sweep — round 1 established that post-hoc and enforced budgets give different
answers, so a post-hoc table would be a different result wearing the same name.

---

## 1. The five questions this report was required to answer

### Does the enrichment close the step gap against the baseline, on which tasks and by how much?

**Partly, and less than predicted.**

On the seven menu/dialog tasks, paired within `(task, rep)` across 35 pairs:

| | steps | success |
|---|---|---|
| A (baseline) | 10.77 | 0.800 |
| B (tool, as it stood) | 13.20 | 0.743 |
| **B+ (tool, enriched)** | **11.60** | **0.829** |

- **B against A** — `+2.43 steps [+0.66, +4.11]`. The defect round 1 measured
  reproduces: the unenriched tool really does spend more steps than a
  screenshot on menu work, and the interval excludes zero.
- **B+ against B** — `−1.60 steps [−2.71, −0.57]`. The enrichment moves it, and
  the interval excludes zero.
- **B+ against A** — `+0.83 steps [−1.34, +2.83]`. No detectable difference at
  this N. The gap that was statistically present is no longer detectable.

So the enrichment removes about two thirds of the measured gap. It does not
remove it. And where it acts is uneven — the whole effect is in three tasks:

| task | A | B | **B+** |
|---|---|---|---|
| `menu_files_new_folder` | 2/5 in 19.2 | 2/5 in 17.8 | **5/5 in 11.8** |
| `menu_save_as_subdir` | 1/5 in 14.2 | 5/5 in 9.0 | **5/5 in 7.6** |
| `files_rename` | 5/5 in 6.0 | 3/5 in 15.0 | **4/5 in 13.2** |
| `text_replace` | 5/5 in 4.0 | 5/5 in 11.0 | 5/5 in 9.0 |
| `menu_replace_all` | 5/5 in 10.4 | 5/5 in 10.0 | 5/5 in 9.0 |
| `menu_calc_insert_column` | 5/5 in 12.6 | 5/5 in 13.6 | 5/5 in **14.6** |
| `calc_add_row` | 5/5 in 9.0 | 1/5 in 16.0 | **0/5 in 16.0** |

`menu_files_new_folder` is the clearest case in the round: 2/5 → 5/5 with six
fewer steps, and it is the task with the deepest menu descent
(`File ▸ Create New ▸ Folder`, then `Edit ▸ Cut`, then `Edit ▸ Paste` inside
the new folder). That is exactly where a table that lists a closed menu's
accelerators should pay, and it does.

`calc_add_row` is the clearest counter-case: the enrichment makes it *worse*,
0/5 against B's 1/5, both at the 16-step ceiling. Reading the step traces, the
agent is not confused by the table — it navigates the sheet correctly and then
exhausts its steps inside LibreOffice's Save-As dialog, which is the same wall
B hit in round 1. Nothing in blocks, reachability or accelerators addresses
that, and the one extra run that scraped a pass in round 1 did not recur. The
task is retained, and so is `menu_calc_insert_column`, where B+ is nominally
the slowest of the three arms.

### Which of the three enrichments does the work?

**Not measured.** The ablation was T6, conditional on P1.1 holding, and the
budget ran out four tiers earlier. `PREDICTIONS.md` §4.4 predicted the ordering
shortcuts > reachability > blocks; that prediction is neither confirmed nor
refuted, and the arms to test it (`B+nb`, `B+nr`, `B+nk`) are implemented and
in `arms/channels.py` waiting to be run.

The one piece of evidence bearing on it is indirect and should be read as
suggestive only: the gain is concentrated in the two deepest menu descents,
which is the shape the shortcut hypothesis predicts and not the shape the
blocks hypothesis predicts. That is not an ablation.

### Does the ambiguity rule solve the vdelta case without deciding by pixels?

**The case is solved. The rule that solves it is not the one the design
document specifies, and that distinction is the most useful finding of the
round.**

| | success | steps | est. $ |
|---|---|---|---|
| C (text-first) | 7/10 | 12.20 | 0.1802 |
| **C+ (text-first + ambiguity)** | **10/10** | **5.00** | **0.0197** |
| B (crop-priority, for reference) | 8/9 | 5.00 | 0.0150 |

Paired over 10 pairs: `−7.20 steps [−8.10, −6.30]`, and a nine-fold drop in
estimated cost. C+ lands exactly on B's step count and matches it on success.
The prediction was "≥ 6/10 and ≤ 7.0 steps, approaching B"; the measurement is
10/10 at 5.00, which is not approaching B but equal to it.

**But the registered mechanism did not fire at all.** §5.2 of the design
document explains round 1's 1/8 result as six list items *sharing a name* —
`+ added list item "job-delta"` received six times. Reading the actual AT-SPI
tree for that page, the six rows are named `job-alpha` … `job-foxtrot`, all
distinct. The same-name rule the document specifies can never fire there. What
the six rows actually share is every attribute the tree exposes *except* the
name, while the task asks about a colour that no attribute reports.

Both rules were implemented and counted separately, which is what makes this
legible rather than a lucky win:

| arm | task | crops forced by ambiguity | by the registered same-name rule | by the peer-set rule |
|---|---|---|---|---|
| C+ | `vdelta_rows` | 30 | **0** | 30 |
| C+ | `vdelta_bars` | 25 | **0** | 25 |

Zero and fifty-five. The outcome prediction holds; the mechanism prediction is
**falsified**, and the improvement belongs entirely to a rule that was written
after reading the tree rather than registered in advance. That is a weaker claim
than pre-registration and is not dressed up as anything else. What can be said
without qualification is that the peer-set rule is still *structural*: it
decides that pixels are needed by comparing role, block, states, text and
geometry, and never by looking at a pixel to make the decision.

The design document's §5.2 should be corrected. Its diagnosis of the benchmark
result it cites is wrong about this benchmark.

### Below what budget does the tool win, with the full suite?

**Not measured.** T5 did not run. Round 1's answer stands unreplicated and, by
its own admission (`PREDICTIONS.md` Fact 2), rests on a nine-task subset in
which arm B exceeded the 8,000-token ceiling in 1 run of 29, against 15 of 21
in the seven tasks the subset excluded.

The infrastructure for it is in place — `scripts/round2.sh t5` runs the three
ceilings endpoints-first, so a partial sweep still brackets the crossing — and
it is the first thing that should run next.

### What does the enrichment cost, in milliseconds and in tokens?

**In time, almost nothing. In tokens, more than predicted.**

| phase | ms per step (B+, 72 runs, 771 steps) |
|---|---|
| geometry duplicate merge | 0.11 |
| blocks | 0.04 |
| ambiguity (both rules) | 0.04 |
| reachability | 0.34 |
| shortcuts | 2.25 |
| **total** | **2.78** |

Against a prediction of ≤ 150 ms and a falsification threshold of 400 ms, 2.78
ms is not close to either. Two implementation choices are responsible:
key bindings and closed-menu contents are cached per `(app, element id)`, so
the 81 ms first read of an application's menu tree is paid once per process,
not per step; and reachability reuses the tree walk the delta already needs.
The merge is the phase I was least sure about — it is pairwise within
same-`(role, name)` groups — and capping groups at 40 members keeps a
spreadsheet's thousands of cells out of it entirely.

Tokens are the other way round:

> Observation tokens, B+ against B, paired over 70 `(task, rep)` pairs:
> **+1,850 [+956, +2,817]** against a B mean of 9,613 — **+19.2 %**.

The prediction was ≤ 15 %, with falsification at 40 %. So the point prediction
is **missed** and the falsification threshold is not reached. Most of the extra
is the closed-menu accelerator summary, which is the same feature the step
saving is attributed to — the enrichment buys steps with tokens, at roughly
1,850 tokens per 1.6 steps saved on the menu group.

Whether that trade is worth taking depends on the budget regime, which is
precisely the question T5 was going to answer and did not.

---

## 2. Every prediction, against what happened

| # | Registered claim | Outcome | Measured |
|---|---|---|---|
| P1.1 | B+ cuts ≥ 2.0 steps vs B on menu/dialog | **partly** | −1.60 [−2.71, −0.57]; direction and separation hold, the magnitude does not |
| P1.1b | B+ lands in 7–11 steps on the three defect tasks (fails at ≥ 13.0) | **missed, not falsified** | 12.73 against B's 14.00 |
| P1.2 | B+ does not hurt the control group | **held** | steps −0.11 [−0.40, +0.11]; success +0.057, overlapping |
| P1.3 | B+ does not fully catch A on menus | **held** | +0.83 [−1.34, +2.83], overlapping |
| P1.4 | B+ = B on anchor-solvable visual tasks | **held** | `visual_badge` 4.0 vs 4.0, `files_save_as` 6.4 vs 6.5, `files_new_note` 10.0 vs 10.0 |
| P1.5 | Ablation ordering shortcuts > reachability > blocks | **not run** | — |
| P2.1 | C+ ≥ 6/10 and ≤ 7.0 steps on vdelta | **held, with room** | 10/10 at 5.00 steps |
| P2.2 | The registered same-name rule is what fires | **falsified** | 0 same-name crops, 55 peer-set crops |
| P3.1 | A crossing between 8k and 30k fresh tokens | **not run** | — |
| P3.2 | B+ cut by the 8k ceiling in 20–50 % of runs | **not run** | — |
| P4.1 | The task object halves constraint loss | **not run** | — |
| P4.2 | The 2-image window costs ≥ 25 % fewer peak image tokens, free | **not run** | — |
| P5.1 | Enrichment ≤ 150 ms/step and ≤ 15 % tokens | **split** | 2.78 ms/step, far inside; +19.2 % tokens, outside the point prediction, inside the falsification threshold |

Six claims tested, six not run. Of the six tested: three held cleanly (P1.2,
P1.3, P1.4), one held beyond its threshold (P2.1), one is half right (P5.1),
one is half right in a way worth stating precisely (P1.1), and one is
**falsified** (P2.2).

### Two things I got wrong in advance, stated as such

**The magnitude of the enrichment's effect.** I predicted ≤ −2.0 steps and got
−1.60; I predicted 7–11 steps on the three defect tasks and got 12.73. I
expected shortcuts to close most of the gap. They closed about two thirds of
the *statistical* gap and much less of the arithmetic one, because the two
tasks where the tool is worst — `calc_add_row` and `files_rename` — fail on a
file-format dialog and a context menu that accelerators do not reach.

**The mechanism behind the vdelta result.** I registered P2.2 saying it was the
most likely prediction to fail for a reason unrelated to whether the idea is
sound, and named the exact failure mode: "the ARIA `listitem` rows in these
pages may not in fact share an identical `name` in the AT-SPI tree, in which
case the rule never fires." That is what happened. Registering it did not make
me right; it made the failure attributable instead of invisible.

### One thing the predictions did not cover, found anyway

On the control group, B+ costs **more money** than B: `+$0.0237 [+0.0112,
+0.0374]` per task, an interval that excludes zero. P1.2 was written about
steps and success and says nothing about cost, so this is not a falsification
of anything — it is a cost the enrichment imposes on tasks it does not help,
which is most of them. It is the same +19 % observation-token overhead seen
from the other side, and it is the strongest argument for making the
closed-menu summary conditional on the task rather than unconditional.

---

## 3. Threats to validity

**The new tasks were built to make the treatment look good, and they did.**
This is declared in `PREDICTIONS.md` §2 and it is not mitigated by declaring
it. Of the three tasks carrying the B+ effect, two are new
(`menu_files_new_folder`, `menu_save_as_subdir`). On the three round-1 tasks in
the menu group — the ones chosen because the defect was already visible on them
— the picture is much weaker: `text_replace` −2.0 steps, `files_rename` −1.8,
and `calc_add_row` 0.0 with worse success. A
reader who discounts the new tasks entirely is left with an effect that is
real but small and does not clear its own registered threshold.

**No ablation.** The claim "the enrichment closes the gap" is supported;
"shortcuts are what close it" is not tested at all. The concentration in deep
menu descents is consistent with it and is not evidence for it.

**N = 5, and the spread is not small.** The variance table in `RESULTS2.md`
reports per-cell standard deviations. Several cells are at 0.0 — the same task
solved the same way five times — but `menu_save_as_subdir` on arm A has
sd 3.6 on a mean of 14.2, and the interval on the principal comparison,
[−2.71, −0.57], is wide enough that the true effect could be a third of the
point estimate or nearly twice it. Where intervals overlap this report says
"no detectable difference at this N" and never "they are equal."

**Temperature is not fixed.** There is no API key and no decoding parameter to
set; the model channel is the `claude` CLI on a subscription. Decoding settings
are identical across arms by construction, so this does not bias any
comparison, but it widens every interval. Pairing within `(task, rep)` is the
compensation, and it is why the paired tables are primary and the unpaired arm
means are secondary.

**Partial fifth repetition in T3.** The control group stopped at its wall-clock
deadline with 110 of 120 runs, so some cells have n = 4. Pairing uses only
matched `(task, rep)` pairs, so this costs power rather than introducing bias,
and per-cell counts are printed.

**`peak_live_images` is not what its name suggests.** It counts full
screenshots plus crops still inside their TTL, so the value of ~21.8 for the
tool arms is dominated by crops. The image-window comparison it was built for
(T4) did not run, so the column is reported but carries no conclusion.

**One arithmetic slip in the frozen predictions.** `PREDICTIONS.md` §2 says the
suite goes "from 22 to 26 (22 short + 4 long, becoming 26 short + 6 long)"; the
true counts are 18 short + 4 long becoming 22 short + 6 long, and §3.1 labels
the 22-item ordering "the 26-task short suite". The ordering itself is written
out entry by entry and has exactly 22 entries, so nothing operative is
ambiguous. It was left uncorrected rather than edit a document whose entire
value is that it is not edited.

---

## 4. What should run next, in order

1. **T5, the budget sweep.** It is the one required question with no answer at
   all, and round 1's headline depends on it. `scripts/round2.sh t5`, ceilings
   endpoints-first.
2. **T6, the ablation.** P1.1 held in direction and separation, which is the
   condition `PREDICTIONS.md` §4.4 set for running it. Without it, "shortcuts
   are what work" remains an untested story about a real effect.
3. **T3 in full**, the fifteen-task control group rather than the pre-registered
   eight, so the no-harm claim rests on the whole suite.
4. **T4**, the image window and the task object. The tasks, the constraint
   decompositions and the per-constraint verifiers are all built and pass their
   controls; only the runs are missing.
5. **Make the closed-menu summary conditional.** It costs +19 % observation
   tokens on every task and pays on a minority of them. Emitting it only for
   applications whose menus the agent has actually opened, or only after the
   first menu click, would keep the win and drop most of the cost.

---

## 5. What round 2 actually established

- The step gap round 1 found is **real and reproduces**: B spends
  `+2.43 [+0.66, +4.11]` more steps than A on menu and dialog work.
- Layer-1 enrichment **reduces it by `−1.60 [−2.71, −0.57]` steps**, enough that
  B+ and A are no longer distinguishable, and does so **without harming the
  control group** on steps or success.
- It costs **2.78 ms per step** and **+19 % observation tokens**, and the token
  side is a real cost on tasks it does not help.
- The ambiguity rule **closes the text-only channel's worst failure completely**
  — 7/10 and 12.2 steps become 10/10 and 5.0, matching the crop-priority arm at
  a ninth of the estimated cost — **through a rule the design document does not
  contain**, while the rule it does contain fired zero times.
- Four of the round's twelve registered claims are answered, two are answered
  in part, one is falsified outright, and **six were not run and are reported as
  not run**.
