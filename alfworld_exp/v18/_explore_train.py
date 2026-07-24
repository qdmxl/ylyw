#!/usr/bin/env python3
"""Step 1: explore the train split; dump ordered index for reproducible H build."""
import os, sys, json
from collections import Counter
sys.path.insert(0, "/mnt/e/Programming/research_ws/YLYW_ALFWorld/ylyw/alfworld_exp")
os.environ.setdefault("ALFWORLD_DATA", os.path.expanduser("~/.cache/alfworld"))
from alfworld_official_wrapper import ALFWorldOfficial

env = ALFWorldOfficial(split="train")
n = env.num_games
print("NUM_GAMES:", n)

# task type distribution + ordered index list
idx_records = []
tt_counter = Counter()
for idx in range(n):
    td = env._traj_cache.get(idx)
    tt = td.get("task_type", "unknown") if td else "MISSING_TRAJ"
    tt_counter[tt] += 1
    gf = env.games[idx]
    idx_records.append({"idx": idx, "game_file": gf, "task_type": tt})

print("TASK_TYPE_DISTRIBUTION:")
for k, v in sorted(tt_counter.items()):
    print(f"   {k:40s} {v}")

# dump ordered index for reproducible selection
outp = "/mnt/e/Programming/research_ws/YLYW_ALFWorld/ylyw/alfworld_exp/v18/train_index.json"
with open(outp, "w", encoding="utf-8") as f:
    json.dump({"num_games": n, "task_type_dist": dict(tt_counter),
               "records": idx_records}, f, ensure_ascii=False, indent=2)
print("WROTE", outp)

# confirm reset + won signal path on a couple of games
for gi in (0, 1):
    obs, info = env.reset(game_idx=gi)
    print(f"\n--- reset game {gi} ---")
    print("  task_type:", info.get("task_type"))
    print("  task_desc:", (info.get("task_desc") or "")[:90])
    print("  won:", info.get("won"), "| done:", info.get("done"))
    print("  n_admissible:", len(info.get("admissible_commands", [])))
    print("  admissible[:4]:", info.get("admissible_commands", [])[:4])
