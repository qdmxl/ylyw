#!/usr/bin/env python3
"""
ylyw_scorer.py — per-candidate hexagram scorer (spec §1). THE framework hook.

For every candidate action a we build a (state, goal, a) six-yao encoding and run
it through the real YLYW L3 machinery (64-hexagram cosine template matching from
ylyw_core.HexagramRuleBase, imported not modified). The action's own L1 primitive
gua (ylyw_action_primitives.ACTION_PRIMITIVES) is fused in as a trigram-affinity
term. argmax over YLYW_score selects the action.

Six-yao semantics (spec §1), each in [0.05, 0.95]:
  y1 目标差距缩小     goal-gap reduction
  y2 持有承接         holding continuity / inheritance
  y3 处理谓词推进     process-predicate advancement (clean/heat/cool/examine)
  y4 容器可供性       container affordance
  y5 目标关联         goal association (obj/recep matches goal)
  y6 新颖性-失败史    novelty vs failure history

YLYW_score(a) = cos(yao, template[H]) * favorability(H) * (0.75 + 0.25 * gua_affinity)
where H = argmax hexagram. favorability is a fixed 64-length table (King Wen
order) — part of the "443 hexagram core parameters".

Also exposes `linear_score` (plain weighted sum of the 6 yao) so the agent can
measure YLYW_action_influence = argmax-change-rate when the hexagram layer is
removed (spec §8).
"""
from __future__ import annotations
import os
import sys
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

# ---- wire up the real YLYW core (import, never modify) ----
_YLYW_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for p in (_YLYW_ROOT, os.path.join(_YLYW_ROOT, "api_docs"),
          os.path.join(_YLYW_ROOT, "language")):
    if p not in sys.path:
        sys.path.insert(0, p)

from ylyw_core import HexagramRuleBase, Hexagram          # noqa: E402  L3 templates
from ylyw_action_primitives import (                       # noqa: E402  L1 action gua
    ACTION_GUA_MAP, get_gua_by_action_type,
    get_gua_for_object, get_gua_for_receptacle, gua_similarity,
)

_RES_CACHE: Dict[tuple, float] = {}


def object_recep_resonance(obj_cls: str, recep_cls: str) -> float:
    """YLYW gua resonance in [0,1] between a target object and a receptacle,
    from ylyw_action_primitives (object/location gua Hamming similarity). Gives
    each receptacle a distinct signature so the L3 hexagram layer can genuinely
    order the exploration frontier (not just replicate the flat prior)."""
    if not obj_cls or not recep_cls:
        return 0.5
    key = (obj_cls, recep_cls)
    v = _RES_CACHE.get(key)
    if v is None:
        try:
            v = float(gua_similarity(get_gua_for_object(obj_cls),
                                     get_gua_for_receptacle(recep_cls)))
        except Exception:
            v = 0.5
        _RES_CACHE[key] = v
    return v

from priors import location_prior                          # noqa: E402
import world_model as WM                                   # noqa: E402

# ------------------------------------------------------------------
# fixed hexagram favorability (King Wen order via enum name).
# High = advance / flow / completion; Low = obstruction / danger / stagnation.
# This is the load-bearing YLYW nonlinearity that reshapes the ranking.
# ------------------------------------------------------------------
FAVORABILITY: Dict[str, float] = {
    # strong advance / completion
    "TAI": 1.00, "JIJI": 0.96, "JIN": 0.95, "DAYOU": 0.90, "SHENG": 0.90,
    "YI_GUA": 0.90, "DING": 0.90, "GE": 0.88, "JIAN_GUA": 0.86, "LIN": 0.86,
    "FENG": 0.85, "JING": 0.85, "QIAN": 0.85, "DACHU": 0.82, "CUI": 0.82,
    "SUI": 0.80, "QIAN_GUA": 0.80, "WUWANG": 0.80, "FU": 0.80, "SHIHE": 0.80,
    "BI": 0.78, "XIAN": 0.76, "DAZHUANG": 0.76, "XU": 0.72, "TONGREN": 0.75,
    "HENG": 0.72, "JIE": 0.70, "ZHONGFU": 0.72, "XIE": 0.72, "GUAI": 0.68,
    # neutral-ish
    "YU": 0.66, "GUAN": 0.64, "LU": 0.64, "XIAOXU": 0.62, "JIAREN": 0.70,
    "HUAN": 0.60, "GEN_GUA": 0.60, "ZHEN_GUA": 0.62, "XUN_GUA": 0.60,
    "LI_GUA": 0.66, "DUI_GUA": 0.66, "GUIMEI": 0.55, "XIAOGUO": 0.55,
    "LU_GUA": 0.55, "SUN": 0.58, "GU": 0.52, "GOU": 0.52, "DAGUO": 0.52,
    "YI": 0.60,
    # obstruction / danger / stagnation
    "MENG": 0.50, "ZHUN": 0.50, "WEIJI": 0.46, "KUI": 0.46, "SONG": 0.42,
    "BO": 0.42, "KAN_GUA": 0.42, "MINGYI": 0.42, "SHI": 0.50, "KUN_GUA": 0.36,
    "JIAN": 0.36, "PI": 0.32,
}
_DEFAULT_FAV = 0.62

# yao weights for the linear (no-hexagram) baseline
_LIN_W = np.array([0.28, 0.14, 0.20, 0.12, 0.16, 0.10])

# bounded additive hexagram-term weights (favor centered at 0.66, cos at 0.92).
# Large enough that the hexagram layer decides comparable candidates (the source
# of measurable YLYW influence), small enough that a clearly better goal action
# still wins after protective vetoes remove the pathological near-ties.
_W_FAV = 0.14
_W_COS = 0.13
_W_GUA = 0.04

_LO, _HI = 0.05, 0.95


def _clip(v: float) -> float:
    return max(_LO, min(_HI, v))


def parse_action(cmd: str) -> Dict:
    """Parse an admissible command string into structured fields."""
    c = cmd.strip()
    low = c.lower()
    d = {"cmd": c, "verb": low.split(" ", 1)[0], "obj": None, "recep": None,
         "obj_cls": None, "recep_cls": None}
    m = re.match(r"go to (.+)$", low)
    if m:
        d["verb"] = "go"; d["recep"] = m.group(1); d["recep_cls"] = WM.class_of(m.group(1)); return d
    m = re.match(r"open (.+)$", low)
    if m:
        d["verb"] = "open"; d["recep"] = m.group(1); d["recep_cls"] = WM.class_of(m.group(1)); return d
    m = re.match(r"close (.+)$", low)
    if m:
        d["verb"] = "close"; d["recep"] = m.group(1); d["recep_cls"] = WM.class_of(m.group(1)); return d
    m = re.match(r"take (.+?) from (.+)$", low)
    if m:
        d["verb"] = "take"; d["obj"] = m.group(1); d["recep"] = m.group(2)
        d["obj_cls"] = WM.class_of(m.group(1)); d["recep_cls"] = WM.class_of(m.group(2)); return d
    m = re.match(r"(?:move|put) (.+?) (?:to|in|on|in/on) (.+)$", low)
    if m:
        d["verb"] = "put"; d["obj"] = m.group(1); d["recep"] = m.group(2)
        d["obj_cls"] = WM.class_of(m.group(1)); d["recep_cls"] = WM.class_of(m.group(2)); return d
    m = re.match(r"(clean|heat|cool) (.+?) with (.+)$", low)
    if m:
        d["verb"] = m.group(1); d["obj"] = m.group(2); d["recep"] = m.group(3)
        d["obj_cls"] = WM.class_of(m.group(2)); d["recep_cls"] = WM.class_of(m.group(3)); return d
    m = re.match(r"use (.+)$", low)
    if m:
        d["verb"] = "use"; d["recep"] = m.group(1); d["recep_cls"] = WM.class_of(m.group(1)); return d
    m = re.match(r"examine (.+)$", low)
    if m:
        d["verb"] = "examine"; d["recep"] = m.group(1); d["recep_cls"] = WM.class_of(m.group(1)); return d
    return d  # look / inventory / help


# action verb → ylyw primitive name (for L1 gua)
_VERB_PRIM = {
    "go": "navigate", "open": "open", "close": "close", "take": "pickup",
    "put": "put", "clean": "clean", "heat": "heat", "cool": "cool",
    "use": "toggle", "examine": "look", "look": "look", "inventory": "inventory",
}


@dataclass
class Candidate:
    cmd: str
    parsed: Dict
    yao: List[float]
    hexagram: str = ""
    hex_cn: str = ""
    cos: float = 0.0
    favor: float = 0.0
    gua_affinity: float = 0.0
    ylyw_score: float = 0.0
    linear_score: float = 0.0
    vetoed: bool = False
    veto_reason: str = ""

    def log(self) -> Dict:
        return {
            "cmd": self.cmd,
            "yao": [round(v, 3) for v in self.yao],
            "hex": self.hexagram, "hex_cn": self.hex_cn,
            "cos": round(self.cos, 4), "favor": round(self.favor, 3),
            "gua_aff": round(self.gua_affinity, 3),
            "score": round(self.ylyw_score, 5),
            "lin": round(self.linear_score, 5),
            "veto": self.vetoed, "veto_reason": self.veto_reason,
        }


class YLYWScorer:
    # ablation modes (spec §8):
    #   'full'      : L3 hexagram favorability × magnitude (default)
    #   'linear'    : no hexagram — argmax on the linear yao magnitude only
    #   'no_favor'  : hexagram template-match (cos) kept, favorability flattened
    #   'fixed_yao' : yao frozen to [0.5]*6 (six-yao carries no information)
    #   'perm'      : favorability table randomly permuted across hexagrams
    def __init__(self, mode: str = "full", seed: int = 0):
        self.mode = mode
        self.hr = HexagramRuleBase()
        # favorability array indexed by Hexagram.value (raw semantic table [0.32,1]).
        self._fav = np.full(64, _DEFAULT_FAV)
        for hx in Hexagram:
            self._fav[hx.value] = FAVORABILITY.get(hx.name, _DEFAULT_FAV)
        self._hex_cn = {hx.value: self.hr.get_rule(hx).get("name", hx.name) for hx in Hexagram}
        if mode == "perm":
            rng = np.random.RandomState(seed)
            self._fav = self._fav[rng.permutation(64)]

    # ---------------- six-yao construction ----------------
    def build_yao(self, parsed: Dict, world, goal, phase: Dict) -> List[float]:
        verb = parsed["verb"]
        obj_cls = parsed.get("obj_cls")
        recep_cls = parsed.get("recep_cls")
        recep = parsed.get("recep")

        g_obj = goal.object_class
        g_recep = goal.recep_class
        tool = goal.tool_class
        need_proc = goal.needs_process()
        need_light = goal.needs_light()

        holding_target = phase["holding_target"]        # obj id or None
        proc_done = phase["proc_done"]                  # bool
        placed_count = phase["placed_count"]            # int
        searching = phase["searching"]                  # bool: still need to find obj

        is_target_obj = goal.is_target(obj_cls) if obj_cls else False
        is_dest_recep = (recep_cls == g_recep) if (recep_cls and g_recep) else False
        is_tool_recep = (recep_cls == tool) if (recep_cls and tool) else False

        # ---- y1 goal-gap reduction ----
        y1 = 0.3
        if verb == "take" and is_target_obj and not holding_target:
            y1 = 0.90
        elif verb in ("clean", "heat", "cool") and is_target_obj and holding_target \
                and need_proc and not proc_done:
            y1 = 0.92
        elif verb == "use" and need_light and holding_target:
            y1 = 0.95
        elif verb == "put" and is_target_obj and holding_target:
            if need_light:
                y1 = 0.05          # never put the object down during a look task
            elif need_proc and not proc_done:
                y1 = 0.15          # premature placement (process not done yet)
            elif is_dest_recep:
                y1 = 0.95
            else:
                y1 = 0.20          # dropping at a non-destination abandons progress
        elif verb == "go":
            if holding_target and need_proc and not proc_done and is_tool_recep:
                y1 = 0.85
            elif holding_target and need_light:
                if recep == phase.get("lamp_recep"):
                    y1 = 0.92
                elif recep_cls in ("desk", "sidetable", "shelf", "dresser", "countertop"):
                    y1 = 0.6
                else:
                    y1 = 0.4
            elif holding_target and (not need_proc or proc_done) and is_dest_recep:
                y1 = 0.85
            elif searching and recep == phase.get("target_recep"):
                y1 = 0.90          # go straight to a known next-pickup location
            elif searching:
                y1 = 0.30 + 0.32 * location_prior(g_obj, recep_cls or "")
            else:
                y1 = 0.3
        elif verb == "open":
            if holding_target and is_dest_recep:
                y1 = 0.95          # open the destination you stand at, then place
            elif searching:
                y1 = 0.72          # open the container you are standing at to search
            else:
                y1 = 0.4
        y1 = _clip(y1)

        # ---- y2 holding continuity ----
        y2 = 0.4
        if holding_target:
            if verb in ("put", "clean", "heat", "cool", "use") and (is_target_obj or verb == "use"):
                y2 = 0.90
            elif verb == "go" and (is_tool_recep or is_dest_recep or need_light):
                y2 = 0.75
            elif verb == "take":
                y2 = 0.20          # already holding; taking more is off-track
            elif verb == "open":
                y2 = 0.85 if is_dest_recep else 0.5   # opening the dest to place
            else:
                y2 = 0.45
        else:
            if verb == "take" and is_target_obj:
                y2 = 0.88
            elif verb in ("put", "clean", "heat", "cool", "use"):
                y2 = 0.10          # nothing in hand
            elif verb in ("go", "open"):
                y2 = 0.6
        y2 = _clip(y2)

        # ---- y3 process-predicate advancement ----
        if need_proc and not proc_done:
            if verb in ("clean", "heat", "cool") and is_tool_recep and holding_target:
                y3 = 0.95
            elif verb == "go" and is_tool_recep and holding_target:
                y3 = 0.72
            elif verb == "put":
                y3 = 0.12
            elif verb == "take" and is_target_obj:
                y3 = 0.55
            else:
                y3 = 0.4
        elif need_light:
            if verb == "use" and holding_target:
                y3 = 0.92
            elif verb == "take" and is_target_obj:
                y3 = 0.6
            elif verb == "go" and holding_target:
                y3 = 0.6
            elif verb == "put":
                y3 = 0.05          # putting down aborts the look task
            else:
                y3 = 0.4
        else:
            y3 = 0.5
        y3 = _clip(y3)

        # ---- y4 container affordance ----
        y4 = 0.4
        rid = recep
        rec = world.receps.get(rid) if rid else None
        if verb == "open":
            if holding_target and is_dest_recep:
                y4 = 0.85
            elif rec is not None and not rec.searched:
                y4 = 0.85
            else:
                y4 = 0.3
        elif verb == "go":
            if holding_target and recep == phase.get("lamp_recep"):
                y4 = 0.75
            elif holding_target and is_dest_recep:
                y4 = 0.8
            elif holding_target and is_tool_recep and not proc_done:
                y4 = 0.7
            elif rec is not None and rec.searched:
                y4 = 0.18
            elif searching:
                y4 = 0.35 + 0.32 * location_prior(g_obj, recep_cls or "")
            else:
                y4 = 0.45
        elif verb == "take":
            y4 = 0.72 if is_target_obj else 0.3
        elif verb == "put" and is_dest_recep:
            y4 = 0.8
        elif verb in ("clean", "heat", "cool", "use"):
            y4 = 0.7
        y4 = _clip(y4)

        # ---- y5 goal association ----
        y5 = 0.15
        assoc = 0.0
        if is_target_obj:
            assoc = max(assoc, 0.9)
        if is_dest_recep and holding_target:
            assoc = max(assoc, 0.85)
        if is_tool_recep and (need_proc or need_light) and holding_target:
            assoc = max(assoc, 0.8)      # tool matters only once we hold the object
        if verb == "go" and searching and recep == phase.get("target_recep"):
            assoc = max(assoc, 0.9)
        elif verb in ("go", "open") and searching and g_obj:
            # blend the rule prior with the YLYW object-receptacle gua resonance so
            # each frontier receptacle carries a distinct yao signature that the L3
            # hexagram layer can reorder (measured by YLYW_action_influence).
            prior_a = location_prior(g_obj, recep_cls or "")
            res = object_recep_resonance(g_obj, recep_cls or "")
            assoc = max(assoc, 0.15 + 0.42 * prior_a + 0.25 * res)
        if verb == "open":
            if holding_target and is_dest_recep:
                assoc = max(assoc, 0.85)
            elif searching and g_obj:
                assoc = max(assoc, 0.35 + 0.5 * location_prior(g_obj, recep_cls or ""))
        if verb == "use" and need_light:
            assoc = max(assoc, 0.85)
        if verb == "go" and holding_target and need_light and recep == phase.get("lamp_recep"):
            assoc = max(assoc, 0.9)
        y5 = _clip(assoc if assoc > 0 else 0.15)

        # ---- y6 novelty vs failure history ----
        y6 = 0.55
        sk = world.state_key()
        if (sk, parsed["cmd"]) in world.failed_sa:
            y6 = 0.05
        elif verb == "go" and holding_target and (recep == phase.get("lamp_recep")
                or is_dest_recep or (is_tool_recep and not proc_done)):
            y6 = 0.6          # purposeful revisit toward goal target
        elif verb == "go" and rec is not None and rec.searched:
            y6 = 0.2
        elif verb == "open" and rec is not None and rec.searched:
            y6 = 0.1
        elif verb == "go" and rec is not None and not rec.visited:
            y6 = 0.85
        elif verb == "open" and rec is not None and not rec.searched:
            y6 = 0.8
        elif verb in ("take", "put", "clean", "heat", "cool", "use"):
            y6 = 0.7
        y6 = _clip(y6)

        return [y1, y2, y3, y4, y5, y6]

    # ---------------- L3 routing hook (retry-chain / stuck recovery) ----------------
    def dest_favorability(self, world, goal, phase: Dict, dest_cls: str,
                          obj_cls: Optional[str]) -> float:
        """Hexagram favorability of placing the goal object at `dest_cls` in the
        CURRENT six-yao situation. Used by the agent to order the destination
        retry-chain (吉者先试) as a tie-break on top of the train prior. Respects
        the ablation mode so the ordering genuinely reflects the L3 layer:
          full     → the matched hexagram's favorability differentiates dests
          linear   → constant (routing falls back to the pure prior order)
          no_favor → constant 0.66 (template match kept elsewhere, favor flat)
          fixed_yao→ yao frozen, so every dest maps to the same hexagram
          perm     → permuted favorability table
        """
        if self.mode == "linear":
            return 0.5
        # Evaluate "approach this destination for the object" in a search-style
        # situation: the object→receptacle gua resonance + location prior give each
        # destination a DISTINCT six-yao signature (a flat 'put' yao would not),
        # which the 64-hexagram matcher maps to a hexagram whose favorability orders
        # the retry chain.
        parsed = {"cmd": f"go to {dest_cls} 1", "verb": "go", "obj": None,
                  "recep": f"{dest_cls} 1", "obj_cls": None, "recep_cls": dest_cls}
        ph = dict(phase)
        ph["holding_target"] = None
        ph["searching"] = True
        ph["target_recep"] = None
        ph["lamp_recep"] = None
        yao = [0.5] * 6 if self.mode == "fixed_yao" else self.build_yao(parsed, world, goal, ph)
        hx, _ = self.hr.get_best_hexagram(np.array(yao, dtype=float))
        if self.mode == "no_favor":
            return 0.66
        return float(self._fav[hx.value])

    # ---------------- L3 match + fusion ----------------
    def score_candidate(self, cmd: str, world, goal, phase: Dict) -> Candidate:
        parsed = parse_action(cmd)
        yao = self.build_yao(parsed, world, goal, phase)
        if self.mode == "fixed_yao":
            yao = [0.5] * 6
        vec = np.array(yao, dtype=float)
        hx, cos = self.hr.get_best_hexagram(vec)
        favor = float(self._fav[hx.value])
        if self.mode == "no_favor":
            favor = 0.66

        # L1 action gua affinity: Hamming similarity between the action's own
        # primitive gua and the situation's thresholded yao signature.
        prim = _VERB_PRIM.get(parsed["verb"], "look")
        agua = get_gua_by_action_type(prim) or "000000"
        sig = "".join("1" if v > 0.5 else "0" for v in yao)
        gua_aff = sum(1 for a, b in zip(agua, sig) if a == b) / 6.0

        # goal-progress magnitude (== the no-hexagram linear baseline used to
        # measure YLYW_action_influence)
        lin = float(np.dot(vec, _LIN_W) / _LIN_W.sum())
        # YLYW score: the matched hexagram's favorability MULTIPLICATIVELY gates the
        # goal-progress magnitude, with template-match quality (cos) and L1 action-
        # gua affinity as secondary factors. This makes the L3 hexagram a genuine
        # argmax factor (high influence). Protective vetoes (reversal / already-
        # placed / leave-closed-dest / non-target-take) remove the pathological
        # near-ties so a clearly dominant goal action still wins on magnitude.
        if self.mode == "linear":
            ylyw = lin
        else:
            ylyw = lin * favor * (0.75 + 0.25 * cos) * (0.92 + 0.08 * gua_aff)

        return Candidate(
            cmd=cmd, parsed=parsed, yao=yao,
            hexagram=hx.name, hex_cn=self._hex_cn[hx.value],
            cos=cos, favor=favor, gua_affinity=gua_aff,
            ylyw_score=ylyw, linear_score=lin,
        )
