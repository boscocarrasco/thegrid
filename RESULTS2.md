# RESULTS2 — round 2, generated from results/raw2/

Every table in this file is produced by `analysis/aggregate2.py` from the raw run records. Nothing here is typed by hand.

- usable runs: **235**
- excluded (rate limit, harness or model error): 2 — of which 2 rate-limited
- total time spent waiting out provider rate limits: 168.5 min
- **estimated** cost of the usable runs: $25.44 — computed from token counts and the published rate, not observed spend; this runs on a subscription and there is no bill to read

## 1. Headline, by arm

| Arm | n | success | steps | fresh tokens | image tokens | est. $ | grounding fails |
|---|---|---|---|---|---|---|---|
| A | 71 | 0.775 [0.676, 0.873] | 10.14 [8.93, 11.38] | 23569 [19365, 27631] | 12453 [10966, 13958] | 0.1024 [0.0845, 0.1206] | 0.45 [0.25, 0.68] |
| B | 72 | 0.708 [0.597, 0.819] | 11.82 [10.65, 12.96] | 18160 [14823, 21737] | 2784 [2548, 3012] | 0.1091 [0.0885, 0.1302] | 0.00 [0.00, 0.00] |
| B+ | 72 | 0.806 [0.708, 0.889] | 10.71 [9.62, 11.83] | 19846 [15562, 24429] | 2632 [2405, 2850] | 0.1155 [0.0911, 0.1418] | 0.00 [0.00, 0.00] |
| C | 10 | 0.700 [0.400, 1.000] | 12.20 [11.30, 13.10] | 27024 [22132, 32243] | 2456 [2456, 2456] | 0.1802 [0.1474, 0.2166] | 0.00 [0.00, 0.00] |
| C+ | 10 | 1.000 [1.000, 1.000] | 5.00 [5.00, 5.00] | 3343 [2123, 4642] | 1338 [1311, 1366] | 0.0197 [0.0148, 0.0248] | 0.00 [0.00, 0.00] |

All dollar figures are **estimated** from tokens, not observed.

## 2. Experiment 1 — does the enrichment close the step gap?

### B+ against B — menu/dialog group

| metric | B mean | B+ mean | paired diff (B+ − B) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 13.20 | 11.60 | -1.60 [-2.71, -0.57] | 35 | **B+ lower** |
| success | 0.743 | 0.829 | 0.086 [-0.029, 0.200] | 35 | no detectable difference at this N |
| model_calls | 13.20 | 11.60 | -1.60 [-2.71, -0.57] | 35 | **B+ lower** |
| cost_usd | 0.1199 | 0.1157 | -0.0042 [-0.0199, 0.0102] | 35 | no detectable difference at this N |

### B+ against A — menu/dialog group

| metric | A mean | B+ mean | paired diff (B+ − A) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 10.77 | 11.60 | 0.83 [-1.34, 2.86] | 35 | no detectable difference at this N |
| success | 0.800 | 0.829 | 0.029 [-0.171, 0.229] | 35 | no detectable difference at this N |
| model_calls | 10.77 | 11.60 | 0.83 [-1.37, 2.91] | 35 | no detectable difference at this N |
| cost_usd | 0.1095 | 0.1157 | 0.0062 [-0.0320, 0.0434] | 35 | no detectable difference at this N |

### B against A — menu/dialog group

| metric | A mean | B mean | paired diff (B − A) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 10.77 | 13.20 | 2.43 [0.63, 4.14] | 35 | **B higher** |
| success | 0.800 | 0.743 | -0.057 [-0.229, 0.143] | 35 | no detectable difference at this N |
| model_calls | 10.77 | 13.20 | 2.43 [0.66, 4.17] | 35 | **B higher** |
| cost_usd | 0.1095 | 0.1199 | 0.0104 [-0.0201, 0.0397] | 35 | no detectable difference at this N |

### B+ against B — the three round-1 defect tasks

| metric | B mean | B+ mean | paired diff (B+ − B) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 14.00 | 12.73 | -1.27 [-2.33, -0.40] | 15 | **B+ lower** |
| success | 0.600 | 0.600 | 0.000 [-0.200, 0.200] | 15 | no detectable difference at this N |
| model_calls | 14.00 | 12.73 | -1.27 [-2.33, -0.40] | 15 | **B+ lower** |
| cost_usd | 0.1267 | 0.1330 | 0.0063 [-0.0121, 0.0241] | 15 | no detectable difference at this N |

### B+ against B — control group (no harm test)

| metric | B mean | B+ mean | paired diff (B+ − B) | pairs | verdict |
|---|---|---|---|---|---|
| steps | 10.51 | 9.86 | -0.11 [-0.40, 0.11] | 35 | no detectable difference at this N |
| success | 0.676 | 0.784 | 0.057 [-0.086, 0.200] | 35 | no detectable difference at this N |
| model_calls | 10.51 | 9.86 | -0.11 [-0.40, 0.11] | 35 | no detectable difference at this N |
| cost_usd | 0.0989 | 0.1153 | 0.0237 [0.0112, 0.0374] | 35 | **B+ higher** |

### Variance across repetitions — menu/dialog group

Spread within a cell is how underpowered the experiment is, so it is reported rather than smoothed away.

| arm | task | n | mean steps | sd steps | successes |
|---|---|---|---|---|---|
| A | calc_add_row | 5 | 9.0 | 0.0 | 5/5 |
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
| B+ | calc_add_row | 5 | 16.0 | 0.0 | 0/5 |
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
| cost_usd | 0.0197 | 0.0150 | -0.0060 [-0.0109, -0.0016] | 9 | **B lower** |

## Which ambiguity rule fired

The registered prediction (P2.2) is about the same-name rule from §5.2 of the design document. The peer-set rule was added after reading the tree and before running anything, and is the weaker claim. They are counted separately so a result is never credited to the rule that did not fire.

| arm | task | runs | crops forced by ambiguity | same-name | peer-set |
|---|---|---|---|---|---|
| C+ | vdelta_bars | 5 | 25 | 0 | 25 |
| C+ | vdelta_rows | 5 | 30 | 0 | 30 |

## Budget sweep

**Not run.** No runs in `results/raw2/` carry an enforced token budget. The question is not answered this round and no post-hoc reclassification is substituted for it: round 1 showed the two give different answers.

## The image window

| arm | window | runs | peak live images | peak live image tokens | re-anchors | compactions | success |
|---|---|---|---|---|---|---|---|
| B | 2 | 72 | 21.8 | 2,336 | 0.8 | 0.4 | 51/72 |
| B+ | 2 | 72 | 21.8 | 2,285 | 0.7 | 0.3 | 58/72 |
| C | 2 | 10 | 2.0 | 2,456 | 1.0 | 0.0 | 7/10 |
| C+ | 2 | 10 | 6.5 | 1,338 | 0.0 | 0.0 | 10/10 |

## What the enrichment costs

Measured per step inside the observer, and reported whether or not the number is flattering (PREDICTIONS.md §8).

| arm | runs | steps | merge ms/step | blocks ms/step | ambiguity ms/step | reach ms/step | shortcuts ms/step | total ms/step |
|---|---|---|---|---|---|---|---|---|
| B+ | 72 | 771 | 0.11 | 0.04 | 0.04 | 0.34 | 2.25 | 2.78 |
| C+ | 10 | 50 | 0.03 | 0.02 | 0.04 | 0.04 | 0.01 | 0.14 |

Observation tokens, B+ against B, paired on 70 (task, rep) pairs: **+1,850** [+956, +2,817] against a B mean of 9,613 — **+19.2%**.

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
| menu_replace_all | 5/5 | 5/5 | 5/5 | — | — | 10.4 | 10.0 | 9.0 | — | — |
| menu_save_as_subdir | 1/5 | 5/5 | 5/5 | — | — | 14.2 | 9.0 | 7.6 | — | — |
| text_replace | 5/5 | 5/5 | 5/5 | — | — | 4.0 | 11.0 | 9.0 | — | — |
| vdelta_bars | 5/5 | 4/5 | 5/5 | 2/5 | 5/5 | 5.0 | 5.0 | 5.0 | 13.2 | 5.0 |
| vdelta_rows | 4/4 | 4/4 | 4/4 | 5/5 | 5/5 | 5.0 | 5.0 | 5.0 | 11.2 | 5.0 |
| visual_badge | 4/4 | 5/5 | 5/5 | — | — | 4.0 | 4.0 | 4.0 | — | — |

