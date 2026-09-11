# RESULTS2 — round 2, generated from results/raw2/

Every table in this file is produced by `analysis/aggregate2.py` from the raw run records. Nothing here is typed by hand.

- usable runs: **341**
- excluded (rate limit, harness or model error): 3 — of which 3 rate-limited
- total time spent waiting out provider rate limits: 228.5 min
- **estimated** cost of the usable runs: $32.54 — computed from token counts and the published rate, not observed spend; this runs on a subscription and there is no bill to read

## 1. Headline, by arm

| Arm | n | success | steps | fresh tokens | image tokens | est. $ | grounding fails |
|---|---|---|---|---|---|---|---|
| A | 73 | 0.767 [0.671, 0.863] | 10.22 [9.04, 11.44] | 23951 [19940, 27945] | 12549 [11102, 13979] | 0.1039 [0.0859, 0.1222] | 0.44 [0.25, 0.66] |
| B | 74 | 0.716 [0.608, 0.811] | 11.81 [10.70, 12.92] | 18013 [14711, 21502] | 2781 [2548, 3006] | 0.1081 [0.0878, 0.1292] | 0.00 [0.00, 0.00] |
| B+ | 74 | 0.811 [0.716, 0.892] | 10.62 [9.57, 11.70] | 19559 [15379, 24144] | 2613 [2389, 2839] | 0.1136 [0.0902, 0.1386] | 0.00 [0.00, 0.00] |
| C | 10 | 0.700 [0.400, 1.000] | 12.20 [11.30, 13.10] | 27024 [21992, 32175] | 2456 [2456, 2456] | 0.1802 [0.1475, 0.2158] | 0.00 [0.00, 0.00] |
| C+ | 10 | 1.000 [1.000, 1.000] | 5.00 [5.00, 5.00] | 3343 [2108, 4667] | 1338 [1311, 1366] | 0.0197 [0.0148, 0.0248] | 0.00 [0.00, 0.00] |

All dollar figures are **estimated** from tokens, not observed.

## 2. Experiment 1 — does the enrichment close the step gap?

Unbudgeted runs only (241 of 341 usable). The 100 runs carrying an enforced token ceiling belong to the budget sweep and are reported there.

### B+ against B — menu/dialog group

| metric | B mean | B+ mean | paired diff (B+ − B) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 13.11 | 11.38 | -1.73 [-2.81, -0.70] | 37 | **B+ lower** |
| success | 0.757 | 0.838 | 0.081 [-0.027, 0.189] | 37 | no detectable difference at this N |
| model_calls | 13.11 | 11.38 | -1.73 [-2.81, -0.73] | 37 | **B+ lower** |
| cost_usd | 0.1173 | 0.1120 | -0.0053 [-0.0201, 0.0084] | 37 | no detectable difference at this N |

### B+ against A — menu/dialog group

| metric | A mean | B+ mean | paired diff (B+ − A) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 10.89 | 11.38 | 0.49 [-1.65, 2.54] | 37 | no detectable difference at this N |
| success | 0.784 | 0.838 | 0.054 [-0.135, 0.243] | 37 | no detectable difference at this N |
| model_calls | 10.89 | 11.38 | 0.49 [-1.65, 2.49] | 37 | no detectable difference at this N |
| cost_usd | 0.1120 | 0.1120 | -0.0000 [-0.0371, 0.0381] | 37 | no detectable difference at this N |

### B against A — menu/dialog group

| metric | A mean | B mean | paired diff (B − A) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 10.89 | 13.11 | 2.22 [0.43, 3.92] | 37 | **B higher** |
| success | 0.784 | 0.757 | -0.027 [-0.216, 0.162] | 37 | no detectable difference at this N |
| model_calls | 10.89 | 13.11 | 2.22 [0.46, 3.92] | 37 | **B higher** |
| cost_usd | 0.1120 | 0.1173 | 0.0053 [-0.0247, 0.0351] | 37 | no detectable difference at this N |

### B+ against B — the three round-1 defect tasks

| metric | B mean | B+ mean | paired diff (B+ − B) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 14.00 | 12.73 | -1.27 [-2.33, -0.40] | 15 | **B+ lower** |
| success | 0.600 | 0.600 | 0.000 [-0.200, 0.200] | 15 | no detectable difference at this N |
| model_calls | 14.00 | 12.73 | -1.27 [-2.27, -0.40] | 15 | **B+ lower** |
| cost_usd | 0.1267 | 0.1330 | 0.0063 [-0.0116, 0.0245] | 15 | no detectable difference at this N |

### B+ against B — control group (no harm test)

| metric | B mean | B+ mean | paired diff (B+ − B) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 10.51 | 9.86 | -0.11 [-0.40, 0.11] | 35 | no detectable difference at this N |
| success | 0.676 | 0.784 | 0.057 [-0.086, 0.200] | 35 | no detectable difference at this N |
| model_calls | 10.51 | 9.86 | -0.11 [-0.40, 0.11] | 35 | no detectable difference at this N |
| cost_usd | 0.0989 | 0.1153 | 0.0237 [0.0112, 0.0375] | 35 | **B+ higher** |

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

## 3. Experiment 2 — ambiguity forces a crop

### C+ against C — the vdelta pair

| metric | C mean | C+ mean | paired diff (C+ − C) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 12.20 | 5.00 | -7.20 [-8.00, -6.30] | 10 | **C+ lower** |
| success | 0.700 | 1.000 | 0.300 [0.000, 0.600] | 10 | no detectable difference at this N |
| model_calls | 12.90 | 5.00 | -7.90 [-9.60, -6.50] | 10 | **C+ lower** |
| cost_usd | 0.1802 | 0.0197 | -0.1605 [-0.1956, -0.1283] | 10 | **C+ lower** |

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
| 8,000 | A | 25 | 0.320 [0.160, 0.520] | 20/25 (80%) | 5.7 |
| 8,000 | B+ | 25 | 0.400 [0.200, 0.600] | 16/25 (64%) | 6.8 |
| 30,000 | A | 25 | 0.720 [0.520, 0.880] | 8/25 (32%) | 8.9 |
| 30,000 | B+ | 25 | 0.600 [0.400, 0.800] | 10/25 (40%) | 12.9 |

### Paired within `(task, rep)`, at each ceiling

The same task and the same repetition seed, one row per pair. A positive success difference means the enriched tool wins at that ceiling.

| ceiling | pairs | success B+ − A | steps B+ − A | verdict |
|---|---|---|---|---|
| 8,000 | 25 | 0.080 [-0.120, 0.320] | 1.08 [-0.36, 2.48] | no detectable difference |
| 30,000 | 25 | -0.120 [-0.320, 0.080] | 4.04 [1.24, 7.28] | no detectable difference |

### Where the curves cross

The point estimate changes sign between **8,000 and 30,000 fresh tokens** (+0.080 → -0.120). Whether that is a real crossing depends on the intervals in the table above, not on the point estimates: read a crossing as established only where the two intervals sit on opposite sides of zero.

At no measured ceiling does the difference clear zero, so this round answers *below what budget does the tool win* with **no budget in the measured range, at this N** — which is not the same as the arms being equal.

## The image window

| arm | window | runs | peak live images | peak live image tokens | re-anchors | compactions | success |
|---|---|---|---|---|---|---|---|
| B | 2 | 74 | 21.8 | 2,346 | 0.8 | 0.4 | 53/74 |
| B+ | 2 | 74 | 21.5 | 2,276 | 0.7 | 0.3 | 60/74 |
| C | 2 | 10 | 2.0 | 2,456 | 1.0 | 0.0 | 7/10 |
| C+ | 2 | 10 | 6.5 | 1,338 | 0.0 | 0.0 | 10/10 |

## What the enrichment costs

Measured per step inside the observer, and reported whether or not the number is flattering (PREDICTIONS.md §8).

| arm | runs | steps | merge ms/step | blocks ms/step | ambiguity ms/step | reach ms/step | shortcuts ms/step | total ms/step |
|---|---|---|---|---|---|---|---|---|
| B+ | 74 | 786 | 0.11 | 0.04 | 0.04 | 0.34 | 2.21 | 2.73 |
| C+ | 10 | 50 | 0.03 | 0.02 | 0.04 | 0.04 | 0.01 | 0.14 |

Observation tokens, B+ against B, paired on 72 (task, rep) pairs: **+1,745** [+871, +2,760] against a B mean of 9,514 — **+18.3%**.

## Per task

| task | A succ | B succ | B+ succ | C succ | C+ succ | A steps | B steps | B+ steps | C steps | C+ steps |
|---|---|---|---|---|---|---|---|---|---|---|
| calc_add_row | 5/5 | 1/5 | 0/5 | — | — | 9.0 | 16.0 | 16.0 | — | — |
| calc_count_eng | 0/5 | 0/5 | 1/4 | — | — | 18.0 | 18.0 | 18.0 | — | — |
| calc_total | 5/5 | 4/5 | 3/5 | — | — | 10.0 | 15.6 | 15.2 | — | — |
| cross_report_summary | 0/4 | 0/5 | 1/4 | — | — | 18.0 | 18.0 | 17.5 | — | — |
| files_new_note | 4/4 | 4/4 | 5/5 | — | — | 9.5 | 10.0 | 10.0 | — | — |
| files_rename | 5/5 | 3/5 | 4/5 | — | — | 6.0 | 15.0 | 13.2 | — | — |
| files_save_as | 5/5 | 4/4 | 5/5 | — | — | 6.4 | 6.5 | 6.4 | — | — |
| menu_calc_insert_column | 5/5 | 5/5 | 5/5 | — | — | 12.6 | 13.6 | 14.6 | — | — |
| menu_files_new_folder | 2/5 | 2/5 | 5/5 | — | — | 19.2 | 17.8 | 11.8 | — | — |
| menu_replace_all | 6/6 | 6/6 | 6/6 | — | — | 10.3 | 10.5 | 9.0 | — | — |
| menu_save_as_subdir | 1/6 | 6/6 | 6/6 | — | — | 14.5 | 9.2 | 7.3 | — | — |
| text_replace | 5/5 | 5/5 | 5/5 | — | — | 4.0 | 11.0 | 9.0 | — | — |
| vdelta_bars | 5/5 | 4/5 | 5/5 | 2/5 | 5/5 | 5.0 | 5.0 | 5.0 | 13.2 | 5.0 |
| vdelta_rows | 4/4 | 4/4 | 4/4 | 5/5 | 5/5 | 5.0 | 5.0 | 5.0 | 11.2 | 5.0 |
| visual_badge | 4/4 | 5/5 | 5/5 | — | — | 4.0 | 4.0 | 4.0 | — | — |

