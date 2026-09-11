#!/usr/bin/env bash
# Run every round-2 tier that has not run yet, in the tier order frozen in
# PREDICTIONS.md §11, under one global estimated-spend guard.
#
# Each tier writes to its own tag, and `already_done()` in the runner skips
# records that completed, so re-entering a tier resumes it rather than
# duplicating it. The guard is global because --max-usd is per-tag: without it,
# four tiers each stopping at 85% of $80 would spend far more than $80.
set -u
cd "$(dirname "$0")/.."
source /tmp/grid-env/env.sh
PY=/usr/bin/python3.12
OUT=results/raw2
LOG=${GRID_LOG:-/tmp/round2}
mkdir -p "$OUT" "$LOG"

CAP=${GRID_SPEND_CAP:-68}          # 85% of the $80 estimated-spend budget
MENU="text_replace,calc_add_row,files_rename,menu_replace_all,menu_save_as_subdir,menu_calc_insert_column,menu_files_new_folder"
CONTROL="files_new_note,files_save_as,text_append,text_delete_line,text_uppercase,calc_total,calc_count_eng,web_form,visual_chart,visual_shapes,visual_badge,cross_report_summary,cross_inventory_note,vdelta_rows,vdelta_bars"
SWEEP10="files_new_note,cross_report_summary,calc_add_row,vdelta_bars,files_save_as,files_rename,calc_count_eng,vdelta_rows,menu_replace_all,menu_files_new_folder"
LONG4="long_march_export,long_notes_digest,long_ledger_edits,long_region_transfer"

spent() {  # total estimated spend across every round-2 record
  $PY - <<'EOF'
import json, glob
t = 0.0
for f in glob.glob("results/raw2/*.jsonl"):
    for ln in open(f):
        try:
            t += json.loads(ln).get("cost_usd", 0) or 0
        except Exception:
            pass
print(f"{t:.2f}")
EOF
}

guard() {  # stop the whole driver once the global cap is reached
  local s; s=$(spent)
  if (( $(echo "$s >= $CAP" | bc -l) )); then
    echo "=== STOP: estimated spend \$$s has reached the \$$CAP cap; not starting $1" \
      | tee -a "$LOG/finish.log"
    return 1
  fi
  echo "=== $1 (estimated spend so far \$$s of \$$CAP) ===" | tee -a "$LOG/finish.log"
  return 0
}

revive() {  # the X server and the AT-SPI bus have died mid-round before
  if $PY -c 'import sys; sys.path.insert(0,"."); from runner.experiment import desktop_alive; sys.exit(0 if desktop_alive() else 1)'; then
    return 0
  fi
  echo "    desktop is down; restarting it" | tee -a "$LOG/finish.log"
  bash scripts/env_up.sh >>"$LOG/envup.log" 2>&1
  source /tmp/grid-env/env.sh
  sleep 5
  $PY -c 'import sys; sys.path.insert(0,"."); from runner.experiment import desktop_alive; sys.exit(0 if desktop_alive() else 1)'
}

run() {  # run <tag> <extra args...>
  local tag=$1; shift
  guard "$tag" || return 1
  # --max-usd is per-tag and the runner stops at 85% of it, so translate the
  # global cap into this tag's own allowance: what the tag has already spent,
  # plus whatever is left globally, grossed up by the 0.85 the runner applies.
  local lim
  lim=$($PY - "$tag" "$CAP" <<'EOF'
import json, glob, os, sys
tag, cap = sys.argv[1], float(sys.argv[2])
total = mine = 0.0
for f in glob.glob("results/raw2/*.jsonl"):
    for ln in open(f):
        try:
            c = json.loads(ln).get("cost_usd", 0) or 0
        except Exception:
            continue
        total += c
        if os.path.basename(f) == tag + ".jsonl":
            mine += c
print(f"{(mine + max(cap - total, 0.0)) / 0.85:.2f}")
EOF
)
  echo "    per-tag allowance \$$lim" | tee -a "$LOG/finish.log"
  # The runner stops cleanly when the desktop dies rather than recording
  # fiction, so a tier can end early through no fault of the plan. Revive the
  # desktop and resume the same tag — already_done() makes that cheap — but
  # only a bounded number of times, so a permanently broken environment does
  # not spin here forever.
  local attempt
  for attempt in 1 2 3; do
    revive || { echo "    desktop will not come back; giving up on $tag" \
                  | tee -a "$LOG/finish.log"; return 1; }
    $PY runner/experiment.py --tag "$tag" --model sonnet --out "$OUT" \
        --max-usd "$lim" --rate-limit-wait 60 "$@" 2>&1 | tee -a "$LOG/$tag.log"
    if ! grep -q "desktop is not alive" <(tail -40 "$LOG/$tag.log"); then
      return 0
    fi
    echo "    $tag stopped on a dead desktop (attempt $attempt); resuming" \
      | tee -a "$LOG/finish.log"
  done
  return 0
}

# The order below is the one frozen in PREDICTIONS.md §11 — T3, T4, T5, T6 —
# not the order that looks most interesting now that some results exist.
# Reordering tiers after seeing data is how a budget cut turns into a choice
# about which answer to keep.

# T3 — Experiment 1 control, the fifteen-task group rather than the
#      pre-registered eight-task reduction that wall clock forced.
run t3_control --arms A,B,B+ --tasks "$CONTROL" --reps 5 || exit 0

# T4 — Experiment 4: the image window and the persistent task object on long
#      tasks. The only experiment of the four with no data at all.
run t4_long_full   --arms B+ --tasks "$LONG4" --reps 5 \
                   --image-window 2 --task-object on || exit 0
run t4_long_wide   --arms B+ --tasks "$LONG4" --reps 5 \
                   --image-window 4 --task-object on || exit 0
run t4_long_notobj --arms B+ --tasks "$LONG4" --reps 5 \
                   --image-window 2 --task-object off || exit 0
run t4_long_base   --arms A  --tasks "$LONG4" --reps 5 || exit 0

# T5 — the two endpoint ceilings, widened from the five tasks they managed to
#      the ten the ordering registers. The middle ceiling (15,000) already ran
#      on all ten, so all three finally cover the same task set.
run t5_budget_8k  --arms A,B+ --tasks "$SWEEP10" --reps 5 \
                  --token-budget 8000  --step-mult 2 || exit 0
run t5_budget_30k --arms A,B+ --tasks "$SWEEP10" --reps 5 \
                  --token-budget 30000 --step-mult 2 || exit 0

# T6 — the ablation, conditional on P1.1, which held in direction.
run t6_ablation --arms B+nb,B+nr,B+nk --tasks "$MENU" --reps 5 || exit 0

echo "=== ALL TIERS ATTEMPTED (estimated spend \$$(spent)) ===" | tee -a "$LOG/finish.log"
