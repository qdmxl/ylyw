#!/usr/bin/env python3
"""Quantify how much the priors changed after excluding H (prior-level leakage)."""
import json
V18 = "/mnt/e/Programming/research_ws/YLYW_ALFWorld/ylyw/alfworld_exp/v18"
full = json.load(open(f"{V18}/train_priors.json", encoding="utf-8"))
held = json.load(open(f"{V18}/train_priors_heldout.json", encoding="utf-8"))

def argmax(d):
    return max(d, key=d.get) if d else None

# process_for_parent-style argmax over clean/heat/cool
def proc_argmax(tbl):
    sub = {k: v for k, v in tbl.items() if k in ("clean", "heat", "cool")}
    return argmax(sub)

flips_proc = []
for parent, ftbl in full.get("process_by_parent", {}).items():
    htbl = held.get("process_by_parent", {}).get(parent, {})
    if proc_argmax(ftbl) != proc_argmax(htbl):
        flips_proc.append((parent, proc_argmax(ftbl), proc_argmax(htbl)))

flips_put = []
for key, ftbl in full.get("putaway_parent_by_proc", {}).items():
    htbl = held.get("putaway_parent_by_proc", {}).get(key, {})
    if argmax(ftbl) != argmax(htbl):
        flips_put.append((key, argmax(ftbl), argmax(htbl)))

flips_look = []
fl = list(full.get("look_object", {}).keys())
hl = list(held.get("look_object", {}).keys())
top5_full, top5_held = fl[:5], hl[:5]

print("=== PRIOR-LEVEL LEAKAGE (full vs heldout) ===")
print("process_by_parent argmax flips:", len(flips_proc))
for f in flips_proc: print("   ", f)
print("putaway_parent_by_proc top-1 flips:", len(flips_put), "/",
      len(full.get("putaway_parent_by_proc", {})))
for f in flips_put[:30]: print("   ", f)
print("look_object top5 full :", top5_full)
print("look_object top5 held :", top5_held)
