# REPORT2 — round 2

What was measured, what came out, which predictions failed, and what threatens
the validity of the rest.

Every number here comes from `RESULTS2.md`, which `analysis/aggregate2.py`
generates from `results/raw2/*.jsonl`. Nothing in either file is typed by hand.
Round 1's raw data was not touched.

**All dollar figures are estimates.** This runs on a subscription through the
`claude` CLI; there is no bill to read. `cost_usd` is computed from token counts
and the published rate. It is useful for comparing arms with each other, which
is all it is used for, and it is not observed spend.

---

## 0. What ran

| Tier | What | Planned | Ran |
|---|---|---|---|
| T1 | Exp 1 core — A, B, B+ × menu/dialog group (7) × 5 | 105 | **105** |
| T2 | Exp 2 — C, C+ × vdelta (2) × 5 | 20 | **20** |
| T3 | Exp 1 control — A, B, B+ × control group (15) × 5 | 225 | **225** |
| T4 | Exp 4 — 3 configs + A × long (4) × 5 | 80 | **80** |
| T5 | Exp 3 — A, B+ × 3 ceilings × 10 tasks × 5 | 300 | **300** |
| T6 | Ablation — B+nb, B+nr, B+nk × menu group × 5 | 105 | **105** |

**841 usable runs, 4 excluded and all four re-run, estimated cost $92.04.**
Plus 6 checkpoint runs. **Every tier of the plan ran, and all twelve registered
predictions are answered.**

Two things about that are worth stating plainly rather than leaving implied.

**The spend cap was lifted, not respected.** `PREDICTIONS.md` §11 set $80
estimated with a stop at 85 %, and that guard worked: it was about to end the
round at $63.05 with experiment 4 two-thirds measured and the ablation not
started. It was lifted by explicit instruction, and the round then cost $92.04
estimated — **15 % over the original budget, and 45 % over the point where the
guard would have stopped.** The three tiers that guard would have cut are the
ones that falsified a prediction (T6), answered a question no other tier could
(T4), and completed the sweep (T5). That is worth knowing when judging the
round: this is not what the stated budget bought.

**Wall clock was far over too.** The round spans about 33 hours against a
10-hour budget, of which roughly 13 hours are provider blocks during which
nothing ran. The backoff waited every one of them out and wrote the wait into
the affected run's record — **288.5 minutes of logged backoff**. Four runs
exhausted the one-hour per-run ceiling and are marked `rate_limited`, which
excludes them from every statistic rather than scoring them as task failures;
**all four were re-run and all four have a completed replacement** (§6).

**Tier order was the one frozen in `PREDICTIONS.md` §11** — T3, T4, T5, T6 —
not the order that looked most interesting once results existed. An earlier
driver had them in a different order and was corrected before the tiers it
would have reordered ran. Reordering tiers after seeing data is how a budget
cut turns into a choice about which answer to keep.

---

## 1. The five questions this report was required to answer

### Does the enrichment close the step gap against the baseline, on which tasks and by how much?

**Partly, and less than predicted.**

On the seven menu/dialog tasks, paired within `(run_tag, task, rep)` across 37
pairs:

| | steps | success |
|---|---|---|
| A (baseline) | 10.89 | 0.784 |
| B (tool, as it stood) | 13.11 | 0.757 |
| **B+ (tool, enriched)** | **11.38** | **0.838** |

- **B against A** — `+2.22 steps [+0.49, +3.89]`. The defect round 1 measured
  reproduces: the unenriched tool really does spend more steps than a
  screenshot on menu work, and the interval excludes zero.
- **B+ against B** — `−1.73 steps [−2.78, −0.73]`. The enrichment moves it, and
  the interval excludes zero.
- **B+ against A** — `+0.49 steps [−1.68, +2.54]`. No detectable difference at
  this N. The gap that was statistically present is no longer detectable.

So the enrichment removes about two thirds of the measured gap. It does not
remove it. And where it acts is uneven — the whole effect is in three tasks:

| task | A | B | **B+** |
|---|---|---|---|
| `menu_files_new_folder` | 2/5 in 19.2 | 2/5 in 17.8 | **5/5 in 11.8** |
| `menu_save_as_subdir` | 1/6 in 14.5 | 6/6 in 9.2 | **6/6 in 7.3** |
| `files_rename` | 5/5 in 6.0 | 3/5 in 15.0 | **4/5 in 13.2** |
| `text_replace` | 5/5 in 4.0 | 5/5 in 11.0 | 5/5 in 9.0 |
| `menu_replace_all` | 6/6 in 10.3 | 6/6 in 10.5 | 6/6 in 9.0 |
| `menu_calc_insert_column` | 5/5 in 12.6 | 5/5 in 13.6 | 5/5 in **14.6** |
| `calc_add_row` | 5/5 in 9.0 | 1/5 in 16.0 | **0/5 in 16.0** |

`menu_files_new_folder` is the clearest case in the round: 2/5 → 5/5 with seven
fewer steps, and it is the task with the deepest menu descent
(`File ▸ Create New ▸ Folder`, then `Edit ▸ Cut`, then `Edit ▸ Paste` inside
the new folder).

`calc_add_row` is the clearest counter-case: 0/5 against B's 1/5, both at the
16-step ceiling. It was audited action by action across all 15 runs (§6), and
the cause is not the enrichment and not a harness fault. It is a step-ceiling
artefact of a behavioural difference between the channels:

| | A | B | B+ |
|---|---|---|---|
| actions to enter the row | **3** | 6 | 6 |
| pattern | `type 'tape\t6\t2'`, `Return`, `ctrl+shift+s` | `type 'tape'`, `Tab`, `type '6'`, `Tab`, `type '2'`, `Return` | same as B |
| result | 5/5 in 9.0 | 1/5 in 16.0 | 0/5 in 16.0 |

The baseline enters the whole row in a single `type` action with embedded tabs.
Both tool arms address the sheet one cell at a time — the element table hands
the model a cell to name, so it names cells — spending three extra steps. Those
three steps are decisive: all nine failing runs terminate at the ceiling inside
LibreOffice's Save-As → *Use Text CSV Format!* chain, with the identical
verifier message `data/values-plus.csv does not exist`. B rep 2 cleared that
chain on step 16 exactly, which is the whole of B's 1/5 against B+'s 0/5.

Two things follow. First, **this is a tool-channel effect, not an enrichment
effect**: B and B+ produce the same six-action pattern in 5/5 runs each. Second,
`max_steps=16` was fixed for this task in round 1 and was deliberately **not**
changed for round 2. Raising it now, having seen which arm it cuts, is exactly
the post-hoc adjustment `PREDICTIONS.md` exists to prevent.

**On the control group the enrichment does not merely fail to hurt — it
helps.** Across the full fifteen-task group, 75 pairs:

| metric | B | B+ | paired diff | verdict |
|---|---|---|---|---|
| steps | 9.24 | 8.72 | `−0.52 [−0.93, −0.16]` | **B+ lower** |
| success | 0.773 | 0.800 | `+0.027 [−0.040, +0.093]` | no detectable difference |
| est. $ | 0.0811 | 0.0968 | `+$0.0157 [+0.0070, +0.0257]` | **B+ higher** |

This is stronger than the pre-registered reduction to eight tasks showed
(`−0.11 [−0.40, +0.11]`, not detectable). With the full group the step saving
clears zero. The money cost also clears zero, and is discussed below.

### Which of the three enrichments does the work?

**Measured, and the registered ordering is wrong.** `PREDICTIONS.md` §4.4
predicted **shortcuts > reachability > blocks**. Each ablation arm computes the
whole enrichment and then withholds one thing, so the computation cost is
identical and only what the model sees changes. Paired on `(task, rep)` across
tiers, 35 pairs each — a positive number means removing it cost steps:

| withheld | steps vs B+ | verdict |
|---|---|---|
| **blocks** | `+1.77 [+0.83, +2.77]` | **carries the most work** |
| **shortcuts** | `+1.06 [+0.09, +2.11]` | **carries work** |
| reachability | `+0.11 [−0.71, +0.97]` | no detectable difference |

Measured ordering: **blocks > shortcuts > reachability**. I put blocks last and
it is first. **P1.5 is falsified.**

Worse for my reasoning than the ordering itself: the previous draft of this
report, written before the ablation ran, offered "indirect evidence" that the
gain was concentrated in the deepest menu descents, "which is the shape the
shortcut hypothesis predicts and not the shape the blocks hypothesis predicts."
That inference was available, plausible, and wrong. It is the clearest argument
in the round for running the ablation rather than reasoning about it — and for
why the sentence was labelled *suggestive only* when it was written.

Reachability is the one enrichment this round cannot justify. Removing it costs
nothing detectable in steps and the arm without it has the highest success of
any arm in the round (`B+nr` 0.914 [0.800, 1.000] against B+'s 0.814). At N=35
that is not evidence it *helps* to remove it, but it is not paying for itself.

### Does the ambiguity rule solve the vdelta case without deciding by pixels?

**The case is solved. The rule that solves it is not the one the design
document specifies, and that distinction is the most useful finding of the
round.**

| | success | steps | est. $ |
|---|---|---|---|
| C (text-only) | 7/10 | 12.20 | $0.1802 |
| **C+ (text-only + ambiguity)** | **10/10** | **5.00** | **$0.0197** |

Paired over 10 pairs: `−7.20 steps [−8.00, −6.30]`, `+0.300 success
[+0.100, +0.600]`, `−$0.1605 [−$0.1961, −$0.1283]`. All three clear zero. C+
matches the crop-priority arm B on both success and steps at **a ninth of the
estimated cost**, and it never looks at a pixel to decide — the crop is forced
by a property of the tree.

But **P2.2 is falsified.** The design document's rule — same role, same name,
disjoint rectangles — fired **zero times**. Every one of the 55 forced crops
came from the peer-set rule, which I added after reading the tree and before
running anything, and which I registered as the weaker claim precisely so this
could be told apart. The six sibling rows in the vdelta task have *distinct*
names; what makes them ambiguous is that they are interchangeable in every
respect the table reports, not that they share a name.

### Below what budget does the tool win, with the full suite?

**At none of the three ceilings, at this N — and that is a real answer, not a
missing one.** All three ceilings ran on all ten registered tasks, 50 runs per
cell, enforced during execution with every step limit doubled:

| ceiling | arm | success | stopped by the budget | steps |
|---|---|---|---|---|
| 8,000 | A | 0.320 [0.200, 0.460] | **39/50 (78 %)** | 5.5 |
| 8,000 | **B+** | **0.380 [0.240, 0.520]** | **32/50 (64 %)** | 6.5 |
| 15,000 | A | 0.540 [0.400, 0.680] | 24/50 (48 %) | 7.3 |
| 15,000 | **B+** | **0.560 [0.420, 0.700]** | 22/50 (44 %) | 8.7 |
| 30,000 | **A** | **0.680 [0.540, 0.800]** | 18/50 (36 %) | 9.2 |
| 30,000 | B+ | 0.660 [0.520, 0.780] | 17/50 (34 %) | 11.4 |

Paired within `(task, rep)`, 50 pairs per ceiling:

| ceiling | success B+ − A | steps B+ − A |
|---|---|---|
| 8,000 | `+0.060 [−0.100, +0.220]` | `+0.98 [+0.06, +1.86]` |
| 15,000 | `+0.020 [−0.140, +0.180]` | `+1.40 [+0.50, +2.36]` |
| 30,000 | `−0.020 [−0.140, +0.100]` | `+2.22 [+0.46, +4.14]` |

**No success interval clears zero at any ceiling.** The point estimate does
change sign, between 15,000 and 30,000, and it declines monotonically as the
ceiling rises — the shape the tight-budget hypothesis predicts, the tool's
advantage being that it says more per token. But the intervals do not establish
a crossing. **P3.1 is bracketed, not established.** The honest summary of
experiment 3 is: *below no budget in the measured range does the tool
detectably win, and the trend is in the predicted direction.*

One thing does clear zero, at all three ceilings, and it is not in the tool's
favour: **B+ spends more steps than the baseline**, and the gap widens as the
budget loosens (+0.98 → +1.40 → +2.22). The tool buys its token efficiency with
steps, and when tokens stop being scarce there is nothing left to buy.

**The cut rate corrects round 1 sharply.** Round 1 reported the tool arm
"stopped by the budget in 0 of 27 runs" at the 8,000-token ceiling. Here B+ is
stopped in **32 of 50 (64 %)**. Fact 2 of `PREDICTIONS.md` — that the round-1
headline was a property of its nine-task subset rather than of the arm — is not
just confirmed, it was understated: I predicted a 20–50 % cut rate.

### What does the enrichment cost, in milliseconds and in tokens?

**In time, almost nothing. In tokens, more than predicted.**

| phase | ms per step (B+, 172 runs, 2,307 steps) |
|---|---|
| geometry duplicate merge | 0.19 |
| blocks | 0.05 |
| ambiguity (both rules) | 0.05 |
| reachability | 0.35 |
| shortcuts | 3.52 |
| **total** | **4.16** |

Against a prediction of ≤ 150 ms and a falsification threshold of 400 ms, 4.16
ms is not close to either. Two implementation choices are responsible: key
bindings and closed-menu contents are cached per `(app, element id)`, so the
81 ms first read of an application's menu tree is paid once per process, not
per step; and reachability reuses the tree walk the delta already needs.

Tokens are the other way round:

> Observation tokens, B+ against B, paired over 112 `(run_tag, task, rep)`
> pairs: **+1,734 [+867, +2,830]** against a B mean of 8,100 — **+21.4 %**.

The prediction was ≤ 15 %, with falsification at 40 %. The point prediction is
**missed** and the falsification threshold is not reached. **P5.1 is split.**

The money version of the same fact is the control-group result above:
`+$0.0157 [+0.0070, +0.0257]` per task, an interval excluding zero, on the
tasks where the enrichment's step saving is smallest. The enrichment buys steps
with tokens. Now that the ablation has run, the obvious economy is visible:
shortcuts cost 3.52 of the 4.16 ms and most of the token overhead, and rank
*second* of three in the ablation, while blocks rank first and cost 0.05 ms.

---

## 2. Experiment 4 — the result that most changes the picture

This is the experiment that would have been cut. On four tasks of 40 allowed
steps, five repetitions each:

| configuration | success | steps | peak image tokens | est. $ |
|---|---|---|---|---|
| **B+ · window 2 · task object on** | **0.850 [0.700, 1.000]** | 20.2 | 2,922 | $0.2704 |
| B+ · window 4 · task object on | 0.800 [0.600, 0.950] | 20.6 | 3,958 | $0.2866 |
| B+ · window 2 · task object off | 0.800 [0.600, 0.950] | 20.8 | 2,941 | $0.2757 |
| A · baseline | 0.350 [0.150, 0.550] | 30.0 | — | $0.4280 |

Paired on `(task, rep)`, 20 pairs each:

| comparison | peak image tokens | steps | success |
|---|---|---|---|
| **window 2 against window 4** | `−1,036 [−1,508, −576]` | `−0.35 [−2.85, +1.70]` | `+0.050 [0.000, +0.150]` |
| task object on against off | `−20 [−77, +36]` | `−0.50 [−3.10, +1.95]` | `+0.050 [−0.100, +0.200]` |
| **B+ against the baseline A** | `+2,922 [+2,734, +3,120]` | `−9.75 [−15.50, −4.15]` | `+0.500 [+0.300, +0.700]` |

**P4.2 holds.** The two-image window costs 26.2 % fewer peak image tokens than
the four-image window (`−1,036` of 3,958, interval clearing zero) and the
success difference is `+0.050` with a lower bound of exactly zero — free, in
the sense the prediction meant: nothing was given up for it.

**P4.1 does not hold.** The persistent task object was predicted to halve
constraint loss. Checking each constraint separately:

| configuration | `long_notes_digest` | `long_march_export` |
|---|---|---|
| A (baseline) | 15/20 violated (75 %) | 15/20 violated (75 %) |
| B+ · task object **off** | **0/20 (0 %)** | 12/20 (60 %) |
| B+ · task object **on** | **0/40 (0 %)** | 21/40 (52 %) |

On one task both configurations are perfect, so there is nothing to halve; on
the other, 60 % → 52 % is not a halving and the configurations are not
separated. The task object is not doing what it was predicted to do.

**The largest single effect in the round is elsewhere in this table.** On long
tasks the enriched tool succeeds `+0.500 [+0.300, +0.700]` more often than the
baseline and uses 9.75 fewer steps, for 37 % less estimated money. Per task:

| task | A | B+ (all three configs) |
|---|---|---|
| `long_notes_digest` | **0/5**, all 40 steps | **15/15** in 17.1 steps |
| `long_region_transfer` | 2/5 in 30.0 | **15/15** in 13.6 |
| `long_ledger_edits` | 5/5 in 10.0 | 15/15 in 14.8 |
| `long_march_export` | 0/5, all 40 steps | 4/15 in 36.6 |

Round 1 found the tool's advantage grew with task length and was read as a
caching effect. This is the same shape measured against explicit per-constraint
verifiers, and it is much larger than anything in the menu group. The headline
of round 2 was supposed to be the menu defect; on the evidence, long tasks
matter more, and the enrichment is not what makes the difference there — the
tool channel is.

---

## 3. Every prediction, against what happened

| # | Registered claim | Outcome | Measured |
|---|---|---|---|
| P1.1 | B+ cuts ≥ 2.0 steps vs B on menu/dialog | **partly** | −1.73 [−2.78, −0.73]; direction and separation hold, magnitude does not |
| P1.1b | B+ lands in 7–11 steps on the three defect tasks (fails at ≥ 13.0) | **missed, not falsified** | 12.73 against B's 14.00 |
| P1.2 | B+ does not hurt the control group | **held, and better** | full 15 tasks: steps −0.52 [−0.93, −0.16], B+ *faster*; success overlapping |
| P1.3 | B+ does not fully catch A on menus | **held** | +0.49 [−1.68, +2.54], overlapping |
| P1.4 | B+ = B on anchor-solvable visual tasks | **held** | `files_save_as` 6.4 vs 6.4, `files_new_note` 10.0 vs 10.0 |
| P1.5 | Ablation ordering shortcuts > reachability > blocks | **falsified** | blocks +1.77, shortcuts +1.06, reachability +0.11 — blocks first, not last |
| P2.1 | C+ ≥ 6/10 and ≤ 7.0 steps on vdelta | **held, with room** | 10/10 at 5.00 steps |
| P2.2 | The registered same-name rule is what fires | **falsified** | 0 same-name crops, 55 peer-set crops |
| P3.1 | A crossing between 8k and 30k fresh tokens | **bracketed, not established** | sign change between 15k and 30k; no success interval clears zero at any ceiling |
| P3.2 | B+ cut by the 8k ceiling in 20–50 % of runs | **understated** | 64 % (32/50), against round 1's reported 0/27 |
| P4.1 | The task object halves constraint loss | **not held** | 60 % → 52 % on the one task with anything to halve; not separated |
| P4.2 | The 2-image window costs ≥ 25 % fewer peak image tokens, free | **held** | −26.2 % [−1,508, −576]; success +0.050 [0.000, +0.150] |

**All twelve were tested.** Four held cleanly (P1.2, P1.3, P1.4, P4.2), one held
beyond its threshold (P2.1), one is split (P5.1), one is half right in a way
worth stating precisely (P1.1), one was understated (P3.2), one is bracketed
(P3.1), one missed its band without reaching falsification (P1.1b), one does not
hold (P4.1), and **two are falsified outright (P1.5, P2.2)**.

### The three things I got wrong in advance

**Which enrichment matters.** I predicted shortcuts first and blocks last. The
ablation says blocks first. I had also written a paragraph of indirect
reasoning supporting the wrong answer, from the shape of the per-task gains.
Both the prediction and the reasoning that would have rescued it were wrong.

**Which ambiguity rule fires.** The design document's same-name rule fired zero
times in 55 opportunities. The rule that did the work identifies rows that are
*interchangeable*, not rows that are *identically named*. Since the whole value
of experiment 2 was that it could fail cleanly, this is the round working as
intended.

**The magnitude of the enrichment's effect.** I predicted ≤ −2.0 steps and got
−1.73; I predicted 7–11 steps on the three defect tasks and got 12.73. Both are
in the right direction and short of the registered size. Predicting a direction
is easy; predicting a magnitude is what makes a prediction worth writing down,
and mine were optimistic.

### What the predictions did not cover, found anyway

- **The enrichment costs money on tasks it does not help**, `+$0.0157
  [+0.0070, +0.0257]` per control-group task. P1.2 was written about steps and
  success and says nothing about cost, so this falsifies nothing — but it is
  the strongest argument for making the closed-menu summary conditional.
- **B+ spends more steps than the baseline at every budget ceiling**, widening
  as the ceiling rises. Experiment 3 was written as a question about success.
- **Long tasks are where the tool channel actually pays**, `+0.500` success
  against the baseline — larger than any effect in the experiment the round was
  designed around.

---

## 4. Threats to validity

**The new tasks were built to make the treatment look good, and they did.**
Declared in `PREDICTIONS.md` §2 and not mitigated by declaring it. Of the three
tasks carrying the B+ effect, two are new (`menu_files_new_folder`,
`menu_save_as_subdir`). On the three round-1 tasks in the menu group the
picture is much weaker: `text_replace` −2.0 steps, `files_rename` −1.8, and
`calc_add_row` 0.0 with worse success. A reader who discounts the new tasks is
left with an effect that is real but small and does not clear its own
registered threshold.

**The ablation and experiment 4 are paired across tiers, not interleaved.** In
T1, T3 and T5 the arms are interleaved, so a pair differs by the arm and by
decoding noise. In T6 and T4 the manipulated variable *is* the tier, so pairs
share the task, the seed and every setting but not the hour they ran in. Two
falsified/held conclusions rest on that weaker control (P1.5, P4.2). Provider
behaviour drifting between tiers would show up as an arm effect, and nothing in
this design can rule that out. Interleaving those tiers is the first thing to
fix next round.

**N = 5, and the spread is not small.** `menu_save_as_subdir` on arm A has
sd 3.4 on a mean of 14.5, and the interval on the principal comparison,
[−2.78, −0.73], is wide enough that the true effect could be a quarter of the
point estimate or over one and a half times it. Where intervals overlap this
report says "no detectable difference at this N" and never "they are equal."

**Temperature is not fixed.** There is no API key and no decoding parameter to
set; the model channel is the `claude` CLI on a subscription. Decoding settings
are identical across arms by construction, so this does not bias any
comparison, but it widens every interval.

**One ceiling's per-task composition still matters.** At 30,000 fresh tokens
`calc_add_row` alone accounts for most of B+'s deficit. Ten tasks is better
than five, but a single task moving a ceiling's point estimate is a reason to
read the trend across ceilings rather than any one of them.

**The analysis pooled conditions until it was caught.** The paired comparison
originally keyed on `(task, rep)`, which was correct while tiers did not share
tasks and became wrong when the budget sweeps re-ran control-group tasks: a
truncated run could be paired against an unconstrained one, and duplicate keys
were silently collapsed. It surfaced as the enrichment's token overhead reading
+1.6 % where it had read +19.2 %. `paired()` now keys on
`(run_tag, task, rep)`, every non-budget table reads only unbudgeted runs
(D7.8), and the two tables that genuinely need cross-tier pairing ask for it
explicitly and say so in their own text.

**`peak_live_images` is not what its name suggests.** It counts full
screenshots plus crops still inside their TTL, so the value of ~20 for the tool
arms is dominated by crops. The image-window comparison uses
`peak_live_image_tokens`, which is the quantity the prediction was about.

**The budget was exceeded by 15 %, and by 45 % over the guard's stopping
point.** Everything in §2 and the ablation in §1 exists because the cap was
lifted. A reader deciding whether this round's method is affordable should use
$92, not $80.

**One arithmetic slip in the frozen predictions.** `PREDICTIONS.md` §2 says the
suite goes "from 22 to 26 (22 short + 4 long, becoming 26 short + 6 long)"; the
true counts are 18 short + 4 long becoming 22 short + 6 long. The ordering
itself is written out entry by entry and has exactly 22 entries, so nothing
operative is ambiguous. It was left uncorrected rather than edit a document
whose entire value is that it is not edited.

---

## 5. What should run next, in order

1. **Drop reachability, or find the case that justifies it.** It costs 0.35 ms
   and some tokens, removing it costs nothing detectable, and the arm without
   it has the round's highest success. Either there is a class of task where it
   pays — modal dialogs are the obvious candidate and the menu group barely
   exercises them — or it should go.
2. **Make the closed-menu summary conditional.** It is 3.52 of 4.16 ms and most
   of the +21.4 % token overhead, and the ablation ranks it *second*. Emitting
   it only when a menu bar is present and the task statement mentions an
   application command would keep the effect and most of the cost.
3. **Interleave T4 and T6.** Two of the round's conclusions rest on cross-tier
   pairing. This is cheap to fix and removes a whole class of doubt.
4. **Move the suite toward long tasks.** The largest effect measured this round
   is on 40-step tasks, and there are four of them against 22 short ones. The
   round was designed around the wrong end of its own suite.
5. **Give `calc_add_row` a multi-cell entry action, pre-registered.** The
   16-step ceiling is currently measuring a typing-granularity difference, not
   an observation-channel difference.

---

## 6. Harness audit of the zero-success cells

Every cell that scored 0/N was audited action by action, to separate real task
failures from harness faults. The question matters because a broken verifier or
a crashing executor reads, in the tables above, exactly like a hard task —
round 1 already produced one unsatisfiable verifier, and this round only found
it because all 28 verifiers were controlled before any arm ran (D7.7).

| check | count | rate |
|---|---|---|
| runs ending with an error field set | **0** | 0 % |
| actions refused by act-time validation (`aborted`) | 20 of 2,841 | 0.70 % |
| grounding failures (a click landing on nothing) | 46 | 1.6 %, **all in arm A** |
| malformed model replies | 19 | 0.6 % of steps — A 12, B 1, B+ 5, C 1 |
| `done`-terminated runs the verifier then failed | 1 of 207 | 0.5 % |

No run crashed. Aborts and grounding failures are the mechanisms working as
designed, not faults: an abort is the id-addressed channel refusing a stale
element, and grounding failures occur only in the arm that clicks coordinates.
The single `done`-but-failed run is `t3_control B vdelta_bars rep 2`: the agent
answered `central` and the longest bar is west. The verifier is right. **No
verifier false negative was found.**

**Every zero cell terminates on a step or token ceiling the experiment sets
deliberately** — none on an exception, an unsatisfiable verifier, or an
executor failure. Two readings follow. A 0/5 in a budget tier is a *budget*
result and must not be read as the arm being unable to do the task; and
`calc_count_eng`, `cross_report_summary` and `cross_inventory_note` are hard
for **every** arm, not for one of them. They are the suite's multi-application
tasks; their difficulty is a fact about the suite, not a finding about the
observation layer.

**Rate-limited runs.** Four runs hit the per-run rate-limit ceiling and were
marked `rate_limited` rather than scored as task failures (D7.6). **All four
were re-run and all four have a completed replacement.** No cell is missing
one, and no run was silently discarded for a rate limit.

---

## 7. What round 2 established

- The step gap round 1 found is **real and reproduces**: B spends
  `+2.22 [+0.49, +3.89]` more steps than A on menu and dialog work.
- Layer-1 enrichment **reduces it by `−1.73 [−2.78, −0.73]` steps**, enough that
  B+ and A are no longer distinguishable, and on the full control group it is
  **faster** than B rather than merely harmless (`−0.52 [−0.93, −0.16]`).
- **Blocks, not shortcuts, carry the effect** — the opposite of the registered
  ordering, and the opposite of the indirect reasoning I had written before the
  ablation ran.
- The ambiguity rule **closes the text-only channel's worst failure completely**
  — 7/10 and 12.2 steps become 10/10 and 5.0, matching the crop-priority arm at
  a ninth of the estimated cost — **through a rule the design document does not
  contain**, while the rule it does contain fired zero times.
- At **none of three enforced ceilings** does the tool detectably beat the
  baseline on success, though the point estimate declines monotonically as the
  ceiling rises. At 8,000 fresh tokens the tool is **stopped by the budget in
  64 % of runs** where round 1 reported 0 %: that headline was a property of
  its task subset, as `PREDICTIONS.md` said before any of this ran.
- **On long tasks the tool wins by more than anything else measured** —
  `+0.500 [+0.300, +0.700]` success against the baseline, 9.75 fewer steps,
  37 % less estimated money — and the narrow image window pays for itself,
  26 % fewer peak image tokens for nothing given up.
- The enrichment costs **4.16 ms per step** and **+21.4 % observation tokens**,
  and the token side is a real cost on the tasks it helps least.
- **No zero-success cell in the round is a harness fault**, and all four
  rate-limited runs were re-run and replaced.
- **All twelve registered claims were tested. Two are falsified.** That is the
  round working: a prediction that cannot fail is not worth registering, and
  both of these were registered specifically because they could.
