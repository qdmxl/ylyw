#!/usr/bin/env python3
"""Step 6/7: compare heldout results (excl vs full priors) + failure attribution."""
import json, os
from pathlib import Path
from collections import Counter
V18 = "/mnt/e/Programming/research_ws/YLYW_ALFWorld/ylyw/alfworld_exp/v18"

excl = json.load(open(f"{V18}/heldout_results_excl.json", encoding="utf-8"))
full = json.load(open(f"{V18}/heldout_results_full.json", encoding="utf-8"))
idx = json.load(open(f"{V18}/train_index.json", encoding="utf-8"))
idx2gf = {r["idx"]: r["game_file"] for r in idx["records"]}

def summarize(res, name):
    R = res["results"]
    n = len(R); w = sum(1 for r in R if r["won"])
    by = {}
    for r in R:
        t = r.get("task_type_real", "?")
        by.setdefault(t, [0, 0]); by[t][1] += 1
        if r["won"]: by[t][0] += 1
    print(f"\n=== {name}: {w}/{n} = {100*w/n:.1f}% ===")
    for t in sorted(by):
        a, b = by[t]
        print(f"   {t:34s} {a}/{b} = {100*a/b:.0f}%")
    return {r["game_idx"]: r for r in R}, w, n

mE, wE, nE = summarize(excl, "HELD-OUT (excl-H priors)  [CORE]")
mF, wF, nF = summarize(full, "HELD-OUT (full priors, control)")

print(f"\n=== PRIOR-LEAKAGE IMPACT ===")
print(f"excl-H: {wE}/{nE} = {100*wE/nE:.1f}%   |   full: {wF}/{nF} = {100*wF/nF:.1f}%   "
      f"delta = {100*(wF-wE)/nE:+.1f} pp")
flipped = []
for gi in sorted(mE):
    if gi in mF and mE[gi]["won"] != mF[gi]["won"]:
        flipped.append((gi, mE[gi]["won"], mF[gi]["won"]))
print(f"per-game won-status flips (excl vs full): {len(flipped)}")
for gi, e, f in flipped:
    print(f"   idx={gi} excl_won={e} full_won={f} :: {mE[gi].get('task_desc','')[:60]}")

print(f"\n=== FAILURE ATTRIBUTION (excl-H run) ===")
fails = [r for r in excl["results"] if not r["won"]]
print(f"total failures: {len(fails)}")
def load_pddl(gi):
    gf = idx2gf.get(gi)
    if not gf: return {}
    tp = Path(gf).parent / "traj_data.json"
    try:
        td = json.load(open(tp))
        return {"pddl": td.get("pddl_params", {}), "task_type": td.get("task_type", ""),
                "wt_len": len(td.get("plan", {}).get("high_pddl", []))}
    except Exception:
        return {}
for r in fails:
    gi = r["game_idx"]
    meta = load_pddl(gi)
    pg = r.get("parsed_goal", {})
    acts = r.get("actions", [])
    print(f"\n--- idx={gi} [{r.get('task_type_real','')}] steps={r['steps']} ---")
    print(f"  desc: {r.get('task_desc','')[:110]}")
    print(f"  pddl: {meta.get('pddl',{})}  wt_len={meta.get('wt_len')}")
    print(f"  parsed: obj={pg.get('object_class')} recep={pg.get('recep_class')} "
          f"proc={pg.get('process')} tt={pg.get('task_type')} count={pg.get('count')}")
    print(f"  last6 actions: {acts[-6:]}")
    if r.get("error"): print(f"  ERROR: {r['error']}")
