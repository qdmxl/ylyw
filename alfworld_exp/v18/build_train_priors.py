#!/usr/bin/env python3
"""build_train_priors.py — scan the ALFWORLD *train* split traj_data.json files
and produce v18/train_priors.json (spec fixes #5 / #6).

TRAIN-split labels are allowed (they are the training set). We aggregate:
  * process_by_parent : P(process | parent_target)  — process ∈ {none,clean,heat,cool}
  * process_by_object : P(process | object_target)
  * putaway_parent    : for (object_target) -> most common parent_target
  * putaway_parent_by_proc : (object_target, process) -> parent distribution
  * look_object       : distribution of object_target for look_at (toggle=DeskLamp)
Only counts; downstream code decides thresholds.
"""
import os, json, glob, argparse
from pathlib import Path
from collections import defaultdict, Counter

TRAIN_GLOB = os.path.expanduser("~/.cache/alfworld/json_2.1.1/train/*/*/traj_data.json")

# --- optional held-out exclusion (spec: rebuild priors on train\H, no leakage) ---
_ap = argparse.ArgumentParser()
_ap.add_argument("--exclude", default="",
                 help="path to heldout_games.json; its game_file trajectories are "
                      "EXCLUDED from the prior counts (strict isolation).")
_ap.add_argument("--output", default="",
                 help="output json path (default: v18/train_priors.json)")
_args, _ = _ap.parse_known_args()

_EXCLUDE = set()
if _args.exclude:
    _h = json.load(open(_args.exclude, encoding="utf-8"))
    for _g in _h.get("games", []):
        _tp = str(Path(_g["game_file"]).parent / "traj_data.json")
        _EXCLUDE.add(os.path.realpath(_tp))
    print(f"[exclude] {len(_EXCLUDE)} held-out trajectories will be excluded")

TASK_PROCESS = {
    "pick_and_place_simple": "none",
    "pick_two_obj_and_place": "none",
    "pick_clean_then_place_in_recep": "clean",
    "pick_heat_then_place_in_recep": "heat",
    "pick_cool_then_place_in_recep": "cool",
    "look_at_obj_in_light": "examine",
}

proc_by_parent = defaultdict(Counter)
proc_by_object = defaultdict(Counter)
putaway_parent = defaultdict(Counter)
putaway_parent_by_proc = defaultdict(Counter)
look_object = Counter()
parent_by_object_proc = defaultdict(Counter)

files = glob.glob(TRAIN_GLOB)
n = 0
n_excluded = 0
for fp in files:
    if _EXCLUDE and os.path.realpath(fp) in _EXCLUDE:
        n_excluded += 1
        continue
    try:
        td = json.load(open(fp))
    except Exception:
        continue
    tt = td.get("task_type", "")
    proc = TASK_PROCESS.get(tt)
    if proc is None:
        continue
    p = td.get("pddl_params", {})
    obj = (p.get("object_target") or "").lower()
    parent = (p.get("parent_target") or "").lower()
    n += 1
    if proc == "examine":
        if obj:
            look_object[obj] += 1
        continue
    if parent:
        proc_by_parent[parent][proc] += 1
    if obj:
        proc_by_object[obj][proc] += 1
        if parent:
            putaway_parent[obj][parent] += 1
            putaway_parent_by_proc[f"{obj}|{proc}"][parent] += 1
            parent_by_object_proc[f"{obj}|{proc}"][parent] += 1

def top(counter, k=6):
    return dict(counter.most_common(k))

out = {
    "_meta": {"n_train_games": n, "n_files": len(files),
              "n_excluded_heldout": n_excluded,
              "exclude_source": _args.exclude or None},
    "process_by_parent": {k: top(v) for k, v in proc_by_parent.items()},
    "process_by_object": {k: top(v) for k, v in proc_by_object.items()},
    "putaway_parent": {k: top(v) for k, v in putaway_parent.items()},
    "putaway_parent_by_proc": {k: top(v) for k, v in putaway_parent_by_proc.items()},
    "look_object": top(look_object, 20),
}
outpath = _args.output or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "train_priors.json")
json.dump(out, open(outpath, "w"), ensure_ascii=False, indent=2)
print("train games:", n, "files:", len(files), "excluded:", n_excluded, "->", outpath)
print("look_object:", top(look_object, 12))
print("process_by_parent[microwave]:", top(proc_by_parent["microwave"]))
print("process_by_parent[fridge]:", top(proc_by_parent["fridge"]))
print("process_by_parent[garbagecan]:", top(proc_by_parent["garbagecan"]))
print("putaway spatula|clean:", top(putaway_parent_by_proc["spatula|clean"]))
print("putaway mug|cool:", top(putaway_parent_by_proc["mug|cool"]))
print("putaway tomato|cool:", top(putaway_parent_by_proc["tomato|cool"]))
print("putaway potato|cool:", top(putaway_parent_by_proc["potato|cool"]))
