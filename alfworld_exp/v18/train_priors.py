#!/usr/bin/env python3
"""train_priors.py — loader for v18/train_priors.json (spec fixes #5 / #6).

The JSON is produced by build_train_priors.py scanning the ALFWORLD *train*
split (training-set labels are permitted; the agent never sees valid PDDL).
Exposes small helpers used by goal_parser:

  process_for_parent(parent_cls)   -> best process ∈ {clean,heat,cool} or None
  putaway_dests(obj_cls, process)  -> ordered destination classes (put-away prior)
  look_object_order()              -> examinable object classes by frequency
"""
from __future__ import annotations
import json
import os
from typing import Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
# Loader-only injection point (no decision logic changes): if YLYW_PRIORS_PATH is
# set, load that priors file instead of the default. Used for the held-out
# generalization test to swap in priors rebuilt on train\H. Default is unchanged,
# so all existing valid_seen/valid_unseen runs are byte-for-byte unaffected.
_PATH = os.environ.get("YLYW_PRIORS_PATH") or os.path.join(_HERE, "train_priors.json")

_DATA: Dict = {}
if os.path.exists(_PATH):
    try:
        _DATA = json.load(open(_PATH, encoding="utf-8"))
    except Exception:
        _DATA = {}

# PDDL parent_target strings are CamelCase in the raw json; the builder already
# lower-cased them, but ALFWORLD receptacle *classes* used by world_model use a
# canonical spelling. Map the few that differ.
_PARENT_TO_CLASS = {
    "countertop": "countertop", "diningtable": "diningtable",
    "sidetable": "sidetable", "coffeetable": "coffeetable",
    "garbagecan": "garbagecan", "coffeemachine": "coffeemachine",
    "sinkbasin": "sinkbasin", "stoveburner": "stoveburner",
    "microwave": "microwave", "fridge": "fridge", "cabinet": "cabinet",
    "drawer": "drawer", "shelf": "shelf", "dresser": "dresser",
    "desk": "desk", "bed": "bed", "sofa": "sofa", "toilet": "toilet",
    "bathtubbasin": "bathtubbasin", "handtowelholder": "handtowelholder",
    "towelholder": "towelholder", "toiletpaperhanger": "toiletpaperhanger",
    "safe": "safe", "armchair": "armchair", "ottoman": "ottoman",
}


def process_for_parent(parent_cls: Optional[str], min_frac: float = 0.55) -> Optional[str]:
    """Dominant *processing* process for tasks whose final destination is this
    receptacle class. Only returns clean/heat/cool if it beats the alternatives
    by `min_frac`. Key learned rules: microwave→cool, fridge→heat."""
    if not parent_cls:
        return None
    tbl = _DATA.get("process_by_parent", {}).get(parent_cls)
    if not tbl:
        return None
    proc_tbl = {k: v for k, v in tbl.items() if k in ("clean", "heat", "cool")}
    if not proc_tbl:
        return None
    total = sum(tbl.values())
    best = max(proc_tbl, key=proc_tbl.get)
    if total and proc_tbl[best] / total >= min_frac:
        return best
    # even below the fraction, a *near-zero* rival is decisive for heat/cool
    return best if proc_tbl[best] >= 3 * (sorted(proc_tbl.values())[-2] if len(proc_tbl) > 1 else 0) + 1 else None


def putaway_dests(obj_cls: Optional[str], process: Optional[str]) -> List[str]:
    """Ordered destination receptacle classes for a put-away (NL omits target)."""
    if not obj_cls:
        return []
    key = f"{obj_cls}|{process or 'none'}"
    tbl = _DATA.get("putaway_parent_by_proc", {}).get(key)
    if not tbl:
        tbl = _DATA.get("putaway_parent", {}).get(obj_cls)
    if not tbl:
        return []
    ordered = sorted(tbl, key=tbl.get, reverse=True)
    return [_PARENT_TO_CLASS.get(p, p) for p in ordered]


def look_object_order() -> List[str]:
    """Examinable object classes ordered by train frequency (spec fix #2)."""
    tbl = _DATA.get("look_object", {})
    return sorted(tbl, key=tbl.get, reverse=True)
