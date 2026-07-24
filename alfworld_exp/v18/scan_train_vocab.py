#!/usr/bin/env python3
"""scan_train_vocab.py — scan ALFWORLD train split task_desc annotations, compare
what goal_parser extracts against the PDDL ground truth (object_target /
parent_target), and surface systematic vocabulary / destination gaps.

Train-split PDDL labels are a permitted offline data source. Output is aggregate
miss statistics (NL phrase -> gt class) used to expand the general dictionaries.
"""
import os, re, json, glob, sys
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from goal_parser import parse_goal

TRAIN_GLOB = os.path.expanduser("~/.cache/alfworld/json_2.1.1/train/*/*/traj_data.json")

PROC_TASKS = {
    "pick_clean_then_place_in_recep": "clean",
    "pick_heat_then_place_in_recep": "heat",
    "pick_cool_then_place_in_recep": "cool",
}

def norm(s):
    return (s or "").lower()

obj_miss = Counter()          # (gt_obj) -> count of task_descs where obj not recovered
obj_miss_examples = defaultdict(list)
recep_miss = Counter()        # (gt_parent) -> count
recep_miss_examples = defaultdict(list)
proc_miss = Counter()         # (gt_proc, parsed_proc) -> count
proc_miss_examples = defaultdict(list)

n_games = 0
n_anns = 0
files = glob.glob(TRAIN_GLOB)
for fp in files:
    try:
        td = json.load(open(fp))
    except Exception:
        continue
    tt = td.get("task_type", "")
    if tt not in ("pick_and_place_simple", "pick_two_obj_and_place",
                  "pick_clean_then_place_in_recep", "pick_heat_then_place_in_recep",
                  "pick_cool_then_place_in_recep", "look_at_obj_in_light"):
        continue
    p = td.get("pddl_params", {})
    gt_obj = norm(p.get("object_target"))
    gt_parent = norm(p.get("parent_target"))
    gt_proc = PROC_TASKS.get(tt)
    n_games += 1
    for ann in td.get("turk_annotations", {}).get("anns", []):
        desc = ann.get("task_desc", "")
        if not desc or len(desc) < 5:
            continue
        n_anns += 1
        try:
            g = parse_goal(desc)
        except Exception:
            continue
        # object recovery: is gt in the ambiguity-expanded candidate list?
        if gt_obj and gt_obj not in (g.object_classes or []):
            obj_miss[gt_obj] += 1
            if len(obj_miss_examples[gt_obj]) < 6:
                obj_miss_examples[gt_obj].append((desc[:80], g.object_class))
        # destination recovery (only for non-look, non-process where parent is a
        # genuine placement target; process tasks' parent is also the dest)
        if tt != "look_at_obj_in_light" and gt_parent:
            avail = g.recep_classes or ([g.recep_class] if g.recep_class else [])
            if gt_parent not in avail:
                recep_miss[gt_parent] += 1
                if len(recep_miss_examples[gt_parent]) < 6:
                    recep_miss_examples[gt_parent].append((desc[:80], g.recep_class))
        # process recovery
        if gt_proc and g.process != gt_proc:
            proc_miss[(gt_proc, g.process)] += 1
            if len(proc_miss_examples[(gt_proc, g.process)]) < 8:
                proc_miss_examples[(gt_proc, g.process)].append(desc[:90])

print(f"games={n_games} anns={n_anns} files={len(files)}")
print("\n===== OBJECT MISSES (gt object never in candidate list) =====")
for obj, c in obj_miss.most_common(40):
    print(f"  {obj:20s} x{c}")
    for ex, parsed in obj_miss_examples[obj][:3]:
        print(f"       parsed={parsed!s:16s} :: {ex}")

print("\n===== DESTINATION MISSES (gt parent never in dest list) =====")
for r, c in recep_miss.most_common(40):
    print(f"  {r:20s} x{c}")
    for ex, parsed in recep_miss_examples[r][:3]:
        print(f"       parsed={parsed!s:16s} :: {ex}")

print("\n===== PROCESS MISSES (gt_proc -> parsed_proc) =====")
for (gt, pr), c in proc_miss.most_common(30):
    print(f"  {gt} -> {pr}  x{c}")
    for ex in proc_miss_examples[(gt, pr)][:4]:
        print(f"       :: {ex}")
