#!/usr/bin/env python3
"""parse_check.py — compare goal_parser output to GT for a split, cross-ref with
current won status to flag potential parse regressions on currently-passing games."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from goal_parser import parse_goal

PROC = {"pick_clean_then_place_in_recep": "clean",
        "pick_heat_then_place_in_recep": "heat",
        "pick_cool_then_place_in_recep": "cool"}

def check(gt_path, res_path, label):
    gt = json.load(open(gt_path))
    won = {}
    if os.path.exists(res_path):
        d = json.load(open(res_path))
        won = {r["game_idx"]: r["won"] for r in d["results"]}
    miss_on_won = []
    miss_total = 0
    for k, g in gt.items():
        i = int(k)
        pg = parse_goal(g["desc"])
        tt = g["task_type"]
        ok_o = (tt == "look_at_obj_in_light") or (g["object"] in (pg.object_classes or []))
        avail = pg.recep_classes or ([pg.recep_class] if pg.recep_class else [])
        ok_r = (tt == "look_at_obj_in_light") or (g["parent"] in avail)
        ok_p = True if tt == "look_at_obj_in_light" else (PROC.get(tt) == pg.process)
        if not (ok_o and ok_r and ok_p):
            miss_total += 1
            flags = "".join(["" if ok_o else "O", "" if ok_r else "R", "" if ok_p else "P"])
            if won.get(i):   # currently-passing but now parse-miss = regression risk
                miss_on_won.append((i, flags, g["desc"][:55]))
    print(f"[{label}] parse-miss total={miss_total}/{len(gt)}; "
          f"miss on currently-WON games={len(miss_on_won)}")
    for i, f, desc in sorted(miss_on_won):
        pg = parse_goal(gt[str(i)]["desc"])
        print(f"   WON[{i}] miss={f} gt(o={gt[str(i)]['object']},r={gt[str(i)]['parent']}) "
              f"parsed(o={pg.object_classes},r={pg.recep_classes or pg.recep_class},p={pg.process}) :: {desc}")

check("gt_seen.json", "results_seen_v181.json", "seen")
print()
check("gt_unseen.json", "results_unseen_v181.json", "unseen")
