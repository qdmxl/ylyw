#!/usr/bin/env python3
"""Step 2: build held-out set H with a FIXED seed, balanced across 6 task types.

Determinism: group by task_type, sort each group by game_file path (stable),
then sample with random.Random(SEED). No global/forbidden RNG.
Records game_file paths (robust to index reordering) + current indices.
"""
import json, random

SEED = 20260723
PER_TYPE = 42          # 42 * 6 = 252 ~ target 250
V18 = "/mnt/e/Programming/research_ws/YLYW_ALFWorld/ylyw/alfworld_exp/v18"

idx = json.load(open(f"{V18}/train_index.json", encoding="utf-8"))
records = idx["records"]

by_type = {}
for r in records:
    by_type.setdefault(r["task_type"], []).append(r)

rng = random.Random(SEED)
selected = []
for tt in sorted(by_type):                     # deterministic type order
    group = sorted(by_type[tt], key=lambda r: r["game_file"])  # deterministic
    k = min(PER_TYPE, len(group))
    picks = rng.sample(group, k)               # seeded, reproducible
    selected.extend(picks)

selected_sorted = sorted(selected, key=lambda r: r["idx"])
from collections import Counter
dist = Counter(r["task_type"] for r in selected_sorted)

out = {
    "seed": SEED,
    "per_type_target": PER_TYPE,
    "n_selected": len(selected_sorted),
    "task_type_dist": dict(dist),
    "split": "train",
    "selection_method": "random.Random(20260723).sample per task_type over "
                        "game_file-sorted groups; recorded by game_file path + idx",
    "games": selected_sorted,
}
outp = f"{V18}/heldout_games.json"
json.dump(out, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("n_selected:", len(selected_sorted))
print("dist:", dict(dist))
print("indices:", ",".join(str(r["idx"]) for r in selected_sorted))
print("WROTE", outp)
