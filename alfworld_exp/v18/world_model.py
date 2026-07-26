#!/usr/bin/env python3
"""
world_model.py — instance-level world state for ALFWorld v18 (spec §4).

Design principles:
  * admissible_commands is the PRIMARY normalized state interface (more stable
    than observation regex). obs text is used as a secondary source for content
    lists / success signals.
  * Instance-level facts only (numbered ids like "cabinet 3", "apple 1"); never
    type-level conflation.
  * Monotone progress flags: visited -> opened -> searched -> exhausted.
    The only non-monotone concept is `revisit_required` (handled by the agent,
    not stored here as decay).
  * The model updates exactly ONCE per transition via `observe_transition`
    (spec §3: no double bookkeeping).

Command grammar observed from the live env (AlfredDemangler wrapper):
  go to <recep>            open <recep>          close <recep>
  take <obj> from <recep>  move <obj> to <recep> (== put)
  clean <obj> with <recep> heat <obj> with <recep> cool <obj> with <recep>
  use <lamp>               examine <x>           inventory / look / help
Instances always carry a number: "cabinet 3", "apple 1", "desklamp 1".
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# Receptacle vs object typing (class-level, from v17 word tables + env probing).
RECEPTACLE_CLASSES = {
    "cabinet", "drawer", "countertop", "diningtable", "coffeetable", "sidetable",
    "desk", "dresser", "shelf", "bed", "sofa", "armchair", "ottoman", "cart",
    "fridge", "microwave", "sinkbasin", "stoveburner", "toaster", "coffeemachine",
    "garbagecan", "safe", "toilet", "bathtubbasin", "handtowelholder",
    "towelholder", "toiletpaperhanger", "tvstand", "laundryhamper", "stove",
    "sink",
}
# Receptacle classes that can be opened.
OPENABLE_CLASSES = {"cabinet", "drawer", "fridge", "microwave", "safe",
                    "box", "laundryhamper"}
# Tool receptacles (used to process objects, not primary storage targets).
TOOL_CLASSES = {"sinkbasin", "microwave", "fridge", "desklamp"}

_ARRIVE_RE = re.compile(r"you arrive at (?:the )?([a-z]+ \d+)", re.I)
_CLOSED_RE = re.compile(r"the ([a-z]+ \d+) is closed", re.I)
_OPEN_RE = re.compile(r"you open the ([a-z]+ \d+)", re.I)
_PICK_RE = re.compile(r"you pick up the ([a-z]+ \d+) from the ([a-z]+ \d+)", re.I)
_PICK_RE2 = re.compile(r"you pick up the ([a-z]+ \d+)", re.I)
_PUT_RE = re.compile(r"you (?:put|place|move) the ([a-z]+ \d+) (?:in|on|to|in/on) (?:the )?([a-z]+ \d+)", re.I)
_SEE_RE = re.compile(r"you see (.+?)\.?$", re.I)
_ITEM_RE = re.compile(r"\ba ([a-z]+ \d+)")


def class_of(instance: str) -> str:
    """'cabinet 3' -> 'cabinet'."""
    return instance.rsplit(" ", 1)[0] if instance else instance


def is_receptacle(instance: str) -> bool:
    return class_of(instance) in RECEPTACLE_CLASSES


def is_openable(instance: str) -> bool:
    return class_of(instance) in OPENABLE_CLASSES


@dataclass
class Receptacle:
    id: str
    cls: str
    visited: bool = False
    is_open: Optional[bool] = None      # None = unknown/not-openable-known
    searched: bool = False              # contents fully observed at least once
    exhausted: bool = False             # searched AND does not / no longer holds target
    contents: Set[str] = field(default_factory=set)

    @property
    def openable(self) -> bool:
        return self.cls in OPENABLE_CLASSES


@dataclass
class Obj:
    id: str
    cls: str
    location: Optional[str] = None      # recep id | 'inventory' | None(unknown)
    in_inventory: bool = False
    deposited: bool = False             # placed at a (goal) receptacle
    processed: Set[str] = field(default_factory=set)  # {'clean','hot','cold','examined'}


class WorldModel:
    """Instance-level world state. One update per transition."""

    def __init__(self):
        self.receps: Dict[str, Receptacle] = {}
        self.objs: Dict[str, Obj] = {}
        self.location: Optional[str] = None
        self.inventory: Set[str] = set()
        self.step_count: int = 0
        # failed (state_key, action) pairs — proven no-progress
        self.failed_sa: Set[Tuple[str, str]] = set()
        self.all_receptacles: Set[str] = set()   # every recep id ever seen in admissible
        self.last_state_key: Optional[str] = None

    # ------------------------------------------------------------------
    # initial ingestion
    # ------------------------------------------------------------------
    def init_from_reset(self, obs: str, admissible: List[str]):
        self._ingest_admissible(admissible)
        self._ingest_obs(obs, action="")

    # ------------------------------------------------------------------
    # helpers to register instances
    # ------------------------------------------------------------------
    def _recep(self, rid: str) -> Receptacle:
        r = self.receps.get(rid)
        if r is None:
            r = Receptacle(id=rid, cls=class_of(rid))
            self.receps[rid] = r
            self.all_receptacles.add(rid)
        return r

    def _obj(self, oid: str) -> Obj:
        o = self.objs.get(oid)
        if o is None:
            o = Obj(id=oid, cls=class_of(oid))
            self.objs[oid] = o
        return o

    # ------------------------------------------------------------------
    # admissible parsing (primary interface)
    # ------------------------------------------------------------------
    def _ingest_admissible(self, admissible: List[str]):
        """Register all receptacles reachable via 'go to', and learn open/closed
        state + contents from location-relative commands."""
        for c in admissible:
            toks = c.split()
            if c.startswith("go to "):
                rid = c[len("go to "):].strip()
                self._recep(rid)
            elif c.startswith("open "):
                rid = c[len("open "):].strip()
                r = self._recep(rid)
                r.is_open = False           # 'open X' offered ⇒ currently closed
            elif c.startswith("close "):
                rid = c[len("close "):].strip()
                r = self._recep(rid)
                r.is_open = True            # 'close X' offered ⇒ currently open

    # ------------------------------------------------------------------
    # observation parsing (secondary)
    # ------------------------------------------------------------------
    def _parse_contents(self, text: str) -> Optional[List[str]]:
        """Return list of instance ids visible in a 'you see ...' clause,
        or [] for 'you see nothing', or None if no such clause."""
        m = _SEE_RE.search(text.strip())
        if not m:
            return None
        body = m.group(1)
        if "nothing" in body:
            return []
        return _ITEM_RE.findall(" " + body)

    def _ingest_obs(self, obs: str, action: str):
        if not obs:
            return
        low = obs

        # arrival → current location
        ma = _ARRIVE_RE.search(low)
        if ma:
            self.location = ma.group(1)
            r = self._recep(self.location)
            r.visited = True

        # closed / open notices
        for m in _CLOSED_RE.finditer(low):
            self._recep(m.group(1)).is_open = False
        mo = _OPEN_RE.search(low)
        if mo:
            r = self._recep(mo.group(1))
            r.is_open = True

        # contents list (only trust when we know which receptacle it refers to)
        target_recep = None
        if ma:
            target_recep = self.location
        if mo:
            target_recep = mo.group(1)
        # "On the X, you see ..." / "In it, you see ..."
        m_on = re.search(r"on the ([a-z]+ \d+), you see", low, re.I)
        if m_on:
            target_recep = m_on.group(1)
        contents = self._parse_contents(low)
        if contents is not None and target_recep is not None:
            r = self._recep(target_recep)
            # object instances only (exclude nested receptacles)
            objitems = [c for c in contents if not is_receptacle(c)]
            r.contents = set(objitems)
            for oid in objitems:
                o = self._obj(oid)
                if not o.in_inventory:
                    o.location = target_recep

        # pick up
        mp = _PICK_RE.search(low)
        if mp:
            oid, rid = mp.group(1), mp.group(2)
            self._take(oid, rid)
        else:
            mp2 = _PICK_RE2.search(low)
            if mp2 and "from" not in low.lower():
                self._take(mp2.group(1), None)

        # put / move
        mput = _PUT_RE.search(low)
        if mput:
            oid, rid = mput.group(1), mput.group(2)
            self._put(oid, rid)

        # process success signals
        al = (action or "").lower()
        if al.startswith("clean ") and "clean" in low.lower():
            self._mark_processed(al, "clean")
        elif al.startswith("heat ") and ("heat" in low.lower() or "hot" in low.lower()):
            self._mark_processed(al, "hot")
        elif al.startswith("cool ") and ("cool" in low.lower() or "chill" in low.lower()):
            self._mark_processed(al, "cold")
        elif al.startswith("use ") and self.inventory:
            # look_at: using the lamp examines whatever is held
            for oid in self.inventory:
                self._obj(oid).processed.add("examined")

    def _mark_processed(self, action_lower: str, tag: str):
        # "clean apple 1 with sinkbasin 1"
        m = re.search(r"^(?:clean|heat|cool) ([a-z]+ \d+) with", action_lower)
        oid = m.group(1) if m else (next(iter(self.inventory), None))
        if oid:
            self._obj(oid).processed.add(tag)

    def _take(self, oid: str, rid: Optional[str]):
        o = self._obj(oid)
        o.in_inventory = True
        o.location = "inventory"
        o.deposited = False
        self.inventory.add(oid)
        if rid and rid in self.receps:
            self.receps[rid].contents.discard(oid)

    def _put(self, oid: str, rid: str):
        o = self._obj(oid)
        o.in_inventory = False
        o.location = rid
        o.deposited = True
        self.inventory.discard(oid)
        r = self._recep(rid)
        r.contents.add(oid)

    # ------------------------------------------------------------------
    # transition entry point (spec §3 — single update per transition)
    # ------------------------------------------------------------------
    def observe_transition(self, action: str, obs: str, admissible_after: List[str],
                           changed: Optional[bool] = None):
        self.step_count += 1
        pre_key = self.last_state_key
        self._ingest_obs(obs, action)
        self._ingest_admissible(admissible_after)
        self._sync_current_location_flags(admissible_after)
        post_key = self.state_key()
        # no-progress detection: state unchanged after a state-changing action type
        if pre_key is not None and pre_key == post_key and self._is_stateful(action):
            self.failed_sa.add((pre_key, action))
        self.last_state_key = post_key

    def _sync_current_location_flags(self, admissible_after: List[str]):
        """When we can act on the current receptacle, mark searched/exhausted."""
        if not self.location:
            return
        r = self.receps.get(self.location)
        if r is None:
            return
        # If the receptacle is not openable, or is open, and we have observed its
        # contents at least once, mark it searched.
        openable = r.openable
        can_open_here = any(c == f"open {r.id}" for c in admissible_after)
        # after arriving/opening we have parsed contents; if openable and still
        # closed (open cmd present) we have NOT searched it yet.
        if openable and can_open_here:
            return  # still closed, not searched
        r.visited = True
        r.searched = True

    @staticmethod
    def _is_stateful(action: str) -> bool:
        a = action.strip().lower()
        return a.split(" ", 1)[0] in {
            "take", "move", "put", "open", "close", "clean", "heat", "cool", "use"
        }

    # ------------------------------------------------------------------
    # state key for anti-oscillation
    # ------------------------------------------------------------------
    def state_key(self) -> str:
        inv = ",".join(sorted(self.inventory))
        opened = ",".join(sorted(r.id for r in self.receps.values() if r.is_open))
        searched = ",".join(sorted(r.id for r in self.receps.values() if r.searched))
        proc = ",".join(sorted(f"{o.id}:{'|'.join(sorted(o.processed))}"
                               for o in self.objs.values() if o.processed))
        dep = ",".join(sorted(o.id for o in self.objs.values() if o.deposited))
        return f"loc={self.location}|inv={inv}|op={opened}|se={searched}|pr={proc}|dep={dep}"

    # ------------------------------------------------------------------
    # queries used by agent / scorer
    # ------------------------------------------------------------------
    def holding_target(self, obj_classes) -> Optional[str]:
        classes = {obj_classes} if isinstance(obj_classes, str) else set(obj_classes or [])
        for oid in self.inventory:
            if class_of(oid) in classes:
                return oid
        return None

    def known_objects_of(self, obj_class: str) -> List[str]:
        return [o.id for o in self.objs.values() if o.cls == obj_class]

    def unsearched_receptacles(self) -> List[str]:
        return [r.id for r in self.receps.values() if not r.searched]

    def find_object_location(self, obj_class: str) -> Optional[str]:
        """A known, non-inventory instance's receptacle, if any."""
        for o in self.objs.values():
            if o.cls == obj_class and not o.in_inventory and o.location \
                    and o.location != "inventory":
                return o.location
        return None

    def find_pending_target_recep(self, obj_classes, dest_class: Optional[str]) -> Optional[str]:
        """Receptacle holding a known target instance that is NOT in inventory and
        NOT already deposited at the destination — i.e. a next pickup target
        (spec §6: revisit the known second-instance location before blind search)."""
        classes = {obj_classes} if isinstance(obj_classes, str) else set(obj_classes or [])
        if not classes:
            return None
        for o in self.objs.values():
            if o.cls not in classes or o.in_inventory:
                continue
            if o.location in (None, "inventory"):
                continue
            if o.deposited and dest_class and class_of(o.location) == dest_class:
                continue   # already placed at destination
            return o.location
        return None

    def find_lamp_recep(self) -> Optional[str]:
        """Receptacle where a (desk/floor) lamp has been observed, if any."""
        for cls in ("desklamp", "floorlamp"):
            loc = self.find_object_location(cls)
            if loc:
                return loc
        return None
