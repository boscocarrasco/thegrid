# PREDICTIONS — round 2

**Written before any round-2 code was implemented and before any round-2 run
was executed. Committed in that state. Not edited afterwards.**

Commit discipline: this file is committed on its own, ahead of every round-2
source change. If a later commit touches it, that commit is a mistake and
`git log --follow PREDICTIONS.md` will show it. The only edits permitted after
the first commit are typographical, and none were made.

Why this exists at all: round 1 built two tasks (`vdelta_rows`, `vdelta_bars`)
*after* seeing that the three visual tasks failed to discriminate B from C.
That was declared honestly in `REPORT.md` §4, but declaring it afterwards does
not remove the doubt — a reader cannot tell how much of the 8/8-vs-1/8 result
is discovery and how much is construction. Registering the design first is the
only thing that does remove it.

---

## 0. What round 1 left on the table

Two facts from `RESULTS.md` and `REPORT.md` motivate everything below. Both
are properties of the existing data, not predictions.

**Fact 1 — the tool arms spend more steps than the baseline, and it is
concentrated.** Excluding the two tasks that fail on every arm, arm A averages
6.5 steps and arm B 8.4 — about 28 % more. Because `model_calls == steps` in
this harness, that is the design document's primary metric moving the wrong
way. Per task (`RESULTS.md` §7):

| Task | A steps | B steps | A succ | B succ |
|---|---|---|---|---|
| `text_replace` | 4.0 | 10.0 | 3/3 | 3/3 |
| `calc_add_row` | 9.0 | 16.0 | 3/3 | 1/3 |
| `files_rename` | 6.0 | 16.0 | 3/3 | 2/3 |

Three different applications, one pattern: menus and modal dialogs. Walking a
flat list of ids is worse than looking at a picture of a menu.

**Fact 2 — the headline equal-budget result rests on a favourable subset.**
The enforced sweep (`REPORT.md` §2.4d) used 9 of the then-16 tasks. Recomputing
fresh tokens from the main run: within those 9, arm B exceeds the 8,000-token
ceiling in 1/29 runs; within the 7 that were excluded, in 15/21. "B was stopped
by the budget in 0/27 runs" is therefore a property of the subset, not of the
arm. Round 2 re-runs the sweep on the whole suite.

---

## 1. Arms under test

| Arm | What it is | Role |
|---|---|---|
| **A** | Baseline. Stateless rebuild, one screenshot per step, xy addressing. The corrected implementation, not the discarded `discarded_armA_v1`. | reference |
| **B** | The tool exactly as it stands in the repo at round-1 close (commit `4faa553`). Table once + verb deltas + verb-priority crops, id addressing. | **control** |
| **B+** | B + blocks + reachability marking + keyboard shortcuts + geometry-based duplicate merge. | treatment |
| **C** | Text-first channel as it stands: deltas in text, crops only for visual roles or a failed `verify_bbox`. | control for exp. 2 |
| **C+** | C + everything in B+ + **ambiguity-forces-crop**. | treatment for exp. 2 |

B is the control, not A. The question round 2 asks is whether the enrichments
fix a defect the tool has, so the comparison that matters is tool-vs-tool.
A is carried throughout as the external reference the step gap is measured
against.

**Anything that is not the enrichment is held identical across arms**: same
model (`sonnet` via the `claude` CLI), same system prompt except for the
addressing rules, same debounce, same step limits, same workspace reset, same
verifiers, same seeds, same interleaving.

Temperature cannot be fixed — this runs on a subscription through the `claude`
CLI, there is no API key and no `temperature` parameter to set. That does not
bias any comparison, because decoding settings are identical across arms by
construction; it only widens intervals. It is compensated for in §7.

---

## 2. The new tasks, and why they exist

**These four tasks were designed specifically to probe the defect described in
Fact 1. That is the whole reason they exist.** Saying so here is what makes it
legitimate; discovering it in the results afterwards would not be. They are
menu- and dialog-heavy by construction, and if the enrichment helps anywhere it
should help here.

A reader is entitled to discount them for exactly that reason. The control
group in §3 exists so that the discount has somewhere to land: if B+ wins only
on the tasks built to make it win, the honest conclusion is narrow.

| id | app | shape | constraint verified |
|---|---|---|---|
| `menu_replace_all` | mousepad | `Search ▸ Find and Replace…` → modal dialog, two text fields, one toggle, `Replace All`, close, save | every `draft` → `final`; nothing else changed; file saved |
| `menu_save_as_subdir` | mousepad | `File ▸ Save As…` → GTK file chooser → navigate into `archive/` → type name → Save | file exists at the nested path with the right bytes; original still present and unchanged |
| `menu_calc_insert_column` | soffice | `Sheet ▸ Insert Columns ▸ Columns Before` (three levels) → type header → `File ▸ Save As…` → format dropdown → "Use Text CSV Format!" confirmation dialog | CSV has the new column in the right position with the right header; existing columns intact |
| `menu_files_new_folder` | pcmanfm | `File ▸ Create New ▸ Folder` → naming dialog → then `Edit ▸ Cut` / enter folder / `Edit ▸ Paste` | folder exists; file inside it; file no longer at the old path |

Each is a three-to-five level navigation with at least one modal dialog. Each
is verified from the filesystem, never from the screen. Each verifier gets the
positive and negative control described in §6.

**No existing task is retired.** Not `cross_report_summary`, which fails on
every arm; not the three visual tasks, which discriminate nothing; not
`files_rename`, which the baseline wins outright. Retiring tasks after seeing
results is how results are manufactured. The suite goes from 22 to 26 (22
short + 4 long, becoming 26 short + 6 long — see §5).

---

## 3. Groups, fixed now

**Menu/dialog group (7)** — where the defect lives:
`text_replace`, `calc_add_row`, `files_rename`, `menu_replace_all`,
`menu_save_as_subdir`, `menu_calc_insert_column`, `menu_files_new_folder`

The first three are round-1 tasks, chosen because round 1 already showed the
defect on them. The last four are the new ones.

**Control group (15)** — everything else in the short suite:
`files_new_note`, `files_save_as`, `text_append`, `text_delete_line`,
`text_uppercase`, `calc_total`, `calc_count_eng`, `web_form`, `visual_chart`,
`visual_shapes`, `visual_badge`, `cross_report_summary`,
`cross_inventory_note`, `vdelta_rows`, `vdelta_bars`

### 3.1 The reduction rule, if cost forces one

Wall-clock will probably not cover every cell (§8 is explicit about this). If a
group has to be cut, tasks are chosen by the following rule, which uses only
task identity and never any measured outcome:

> Assign each task to an application group by the **first** entry of its `apps`
> tuple. Order the groups `mousepad, pcmanfm, soffice, chromium`. Within each
> group order tasks alphabetically by id. Then take tasks round-robin across
> the groups, skipping groups that are exhausted, until the quota is filled.

Applied to the 26-task short suite this produces one fixed ordering, written
out here so there is no room to choose later:

1. `files_new_note` · 2. `cross_report_summary` · 3. `calc_add_row` ·
4. `vdelta_bars` · 5. `files_save_as` · 6. `files_rename` ·
7. `calc_count_eng` · 8. `vdelta_rows` · 9. `menu_replace_all` ·
10. `menu_files_new_folder` · 11. `calc_total` · 12. `visual_badge` ·
13. `menu_save_as_subdir` · 14. `cross_inventory_note` · 15. `visual_chart` ·
16. `text_append` · 17. `menu_calc_insert_column` · 18. `visual_shapes` ·
19. `text_delete_line` · 20. `web_form` · 21. `text_replace` ·
22. `text_uppercase`

Concrete consequences, fixed now:

- **Reduced control group (quota 8)** = the first 8 entries of that ordering
  that belong to the control group:
  `files_new_note`, `cross_report_summary`, `vdelta_bars`, `files_save_as`,
  `calc_count_eng`, `vdelta_rows`, `calc_total`, `visual_badge`.
- **Budget-sweep subset (quota 10)** = the first 10 entries outright:
  `files_new_note`, `cross_report_summary`, `calc_add_row`, `vdelta_bars`,
  `files_save_as`, `files_rename`, `calc_count_eng`, `vdelta_rows`,
  `menu_replace_all`, `menu_files_new_folder`.

---

## 4. Experiment 1 — does enrichment close the step gap?

**Design.** Arms A, B, B+ × menu/dialog group (7) × 5 repetitions = 105 runs,
interleaved. Then arms A, B, B+ × control group (15) × 5 = 225 runs.

**Primary endpoint.** Paired difference in steps, B+ − B, on the menu/dialog
group, paired within `(task, rep)`.

### P1.1 — the principal prediction

B+ reduces steps against B on the menu/dialog group.

- **Point prediction:** mean paired difference **≤ −2.0 steps**, and on the
  three round-1 defect tasks B+ lands between **7 and 11** mean steps against
  B's 14.0, i.e. closing 40–70 % of the gap to A's 6.3.
- **Falsified if** the 95 % bootstrap interval on the mean paired difference
  includes 0 or lies above it, **or** if B+ averages ≥ 13.0 steps on the three
  defect tasks.

I expect keyboard shortcuts to do most of this and reachability to do most of
the rest. That expectation is itself tested in §4.4.

### P1.2 — no harm elsewhere

- **Prediction:** on the control group the 95 % interval on the mean paired
  step difference B+ − B **includes 0**, and B+ success is not below B's with a
  non-overlapping interval.
- **Falsified if** B+ is worse on the control group with an interval excluding
  0. That outcome would mean the enrichment buys menu performance with general
  performance, which is a different and worse result than "it does not work".

### P1.3 — the gap to baseline

- **Prediction:** B+ does **not** fully reach A on the menu/dialog group. I
  expect A to remain nominally ahead on steps, with overlapping intervals.
- **Falsified if** B+ beats A on steps with a non-overlapping interval. That
  would be a stronger result than predicted and should be reported as such.

### P1.4 — where the enrichment does nothing

- **Prediction:** on `visual_chart`, `visual_shapes`, `visual_badge`,
  `web_form` — all solved in 4–8 steps from the anchor alone in round 1 — B+
  and B are indistinguishable. The enrichment has nothing to act on there.
- This is a *negative* prediction and a sanity check. If B+ differs from B on
  these tasks, something other than the enrichment changed, and the experiment
  is broken rather than informative.

### 4.4 Ablation — conditional, and only if P1.1 holds

If and only if P1.1 is confirmed, run three ablations on the **menu/dialog
group only**, N = 5: B+ without blocks, B+ without reachability, B+ without
shortcuts (105 runs).

- **Prediction:** removing shortcuts costs the most — at least half the
  measured B+ − B improvement. Removing reachability costs the second most.
  Removing blocks costs the least and may cost nothing detectable.
- **Falsified if** the ordering is different, or if no single ablation accounts
  for ≥ 25 % of the improvement (which would mean the three interact and none
  is separately responsible — a legitimate finding, but not the predicted one).

**If P1.1 is falsified, no ablation is run.** Ablating a treatment that did not
work is a way to find a subgroup where it did.

---

## 5. Experiment 2 — the cleanest falsifiable prediction

Round 1: on `vdelta_rows` and `vdelta_bars` the text-only channel C scored
**1/8** and took ~11.5 steps, against B's 8/8 in 5.0. The diagnosis in
`REPORT.md` §2.5 is that C received `+ added list item "job-delta"` six times
and could not tell the six apart, so it clicked at random.

The ambiguity rule is supposed to fix exactly this, and to fix it **without
looking at a single pixel to make the decision**. The rule is purely
structural: several elements share role and name, their rectangles are
**disjoint**, therefore the tree has said everything it knows and it was not
enough, therefore crop each of them.

**Design.** Arms C, C+ × {`vdelta_rows`, `vdelta_bars`} × 5 = 20 runs. B's
numbers on those tasks come from experiment 1's control group, same N.

### P2.1 — the outcome prediction

- **Prediction:** C+ scores **≥ 6/10** across the two tasks (against C's
  1/8 ≈ 0.125) and takes **≤ 7.0** steps (against C's ~11.5), approaching B's
  5.0 and 8/8.
- **Falsified if** C+ scores ≤ 3/10, or if its success interval overlaps C's
  while excluding B's.

### P2.2 — the mechanism check, which must hold either way

Independently of the outcome, the logs must show that the crops were requested
*by the ambiguity rule* and not by the pre-existing visual-role rule. The
runner will record `crops_ambiguity` separately from `crops_visual`.

- **Prediction:** on these two tasks, ≥ 1 ambiguous group of ≥ 4 elements
  sharing role and name with pairwise-disjoint rectangles is detected, and
  `crops_ambiguity > 0` in every C+ run.
- **Falsified if** `crops_ambiguity == 0` while success nonetheless rises. In
  that case the improvement came from somewhere else and the prediction about
  the mechanism is wrong even if the prediction about the outcome is right.
  **That distinction must be reported.**

This is the cleanest prediction of the round precisely because it can fail in
two independent ways, and because a plausible failure mode exists: the
ARIA `listitem` rows in these pages may not in fact share an identical `name`
in the AT-SPI tree, in which case the rule never fires and P2.1 fails for a
reason that has nothing to do with whether the idea is sound.

---

## 6. Experiment 3 — the budget sweep, on the whole suite

**What changes from round 1:** the full suite instead of a 9-task subset;
three ceilings instead of one; and the reported quantity is *where the curves
cross*, not who wins.

**Budgeting stays on fresh tokens** = `tokens_in + tokens_cache_create +
tokens_out`. The reason, restated because it is the single decision that most
moves the conclusion: a cache read is neither work the provider redid nor a
cost the user pays at full rate. Charging it would bill the append-only arms
for the very thing that makes them cheap, and would let anyone pick the winner
by picking the denominator. Round 1 showed this directly — budgeting on raw
totals makes A win at every ceiling, budgeting on fresh tokens makes B win at
every ceiling, on the same runs (`REPORT.md` §2.4a vs §2.4b).

**Design.** Arms A, B+ × 3 ceilings (8,000 / 15,000 / 30,000 fresh tokens) ×
budget-sweep subset (10 tasks, fixed in §3.1) × 5 reps = 300 runs. Enforced
during execution, step limits doubled so an arm with budget to spare can
convert it into steps. Ceilings are run in the order **8,000 → 30,000 →
15,000**, endpoints first, so that a partial run still brackets the crossing.

Why 10 tasks and not 26: the honest reason is wall-clock (§8). The subset was
fixed by the §3.1 rule before any round-2 run, and the rule reads only task
ids and application names.

### P3.1 — there is a crossing, and it is in range

- **Prediction:** at **8,000** B+ beats A by **≥ 10 points**; at **15,000** the
  intervals **overlap**; at **30,000** A is **nominally ahead**. The crossing
  lies between 8,000 and 30,000.
- **Falsified if** A is ahead at 8,000, or if B+ is ahead at 30,000 with a
  non-overlapping interval (no crossing in range — a stronger result than
  predicted), or if the ordering is non-monotonic.

### P3.2 — the round-1 headline does not survive the full suite

- **Prediction:** B+ will be stopped by the 8,000 ceiling in **more than 1/29**
  of runs — specifically I expect **20–50 %** of B+ runs at 8,000 to be cut,
  against the "0/27" round 1 reported on its subset.
- **Falsified if** B+ is cut in < 10 % of runs at 8,000, which would mean the
  subset effect identified in Fact 2 was smaller than the recomputation
  suggested.

I expect this prediction to hold, and I expect it to make the round-1 headline
look worse. Registering it now is the point.

---

## 7. Experiment 4 — long tasks, the image window and the task object

**Two new long tasks**, each with constraints that are explicit in the
statement and separately checkable, so that "failed the task" and "forgot a
constraint" can be told apart:

| id | statement constraints, checked one by one |
|---|---|
| `long_march_export` | c1 output is CSV · c2 contains exactly the March rows · c3 the original spreadsheet is byte-identical afterwards · c4 output is at the named path |
| `long_notes_digest` | c1 one line per note · c2 `name: first-line` format · c3 sorted alphabetically by name · c4 all three originals still present and unchanged |

The four existing long tasks keep their verifiers but gain a per-constraint
decomposition, so every long run reports a vector of constraint outcomes
alongside its pass/fail.

**Design.** Three configurations of B+, plus A as reference, on 4 long tasks
(the 2 new ones plus `long_ledger_edits` and `long_region_transfer`, chosen
because they have the most separable constraints), N = 5:

| config | image window | task object |
|---|---|---|
| B+ full | 2 | on |
| B+ wide-window | 4 | on |
| B+ no-task-object | 2 | off |

### P4.1 — the task object reduces constraint loss

- **Prediction:** constraint violation rate (constraints failed ÷ constraints
  checked, counted **only on runs that completed the main action**) falls by
  **at least half** with the task object on, and the 95 % interval on the
  paired difference excludes 0.
- **Falsified if** the interval includes 0. Given N = 5 × 4 tasks = 20 pairs
  and violation rates likely in the 10–30 % range, this is the prediction in
  this document most likely to fail for lack of power rather than for lack of
  effect, and if it does fail that is how it must be reported.

### P4.2 — the two-image window is free

- **Prediction:** peak live image tokens fall by **≥ 25 %** going from a
  4-image to a 2-image window, with **no detectable change in success**.
- **Falsified if** success drops with an interval excluding 0. The design
  document claims the compressed version performs *better*; I do not predict
  better, only not worse, and at this N I do not expect to be able to
  distinguish the two.

---

## 8. Experiment 5 — what the enrichment costs

Any new cost the enrichment introduces is measured and reported, including
when it is unflattering. The observer will time block detection, reachability
comparison and duplicate search separately and record them per step.

### P5.1

- **Prediction:** the four enrichments together add **≤ 150 ms** to per-step
  observation time and **≤ 15 %** to observation tokens, against B.
- **Falsified if** either exceeds **400 ms** or **40 %**.

Reachability needs a comparison against the previous tree state, which the
observer already holds for the delta, so I expect it to be nearly free. Blocks
need a container walk over a tree that has already been walked. The duplicate
merge is the one I am least sure about: it is pairwise over same-`(role, name)`
groups, and a spreadsheet with a thousand identically-named cells is the bad
case.

---

## 9. Negative controls and pre-run checks

These are not predictions about the world; they are conditions that must hold
or the experiment is invalid, and they are checked **before** the measurement
runs, not after.

1. **Block stability.** A test analogous to `tests/test_id_stability.py`: block
   identities must be stable at 0 % churn across an idle step, an `xrefresh`
   repaint, a content change and a window move. If blocks churn, every delta
   that mentions a block is noise.
2. **Verifier controls for all 26 short tasks**, including the 6 that read page
   state over CDP, which round 1 left uncovered. Each verifier must accept a
   hand-built correct end state and reject an untouched workspace. An
   unsatisfiable verifier reads exactly like a hard task — that already
   happened once, to `calc_total`, and cost 11 correct runs.
3. **Checkpoint before spending budget.** Two menu tasks end to end on A, B and
   B+ before any measurement run. What is being checked is that the arms are
   still comparable and that nothing besides the enrichment moved.
4. **Round-1 raw data is not touched.** New files only, under `results/raw2/`.

---

## 10. Analysis plan, fixed now

- **N ≥ 5 per cell.** At N = 3 nothing below about a 15-point difference is
  detectable, and every aggregate conclusion in round 1 sits in that regime.
- **Paired analysis is primary.** Each arm runs every task at every repetition
  index, and comparisons are made on the **within-pair difference**
  `(task, rep)`, not on means between arms. Most of the variance in this
  harness comes from the task; pairing removes it. Unpaired means are reported
  as secondary.
- **Bootstrap intervals**, 5,000 resamples, on the paired differences. **When
  intervals overlap the wording is "no detectable difference at this N", never
  "they are equal."**
- **Variance is reported, not just the mean.** For every cell, the standard
  deviation across repetitions of the same `(arm, task)` is reported. If it is
  large, that is a statement about how underpowered the experiment is and it
  goes in the report as such.
- **Rate-limited runs are never silently dropped and never scored as task
  failures.** A run interrupted by a usage or rate limit is retried with
  exponential backoff, and the wait and its duration are written into that
  run's record. Runs lost to rate limits and not flagged would bias every
  table toward whichever arm happened to run earlier.
- **`cost_usd` is an estimate, always labelled as one.** This runs on a
  subscription: there is no bill to read. `cost_usd` is computed from token
  counts and the published rate. It is useful for comparing arms with each
  other, which is all it is used for. It is not observed spend and must not be
  read as such.

---

## 11. Expected budget, and what will probably not get run

Budget: `MAX_WALL_CLOCK_HOURS` and `MAX_ESTIMATED_SPEND_USD`, defaulting to
**10 hours** and **80 USD estimated**. Stop at 85 % of either.

Measured round-1 throughput: ~34–55 s of model time per short run, ~55–66 s per
long run, plus workspace reset. Call it 70 s per short run and 100 s per long
run end to end.

| Tier | What | Runs | Est. wall |
|---|---|---|---|
| T1 | Exp 1 core — A, B, B+ × menu group (7) × 5 | 105 | 2.0 h |
| T2 | Exp 2 — C, C+ × vdelta (2) × 5 | 20 | 0.4 h |
| T3 | Exp 1 control — A, B, B+ × control group (15) × 5 | 225 | 4.4 h |
| T4 | Exp 4 — 3 configs + A × long (4) × 5 | 80 | 2.2 h |
| T5 | Exp 3 — A, B+ × 3 ceilings × subset (10) × 5 | 300 | 5.8 h |
| T6 | Ablation, conditional on P1.1 | 105 | 2.0 h |
| | **total** | **835** | **16.8 h** |

**That is more than the budget allows, and I am saying so before starting
rather than discovering it at hour nine.** Tiers run strictly in the order
above. T3 falls back to the reduced 8-task control group (120 runs, 2.3 h) if
T1+T2 have consumed more than 3 hours. T5's ceilings run endpoints-first so a
partial sweep still brackets the crossing.

The priority order is set by what each tier can falsify. T1 and T2 carry the
two predictions that can most cleanly fail, so they run first even though T5
answers a question the report is explicitly required to address. If T5 does not
run, `REPORT2.md` will say that the budget question was not measured this
round, and will not substitute a post-hoc reclassification for it — round 1
already showed that post-hoc and enforced budgets give different answers.

**Whatever does not run will be named as not run. No cell in any table will be
filled with a plausible number.**

---

## 12. Summary of falsifiable claims

| # | Claim | Falsified by |
|---|---|---|
| P1.1 | B+ cuts ≥ 2.0 steps vs B on menu/dialog tasks | paired interval includes 0, or B+ ≥ 13.0 steps on the 3 defect tasks |
| P1.2 | B+ does not hurt the control group | B+ worse with interval excluding 0 |
| P1.3 | B+ does not fully catch A on menus | B+ beats A with non-overlapping interval |
| P1.4 | B+ = B on anchor-solvable visual tasks | any detectable difference |
| P1.5 | Shortcuts > reachability > blocks in ablation | different ordering, or no single ablation ≥ 25 % |
| P2.1 | C+ ≥ 6/10 on vdelta, ≤ 7.0 steps | C+ ≤ 3/10, or overlaps C and not B |
| P2.2 | The ambiguity rule is what fires | `crops_ambiguity == 0` while success rises |
| P3.1 | Crossing between 8k and 30k fresh tokens | A ahead at 8k, or B+ ahead at 30k with non-overlapping interval |
| P3.2 | B+ cut by the 8k ceiling in 20–50 % of runs | < 10 % |
| P4.1 | Task object halves constraint loss | paired interval includes 0 |
| P4.2 | 2-image window costs ≥ 25 % fewer peak image tokens, free | success drops with interval excluding 0 |
| P5.1 | Enrichment costs ≤ 150 ms/step and ≤ 15 % tokens | > 400 ms or > 40 % |

Twelve claims. I expect P1.1, P1.4, P2.2, P3.1, P3.2 and P5.1 to hold; P1.2 and
P1.3 to hold trivially; P2.1 to be the interesting one; P1.5 and P4.1 to be the
most likely to fail, P4.1 for lack of power and P1.5 because the three
enrichments probably interact more than this framing admits.
