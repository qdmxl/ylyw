#!/bin/bash
# run_ablations.sh — v18.2 ablation four-set (full/linear/perm/fixed_yao) on both
# splits. 'full' is produced by the main eval; this fills in the other three modes.
set -e
cd /mnt/e/Programming/research_ws/YLYW_ALFWorld/ylyw/alfworld_exp/v18
for mode in linear perm fixed_yao; do
  for split in valid_seen valid_unseen; do
    end=140; [ "$split" = "valid_unseen" ] && end=134
    echo "=== $mode $split ==="
    python run_v18_eval.py --split $split --start 0 --end $end \
        --ablation $mode --output abl_${mode}_${split}_v182.json \
        > abl_${mode}_${split}_v182.log 2>&1
    tail -1 abl_${mode}_${split}_v182.log
  done
done
echo ABLATIONS_DONE
