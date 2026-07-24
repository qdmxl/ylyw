#!/usr/bin/env python3
"""
run_v18_eval.py — honest evaluation entry for the v18 agent (spec §2).

Red lines enforced here:
  * agent-facing info WHITELIST: only task_desc / observation / admissible_commands.
    task_type / pddl_params / gamefile / expert_plan stay on the evaluator side and
    are used ONLY for post-hoc statistics, never passed to the agent.
  * fresh agent per game (no cross-episode mutable state).
  * 50-step cap, never relaxed.
  * win is ONLY env `won`; no self-report path.

Usage (inside WSL):
  python v18/run_v18_eval.py --split valid_seen --start 0 --end 40 \
         --output v18/results_seen_0_40.json
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time

sys.path.insert(0, "/mnt/e/Programming/research_ws/YLYW_ALFWorld/ylyw/alfworld_exp")
os.environ.setdefault("ALFWORLD_DATA", os.path.expanduser("~/.cache/alfworld"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# NOTE: alfworld_official_wrapper and agent_v18 are imported lazily inside main()
# AFTER --priors has been applied to os.environ, so that train_priors.py (imported
# transitively by agent_v18 -> goal_parser) picks up the requested priors file.

MAX_STEPS = 50

# Only these keys ever reach the agent.
AGENT_INFO_WHITELIST = ("task_desc", "admissible_commands")


def agent_view(info: dict) -> dict:
    return {k: info.get(k) for k in AGENT_INFO_WHITELIST}


def run_single(env, agent: AgentV18, game_idx: int) -> dict:
    obs, info = env.reset(game_idx=game_idx)
    view = agent_view(info)
    task_desc = view.get("task_desc") or ""
    admissible = view.get("admissible_commands") or ["look"]

    agent.reset(task_desc, obs, admissible, game_id=game_idx)

    won = False
    steps = 0
    actions = []
    for _ in range(MAX_STEPS):
        action = agent.act(obs, admissible)
        actions.append(action)
        obs, info = env.step(action)
        steps += 1
        # ONLY the environment decides victory.
        won = bool(info.get("won", False))
        admissible = (agent_view(info).get("admissible_commands")) or ["look"]
        agent.observe_transition(action, obs, admissible, won=won)
        if won or info.get("done", False):
            break

    infl = agent.influence_stats()
    return {
        "game_idx": game_idx,
        "won": won,
        "steps": steps,
        "actions": actions,
        # evaluator-side ground truth (NOT seen by agent) — post-hoc stats only
        "task_type_real": info.get("task_type", ""),
        "task_desc": task_desc,
        "parsed_goal": agent.goal.as_dict() if agent.goal else {},
        "influence": infl,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="valid_seen")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=40)
    ap.add_argument("--games", default="",
                    help="explicit comma-separated game indices (overrides start/end)")
    ap.add_argument("--games-file", default="",
                    help="heldout_games.json; selects games by game_file PATH mapped "
                         "to the current env ordering (robust to index reordering)")
    ap.add_argument("--priors", default="",
                    help="path to a train_priors json to load instead of the default "
                         "(injected via YLYW_PRIORS_PATH before agent import)")
    ap.add_argument("--output", default="v18/results.json")
    ap.add_argument("--logjsonl", default="")
    ap.add_argument("--ablation", default="full",
                    help="full|linear|no_favor|fixed_yao|perm")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    # Apply priors injection BEFORE importing the agent stack (train_priors.py reads
    # YLYW_PRIORS_PATH at import time). Loader-only mechanism; no decision changes.
    if args.priors:
        os.environ["YLYW_PRIORS_PATH"] = os.path.abspath(args.priors)
    global ALFWorldOfficial, AgentV18
    from alfworld_official_wrapper import ALFWorldOfficial   # noqa: E402
    from agent_v18 import AgentV18                            # noqa: E402
    import train_priors as _tp                                # noqa: E402
    print(f"[priors] loaded from: {_tp._PATH}")

    env = ALFWorldOfficial(split=args.split)
    n = env.num_games
    end = min(args.end, n)

    # Resolve --games-file (path-based selection, reorder-robust).
    games_from_file = None
    if args.games_file:
        h = json.load(open(args.games_file, encoding="utf-8"))
        want = [g["game_file"] for g in h.get("games", [])]
        path_to_idx = {gf: i for i, gf in enumerate(env.games)}
        rp_to_idx = {os.path.realpath(gf): i for i, gf in enumerate(env.games)}
        resolved, missing = [], []
        for gf in want:
            if gf in path_to_idx:
                resolved.append(path_to_idx[gf])
            elif os.path.realpath(gf) in rp_to_idx:
                resolved.append(rp_to_idx[os.path.realpath(gf)])
            else:
                missing.append(gf)
        if missing:
            print(f"WARNING: {len(missing)} held-out game_files not found in env; "
                  f"first missing: {missing[0]}")
        games_from_file = resolved
        print(f"[games-file] resolved {len(resolved)}/{len(want)} held-out games "
              f"to current-env indices")

    logpath = args.logjsonl or None
    if logpath and os.path.exists(logpath):
        os.remove(logpath)

    if games_from_file is not None:
        game_range = games_from_file
    elif args.games.strip():
        game_range = [int(x) for x in args.games.split(",") if x.strip() != ""]
    else:
        game_range = list(range(args.start, end))

    results = []
    t0 = time.time()
    for gi in game_range:
        agent = AgentV18(log_path=logpath, verbose=args.verbose,
                         ylyw_mode=args.ablation)                   # FRESH per game
        try:
            r = run_single(env, agent, gi)
        except Exception as e:
            import traceback
            traceback.print_exc()
            r = {"game_idx": gi, "won": False, "steps": MAX_STEPS,
                 "error": str(e), "actions": []}
        if logpath:
            agent.dump_logs(extra={"won": r["won"]})
        results.append(r)
        tag = "WON " if r["won"] else "lost"
        print(f"[{gi:3d}] {tag} steps={r['steps']:2d} "
              f"type={r.get('task_type_real',''):32s} :: {r.get('task_desc','')[:50]}")

    n_won = sum(1 for r in results if r["won"])
    n_tot = len(results)
    # per-type breakdown (evaluator-side)
    by_type = {}
    for r in results:
        t = r.get("task_type_real", "?")
        by_type.setdefault(t, [0, 0])
        by_type[t][1] += 1
        if r["won"]:
            by_type[t][0] += 1
    # influence aggregate
    inf_changed = sum(r.get("influence", {}).get("argmax_changed_vs_linear", 0) for r in results)
    inf_multi = sum(r.get("influence", {}).get("multi_candidate_decisions", 0) for r in results)
    inf_decisions = sum(r.get("influence", {}).get("decisions", 0) for r in results)

    summary = {
        "split": args.split,
        "range": [args.start, end],
        "success_rate": n_won / n_tot if n_tot else 0.0,
        "n_won": n_won,
        "n_total": n_tot,
        "by_type": {k: {"won": v[0], "total": v[1],
                        "rate": v[0] / v[1] if v[1] else 0.0}
                    for k, v in by_type.items()},
        "candidate_coverage": (inf_multi / inf_decisions) if inf_decisions else 0.0,
        "total_decisions": inf_decisions,
        "multi_candidate_decisions": inf_multi,
        "ylyw_influence_rate": (inf_changed / inf_multi) if inf_multi else 0.0,
        "ablation": args.ablation,
        "wall_time_s": round(time.time() - t0, 1),
        "results": results,
    }
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"SPLIT={args.split}  games[{args.start}:{end}]  "
          f"SUCCESS {n_won}/{n_tot} = {summary['success_rate']*100:.1f}%")
    for k, v in summary["by_type"].items():
        print(f"   {k:34s} {v['won']}/{v['total']} = {v['rate']*100:.0f}%")
    print(f"candidate_coverage (≥2 alive): {summary['candidate_coverage']*100:.1f}% "
          f"({inf_multi}/{inf_decisions})")
    print(f"YLYW influence (argmax≠linear on multi-cand): "
          f"{summary['ylyw_influence_rate']*100:.1f}%  "
          f"({inf_changed}/{inf_multi})")
    print(f"wall={summary['wall_time_s']}s  → {args.output}")


if __name__ == "__main__":
    main()
