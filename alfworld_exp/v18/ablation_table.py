#!/usr/bin/env python3
"""ablation_table.py — summarize the v18.2 ablation four-set on both splits."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))

FILES = {
    ("full", "valid_seen"): "results_seen_v182.json",
    ("full", "valid_unseen"): "results_unseen_v182.json",
}
for mode in ("linear", "perm", "fixed_yao"):
    for split in ("valid_seen", "valid_unseen"):
        FILES[(mode, split)] = f"abl_{mode}_{split}_v182.json"

def load(fn):
    p = os.path.join(HERE, fn)
    if not os.path.exists(p):
        return None
    d = json.load(open(p, encoding="utf-8"))
    return d

print(f"{'mode':10s} {'seen':>12s} {'unseen':>12s}")
for mode in ("full", "linear", "perm", "fixed_yao"):
    row = f"{mode:10s}"
    for split in ("valid_seen", "valid_unseen"):
        d = load(FILES[(mode, split)])
        if d is None:
            row += f" {'--':>12s}"
        else:
            row += f" {d['n_won']:>3d}/{d['n_total']:<3d}={d['success_rate']*100:4.1f}%"
    print(row)

# L3 contribution = full - linear
print("\nPer-type (full):")
for split in ("valid_seen", "valid_unseen"):
    d = load(FILES[("full", split)])
    if d:
        print(f"  {split}: " + " ".join(f"{k.split('_')[1][:4]}={v['won']}/{v['total']}"
                                        for k, v in d["by_type"].items()))
