#!/usr/bin/env python3
"""
goal_parser.py — task_desc → structured goal predicates (v18).

Only consumes the natural-language `task_desc`. NEVER reads task_type/pddl_params
from info (spec §2 red line). Reuses (imports) the v17 word tables from
task_desc_parser.py and adds structured predicate output + per-field probes.

Output goal object exposes:
  task_type            one of the 6 canonical ALFWorld families (inferred from NL)
  object_class         canonical target object class (e.g. 'alarmclock')
  recep_class          canonical destination receptacle class (e.g. 'diningtable')
  process              None | 'clean' | 'heat' | 'cool' | 'examine'
  tool_class           None | 'sinkbasin' | 'microwave' | 'fridge' | 'desklamp'
  count                1 or 2 (pick_two → 2)
  predicates()         list of ground predicate dicts for scoring / testing

Predicate vocabulary (spec §1):
  holding(x) / clean(x) / hot(x) / cold(x) / at(x,recep) /
  count_at(x,recep)=n / examined_under_light(x)
"""
from __future__ import annotations
import os
import re
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Dict

# NL receptacle head-words → canonical PDDL receptacle class, for spatial parsing
# ("<recepA> left/right of <recepB>" → take recepA as the destination).
_RECEP_WORD_MAP = {
    "cabinet": "cabinet", "cupboard": "cabinet", "drawer": "drawer",
    "shelf": "shelf", "counter": "countertop", "countertop": "countertop",
    "sidetable": "sidetable", "side table": "sidetable", "desk": "desk",
    "dresser": "dresser", "table": "diningtable", "fridge": "fridge",
    "refrigerator": "fridge", "microwave": "microwave", "sink": "sinkbasin",
    "stove": "stoveburner", "toilet": "toilet",
}
_re_spatial = re.compile(
    r"\b(cabinet|cupboard|drawer|shelf|countertop|counter|side table|sidetable|"
    r"desk|dresser|table|fridge|refrigerator|microwave|sink|stove|toilet)\b"
    r"[^,.;]*?\b(?:to the |on the )?(?:left|right)\s+of\b")
# "move X FROM <source> TO <dest>" — the destination is the receptacle after "to"
# (v17 sometimes returns the source). Capture the LAST such receptacle word.
_re_from_to = re.compile(
    r"\bto (?:the |a |an )?(bed|table|desk|shelf|side table|sidetable|dresser|"
    r"drawer|cabinet|cupboard|countertop|counter|sofa|couch|diningtable|"
    r"coffeetable|garbagecan|fridge|refrigerator|sink|toilet|ottoman)\b")
# General placement-destination scan for "take X from <src> ... put it on/in <dest>"
# sentences where the destination follows a placement preposition. Longer phrases
# first so 'dining table' wins over bare 'table'. Only consulted when 'from' is
# present (source/dest sentences), and tool receptacles are filtered out.
_re_place_dest = re.compile(
    r"\b(?:on|onto|in|into|inside|to)\s+(?:the |a |an |top of the |top of |front of )?"
    r"(dining table|coffee table|side table|end table|night stand|nightstand|"
    r"arm chair|garbage can|coffee machine|coffee maker|chest of drawers|"
    r"bed|table|desk|shelf|dresser|drawer|cabinet|cupboard|countertop|counter|"
    r"sofa|couch|armchair|ottoman|garbagecan|fridge|refrigerator|microwave|"
    r"sink|toilet|safe|cart|stove)\b")
_PLACE_WORD_MAP = {
    "dining table": "diningtable", "coffee table": "coffeetable",
    "side table": "sidetable", "end table": "sidetable",
    "night stand": "sidetable", "nightstand": "sidetable",
    "arm chair": "armchair", "armchair": "armchair",
    "garbage can": "garbagecan", "garbagecan": "garbagecan",
    "coffee machine": "coffeemachine", "coffee maker": "coffeemachine",
    "chest of drawers": "dresser", "bed": "bed", "table": "diningtable",
    "desk": "desk", "shelf": "shelf", "dresser": "dresser", "drawer": "drawer",
    "cabinet": "cabinet", "cupboard": "cabinet", "countertop": "countertop",
    "counter": "countertop", "sofa": "sofa", "couch": "sofa",
    "ottoman": "ottoman", "fridge": "fridge", "refrigerator": "fridge",
    "microwave": "microwave", "sink": "sinkbasin", "toilet": "toilet",
    "safe": "safe", "cart": "cart", "stove": "stoveburner",
}
_TOOL_RECEP = {"clean": "sinkbasin", "heat": "microwave", "cool": "fridge"}

# Import v17 word tables + base parser (teacher file, imported not modified).
_EXP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _EXP_DIR not in sys.path:
    sys.path.insert(0, _EXP_DIR)
from task_desc_parser import (  # noqa: E402
    parse_task_desc as _v17_parse,
    OBJECT_ALIASES,
    RECEP_ALIASES,
)
from train_priors import (  # noqa: E402
    process_for_parent, putaway_dests, look_object_order,
)

# Supplementary receptacle aliases: longer specific phrases the v17 table maps
# to the wrong (shorter) receptacle, e.g. "toilet paper holder" -> "toilet".
_EXTRA_RECEP_ALIASES = {
    "toilet paper holder": "toiletpaperhanger",
    "toilet paper hanger": "toiletpaperhanger",
    "toiletpaper hanger": "toiletpaperhanger",
    "toilet paper dispenser": "toiletpaperhanger",
    "toilet paper hook": "toiletpaperhanger",
    "hand towel holder": "handtowelholder",
    "towel holder": "towelholder",
    "towel rack": "towelholder",
    "night stand": "sidetable",
    "nightstand": "sidetable",
    "bedside table": "sidetable",
    # bathroom / kitchen destination phrases surfaced by the train scan
    "under the sink": "cabinet",         # 'the cabinet under the sink'
    "under sink": "cabinet",
    "toilet tank": "toilet", "water tank": "toilet",
    "toilet's water tank": "toilet", "tank of the toilet": "toilet",
    "chest of drawers": "dresser",
    "arm chair": "armchair", "armchair": "armchair",
    "coffee pot": "coffeemachine",
    "foot rest": "ottoman", "footrest": "ottoman",
    "foot stool": "ottoman", "footstool": "ottoman",
    "rack": "cart",                       # 'put X on a/the rack' (drying/utility cart)
    "bath tub": "bathtubbasin", "bathtub": "bathtubbasin", "tub": "bathtubbasin",
}

# Supplementary object aliases missing from the v17 table (NL variants we hit).
# Longer phrases are matched first (see parse loop). Fix #3 aliases folded in.
_EXTRA_OBJECT_ALIASES = {
    "newsletter": "newspaper", "newsletters": "newspaper", "paper": "newspaper",
    "roll of toilet paper": "toiletpaper", "rolls of toilet paper": "toiletpaper",
    "toilet roll": "toiletpaper", "toilet rolls": "toiletpaper",
    "disc": "cd", "disk": "cd", "disks": "cd", "discs": "cd",
    "wineglass": "winebottle", "mobile": "cellphone",
    "smartphone": "cellphone", "alarm": "alarmclock",
    "rag": "cloth", "wash cloth": "cloth", "washcloth": "cloth", "dish rag": "cloth",
    "hand soap": "soapbottle", "soap bottle": "soapbottle",
    "bar of soap": "soapbar", "soap bar": "soapbar",
    "magazine": "newspaper", "magazines": "newspaper",
    # --- train-scan discovered general synonyms (fire when v17 finds no object) ---
    "green vegetable": "lettuce", "vegetable": "lettuce", "cabbage": "lettuce",
    "head of lettuce": "lettuce",
    "card": "creditcard",                       # 'cards' too (substring match)
    "tissue": "tissuebox", "tissues": "tissuebox", "box of tissues": "tissuebox",
    "glass": "cup",                             # bare 'glass' → cup (ambig→glassbottle)
    "jar": "vase", "jars": "vase",             # ceramic jars are 'vase' in ALFWORLD
    "watering can": "wateringcan",
    "computer": "laptop",
    "skillet": "pan",
    "scoop": "ladle", "ice cream scoop": "ladle",
    "cushion": "pillow",
    "figurine": "statue", "figurines": "statue", "figure": "statue",
    "sculpture": "statue",
    "dispenser": "soapbottle", "soap dispenser": "soapbottle",
    "tennis racket": "tennisracket",
    "tray": "plate",
    "window cleaner": "spraybottle", "cleaner": "spraybottle",
}

# Overrides that fire even when v17 produced a (usually wrong) object class.
# e.g. 'boxes of tissues' → v17 matches 'box' but the object is really a tissuebox.
_OBJECT_OVERRIDE_TISSUE = ("tissue",)

# Overrides applied even when the v17 table produced *some* object (used when the
# base object class has no PDDL instances / is the wrong referent). key phrase in
# task_desc → object class.
_OBJECT_OVERRIDE_PHRASES = {
    "hand soap": "soapbottle",
    "disk": "cd", "disks": "cd",
}

# Process → tool receptacle class
PROCESS_TOOL = {
    "clean": "sinkbasin",
    "heat": "microwave",
    "cool": "fridge",
    "examine": "desklamp",
}

# Broad tail of examinable object classes not always present in the frequency
# prior (e.g. mug/cup), appended after the prior for look-enum retry (Fix #2).
_LOOK_TAIL = [
    "mug", "cup", "bowl", "plate", "saltshaker", "peppershaker", "soapbottle",
    "spraybottle", "candle", "cloth", "handtowel", "toiletpaper", "cd", "vase",
    "pen", "pencil", "cellphone", "keychain", "creditcard", "watch", "spatula",
    "fork", "spoon", "knife", "butterknife", "glassbottle", "winebottle",
]

TASK_PROCESS = {
    "pick_and_place_simple": None,
    "pick_two_obj_and_place": None,
    "pick_clean_then_place_in_recep": "clean",
    "pick_heat_then_place_in_recep": "heat",
    "pick_cool_then_place_in_recep": "cool",
    "look_at_obj_in_light": "examine",
}


# NL object names are ambiguous vs PDDL classes; expand to plausible referents so
# the agent can try alternates (it only ever trusts env `won`). Ordered by prior
# likelihood for these ALFWorld task families.
OBJECT_AMBIGUITY = {
    "knife": ["knife", "butterknife"],
    "butterknife": ["butterknife", "knife"],
    "cup": ["cup", "mug"],
    "mug": ["mug", "cup"],
    "soapbar": ["soapbar", "soapbottle"],
    "soapbottle": ["soapbottle", "soapbar"],
    "cellphone": ["cellphone"],
    "spoon": ["spoon", "ladle"],
    "pot": ["pot", "pan", "kettle"],
    "pan": ["pan", "pot"],
    # Fix #1: NL "(salt) shaker" is very often the PepperShaker in ALFWORLD;
    # try the literal salt first, fall back to pepper (only env `won` is trusted).
    "saltshaker": ["saltshaker", "peppershaker"],
    "peppershaker": ["peppershaker", "saltshaker"],
    # wash scenes call plates "bowls" and vice-versa; 'tray' → plate/pan/bowl
    "bowl": ["bowl", "plate"],
    "plate": ["plate", "bowl", "pan"],
    # bare "bottle" (e.g. "green bottle") — try the common bottle referents
    "bottle": ["soapbottle", "winebottle", "glassbottle", "bottle"],
    # 'glass'/'jar'/'vase' are visually interchangeable glass/ceramic vessels;
    # 'glass' → cup first then the glass bottle; jars/vases can be either.
    "cup": ["cup", "mug", "glassbottle"],
    "vase": ["vase", "glassbottle", "statue"],
    "glassbottle": ["glassbottle", "vase", "winebottle"],
    "statue": ["statue", "vase"],
    # towel/cloth/handtowel share the NL word 'towel'
    "towel": ["towel", "cloth", "handtowel"],
    "handtowel": ["handtowel", "towel", "cloth"],
    "cloth": ["cloth", "towel", "handtowel"],
    # tissue box sometimes annotated bare 'box'
    "tissuebox": ["tissuebox", "box"],
}


@dataclass
class Goal:
    task_desc: str
    task_type: str
    object_class: Optional[str]
    recep_class: Optional[str]
    process: Optional[str]
    tool_class: Optional[str]
    count: int = 1
    object_classes: List[str] = field(default_factory=list)  # plausible target classes
    recep_classes: List[str] = field(default_factory=list)   # ordered destination candidates
    is_putaway: bool = False        # destination inferred from prior (NL omitted it)
    is_look_enum: bool = False      # look task with enumerated object candidates
    # book-keeping for testability
    raw: Dict = field(default_factory=dict)

    def is_target(self, obj_cls: Optional[str]) -> bool:
        if not obj_cls:
            return False
        return obj_cls in (self.object_classes or ([self.object_class] if self.object_class else []))

    # ---- convenience predicates ----
    def needs_process(self) -> bool:
        return self.process in ("clean", "heat", "cool")

    def needs_light(self) -> bool:
        return self.process == "examine"

    def predicates(self) -> List[Dict]:
        """Structured ground-goal predicates (for scoring + unit testing)."""
        preds: List[Dict] = []
        obj = self.object_class
        if obj is None:
            return preds
        if self.needs_light():
            preds.append({"pred": "examined_under_light", "obj": obj})
            preds.append({"pred": "holding", "obj": obj})
            return preds
        # every non-look task ends with the object placed at recep
        if self.count >= 2:
            preds.append({"pred": "count_at", "obj": obj,
                          "recep": self.recep_class, "n": self.count})
        else:
            preds.append({"pred": "at", "obj": obj, "recep": self.recep_class})
        if self.process == "clean":
            preds.append({"pred": "clean", "obj": obj})
        elif self.process == "heat":
            preds.append({"pred": "hot", "obj": obj})
        elif self.process == "cool":
            preds.append({"pred": "cold", "obj": obj})
        return preds

    def as_dict(self) -> Dict:
        return {
            "task_type": self.task_type,
            "object_class": self.object_class,
            "recep_class": self.recep_class,
            "process": self.process,
            "tool_class": self.tool_class,
            "count": self.count,
        }


def parse_goal(task_desc: str) -> Goal:
    """task_desc → Goal. Pure NL; no PDDL/info truth used."""
    base = _v17_parse(task_desc or "")
    tt = base.get("task_type", "pick_and_place_simple")
    objs = base.get("target_objects", []) or []
    receps = base.get("target_receps", []) or []

    # --- process re-inference guards (fix destination-noun false triggers) ---
    low = (task_desc or "").lower()
    # explicit cooking verbs only (avoid incidental words like "warm room").
    # 'warm'/'cooked'/'toast' are genuine heat cues that the v17 table under-weighs.
    heat_verb = any(k in low for k in ("heat", "heating", "heated", "cook", "cooked",
                                       "cooking", "warm", "warmed", "toast", "boil",
                                       "grill", "microwaved", "microwave the"))
    cool_verb = any(k in low for k in ("cool", "chill", "chilled", "cold",
                                       "freeze", "frozen"))
    # Explicit process VERBS via word boundaries. The NOUNS 'refrigerator' / 'fridge'
    # / 'microwave' are PLACES, not process cues — the v17 table's 'refrigerat'
    # substring wrongly fired cool for 'put a cooked tomato into the refrigerator'.
    ex_heat = bool(re.search(
        r"\b(heat|heated|heating|warm|warmed|warming|cook|cooked|cooking|toast|"
        r"toasted|boil|boiled|grill|grilled|reheat)\b", low))
    ex_cool = bool(re.search(
        r"\b(cool|cooled|cooling|chill|chilled|chilling|cold|freeze|frozen|"
        r"freezing|refrigerate|refrigerated)\b", low))
    # An ADJECTIVE / past-participle describes the object's desired END STATE, which
    # is the true success condition (e.g. 'cook a chilled tomato' → the tomato must
    # be COLD → cool; 'a cooked tomato into the refrigerator' → HOT → heat). This
    # takes priority over verb order; only when neither side has an end-state
    # adjective do we fall back to earliest-verb-wins ('Heat and chill a potato').
    heat_adj = bool(re.search(
        r"\b(heated|warmed|warm|hot|cooked|toasted|boiled|grilled|microwaved)\b", low))
    cool_adj = bool(re.search(
        r"\b(chilled|cooled|cold|frozen|icy|iced|refrigerated)\b", low))
    if tt in ("pick_cool_then_place_in_recep", "pick_heat_then_place_in_recep"):
        want = None
        if heat_adj and not cool_adj:
            want = "heat"
        elif cool_adj and not heat_adj:
            want = "cool"
        elif ex_heat and not ex_cool:
            want = "heat"
        elif ex_cool and not ex_heat:
            want = "cool"
        elif ex_heat and ex_cool:
            hpos = min([low.find(x) for x in ("heat", "warm", "cook", "toast", "boil")
                        if x in low] or [10**6])
            cpos = min([low.find(x) for x in ("cool", "chill", "cold", "freeze", "frozen")
                        if x in low] or [10**6])
            want = "heat" if hpos <= cpos else "cool"
        if want == "heat":
            tt = "pick_heat_then_place_in_recep"
        elif want == "cool":
            tt = "pick_cool_then_place_in_recep"
    # legacy microwave-based cool→heat rule (kept; harmless after the above).
    if tt == "pick_cool_then_place_in_recep" and not cool_verb and heat_verb \
            and "microwave" in low:
        tt = "pick_heat_then_place_in_recep"
    # "microwave oven table" / "on the microwave" → microwave is a place, not heat.
    if tt == "pick_heat_then_place_in_recep" and not heat_verb:
        if ("table" in low) or ("on the microwave" in low) or ("oven table" in low):
            tt = "pick_and_place_simple"
    # clean false-positive: 'water tank' / 'toilet tank' — the substring 'water'
    # wrongly fired clean although there is no genuine wash cue.
    if tt == "pick_clean_then_place_in_recep" and "tank" in low and not re.search(
            r"\b(clean|cleaned|cleaning|wash|washed|washing|rinse|rinsed|dirty|"
            r"soiled|soapy|wet|filthy|grimy|scrub)\b", low):
        tt = "pick_and_place_simple"

    count = 2 if tt == "pick_two_obj_and_place" else 1

    object_class = objs[0] if objs else None
    recep_class = receps[0] if receps else None

    # fall back to supplementary aliases when the v17 table missed the object
    if object_class is None:
        for alias in sorted(_EXTRA_OBJECT_ALIASES, key=len, reverse=True):
            if alias in low:
                object_class = _EXTRA_OBJECT_ALIASES[alias]
                break

    # phrase overrides that fire even when v17 produced a (wrong) object class
    for phrase, oc in _OBJECT_OVERRIDE_PHRASES.items():
        if phrase in low:
            object_class = oc
            break
    # 'boxes of tissues' → v17 matches bare 'box'; the object is a tissue box.
    if "tissue" in low and object_class in (None, "box"):
        object_class = "tissuebox"

    # "coffee maker/machine/table" makes the v17 table match coffee->cup; if the
    # sentence actually names a mug, that is the real target object.
    if object_class == "cup" and "mug" in low:
        object_class = "mug"
    # bare 'coffee' inside a receptacle name ('coffee table/machine/maker/pot')
    # wrongly yields cup; if no genuine cup word is present, re-extract from aliases.
    if object_class == "cup" and not re.search(r"\b(cup|coffee cup|glass|mug)\b", low) \
            and any(p in low for p in ("coffee table", "coffee machine",
                                       "coffee maker", "coffee pot")):
        object_class = None
        for alias in sorted(_EXTRA_OBJECT_ALIASES, key=len, reverse=True):
            if alias in low and alias != "cup":
                object_class = _EXTRA_OBJECT_ALIASES[alias]
                break
        if object_class is None:
            # fall back to any v17 object alias that is not the coffee->cup match
            for alias in sorted(OBJECT_ALIASES, key=len, reverse=True):
                if alias in ("coffee", "cup"):
                    continue
                if alias in low:
                    object_class = OBJECT_ALIASES[alias]
                    break

    # ---------------- destination receptacle resolution ----------------
    # override receptacle when a longer specific phrase was mis-mapped (longest
    # phrase first so 'towel rack' wins over 'rack', 'under the sink' over 'sink').
    for phrase in sorted(_EXTRA_RECEP_ALIASES, key=len, reverse=True):
        if phrase in low:
            recep_class = _EXTRA_RECEP_ALIASES[phrase]
            break

    # look_at has no destination receptacle
    if tt == "look_at_obj_in_light":
        recep_class = None

    # process cues (computed early; gate the fridge/microwave dest rules).
    # NB: a bare mention of "microwave"/"refrigerator" as a place is NOT a heat/
    # cool cue — those tools are named as destinations too.
    heat_cue = any(k in low for k in ("heat", "heated", "warm", "cook", "cooked",
                                      "boil", "toast", " hot"))
    cool_cue = any(k in low for k in ("cool", "cooled", "chill", "chilled", "cold",
                                      "frozen", "freeze"))
    clean_cue = any(k in low for k in ("clean", "wash", "rinse", "dirty", "soil",
                                       "filled", "rinsed"))

    if tt != "look_at_obj_in_light":
        # Fix #4: "throw away / throw in / in the trash" → garbage can
        if any(k in low for k in ("throw away", "throw it away", "throw them away",
                                  "thrown away", "throw out", "throw in the",
                                  "in the trash", "in the garbage", "garbage can",
                                  "trash can", "trashcan", "dispose")):
            recep_class = "garbagecan"

        # Fix #4: spatial "<recepA> (to the) left/right of <recepB>" → take recepA
        m_sp = _re_spatial.search(low)
        if m_sp:
            rc = _RECEP_WORD_MAP.get(m_sp.group(1))
            if rc:
                recep_class = rc

        # "move X from <source> to <dest>" — destination is the recep after "to".
        if " from " in low and " to " in low:
            ft = _re_from_to.findall(low)
            if ft:
                rc = _RECEP_WORD_MAP.get(ft[-1])
                if rc:
                    recep_class = rc
        # general source→dest: "take X from <src> ... put it on/in <dest>" where the
        # destination follows a placement preposition (not 'from'). Take the LAST
        # placement receptacle; skip the tool receptacle of a process task.
        if " from " in low:
            tool_r = _TOOL_RECEP.get(TASK_PROCESS.get(tt))
            dests = [_PLACE_WORD_MAP.get(w) for w in _re_place_dest.findall(low)]
            dests = [d for d in dests if d and d != tool_r]
            if dests:
                recep_class = dests[-1]

        # "middle shelf in the refrigerator" — the shelf is *inside* the fridge, so
        # the placement receptacle is the fridge — but ONLY for a heat task, where
        # the fridge is genuinely the destination. For a cool task the fridge is
        # the cooling tool and the real destination is elsewhere ("cool the plate
        # in the fridge, then store it in the cabinet"). Symmetric for microwave.
        if (("in the refrigerator" in low or "in the fridge" in low
                or "inside the refrigerator" in low or "inside the fridge" in low)
                and heat_cue and not cool_cue):
            recep_class = "fridge"
        if (("in the microwave" in low or "inside the microwave" in low
                or "into the microwave" in low) and not heat_cue):
            recep_class = "microwave"

        # "kitchen island" is a countertop/dining surface, not in the alias table
        if recep_class is None and "island" in low:
            recep_class = "countertop"
        # bare "table" → dining table (agent remaps if absent from scene)
        if recep_class is None and "table" in low:
            recep_class = "diningtable"

    # ---------------- process determination ----------------
    process = TASK_PROCESS.get(tt)

    # Fix #5: destination-driven heat/cool disambiguation from train priors.
    #   microwave-as-destination → cool ;  fridge-as-destination → heat.
    # Asymmetric on purpose: heat NEVER ends at a microwave in train, so adopting
    # cool for a microwave destination is safe even without an NL cue. But cool
    # DOES legitimately end at the fridge, so only flip cool→heat when the text
    # explicitly says so (avoids mis-flipping "put the plate inside the fridge").
    if process in ("heat", "cool") or (tt == "pick_and_place_simple"
                                       and recep_class in ("microwave", "fridge")):
        dp = process_for_parent(recep_class)
        if dp in ("heat", "cool") and dp != process:
            adopt = False
            if dp == "cool" and not heat_cue:
                adopt = True                      # microwave dest / never a heat end
            elif dp == "heat" and heat_cue:
                adopt = True                      # explicit heat word + fridge dest
            if adopt:
                process = dp
                tt = ("pick_heat_then_place_in_recep" if dp == "heat"
                      else "pick_cool_then_place_in_recep")

    tool = PROCESS_TOOL.get(process) if process else None

    # heat task whose destination is the fridge (microwave is only the tool),
    # e.g. "...back in the refrigerator when done heating in the microwave":
    if tt == "pick_heat_then_place_in_recep" and recep_class in (None, "microwave") \
            and ("refrigerat" in low or "fridge" in low):
        recep_class = "fridge"

    # ---------------- put-away destination prior (Fix #6) ----------------
    # bare "table" is ambiguous across dining/side/coffee/counter/desk/dresser
    # surfaces; expand to an ordered candidate list so the agent's dest-retry can
    # reach the right one (the scene-presence filter picks what's actually there).
    bare_table = ("table" in low) and not any(p in low for p in (
        "side table", "sidetable", "coffee table", "coffeetable",
        "dining table", "diningtable", "night table", "end table", "pool table"))
    _TABLE_CANDS = ["diningtable", "sidetable", "coffeetable", "countertop",
                    "desk", "dresser"]
    is_putaway = False
    recep_classes: List[str] = []
    if recep_class is not None:
        if bare_table and recep_class in _TABLE_CANDS:
            recep_classes = [recep_class] + [t for t in _TABLE_CANDS if t != recep_class]
        else:
            recep_classes = [recep_class]
    elif tt != "look_at_obj_in_light" and object_class:
        # NL omitted the destination — use the train put-away prior.
        cand = putaway_dests(object_class, process)
        if cand:
            recep_classes = cand
            recep_class = cand[0]
            is_putaway = True

    # ---------------- object candidate list ----------------
    is_look_enum = False
    if tt == "look_at_obj_in_light":
        # examine task: build an ordered candidate list. If NL named a plausible
        # examinable object keep it first, then the frequency prior, then a broad
        # tail of remaining examinable classes (mug/cup etc. are rare but real).
        prior = look_object_order()
        cands: List[str] = []
        if object_class:
            cands.append(object_class)
        for c in prior + _LOOK_TAIL:
            if c not in cands:
                cands.append(c)
        object_classes = cands
        is_look_enum = True
    else:
        # bare "bottle" ("green bottle", "bottle of wine") — order the plausible
        # bottle referents by the modifier context (only env `won` is trusted).
        if object_class == "bottle":
            if "wine" in low:
                object_classes = ["winebottle", "glassbottle", "soapbottle", "bottle"]
            elif "spray" in low or "cleaner" in low or "window" in low:
                object_classes = ["spraybottle", "soapbottle", "bottle"]
            elif any(k in low for k in ("soap", "lotion", "dispenser", "shampoo")):
                object_classes = ["soapbottle", "spraybottle", "winebottle", "glassbottle"]
            elif "glass" in low:
                object_classes = ["glassbottle", "winebottle", "bottle"]
            else:
                object_classes = OBJECT_AMBIGUITY.get("bottle")
        else:
            object_classes = OBJECT_AMBIGUITY.get(
                object_class, [object_class] if object_class else [])

    return Goal(
        task_desc=task_desc,
        task_type=tt,
        object_class=object_class,
        recep_class=recep_class,
        process=process,
        tool_class=tool,
        count=count,
        object_classes=list(object_classes),
        recep_classes=list(recep_classes),
        is_putaway=is_putaway,
        is_look_enum=is_look_enum,
        raw=base,
    )


# ---------------- self-test / accuracy probe ----------------
if __name__ == "__main__":
    tests = [
        ("look at the clock under the lamp", "look_at_obj_in_light", "alarmclock", None),
        ("place two knifes in the kitchen drawer", "pick_two_obj_and_place", "knife", "drawer"),
        ("Place a heated egg on the kitchen island.", "pick_heat_then_place_in_recep", "egg", None),
        ("put a chilled apple on a kitchen counter", "pick_cool_then_place_in_recep", "apple", "countertop"),
        ("place clean lettuce inside of the kitchen fridge", "pick_clean_then_place_in_recep", "lettuce", "fridge"),
    ]
    for desc, et, eo, er in tests:
        g = parse_goal(desc)
        print(f"{desc!r}\n   -> {g.as_dict()}  preds={g.predicates()}")
        assert g.task_type == et, (g.task_type, et)
        assert g.object_class == eo, (g.object_class, eo)
    print("OK")
