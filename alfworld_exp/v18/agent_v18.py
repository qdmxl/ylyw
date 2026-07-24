#!/usr/bin/env python3
"""
agent_v18.py — YLYW-ALFWorld v18 agent. Strict two-phase controller (spec §3):

    action = agent.act(obs, admissible)          # pure decision
    obs2, info2 = env.step(action)
    agent.observe_transition(action, obs2, admissible_after, won)

Pipeline per step:
  1. build candidate set from admissible_commands
  2. compute task phase from the instance world model
  3. veto physically-pointless / proven-no-progress candidates (spec §4-6)
     — veto only removes candidates; the hexagram scorer picks the winner
  4. YLYWScorer scores every surviving candidate (six-yao → 64-hexagram → score)
  5. argmax = action; full decision log appended to JSONL

No self-reported win; the eval loop trusts only env `won`.
"""
from __future__ import annotations
import json
import os
import sys
from typing import Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from goal_parser import parse_goal, Goal          # noqa: E402
from world_model import WorldModel, class_of       # noqa: E402
from ylyw_scorer import YLYWScorer, Candidate      # noqa: E402

# When the NL-parsed destination class has no instance in the scene (human names
# like "tv stand" may not match the PDDL receptacle), fall back to the closest
# plausible surface actually present. Pure NL grounding; no PDDL truth used.
DEST_FALLBACK = {
    "tvstand": ["dresser", "sidetable", "shelf", "coffeetable", "diningtable", "cabinet"],
    "sidetable": ["dresser", "shelf", "coffeetable", "countertop"],
    "coffeetable": ["sidetable", "diningtable", "sofa"],
    "diningtable": ["countertop", "sidetable"],
    "countertop": ["diningtable", "sidetable"],
    "cabinet": ["drawer", "shelf", "countertop", "dresser"],
    "drawer": ["cabinet", "sidetable", "countertop"],
    "shelf": ["dresser", "sidetable", "cabinet"],
    "dresser": ["sidetable", "shelf"],
    "sinkbasin": ["countertop"],
    "garbagecan": ["countertop"],
    "cart": ["countertop", "shelf", "garbagecan", "sidetable"],
    "safe": ["drawer", "dresser", "sidetable", "cabinet"],
    "toilet": ["toiletpaperhanger", "cabinet", "countertop"],
    "armchair": ["sofa", "sidetable", "coffeetable"],
    "sofa": ["armchair", "coffeetable", "sidetable"],
    "coffeemachine": ["countertop", "cabinet", "shelf"],
}

_INFO_VERBS = {"look", "inventory", "examine", "help"}

# Generic placement surfaces tried (in order) as a last-resort destination retry
# for simple move tasks whose stated surface is a noisy annotation (e.g. "move
# the pencil ... on the desk" whose PDDL target is actually a shelf).
_RETRY_SURFACES = ["shelf", "sidetable", "dresser", "countertop", "diningtable",
                   "drawer", "cabinet", "desk", "coffeetable", "garbagecan"]

import re as _re
_TAKE_RE = _re.compile(r"take (.+?) from (.+)$", _re.I)
_MOVE_RE = _re.compile(r"(?:move|put) (.+?) (?:to|in|on|in/on) (.+)$", _re.I)


def _is_reversal(prev: str, cur: str) -> bool:
    """True if `cur` exactly undoes `prev` (take X from Y <-> move X to Y)."""
    pt, pm = _TAKE_RE.match(prev.lower()), _MOVE_RE.match(prev.lower())
    ct, cm = _TAKE_RE.match(cur.lower()), _MOVE_RE.match(cur.lower())
    if pt and cm:   # prev take X from Y ; cur move X to Y
        return pt.group(1) == cm.group(1) and pt.group(2) == cm.group(2)
    if pm and ct:   # prev move X to Y ; cur take X from Y
        return pm.group(1) == ct.group(1) and pm.group(2) == ct.group(2)
    return False


class AgentV18:
    def __init__(self, log_path: Optional[str] = None, look_budget: int = 1,
                 max_steps: int = 50, verbose: bool = False,
                 ylyw_mode: str = "full", seed: int = 0):
        self.scorer = YLYWScorer(mode=ylyw_mode, seed=seed)
        self.log_path = log_path
        self.look_budget = look_budget
        self.max_steps = max_steps
        self.verbose = verbose
        self._log_fp = None
        self.reset_state()

    def reset_state(self):
        self.goal: Optional[Goal] = None
        self.world = WorldModel()
        self.step_idx = 0
        self._look_used = 0
        self._decision_logs: List[Dict] = []
        self.game_id = None
        self.task_desc = ""
        self._last_action: Optional[str] = None
        self._recoveries = 0
        self._deposited_failed: set = set()   # object classes proven wrong (retry)
        self._recep_failed: set = set()        # destination classes proven wrong
        self._cmd_count: Dict[str, int] = {}   # exact-command issue counter (loop guard)
        self._retry_events = 0                  # bounded number of retries per episode
        self._count_bonus = 0                   # multiplicity under-count correction
        self._l3_routed = 0                     # L3-favor reorderings of the dest chain
        self._retry_toggle = 0                  # alternates dest/obj retry when both plausible

    # ------------------------------------------------------------------
    def reset(self, task_desc: str, obs: str, admissible: List[str], game_id=None):
        self.reset_state()
        self.task_desc = task_desc
        self.game_id = game_id
        self.goal = parse_goal(task_desc)
        self.world.init_from_reset(obs, admissible)
        self._resolve_destination()
        self.world.last_state_key = self.world.state_key()

    def _present_classes(self) -> set:
        return {class_of(rid) for rid in self.world.all_receptacles}

    def _resolve_one_dest(self, rc: Optional[str], present: set) -> Optional[str]:
        """Map a desired dest class to a present one (self or DEST_FALLBACK)."""
        if not rc:
            return None
        if rc in present:
            return rc
        for alt in DEST_FALLBACK.get(rc, []):
            if alt in present:
                return alt
        return None

    def _available_dests(self) -> List[str]:
        """Ordered, present, not-yet-failed destination classes (Fix #4/#6 retry).
        Resolves each candidate through DEST_FALLBACK; de-dupes preserving order."""
        g = self.goal
        present = self._present_classes()
        out: List[str] = []
        cands = g.recep_classes or ([g.recep_class] if g.recep_class else [])
        if len(cands) == 1:
            # single explicit destination: resolve through DEST_FALLBACK (human name
            # may not match the PDDL class) and widen with fallback surfaces so a
            # mislabel ('drawer' vs the adjacent cabinet) is still recoverable.
            r = self._resolve_one_dest(cands[0], present)
            if r and r not in self._recep_failed:
                out.append(r)
            for alt in DEST_FALLBACK.get(cands[0], []):
                if alt in present and alt not in out and alt not in self._recep_failed:
                    out.append(alt)
        else:
            # multi-candidate list (put-away prior / bare-'table' surfaces): the
            # candidates are already comprehensive, so take only the DIRECTLY present
            # classes in prior order. Resolving absent ones through DEST_FALLBACK
            # would inject unrelated, unplaceable receptacles (sidetable→shelf).
            for rc in cands:
                if rc in present and rc not in out and rc not in self._recep_failed:
                    out.append(rc)
        return out

    def _resolve_destination(self):
        """Point goal.recep_class at the first available (present, not-failed)
        destination candidate for this scene."""
        g = self.goal
        if not (g.recep_classes or g.recep_class):
            return
        avail = self._available_dests()
        if avail:
            g.recep_class = avail[0]

    # ------------------------------------------------------------------
    # phase computation (from world model; never from info truth)
    # ------------------------------------------------------------------
    def _known_instance(self, cls: str) -> bool:
        """True if a non-deposited, non-inventory instance of cls is known."""
        for o in self.world.objs.values():
            if o.cls == cls and not o.in_inventory and not o.deposited \
                    and o.location not in (None, "inventory"):
                return True
        return False

    def _has_unsearched(self) -> bool:
        """Any receptacle not yet searched (frontier remains for the primary)."""
        return any(not r.searched for r in self.world.receps.values())

    def _deposited_elsewhere(self, cls: str) -> bool:
        """A known instance of cls we already placed at a now-abandoned destination
        (deposited, not in inventory, and NOT at the current target recep) — it must
        be re-acquired and relocated rather than searching for a fresh instance."""
        g = self.goal
        for o in self.world.objs.values():
            if o.cls == cls and o.deposited and not o.in_inventory and o.location \
                    and o.location != "inventory" and class_of(o.location) != g.recep_class:
                return True
        return False

    def _phase(self) -> Dict:
        g = self.goal
        gclasses = [c for c in (g.object_classes or ([g.object_class] if g.object_class else []))
                    if c not in self._deposited_failed]
        if not gclasses:   # all demoted — reconsider everything
            gclasses = g.object_classes or ([g.object_class] if g.object_class else [])
        # focus: highest-priority candidate class that has a known instance; if none
        # is known yet, the first candidate (so exploration is unbiased). Used to
        # stop the agent grabbing a lower-priority ambiguous class (e.g. mug when
        # the goal really is a cup) before the preferred one is ruled out.
        focus_class = None
        if g.count >= 2:
            # pick_two: stick to the primary (highest-priority, non-demoted) class so
            # we collect COUNT of the SAME referent — never mix ambiguity classes
            # (soapbar vs soapbottle). Demotion happens only when the primary is
            # proven exhausted (see _maybe_retry).
            focus_class = gclasses[0] if gclasses else None
        else:
            # single-object: prefer relocating an object already placed at an
            # abandoned destination, else the highest-priority known instance.
            for c in gclasses:
                if self._deposited_elsewhere(c):
                    focus_class = c
                    break
            if focus_class is None:
                for c in gclasses:
                    if self._known_instance(c):
                        focus_class = c
                        break
            if focus_class is None and gclasses:
                focus_class = gclasses[0]
        holding_target = self.world.holding_target(gclasses) if gclasses else None
        proc_tag = {"clean": "clean", "heat": "hot", "cool": "cold"}.get(g.process)
        proc_done = True
        if g.needs_process() and holding_target:
            proc_done = proc_tag in self.world.objs[holding_target].processed
        elif g.needs_process():
            proc_done = False
        # placed targets (deposited at destination class), counting any target class
        placed = 0
        if g.recep_class:
            for o in self.world.objs.values():
                if o.cls in gclasses and o.deposited and o.location \
                        and class_of(o.location) == g.recep_class:
                    placed += 1
        eff_count = g.count + self._count_bonus
        searching = (holding_target is None) and (placed < eff_count)
        holding_junk = None
        for oid in self.world.inventory:
            if class_of(oid) not in gclasses:
                holding_junk = oid
                break
        return {
            "holding_target": holding_target,
            "proc_done": proc_done,
            "placed_count": placed,
            "eff_count": eff_count,
            "searching": searching,
            "gclasses": gclasses,
            "focus_class": focus_class,
            "holding_junk": holding_junk,
            "lamp_recep": self.world.find_lamp_recep() if g.needs_light() else None,
            # track only the FOCUS class: pointing at a secondary-class instance we
            # are not yet willing to take (await_primary) would cause oscillation.
            "target_recep": (self.world.find_pending_target_recep(
                                [focus_class] if focus_class else gclasses, g.recep_class)
                             if (searching and gclasses) else None),
        }

    # ------------------------------------------------------------------
    # veto (spec §4-6): remove candidates only
    # ------------------------------------------------------------------
    def _veto(self, cand: Candidate, phase: Dict) -> (bool, str):
        p = cand.parsed
        verb = p["verb"]
        cmd = cand.cmd
        g = self.goal
        world = self.world

        if verb in _INFO_VERBS:
            # look/examine default-disabled; allow one 'look' only if we have no
            # location fix yet (obs/admissible inconsistency proxy).
            if verb == "look" and self._look_used < self.look_budget \
                    and world.location is None:
                return False, ""
            return True, "info_action"
        if verb == "close":
            return True, "no_close"

        # holding the wrong (demoted) object: free hands before anything else so a
        # new candidate can be picked up (Fix #1/#2 — look and dest-incompat retry).
        if phase.get("holding_junk"):
            if not (verb == "put" and p["obj"] == phase["holding_junk"]):
                return True, "drop_junk_first"

        sk = world.state_key()
        if (sk, cmd) in world.failed_sa:
            return True, "failed_sa"

        # anti-oscillation: veto an action that exactly undoes the last one
        if self._last_action and _is_reversal(self._last_action, cmd):
            return True, "reversal"

        # loop guard (Fix #0): an exact command issued many times is not making
        # progress. Never veto the actual winning move (place/process/use/goto
        # toward the current goal target).
        if self._cmd_count.get(cmd, 0) >= 4:
            exempt = False
            if verb == "put" and phase["holding_target"] and p["recep_cls"] == g.recep_class:
                exempt = True
            elif verb in ("clean", "heat", "cool") and phase["holding_target"] \
                    and not phase["proc_done"] and p["recep_cls"] == g.tool_class:
                exempt = True
            elif verb == "use" and g.needs_light() and phase["holding_target"]:
                exempt = True
            elif verb == "go" and phase["holding_target"] and (
                    p["recep_cls"] == g.recep_class or p["recep_cls"] == g.tool_class
                    or p["recep"] == phase.get("lamp_recep")
                    or p["recep"] == phase.get("target_recep")):
                exempt = True
            if not exempt:
                return True, "loop_cap"

        if verb == "go":
            # don't wander off a closed destination we are holding the target at:
            # opening it (then placing) is the productive move.
            if phase["holding_target"]:
                lr = world.receps.get(world.location) if world.location else None
                if lr is not None and lr.openable and lr.is_open is False \
                        and lr.cls == g.recep_class:
                    return True, "leave_closed_dest"
            rec = world.receps.get(p["recep"])
            # look task, lamp not yet located: sweep UNVISITED receptacles to find
            # it — do not revisit visited ones while frontier remains (else the
            # hexagram favor can trap us oscillating between two visited spots).
            if g.needs_light() and phase["holding_target"] \
                    and phase.get("lamp_recep") is None:
                if rec is not None and rec.visited \
                        and any(not r.visited for r in world.receps.values()):
                    return True, "look_sweep_unvisited"
            if rec is not None and rec.searched:
                revisit_ok = (
                    (bool(phase["holding_target"]) and (
                        p["recep_cls"] == g.recep_class or p["recep_cls"] == g.tool_class
                        or p["recep"] == phase.get("lamp_recep")
                        or g.needs_light()))
                    or p["recep"] == phase.get("target_recep"))  # known next-pickup loc
                if not revisit_ok:
                    return True, "searched_recep"
        if verb == "open":
            rec = world.receps.get(p["recep"])
            if rec is not None and rec.is_open:
                return True, "already_open"
            if rec is not None and rec.searched:
                keep = bool(phase["holding_target"]) and p["recep_cls"] == g.recep_class
                if not keep:
                    return True, "searched_no_reopen"
        if verb == "take":
            # target membership respects demotions (gclasses = candidates minus
            # the classes already proven wrong via retry).
            gcl = phase.get("gclasses") or []
            is_target = (p["obj_cls"] in gcl) if gcl else True
            if not is_target and gcl:
                return True, "non_target_take"
            # focus priority (Fix #1): don't grab a lower-priority ambiguous class
            # while a higher-priority candidate is known present (e.g. mug vs cup).
            foc = phase.get("focus_class")
            if foc and p["obj_cls"] != foc and self._known_instance(foc):
                return True, "lower_priority_take"
            # await-primary (Fix #1): don't settle for a secondary ambiguous
            # referent while the primary candidate could still be found by
            # exploring the frontier (e.g. grabbing a mug/soapbottle before the
            # cup/soapbar the NL actually named). Single-object tasks only — for
            # pick_two the double-work of a wrong guess is too costly, so we trust
            # the first-found focus class and rely on retry instead.
            if (g.count < 2 and not g.is_look_enum and len(gcl) > 1
                    and p["obj_cls"] != gcl[0] and not self._known_instance(gcl[0])
                    and self._has_unsearched()):
                return True, "await_primary"
            # pick_two: don't grab a secondary ambiguity class while unsearched
            # receptacles may still hold another PRIMARY instance — collect two of
            # the SAME class, not a mix (soapbar/soapbottle, salt/pepper).
            if (g.count >= 2 and len(gcl) > 1 and p["obj_cls"] != gcl[0]
                    and self._has_unsearched()):
                return True, "await_primary_two"
            if phase["holding_target"] and g.count < 2:
                return True, "already_holding"
            # never re-take a target we already deposited at the destination
            o = world.objs.get(p["obj"])
            if o is not None and o.deposited and o.location \
                    and class_of(o.location) == g.recep_class:
                return True, "already_placed"
        return False, ""

    # ------------------------------------------------------------------
    # retry driver: only the env `won` is trusted, so if we appear "done" but
    # are still asked to act, the NL referent (object class) or the destination
    # was wrong — demote it and pursue the next candidate (spec fixes #1/#4/#6).
    # ------------------------------------------------------------------
    def _dest_incompatible(self, phase: Dict, admissible: List[str]) -> bool:
        """We are standing at the destination holding a fully-processed target, yet
        the destination offers no way to place THIS object class there — so the NL
        referent was wrong (e.g. a coffee-machine accepts a mug, not a cup)."""
        g = self.goal
        ht = phase["holding_target"]
        if not ht or len(g.object_classes) <= 1 or not g.recep_class:
            return False
        if g.needs_process() and not phase["proc_done"]:
            return False
        loc = self.world.location
        if not loc or class_of(loc) != g.recep_class:
            return False
        rec = self.world.receps.get(loc)
        if rec is not None and rec.openable and rec.is_open is not True:
            return False            # closed container: open it, don't demote
        for c in admissible:
            m = _MOVE_RE.match(c.lower())
            if m and m.group(1) == ht and class_of(m.group(2)) == g.recep_class:
                return False        # a valid placement here exists → compatible
        # only trust this when a placement onto some other receptacle IS offered
        # (i.e. the object is placeable in general, just not on this dest class)
        if not any(_MOVE_RE.match(c.lower()) for c in admissible):
            return False
        return True

    def _cannot_process_held(self, phase: Dict, admissible: List[str]) -> bool:
        """Holding a target object for a process task, standing at the tool, yet the
        tool offers no way to process THIS object — so the NL referent was wrong
        (e.g. a 'towel' where the goal needs a cleanable 'cloth')."""
        g = self.goal
        ht = phase["holding_target"]
        if not (ht and g.needs_process() and not phase["proc_done"]):
            return False
        if len(g.object_classes) <= 1:
            return False
        loc = self.world.location
        if not loc or class_of(loc) != g.tool_class:
            return False
        rec = self.world.receps.get(loc)
        if rec is not None and rec.openable and rec.is_open is not True:
            return False            # closed tool (microwave/fridge): open it first
        verb = {"clean": "clean", "heat": "heat", "cool": "cool"}[g.process]
        return not any(c.lower().startswith(f"{verb} {ht} ") for c in admissible)

    def _maybe_retry(self, phase: Dict, admissible: List[str]) -> Dict:
        g = self.goal
        if self._retry_events >= 10:
            return phase

        # --- unprocessable held object: wrong referent the tool won't process ---
        if self._cannot_process_held(phase, admissible):
            self._deposited_failed.add(class_of(phase["holding_target"]))
            self._retry_events += 1
            for r in self.world.receps.values():
                r.searched = False
            return self._phase()

        # --- pick_two primary exhausted: we have placed fewer than `count` of the
        # primary class and no un-placed instance of it remains anywhere in the fully
        # explored scene → the NL referent was wrong, demote to the next candidate. ---
        if (g.count >= 2 and len(g.object_classes) > 1
                and phase["holding_target"] is None and phase["searching"]
                and phase["placed_count"] < phase["eff_count"]):
            gcl = phase.get("gclasses") or []
            primary = gcl[0] if gcl else None
            explored = all(r.visited for r in self.world.receps.values())
            if primary and explored and not self._known_instance(primary):
                self._deposited_failed.add(primary)
                self._recep_failed.clear()
                for r in self.world.receps.values():
                    r.searched = False
                self._retry_events += 1
                self._resolve_destination()
                return self._phase()

        # --- dest-incompatibility: wrong referent that the destination rejects ---
        if self._dest_incompatible(phase, admissible):
            self._deposited_failed.add(class_of(phase["holding_target"]))
            self._retry_events += 1
            for r in self.world.receps.values():
                r.searched = False
            return self._phase()

        # --- look-enum retry: examined the wrong object → try next candidate ---
        if g.is_look_enum and phase["holding_target"] is not None:
            ht = phase["holding_target"]
            if "examined" in self.world.objs[ht].processed:
                self._deposited_failed.add(class_of(ht))
                self._retry_events += 1
                return self._phase()
            return phase

        # --- placement retry: placed >= (effective) count but env has not won ---
        if (phase["holding_target"] is None and not phase["searching"]
                and phase["placed_count"] >= phase["eff_count"] and not g.is_look_enum):
            # (a) under-counted multiplicity: for an UNAMBIGUOUS object whose NL
            # plurality was missed (e.g. "spray bottles" parsed as one), place an
            # extra known instance at the SAME destination before abandoning it.
            # Ambiguous objects (salt/pepper) skip this and prefer demotion.
            if len(g.object_classes) <= 1 and self._count_bonus < 3:
                extra = next(
                    (o for o in self.world.objs.values()
                     if o.cls in phase["gclasses"] and not o.deposited
                     and not o.in_inventory and o.location not in (None, "inventory")
                     and class_of(o.location) != g.recep_class), None)
                if extra is not None:
                    self._count_bonus += 1
                    return self._phase()
            deposited_here = [
                o for o in self.world.objs.values()
                if o.deposited and o.cls in phase["gclasses"] and o.location
                and class_of(o.location) == g.recep_class]
            remaining_obj = [c for c in (g.object_classes or [])
                             if c not in self._deposited_failed
                             and c not in {o.cls for o in deposited_here}]
            tried_dest = self._recep_failed | ({g.recep_class} if g.recep_class else set())
            remaining_dest = [d for d in self._available_dests() if d not in tried_dest]
            explored_all0 = all(r.visited for r in self.world.receps.values())
            # A single UNAMBIGUOUS object with an explicitly-named destination may be
            # an under-counted pick_two ('spray bottles' parsed as one). Do NOT switch
            # to a fallback destination until the scene is fully explored — a hidden
            # 2nd instance belongs at the SAME destination (count-bump). Ambiguous
            # objects / put-away tasks keep the widened dest chain for mislabel
            # recovery ('bottle' → soap/wine; NL-omitted destinations).
            if (len(g.object_classes) <= 1 and g.count < 2 and not g.is_putaway
                    and not explored_all0):
                remaining_dest = []
            # ambiguous pick_two: never relocate already-placed items to a different
            # destination — collect more same-class instances at the SAME dest
            # (sticky-primary focus + demotion) instead. Unambiguous pick_two keeps
            # the dest chain so a mislabeled destination ('cabinet'→dresser) recovers.
            if g.count >= 2 and len(g.object_classes) > 1:
                remaining_dest = []
            # last-resort surface fallback for simple move tasks (noisy dest label,
            # e.g. pencil "on the desk" whose PDDL target is a shelf). Only after a
            # full exploration pass, so a mis-counted pick_two (place a 2nd instance
            # at the SAME dest) is completed first rather than scattered elsewhere.
            explored_all = all(r.visited for r in self.world.receps.values())
            if (not remaining_dest and g.process is None and g.count < 2
                    and explored_all):
                present = self._present_classes()
                remaining_dest = [s for s in _RETRY_SURFACES
                                  if s in present and s not in tried_dest]

            # --- L3 routing (spec Task 2): order the destination retry-chain by the
            # hexagram favorability of placing the object there (吉者先试). The train
            # prior stays dominant — favorability only reorders WITHIN adjacent-rank
            # buckets (near-equal prior). Under ablations that flatten the gua this
            # is a no-op, so the ordering is a genuine, measurable L3 contribution.
            if len(remaining_dest) > 1:
                obj_for = deposited_here[0].cls if deposited_here else g.object_class
                order = list(remaining_dest)
                favs = {d: round(self.scorer.dest_favorability(
                            self.world, g, phase, d, obj_for), 3) for d in order}
                # 吉者先试: order by hexagram favorability. The favorability already
                # embeds the location prior (through the six-yao features), so the
                # train prior keeps high weight; the 64-hexagram 吉凶 provides the
                # final ordering and breaks ties via the prior order (stable index).
                idx = sorted(range(len(order)), key=lambda i: (-favs[order[i]], i))
                new_order = [order[i] for i in idx]
                if new_order != order:
                    self._l3_routed += 1
                remaining_dest = new_order

            def _switch_dest():
                if g.recep_class:
                    self._recep_failed.add(g.recep_class)
                g.recep_class = remaining_dest[0]
                for r in self.world.receps.values():
                    r.searched = False
                # a re-plan invalidates the last-action reversal guard: re-taking
                # the object we just placed (to relocate it) is now productive.
                self._last_action = None
                self._retry_events += 1
                return self._phase()

            def _demote_obj():
                for o in deposited_here:
                    self._deposited_failed.add(o.cls)
                # a fresh object referent deserves the full destination chain again
                # (the previous object may have exhausted the ambiguous table dests).
                self._recep_failed.clear()
                for r in self.world.receps.values():
                    r.searched = False
                self._last_action = None
                self._retry_events += 1
                self._resolve_destination()
                return self._phase()

            # Decide whether a failed placement means the DESTINATION was wrong or the
            # OBJECT referent was wrong. Three regimes:
            #   * put-away (NL omitted dest)  → object trusted, dest uncertain → DEST
            #   * single explicit dest        → object suspect ('clean knife'→butter-
            #                                    knife) → OBJECT
            #   * ambiguous surface ('table' → dining/side/coffee/…) → genuinely
            #     2-way ambiguous, so ALTERNATE dest/object across retries to give
            #     both referents a chance within budget.
            # Only chase an alternate object class if an instance is actually visible;
            # otherwise demoting the (placed, plausibly-right) object triggers a
            # fruitless re-search — relocate to another destination instead.
            alt_obj_visible = any(self._known_instance(c) for c in remaining_obj)
            can_dest = bool(remaining_dest)
            can_obj = bool(remaining_obj) and alt_obj_visible
            dest_ambiguous = (not g.is_putaway) and len(g.recep_classes or []) > 1
            if g.is_putaway and can_dest:
                return _switch_dest()
            if dest_ambiguous and can_dest and can_obj:
                self._retry_toggle ^= 1
                return _switch_dest() if self._retry_toggle else _demote_obj()
            if can_obj:
                return _demote_obj()
            if can_dest:
                return _switch_dest()
            if remaining_dest:     # right object, wrong destination → try next
                return _switch_dest()
            if remaining_obj:      # last resort: chase an unseen alternate referent
                return _demote_obj()
        return phase

    # ------------------------------------------------------------------
    # act (pure decision)
    # ------------------------------------------------------------------
    def _score_all(self, admissible: List[str], phase: Dict) -> List[Candidate]:
        cands: List[Candidate] = []
        for cmd in admissible:
            if cmd == "help":
                continue
            c = self.scorer.score_candidate(cmd, self.world, self.goal, phase)
            vetoed, reason = self._veto(c, phase)
            c.vetoed = vetoed
            c.veto_reason = reason
            cands.append(c)
        return cands

    def act(self, obs: str, admissible: List[str]) -> str:
        self.step_idx += 1
        phase = self._phase()
        # If we believe the task is placed (placed>=count, nothing in hand) yet we
        # are still being asked to act, the env did NOT register a win — the object
        # class we processed was the wrong NL referent (e.g. "knife" meant
        # butterknife). Demote it and pursue the alternate ambiguous class.
        g = self.goal
        phase = self._maybe_retry(phase, admissible)

        cands = self._score_all(admissible, phase)
        alive = [c for c in cands if not c.vetoed]

        def productive(cs):
            return [c for c in cs if c.parsed["verb"] not in _INFO_VERBS]

        # recovery (spec §5): if we are stuck with no productive move, re-open the
        # frontier (drop monotone searched flags) instead of emitting a dead
        # info action, then rescore once.
        if not productive(alive) and self._recoveries < 6:
            self._recoveries += 1
            for r in self.world.receps.values():
                r.searched = False
                r.exhausted = False
            self.world.failed_sa.clear()
            phase = self._phase()
            cands = self._score_all(admissible, phase)
            alive = [c for c in cands if not c.vetoed]

        prod = productive(alive)
        pool = prod if prod else (alive if alive else cands)
        best = max(pool, key=lambda c: c.ylyw_score)

        if best.parsed["verb"] == "look":
            self._look_used += 1
        self._cmd_count[best.cmd] = self._cmd_count.get(best.cmd, 0) + 1

        # decision log
        ranked = sorted(cands, key=lambda c: c.ylyw_score, reverse=True)
        rec = {
            "step": self.step_idx,
            "game_id": self.game_id,
            "phase": {k: v for k, v in phase.items()},
            "goal": self.goal.as_dict(),
            "location": self.world.location,
            "chosen": best.cmd,
            "chosen_hex": best.hexagram,
            "chosen_hex_cn": best.hex_cn,
            "n_candidates": len(cands),
            "n_alive": len(alive),
            "candidates": [c.log() for c in ranked[:12]],
        }
        self._decision_logs.append(rec)
        if self.verbose:
            print(f"[{self.step_idx}] {best.cmd}  <{best.hex_cn}> "
                  f"score={best.ylyw_score:.3f} alive={len(alive)}/{len(cands)}")
        return best.cmd

    # ------------------------------------------------------------------
    # observe (single update per transition)
    # ------------------------------------------------------------------
    def observe_transition(self, action: str, obs2: str,
                           admissible_after: List[str], won: bool = False):
        self.world.observe_transition(action, obs2, admissible_after)
        self._last_action = action

    # ------------------------------------------------------------------
    def dump_logs(self, extra: Dict = None):
        if not self.log_path:
            return
        with open(self.log_path, "a", encoding="utf-8") as f:
            for rec in self._decision_logs:
                if extra:
                    rec = {**rec, **extra}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def influence_stats(self) -> Dict:
        """Sampled YLYW participation metrics from this episode's logs (spec §8)."""
        multi = 0
        changed = 0
        total = 0
        for rec in self._decision_logs:
            cands = rec.get("candidates", [])
            alive = [c for c in cands if not c["veto"]]
            if len(alive) < 2:
                continue
            total += 1
            multi += 1
            ylyw_best = max(alive, key=lambda c: c["score"])["cmd"]
            lin_best = max(alive, key=lambda c: c["lin"])["cmd"]
            if ylyw_best != lin_best:
                changed += 1
        return {"decisions": len(self._decision_logs),
                "multi_candidate_decisions": multi,
                "argmax_changed_vs_linear": changed,
                "l3_dest_routings": self._l3_routed,
                "influence_rate": (changed / total) if total else 0.0}
