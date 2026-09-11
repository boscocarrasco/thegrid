#!/usr/bin/env bash
# Round-2 experiment tiers, in the priority order fixed in PREDICTIONS.md §11.
#
# The order is the point. The full plan is ~16.8 h against a 10 h budget, which
# PREDICTIONS.md says up front rather than discovering at hour nine, so the
# order in which things get cut was decided before any data existed. T1 and T2
# carry the two predictions that can most cleanly fail and therefore run first,
# even though T5 answers a question REPORT2.md is required to address.
#
#   bash scripts/round2.sh t1        run one tier
#   bash scripts/round2.sh t1 t2     run several, in order
set -u
cd "$(dirname "$0")/.."
source /tmp/grid-env/env.sh
PY=/usr/bin/python3.12
OUT=results/raw2
LOG=${GRID_LOG:-/tmp/round2}
mkdir -p "$OUT" "$LOG"

MENU="text_replace,calc_add_row,files_rename,menu_replace_all,menu_save_as_subdir,menu_calc_insert_column,menu_files_new_folder"
CONTROL="files_new_note,files_save_as,text_append,text_delete_line,text_uppercase,calc_total,calc_count_eng,web_form,visual_chart,visual_shapes,visual_badge,cross_report_summary,cross_inventory_note,vdelta_rows,vdelta_bars"
CONTROL8="files_new_note,cross_report_summary,vdelta_bars,files_save_as,calc_count_eng,vdelta_rows,calc_total,visual_badge"
VDELTA="vdelta_rows,vdelta_bars"
SWEEP10="files_new_note,cross_report_summary,calc_add_row,vdelta_bars,files_save_as,files_rename,calc_count_eng,vdelta_rows,menu_replace_all,menu_files_new_folder"
LONG4="long_march_export,long_notes_digest,long_ledger_edits,long_region_transfer"

COMMON="--model sonnet --out $OUT --max-usd ${MAX_ESTIMATED_SPEND_USD:-80} --rate-limit-wait 60"

run() {  # run <tag> <extra args...>
  local tag=$1; shift
  echo "=== $tag ==="
  $PY runner/experiment.py --tag "$tag" $COMMON "$@" 2>&1 | tee -a "$LOG/$tag.log"
}

for tier in "$@"; do
case "$tier" in
  t1)  # Experiment 1 core: the menu/dialog group, where the defect lives
       run t1_menu --arms A,B,B+ --tasks "$MENU" --reps 5 ;;
  t2)  # Experiment 2: the cleanest falsifiable prediction
       run t2_vdelta --arms C,C+ --tasks "$VDELTA" --reps 5 ;;
  t3)  # Experiment 1 control: does the enrichment cost anything elsewhere
       run t3_control --arms A,B,B+ --tasks "$CONTROL" --reps 5 ;;
  t3r) # the pre-registered reduction of t3, if wall clock forces it
       run t3_control --arms A,B,B+ --tasks "$CONTROL8" --reps 5 ;;
  t4)  # Experiment 4: image window and persistent task object on long tasks
       run t4_long_full   --arms B+ --tasks "$LONG4" --reps 5 \
                          --image-window 2 --task-object on
       run t4_long_wide   --arms B+ --tasks "$LONG4" --reps 5 \
                          --image-window 4 --task-object on
       run t4_long_notobj --arms B+ --tasks "$LONG4" --reps 5 \
                          --image-window 2 --task-object off
       run t4_long_base   --arms A  --tasks "$LONG4" --reps 5 ;;
  t5)  # Experiment 3: the budget sweep, enforced, endpoints first so a
       # partial sweep still brackets the crossing
       run t5_budget_8k  --arms A,B+ --tasks "$SWEEP10" --reps 5 \
                         --token-budget 8000  --step-mult 2
       run t5_budget_30k --arms A,B+ --tasks "$SWEEP10" --reps 5 \
                         --token-budget 30000 --step-mult 2
       run t5_budget_15k --arms A,B+ --tasks "$SWEEP10" --reps 5 \
                         --token-budget 15000 --step-mult 2 ;;
  t6)  # Ablation — only if P1.1 held. Menu group only.
       run t6_ablation --arms B+nb,B+nr,B+nk --tasks "$MENU" --reps 5 ;;
  *)   echo "unknown tier: $tier" >&2 ;;
esac
done
