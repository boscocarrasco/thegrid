# RESULTS2 — round 2, generated from results/raw2/

Every table in this file is produced by `analysis/aggregate2.py` from the raw run records. Nothing here is typed by hand.

- usable runs: **841**
- excluded (rate limit, harness or model error): 4 — of which 4 rate-limited
- total time spent waiting out provider rate limits: 288.5 min
- **estimated** cost of the usable runs: $92.04 — computed from token counts and the published rate, not observed spend; this runs on a subscription and there is no bill to read

## 1. Headline, by arm

| Arm | n | success | steps | fresh tokens | image tokens | est. $ | grounding fails |
|---|---|---|---|---|---|---|---|
| A | 132 | 0.727 [0.652, 0.803] | 12.50 [10.84, 14.32] | 33757 [27616, 40106] | 15350 [13294, 17536] | 0.1476 [0.1207, 0.1766] | 0.41 [0.23, 0.60] |
| B | 112 | 0.768 [0.688, 0.839] | 10.52 [9.55, 11.49] | 15672 [12780, 18814] | 2556 [2362, 2747] | 0.0930 [0.0764, 0.1113] | 0.00 [0.00, 0.00] |
| B+ | 172 | 0.814 [0.756, 0.872] | 13.41 [12.15, 14.76] | 27036 [22096, 32380] | 3104 [2840, 3365] | 0.1631 [0.1326, 0.1966] | 0.00 [0.00, 0.00] |
| B+nb | 35 | 0.743 [0.600, 0.886] | 13.37 [12.26, 14.46] | 21873 [17661, 26281] | 3129 [2940, 3332] | 0.1314 [0.1060, 0.1562] | 0.00 [0.00, 0.00] |
| B+nk | 35 | 0.771 [0.629, 0.914] | 12.66 [11.54, 13.83] | 19977 [15625, 24745] | 3033 [2848, 3238] | 0.1212 [0.0954, 0.1486] | 0.00 [0.00, 0.00] |
| B+nr | 35 | 0.914 [0.800, 1.000] | 11.71 [10.69, 12.77] | 19621 [14903, 24749] | 2865 [2715, 3036] | 0.1169 [0.0898, 0.1443] | 0.00 [0.00, 0.00] |
| C | 10 | 0.700 [0.400, 1.000] | 12.20 [11.30, 13.10] | 27024 [22106, 32183] | 2456 [2456, 2456] | 0.1802 [0.1484, 0.2147] | 0.00 [0.00, 0.00] |
| C+ | 10 | 1.000 [1.000, 1.000] | 5.00 [5.00, 5.00] | 3343 [2092, 4641] | 1338 [1311, 1366] | 0.0197 [0.0149, 0.0247] | 0.00 [0.00, 0.00] |

All dollar figures are **estimated** from tokens, not observed.

## 2. Experiment 1 — does the enrichment close the step gap?

Unbudgeted runs only (541 of 841 usable). The 300 runs carrying an enforced token ceiling belong to the budget sweep and are reported there.

### B+ against B — menu/dialog group

| metric | B mean | B+ mean | paired diff (B+ − B) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 13.11 | 11.38 | -1.73 [-2.78, -0.73] | 37 | **B+ lower** |
| success | 0.757 | 0.838 | 0.081 [-0.027, 0.216] | 37 | no detectable difference at this N |
| model_calls | 13.11 | 11.38 | -1.73 [-2.78, -0.73] | 37 | **B+ lower** |
| cost_usd | 0.1173 | 0.1120 | -0.0053 [-0.0202, 0.0088] | 37 | no detectable difference at this N |

### B+ against A — menu/dialog group

| metric | A mean | B+ mean | paired diff (B+ − A) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 10.89 | 11.38 | 0.49 [-1.68, 2.54] | 37 | no detectable difference at this N |
| success | 0.784 | 0.838 | 0.054 [-0.135, 0.243] | 37 | no detectable difference at this N |
| model_calls | 10.89 | 11.38 | 0.49 [-1.59, 2.46] | 37 | no detectable difference at this N |
| cost_usd | 0.1120 | 0.1120 | -0.0000 [-0.0375, 0.0376] | 37 | no detectable difference at this N |

### B against A — menu/dialog group

| metric | A mean | B mean | paired diff (B − A) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 10.89 | 13.11 | 2.22 [0.49, 3.89] | 37 | **B higher** |
| success | 0.784 | 0.757 | -0.027 [-0.216, 0.162] | 37 | no detectable difference at this N |
| model_calls | 10.89 | 13.11 | 2.22 [0.51, 3.89] | 37 | **B higher** |
| cost_usd | 0.1120 | 0.1173 | 0.0053 [-0.0242, 0.0351] | 37 | no detectable difference at this N |

### B+ against B — the three round-1 defect tasks

| metric | B mean | B+ mean | paired diff (B+ − B) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 14.00 | 12.73 | -1.27 [-2.27, -0.40] | 15 | **B+ lower** |
| success | 0.600 | 0.600 | 0.000 [-0.200, 0.200] | 15 | no detectable difference at this N |
| model_calls | 14.00 | 12.73 | -1.27 [-2.33, -0.40] | 15 | **B+ lower** |
| cost_usd | 0.1267 | 0.1330 | 0.0063 [-0.0119, 0.0240] | 15 | no detectable difference at this N |

### B+ against B — control group (no harm test)

| metric | B mean | B+ mean | paired diff (B+ − B) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 9.24 | 8.72 | -0.52 [-0.93, -0.16] | 75 | **B+ lower** |
| success | 0.773 | 0.800 | 0.027 [-0.040, 0.093] | 75 | no detectable difference at this N |
| model_calls | 9.24 | 8.72 | -0.52 [-0.93, -0.17] | 75 | **B+ lower** |
| cost_usd | 0.0811 | 0.0968 | 0.0157 [0.0070, 0.0257] | 75 | **B+ higher** |

### Variance across repetitions — menu/dialog group

Spread within a cell is how underpowered the experiment is, so it is reported rather than smoothed away.

| arm | task | n | mean steps | sd steps | successes |
|---|---|---|---|---|---|
| A | calc_add_row | 5 | 9.0 | 0.0 | 5/5 |
| A | files_rename | 5 | 6.0 | 0.0 | 5/5 |
| A | menu_calc_insert_column | 5 | 12.6 | 0.8 | 5/5 |
| A | menu_files_new_folder | 5 | 19.2 | 1.6 | 2/5 |
| A | menu_replace_all | 6 | 10.3 | 0.5 | 6/6 |
| A | menu_save_as_subdir | 6 | 14.5 | 3.4 | 1/6 |
| A | text_replace | 5 | 4.0 | 0.0 | 5/5 |
| B | calc_add_row | 5 | 16.0 | 0.0 | 1/5 |
| B | files_rename | 5 | 15.0 | 1.3 | 3/5 |
| B | menu_calc_insert_column | 5 | 13.6 | 0.8 | 5/5 |
| B | menu_files_new_folder | 5 | 17.8 | 2.9 | 2/5 |
| B | menu_replace_all | 6 | 10.5 | 1.1 | 6/6 |
| B | menu_save_as_subdir | 6 | 9.2 | 0.4 | 6/6 |
| B | text_replace | 5 | 11.0 | 1.5 | 5/5 |
| B+ | calc_add_row | 5 | 16.0 | 0.0 | 0/5 |
| B+ | files_rename | 5 | 13.2 | 2.1 | 4/5 |
| B+ | menu_calc_insert_column | 5 | 14.6 | 2.3 | 5/5 |
| B+ | menu_files_new_folder | 5 | 11.8 | 4.2 | 5/5 |
| B+ | menu_replace_all | 6 | 9.0 | 0.0 | 6/6 |
| B+ | menu_save_as_subdir | 6 | 7.3 | 0.9 | 6/6 |
| B+ | text_replace | 5 | 9.0 | 0.0 | 5/5 |
| B+nb | calc_add_row | 5 | 15.8 | 0.4 | 2/5 |
| B+nb | files_rename | 5 | 15.2 | 1.2 | 2/5 |
| B+nb | menu_calc_insert_column | 5 | 14.4 | 0.8 | 5/5 |
| B+nb | menu_files_new_folder | 5 | 18.2 | 2.2 | 2/5 |
| B+nb | menu_replace_all | 5 | 10.8 | 0.4 | 5/5 |
| B+nb | menu_save_as_subdir | 5 | 9.0 | 0.0 | 5/5 |
| B+nb | text_replace | 5 | 10.2 | 0.4 | 5/5 |
| B+nk | calc_add_row | 5 | 16.0 | 0.0 | 0/5 |
| B+nk | files_rename | 5 | 12.2 | 2.2 | 4/5 |
| B+nk | menu_calc_insert_column | 5 | 14.0 | 1.3 | 5/5 |
| B+nk | menu_files_new_folder | 5 | 17.8 | 2.3 | 3/5 |
| B+nk | menu_replace_all | 5 | 10.0 | 0.0 | 5/5 |
| B+nk | menu_save_as_subdir | 5 | 9.0 | 0.0 | 5/5 |
| B+nk | text_replace | 5 | 9.6 | 0.8 | 5/5 |
| B+nr | calc_add_row | 5 | 16.0 | 0.0 | 2/5 |
| B+nr | files_rename | 5 | 12.0 | 2.1 | 5/5 |
| B+nr | menu_calc_insert_column | 5 | 13.2 | 1.0 | 5/5 |
| B+nr | menu_files_new_folder | 5 | 14.6 | 2.9 | 5/5 |
| B+nr | menu_replace_all | 5 | 9.0 | 0.0 | 5/5 |
| B+nr | menu_save_as_subdir | 5 | 8.2 | 0.4 | 5/5 |
| B+nr | text_replace | 5 | 9.0 | 0.0 | 5/5 |

## 3. Experiment 2 — ambiguity forces a crop

### C+ against C — the vdelta pair

| metric | C mean | C+ mean | paired diff (C+ − C) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 12.20 | 5.00 | -7.20 [-8.00, -6.30] | 10 | **C+ lower** |
| success | 0.700 | 1.000 | 0.300 [0.100, 0.600] | 10 | **C+ higher** |
| model_calls | 12.90 | 5.00 | -7.90 [-9.50, -6.50] | 10 | **C+ lower** |
| cost_usd | 0.1802 | 0.0197 | -0.1605 [-0.1961, -0.1283] | 10 | **C+ lower** |

### B against C+ — the vdelta pair

| metric | C+ mean | B mean | paired diff (B − C+) | pairs | verdict |
|---|---|---|---|---|---|

## Which ambiguity rule fired

The registered prediction (P2.2) is about the same-name rule from §5.2 of the design document. The peer-set rule was added after reading the tree and before running anything, and is the weaker claim. They are counted separately so a result is never credited to the rule that did not fire.

| arm | task | runs | crops forced by ambiguity | same-name | peer-set |
|---|---|---|---|---|---|
| C+ | vdelta_bars | 5 | 25 | 0 | 25 |
| C+ | vdelta_rows | 5 | 30 | 0 | 30 |

## Budget sweep — enforced during execution, on fresh tokens

Budgeting is on fresh tokens (input + cache-write + output). A cache read is neither work the provider redid nor a cost paid at full rate; charging it would bill the append-only arms for the very thing that makes them cheap, and would let anyone pick the winner by picking the denominator.

| ceiling | arm | n | success | stopped by the budget | steps |
|---|---|---|---|---|---|
| 8,000 | A | 50 | 0.320 [0.200, 0.460] | 39/50 (78%) | 5.5 |
| 8,000 | B+ | 50 | 0.380 [0.240, 0.520] | 32/50 (64%) | 6.5 |
| 15,000 | A | 50 | 0.540 [0.400, 0.680] | 24/50 (48%) | 7.3 |
| 15,000 | B+ | 50 | 0.560 [0.420, 0.700] | 22/50 (44%) | 8.7 |
| 30,000 | A | 50 | 0.680 [0.540, 0.800] | 18/50 (36%) | 9.2 |
| 30,000 | B+ | 50 | 0.660 [0.520, 0.780] | 17/50 (34%) | 11.4 |

### Paired within `(task, rep)`, at each ceiling

The same task and the same repetition seed, one row per pair. A positive success difference means the enriched tool wins at that ceiling.

| ceiling | pairs | success B+ − A | steps B+ − A | verdict |
|---|---|---|---|---|
| 8,000 | 50 | 0.060 [-0.100, 0.220] | 0.98 [0.06, 1.86] | no detectable difference |
| 15,000 | 50 | 0.020 [-0.140, 0.180] | 1.40 [0.50, 2.36] | no detectable difference |
| 30,000 | 50 | -0.020 [-0.140, 0.100] | 2.22 [0.46, 4.14] | no detectable difference |

### Where the curves cross

The point estimate changes sign between **15,000 and 30,000 fresh tokens** (+0.020 → -0.020). Whether that is a real crossing depends on the intervals in the table above, not on the point estimates: read a crossing as established only where the two intervals sit on opposite sides of zero.

At no measured ceiling does the difference clear zero, so this round answers *below what budget does the tool win* with **no budget in the measured range, at this N** — which is not the same as the arms being equal.

## Experiment 4 — long tasks, image window and task object

Four tasks of 40 allowed steps, five repetitions each. The three `B+` configurations differ by exactly one setting, and each setting is its own tier, so these are paired on `(task, rep)` across tiers: same task, same seed, same everything but the manipulated variable and the hour it ran in.

| configuration | n | success | steps | peak live images | peak image tokens | re-anchors | compactions | est. $ |
|---|---|---|---|---|---|---|---|---|
| B+ · window 2 · task object **on** | 20 | 0.850 [0.700, 1.000] | 20.2 | 22.8 | 2,922 | 1.4 | 0.7 | $0.2704 |
| B+ · window **4** · task object on | 20 | 0.800 [0.600, 0.950] | 20.6 | 27.1 | 3,958 | 2.0 | 0.2 | $0.2866 |
| B+ · window 2 · task object **off** | 20 | 0.800 [0.600, 0.950] | 20.8 | 24.1 | 2,941 | 1.4 | 0.8 | $0.2757 |
| A · baseline (screenshot each step) | 20 | 0.350 [0.150, 0.550] | 30.0 | 1.0 | 0 | 0.0 | 0.0 | $0.4280 |

| comparison | pairs | peak image tokens | steps | success |
|---|---|---|---|---|
| window 2 against window 4 | 20 | -1036 [-1508, -576] | -0.35 [-2.85, 1.70] | 0.050 [0.000, 0.150] |
| task object on against off | 20 | -20 [-77, 36] | -0.50 [-3.10, 1.95] | 0.050 [-0.100, 0.200] |
| B+ against the baseline A | 20 | 2922 [2734, 3120] | -9.75 [-15.50, -4.15] | 0.500 [0.300, 0.700] |

## Constraints, checked one at a time

What separates *failed the task* from *forgot a constraint*. The violation rate counts only constraints on runs that did something — a run that never started cannot be said to have forgotten anything.

| arm | task object | task | runs | task success | constraint violations | rate |
|---|---|---|---|---|---|---|
| A | off | long_march_export | 5 | 0/5 | 15/20 | 75% |
| A | off | long_notes_digest | 5 | 0/5 | 15/20 | 75% |
| B+ | off | long_march_export | 5 | 1/5 | 12/20 | 60% |
| B+ | off | long_notes_digest | 5 | 5/5 | 0/20 | 0% |
| B+ | on | long_march_export | 10 | 3/10 | 21/40 | 52% |
| B+ | on | long_notes_digest | 10 | 10/10 | 0/40 | 0% |

## Ablation — which enrichment does the work

Each arm computes the whole enrichment and then withholds one thing, so the cost of computing it is identical across arms and only what the model sees changes. A **positive** step difference means removing that enrichment made the agent spend more steps — that enrichment was doing work.

*Paired on `(task, rep)` across tiers.* The ablation arms ran in their own tier rather than interleaved with `B+`, so these pairs share the task, the seed and every setting, but not the hour they ran in. That is a weaker control than the interleaved comparisons above, and the intervals should be read with that in mind.

| withheld | arm | pairs | steps vs B+ | success vs B+ | verdict |
|---|---|---|---|---|---|
| blocks | `B+nb` | 35 | 1.77 [0.83, 2.77] | -0.086 [-0.257, 0.086] | **carries work** |
| reachability | `B+nr` | 35 | 0.11 [-0.71, 0.97] | 0.086 [0.000, 0.200] | no detectable difference at this N |
| shortcuts | `B+nk` | 35 | 1.06 [0.09, 2.11] | -0.057 [-0.171, 0.057] | **carries work** |

| arm | menu-group success | menu-group steps |
|---|---|---|
| B+ | 31/37 | 11.38 |
| B+nb | 26/35 | 13.37 |
| B+nr | 32/35 | 11.71 |
| B+nk | 27/35 | 12.66 |

## The image window

| arm | window | runs | peak live images | peak live image tokens | re-anchors | compactions | success |
|---|---|---|---|---|---|---|---|
| B | 2 | 112 | 17.5 | 2,212 | 0.7 | 0.3 | 86/112 |
| B+ | 2 | 152 | 19.7 | 2,321 | 0.8 | 0.4 | 124/152 |
| B+ | 4 | 20 | 27.1 | 3,958 | 2.0 | 0.2 | 16/20 |
| B+nb | 2 | 35 | 31.2 | 2,703 | 1.0 | 0.3 | 26/35 |
| B+nk | 2 | 35 | 29.1 | 2,679 | 1.0 | 0.3 | 27/35 |
| B+nr | 2 | 35 | 25.0 | 2,619 | 1.0 | 0.2 | 32/35 |
| C | 2 | 10 | 2.0 | 2,456 | 1.0 | 0.0 | 7/10 |
| C+ | 2 | 10 | 6.5 | 1,338 | 0.0 | 0.0 | 10/10 |

## What the enrichment costs

Measured per step inside the observer, and reported whether or not the number is flattering (PREDICTIONS.md §8).

| arm | runs | steps | merge ms/step | blocks ms/step | ambiguity ms/step | reach ms/step | shortcuts ms/step | total ms/step |
|---|---|---|---|---|---|---|---|---|
| B+ | 172 | 2307 | 0.19 | 0.05 | 0.05 | 0.35 | 3.52 | 4.16 |
| B+nb | 35 | 468 | 0.10 | 0.05 | 0.05 | 0.42 | 1.76 | 2.37 |
| B+nk | 35 | 443 | 0.20 | 0.05 | 0.04 | 0.41 | 3.46 | 4.17 |
| B+nr | 35 | 410 | 0.10 | 0.05 | 0.05 | 0.43 | 0.06 | 0.69 |
| C+ | 10 | 50 | 0.03 | 0.02 | 0.04 | 0.04 | 0.01 | 0.14 |

Observation tokens, B+ against B, paired on 112 (task, rep) pairs: **+1,734** [+843, +2,830] against a B mean of 8,100 — **+21.4%**.

## Per task

| task | A succ | B succ | B+ succ | B+nb succ | B+nk succ | B+nr succ | C succ | C+ succ | A steps | B steps | B+ steps | B+nb steps | B+nk steps | B+nr steps | C steps | C+ steps |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| calc_add_row | 5/5 | 1/5 | 0/5 | 2/5 | 0/5 | 2/5 | — | — | 9.0 | 16.0 | 16.0 | 15.8 | 16.0 | 16.0 | — | — |
| calc_count_eng | 0/5 | 0/5 | 1/5 | — | — | — | — | — | 18.0 | 18.0 | 18.0 | — | — | — | — | — |
| calc_total | 5/5 | 4/5 | 3/5 | — | — | — | — | — | 10.0 | 15.6 | 15.2 | — | — | — | — | — |
| cross_inventory_note | 0/5 | 0/5 | 0/5 | — | — | — | — | — | 18.0 | 18.0 | 18.0 | — | — | — | — | — |
| cross_report_summary | 0/5 | 0/5 | 1/5 | — | — | — | — | — | 18.0 | 18.0 | 17.6 | — | — | — | — | — |
| files_new_note | 5/5 | 5/5 | 5/5 | — | — | — | — | — | 9.4 | 10.0 | 10.0 | — | — | — | — | — |
| files_rename | 5/5 | 3/5 | 4/5 | 2/5 | 4/5 | 5/5 | — | — | 6.0 | 15.0 | 13.2 | 15.2 | 12.2 | 12.0 | — | — |
| files_save_as | 5/5 | 5/5 | 5/5 | — | — | — | — | — | 6.4 | 6.4 | 6.4 | — | — | — | — | — |
| long_ledger_edits | 5/5 | — | 15/15 | — | — | — | — | — | 10.0 | — | 14.8 | — | — | — | — | — |
| long_march_export | 0/5 | — | 4/15 | — | — | — | — | — | 40.0 | — | 36.6 | — | — | — | — | — |
| long_notes_digest | 0/5 | — | 15/15 | — | — | — | — | — | 40.0 | — | 17.1 | — | — | — | — | — |
| long_region_transfer | 2/5 | — | 15/15 | — | — | — | — | — | 30.0 | — | 13.6 | — | — | — | — | — |
| menu_calc_insert_column | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | — | — | 12.6 | 13.6 | 14.6 | 14.4 | 14.0 | 13.2 | — | — |
| menu_files_new_folder | 2/5 | 2/5 | 5/5 | 2/5 | 3/5 | 5/5 | — | — | 19.2 | 17.8 | 11.8 | 18.2 | 17.8 | 14.6 | — | — |
| menu_replace_all | 6/6 | 6/6 | 6/6 | 5/5 | 5/5 | 5/5 | — | — | 10.3 | 10.5 | 9.0 | 10.8 | 10.0 | 9.0 | — | — |
| menu_save_as_subdir | 1/6 | 6/6 | 6/6 | 5/5 | 5/5 | 5/5 | — | — | 14.5 | 9.2 | 7.3 | 9.0 | 9.0 | 8.2 | — | — |
| text_append | 5/5 | 5/5 | 5/5 | — | — | — | — | — | 5.4 | 9.4 | 5.0 | — | — | — | — | — |
| text_delete_line | 5/5 | 5/5 | 5/5 | — | — | — | — | — | 9.0 | 9.0 | 6.2 | — | — | — | — | — |
| text_replace | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | — | — | 4.0 | 11.0 | 9.0 | 10.2 | 9.6 | 9.0 | — | — |
| text_uppercase | 5/5 | 5/5 | 5/5 | — | — | — | — | — | 4.8 | 4.2 | 4.4 | — | — | — | — | — |
| vdelta_bars | 5/5 | 4/5 | 5/5 | — | — | — | 2/5 | 5/5 | 5.0 | 5.0 | 5.0 | — | — | — | 13.2 | 5.0 |
| vdelta_rows | 5/5 | 5/5 | 5/5 | — | — | — | 5/5 | 5/5 | 5.0 | 5.0 | 5.0 | — | — | — | 11.2 | 5.0 |
| visual_badge | 5/5 | 5/5 | 5/5 | — | — | — | — | — | 4.0 | 4.0 | 4.0 | — | — | — | — | — |
| visual_chart | 5/5 | 5/5 | 5/5 | — | — | — | — | — | 4.0 | 4.0 | 4.0 | — | — | — | — | — |
| visual_shapes | 5/5 | 5/5 | 5/5 | — | — | — | — | — | 4.4 | 4.0 | 4.0 | — | — | — | — | — |
| web_form | 5/5 | 5/5 | 5/5 | — | — | — | — | — | 8.0 | 8.0 | 8.0 | — | — | — | — | — |

