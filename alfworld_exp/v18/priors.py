#!/usr/bin/env python3
"""
priors.py — rule-based object→receptacle location priors (spec §6 frontier).

Copied and lightly cleaned from v17's OBJECT_LOCATION_PRIORS table (endorsed by
spec: "先验来自规则词典（可后续换 LLM 版对照）"). Weights 1..3 = likelihood a
given object class is found on a given receptacle class. Used only to shape the
YLYW container-affordance / novelty yao features — never to pre-select actions.
"""
from __future__ import annotations
from typing import Dict

OBJECT_LOCATION_PRIORS: Dict[str, Dict[str, int]] = {
    "plate": {"countertop": 3, "cabinet": 2, "diningtable": 2, "sinkbasin": 1, "drawer": 1},
    "bowl": {"countertop": 3, "cabinet": 2, "diningtable": 2, "sinkbasin": 1},
    "cup": {"countertop": 3, "coffeemachine": 3, "cabinet": 2, "sinkbasin": 1},
    "mug": {"countertop": 3, "coffeemachine": 3, "desk": 2, "shelf": 2, "cabinet": 1, "sinkbasin": 1},
    "apple": {"countertop": 3, "fridge": 2, "diningtable": 2, "garbagecan": 1},
    "tomato": {"countertop": 3, "fridge": 2, "diningtable": 2},
    "potato": {"countertop": 3, "fridge": 2, "sinkbasin": 1},
    "egg": {"countertop": 3, "fridge": 3},
    "bread": {"countertop": 3, "diningtable": 2, "toaster": 2},
    "lettuce": {"countertop": 3, "fridge": 2},
    "knife": {"countertop": 3, "diningtable": 2, "drawer": 2, "sinkbasin": 1},
    "butterknife": {"countertop": 3, "diningtable": 2, "drawer": 2},
    "fork": {"countertop": 2, "diningtable": 2, "drawer": 2, "sinkbasin": 1},
    "spoon": {"countertop": 2, "diningtable": 2, "drawer": 2, "sinkbasin": 1},
    "spatula": {"countertop": 3, "diningtable": 1, "drawer": 2},
    "ladle": {"countertop": 2, "diningtable": 1, "drawer": 2},
    "pan": {"stoveburner": 3, "countertop": 2},
    "pot": {"stoveburner": 3, "countertop": 2},
    "kettle": {"stoveburner": 3, "countertop": 2},
    "soapbar": {"countertop": 3, "sinkbasin": 2, "bathtubbasin": 2, "toilet": 1},
    "soapbottle": {"countertop": 3, "sinkbasin": 2, "cabinet": 1},
    "book": {"desk": 3, "shelf": 3, "bed": 2, "sidetable": 2, "coffeetable": 2, "dresser": 1},
    "pen": {"desk": 3, "drawer": 2, "shelf": 1},
    "pencil": {"desk": 3, "drawer": 2, "shelf": 1},
    "cd": {"desk": 2, "shelf": 3, "drawer": 2, "dresser": 2, "safe": 1},
    "alarmclock": {"desk": 3, "sidetable": 3, "shelf": 2, "dresser": 2},
    "cellphone": {"desk": 3, "sidetable": 2, "bed": 1, "dresser": 1},
    "laptop": {"desk": 3, "bed": 2, "coffeetable": 1},
    "remotecontrol": {"coffeetable": 3, "sidetable": 2, "sofa": 2, "bed": 1, "dresser": 1},
    "creditcard": {"desk": 2, "sidetable": 2, "drawer": 2, "dresser": 2, "shelf": 1},
    "keychain": {"desk": 2, "sidetable": 2, "drawer": 2, "dresser": 2, "shelf": 1, "countertop": 1},
    "vase": {"shelf": 3, "desk": 2, "sidetable": 2, "coffeetable": 2, "dresser": 2, "countertop": 2},
    "statue": {"shelf": 3, "desk": 2, "sidetable": 2, "dresser": 2},
    "pillow": {"bed": 3, "sofa": 3, "armchair": 1},
    "teddybear": {"bed": 3, "sofa": 2, "armchair": 1},
    "towel": {"towelholder": 3, "countertop": 2, "bathtubbasin": 1},
    "handtowel": {"handtowelholder": 3, "countertop": 2},
    "toiletpaper": {"toiletpaperhanger": 3, "cabinet": 2, "countertop": 1},
    "cloth": {"countertop": 2, "bathtubbasin": 2},
    "spraybottle": {"countertop": 3, "cabinet": 2, "toilet": 1},
    "candle": {"countertop": 2, "shelf": 2, "bathtubbasin": 1},
    "tissuebox": {"sidetable": 2, "desk": 2, "shelf": 2, "toilet": 1, "countertop": 1},
    "newspaper": {"desk": 2, "coffeetable": 2, "sidetable": 2, "sofa": 1, "bed": 1},
    "winebottle": {"countertop": 3, "fridge": 2, "cabinet": 1},
    "bottle": {"countertop": 3, "shelf": 2},
    "glassbottle": {"countertop": 3, "shelf": 2, "fridge": 1},
    "box": {"desk": 2, "shelf": 2, "dresser": 2, "sidetable": 1},
    "watch": {"desk": 2, "sidetable": 2, "dresser": 2, "shelf": 1},
    "baseballbat": {"bed": 2, "desk": 1, "dresser": 1},
    "basketball": {"bed": 1, "desk": 1},
    "dishsponge": {"sinkbasin": 3, "countertop": 2},
    "scrubbrush": {"sinkbasin": 3, "countertop": 2},
    "papertowelroll": {"countertop": 2, "cabinet": 2},
    "saltshaker": {"countertop": 2, "cabinet": 2, "diningtable": 2, "drawer": 1},
    "peppershaker": {"countertop": 2, "cabinet": 2, "diningtable": 2, "drawer": 1},
    "pen ": {},
}


def location_prior(obj_class: str, recep_class: str) -> float:
    """Return prior weight in [0,1] that obj_class sits on recep_class."""
    if not obj_class:
        return 0.3
    table = OBJECT_LOCATION_PRIORS.get(obj_class, {})
    w = table.get(recep_class, 0)
    return min(1.0, w / 3.0) if w else 0.15


# Which receptacle classes tend to be the *destination* for placement tasks.
COMMON_DESTINATIONS = {
    "countertop", "diningtable", "sidetable", "coffeetable", "desk", "shelf",
    "drawer", "cabinet", "fridge", "garbagecan", "sinkbasin", "bed", "sofa",
    "dresser",
}
