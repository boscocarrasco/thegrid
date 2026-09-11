# RESULTS2 — round 2, generated from results/raw2/

Every table in this file is produced by `analysis/aggregate2.py` from the raw run records. Nothing here is typed by hand.

- usable runs: **285**
- excluded (rate limit, harness or model error): 2 — of which 2 rate-limited
- total time spent waiting out provider rate limits: 168.5 min
- **estimated** cost of the usable runs: $27.40 — computed from token counts and the published rate, not observed spend; this runs on a subscription and there is no bill to read

## 1. Headline, by arm

| Arm | n | success | steps | fresh tokens | image tokens | est. $ | grounding fails |
|---|---|---|---|---|---|---|---|
| A | 96 | 0.656 [0.562, 0.750] | 8.98 [8.00, 9.99] | 19452 [16112, 22896] | 11026 [9824, 12254] | 0.0847 [0.0707, 0.0993] | 0.44 [0.26, 0.62] |
| B | 72 | 0.708 [0.597, 0.819] | 11.82 [10.62, 12.93] | 18160 [14860, 21704] | 2784 [2553, 3015] | 0.1091 [0.0890, 0.1306] | 0.00 [0.00, 0.00] |
| B+ | 97 | 0.701 [0.608, 0.794] | 9.69 [8.77, 10.66] | 16727 [13407, 20257] | 2423 [2235, 2609] | 0.0970 [0.0781, 0.1174] | 0.00 [0.00, 0.00] |
| C | 10 | 0.700 [0.400, 1.000] | 12.20 [11.30, 13.10] | 27024 [22027, 32333] | 2456 [2456, 2456] | 0.1802 [0.1478, 0.2160] | 0.00 [0.00, 0.00] |
| C+ | 10 | 1.000 [1.000, 1.000] | 5.00 [5.00, 5.00] | 3343 [2122, 4636] | 1338 [1311, 1366] | 0.0197 [0.0148, 0.0248] | 0.00 [0.00, 0.00] |

All dollar figures are **estimated** from tokens, not observed.

## 2. Experiment 1 — does the enrichment close the step gap?

### B+ against B — menu/dialog group

| metric | B mean | B+ mean | paired diff (B+ − B) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 13.20 | 10.50 | -3.49 [-5.29, -1.83] | 35 | **B+ lower** |
| success | 0.743 | 0.725 | 0.086 [-0.029, 0.229] | 35 | no detectable difference at this N |
| model_calls | 13.20 | 10.50 | -3.49 [-5.23, -1.89] | 35 | **B+ lower** |
| cost_usd | 0.1199 | 0.1081 | -0.0315 [-0.0547, -0.0105] | 35 | **B+ lower** |

### B+ against A — menu/dialog group

| metric | A mean | B+ mean | paired diff (B+ − A) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 10.25 | 10.50 | -0.71 [-2.71, 1.26] | 35 | no detectable difference at this N |
| success | 0.725 | 0.725 | 0.143 [-0.029, 0.314] | 35 | no detectable difference at this N |
| model_calls | 10.25 | 10.50 | -0.71 [-2.77, 1.26] | 35 | no detectable difference at this N |
| cost_usd | 0.1006 | 0.1081 | -0.0165 [-0.0472, 0.0142] | 35 | no detectable difference at this N |

### B against A — menu/dialog group

| metric | A mean | B mean | paired diff (B − A) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 10.25 | 13.20 | 2.77 [0.91, 4.57] | 35 | **B higher** |
| success | 0.725 | 0.743 | 0.057 [-0.114, 0.229] | 35 | no detectable difference at this N |
| model_calls | 10.25 | 13.20 | 2.77 [0.89, 4.63] | 35 | **B higher** |
| cost_usd | 0.1006 | 0.1199 | 0.0150 [-0.0178, 0.0466] | 35 | no detectable difference at this N |

### B+ against B — the three round-1 defect tasks

| metric | B mean | B+ mean | paired diff (B+ − B) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 14.00 | 10.25 | -5.67 [-8.60, -2.93] | 15 | **B+ lower** |
| success | 0.600 | 0.450 | 0.000 [-0.200, 0.200] | 15 | no detectable difference at this N |
| model_calls | 14.00 | 10.25 | -5.67 [-8.53, -3.00] | 15 | **B+ lower** |
| cost_usd | 0.1267 | 0.1135 | -0.0574 [-0.0972, -0.0198] | 15 | **B+ lower** |

### B+ against B — control group (no harm test)

| metric | B mean | B+ mean | paired diff (B+ − B) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 10.51 | 9.12 | -1.22 [-2.06, -0.47] | 36 | **B+ lower** |
| success | 0.676 | 0.684 | -0.083 [-0.250, 0.083] | 36 | no detectable difference at this N |
| model_calls | 10.51 | 9.12 | -1.22 [-2.08, -0.50] | 36 | **B+ lower** |
| cost_usd | 0.0989 | 0.0892 | 0.0091 [-0.0056, 0.0248] | 36 | no detectable difference at this N |

### Variance across repetitions — menu/dialog group

Spread within a cell is how underpowered the experiment is, so it is reported rather than smoothed away.

| arm | task | n | mean steps | sd steps | successes |
|---|---|---|---|---|---|
| A | calc_add_row | 10 | 7.8 | 1.9 | 6/10 |
| A | files_rename | 5 | 6.0 | 0.0 | 5/5 |
| A | menu_calc_insert_column | 5 | 12.6 | 0.8 | 5/5 |
| A | menu_files_new_folder | 5 | 19.2 | 1.6 | 2/5 |
| A | menu_replace_all | 5 | 10.4 | 0.5 | 5/5 |
| A | menu_save_as_subdir | 5 | 14.2 | 3.6 | 1/5 |
| A | text_replace | 5 | 4.0 | 0.0 | 5/5 |
| B | calc_add_row | 5 | 16.0 | 0.0 | 1/5 |
| B | files_rename | 5 | 15.0 | 1.3 | 3/5 |
| B | menu_calc_insert_column | 5 | 13.6 | 0.8 | 5/5 |
| B | menu_files_new_folder | 5 | 17.8 | 2.9 | 2/5 |
| B | menu_replace_all | 5 | 10.0 | 0.0 | 5/5 |
| B | menu_save_as_subdir | 5 | 9.0 | 0.0 | 5/5 |
| B | text_replace | 5 | 11.0 | 1.5 | 5/5 |
| B+ | calc_add_row | 10 | 9.4 | 6.6 | 0/10 |
| B+ | files_rename | 5 | 13.2 | 2.1 | 4/5 |
| B+ | menu_calc_insert_column | 5 | 14.6 | 2.3 | 5/5 |
| B+ | menu_files_new_folder | 5 | 11.8 | 4.2 | 5/5 |
| B+ | menu_replace_all | 5 | 9.0 | 0.0 | 5/5 |
| B+ | menu_save_as_subdir | 5 | 7.6 | 0.8 | 5/5 |
| B+ | text_replace | 5 | 9.0 | 0.0 | 5/5 |

## 3. Experiment 2 — ambiguity forces a crop

### C+ against C — the vdelta pair

| metric | C mean | C+ mean | paired diff (C+ − C) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 12.20 | 5.00 | -7.20 [-8.10, -6.30] | 10 | **C+ lower** |
| success | 0.700 | 1.000 | 0.300 [0.000, 0.600] | 10 | no detectable difference at this N |
| model_calls | 12.90 | 5.00 | -7.90 [-9.50, -6.50] | 10 | **C+ lower** |
| cost_usd | 0.1802 | 0.0197 | -0.1605 [-0.1947, -0.1292] | 10 | **C+ lower** |

### B against C+ — the vdelta pair

| metric | C+ mean | B mean | paired diff (B − C+) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 5.00 | 5.00 | 0.00 [0.00, 0.00] | 9 | no detectable difference at this N |
| success | 1.000 | 0.889 | -0.111 [-0.333, 0.000] | 9 | no detectable difference at this N |
| model_calls | 5.00 | 5.00 | 0.00 [0.00, 0.00] | 9 | no detectable difference at this N |
| cost_usd | 0.0197 | 0.0150 | -0.0060 [-0.0107, -0.0016] | 9 | **B lower** |

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

## The image window

| arm | window | runs | peak live images | peak live image tokens | re-anchors | compactions | success |
|---|---|---|---|---|---|---|---|
| B | 2 | 72 | 21.8 | 2,336 | 0.8 | 0.4 | 51/72 |
| B+ | 2 | 97 | 18.5 | 2,166 | 0.7 | 0.2 | 68/97 |
| C | 2 | 10 | 2.0 | 2,456 | 1.0 | 0.0 | 7/10 |
| C+ | 2 | 10 | 6.5 | 1,338 | 0.0 | 0.0 | 10/10 |

## What the enrichment costs

Measured per step inside the observer, and reported whether or not the number is flattering (PREDICTIONS.md §8).

| arm | runs | steps | merge ms/step | blocks ms/step | ambiguity ms/step | reach ms/step | shortcuts ms/step | total ms/step |
|---|---|---|---|---|---|---|---|---|
| B+ | 97 | 940 | 0.09 | 0.04 | 0.04 | 0.31 | 2.41 | 2.88 |
| C+ | 10 | 50 | 0.03 | 0.02 | 0.04 | 0.04 | 0.01 | 0.14 |

Observation tokens, B+ against B, paired on 71 (task, rep) pairs: **+151** [-927, +1,278] against a B mean of 9,613 — **+1.6%**.

## Per task

| task | A succ | B succ | B+ succ | C succ | C+ succ | A steps | B steps | B+ steps | C steps | C+ steps |
|---|---|---|---|---|---|---|---|---|---|---|
| calc_add_row | 6/10 | 1/5 | 0/10 | — | — | 7.8 | 16.0 | 9.4 | — | — |
| calc_count_eng | 0/5 | 0/5 | 1/4 | — | — | 18.0 | 18.0 | 18.0 | — | — |
| calc_total | 5/5 | 4/5 | 3/5 | — | — | 10.0 | 15.6 | 15.2 | — | — |
| cross_report_summary | 0/9 | 0/5 | 1/9 | — | — | 10.8 | 18.0 | 14.1 | — | — |
| files_new_note | 6/9 | 4/4 | 5/10 | — | — | 8.4 | 10.0 | 9.0 | — | — |
| files_rename | 5/5 | 3/5 | 4/5 | — | — | 6.0 | 15.0 | 13.2 | — | — |
| files_save_as | 5/10 | 4/4 | 10/10 | — | — | 5.3 | 6.5 | 6.5 | — | — |
| menu_calc_insert_column | 5/5 | 5/5 | 5/5 | — | — | 12.6 | 13.6 | 14.6 | — | — |
| menu_files_new_folder | 2/5 | 2/5 | 5/5 | — | — | 19.2 | 17.8 | 11.8 | — | — |
| menu_replace_all | 5/5 | 5/5 | 5/5 | — | — | 10.4 | 10.0 | 9.0 | — | — |
| menu_save_as_subdir | 1/5 | 5/5 | 5/5 | — | — | 14.2 | 9.0 | 7.6 | — | — |
| text_replace | 5/5 | 5/5 | 5/5 | — | — | 4.0 | 11.0 | 9.0 | — | — |
| vdelta_bars | 10/10 | 4/5 | 10/10 | 2/5 | 5/5 | 5.0 | 5.0 | 5.0 | 13.2 | 5.0 |
| vdelta_rows | 4/4 | 4/4 | 4/4 | 5/5 | 5/5 | 5.0 | 5.0 | 5.0 | 11.2 | 5.0 |
| visual_badge | 4/4 | 5/5 | 5/5 | — | — | 4.0 | 4.0 | 4.0 | — | — |

