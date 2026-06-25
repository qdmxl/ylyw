#!/usr/bin/env python3
"""
YLYW + ALFWorld 测试环境

轻量 ALFWorld 仿真器 - 85 个 valid_unseen 任务，7 种类型。
绕过 textworld PDDL 引擎，直接读取游戏 JSON 数据。

用法:
  python3 alfworld_agent.py --mode test          # 测试
  python3 alfworld_agent.py --mode random -n 20  # 随机agent
  python3 alfworld_agent.py --mode stats         # 统计
"""

import json
import os
import re
import random
import sys
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

# ── Paths ───────────────────────────────────────────────
ALFWORLD_DATA = Path.home() / ".cache" / "alfworld" / "json_2.1.1"
SPLIT = "valid_unseen"


# ── Helpers ──────────────────────────────────────────────
def shorten_name(name: str) -> str:
    """PDDL full name -> short name"""
    if '_bar_' in name:
        return name.split('_bar_')[0].lower()
    return name.lower()


def plan_to_walkthrough(plan: List[dict]) -> List[str]:
    """Convert expert plan to ALFWorld text commands (short names)"""
    cmds = []
    for entry in plan:
        da = entry.get('discrete_action', {})
        action = da.get('action', '')
        args = da.get('args', [])
        short_args = [shorten_name(a) for a in args]
        
        if action == 'NoOp':
            continue
        elif action == 'GotoLocation':
            cmds.append(f"go to {short_args[0]} 1")
        elif action == 'PickupObject':
            src = short_args[1] if len(short_args) > 1 else '?'
            cmds.append(f"take {short_args[0]} 1 from {src} 1")
        elif action == 'PutObject':
            dst = short_args[1] if len(short_args) > 1 else '?'
            cmds.append(f"put {short_args[0]} 1 in/on {dst} 1")
        elif action == 'OpenObject':
            cmds.append(f"open {short_args[0]} 1")
        elif action == 'CloseObject':
            cmds.append(f"close {short_args[0]} 1")
        elif action == 'ToggleObject':
            cmds.append(f"use {short_args[0]} 1")
        elif action == 'CleanObject':
            tool = short_args[1] if len(short_args) > 1 else '?'
            cmds.append(f"clean {short_args[0]} 1 with {tool} 1")
        elif action == 'HeatObject':
            tool = short_args[1] if len(short_args) > 1 else '?'
            cmds.append(f"heat {short_args[0]} 1 with {tool} 1")
        elif action == 'CoolObject':
            tool = short_args[1] if len(short_args) > 1 else '?'
            cmds.append(f"cool {short_args[0]} 1 with {tool} 1")
        elif action == 'SliceObject':
            tool = short_args[1] if len(short_args) > 1 else '?'
            cmds.append(f"slice {short_args[0]} 1 with {tool} 1")
        else:
            cmds.append(f"{action} {' '.join(short_args)}")
    return cmds


# ── ALFWorld Light Emulator ──────────────────────────────
class ALFWorldLight:
    """轻量 ALFWorld TextWorld 仿真器"""
    
    def __init__(self, data_dir=ALFWORLD_DATA, split=SPLIT):
        self.data_dir = Path(data_dir)
        self.split = split
        self.games = []
        self._load_games()
        
        self.current_game = -1
        self.current_step = 0
        self.max_steps = 50
        self.walkthrough = []
        self.task_desc = ""
        self.task_type = ""
        self.done = False
        self.won = False
    
    def _load_games(self):
        split_dir = self.data_dir / self.split
        for d in sorted(os.listdir(str(split_dir))):
            full = split_dir / d
            if full.is_dir():
                trials = sorted([t for t in os.listdir(str(full))
                               if (full / t).is_dir() and t.startswith('trial_')])
                if trials:
                    self.games.append((str(full), trials[0]))
    
    def reset(self, game_idx: int = None) -> Tuple[str, dict]:
        """Reset to game, return (observation, info)"""
        if game_idx is not None:
            self.current_game = game_idx % len(self.games)
        else:
            self.current_game = random.randint(0, len(self.games) - 1)
        
        game_dir, trial_id = self.games[self.current_game]
        trial_dir = Path(game_dir) / trial_id
        
        with open(trial_dir / 'traj_data.json') as f:
            self.traj_data = json.load(f)
        
        # Build walkthrough from plan (always use plan for consistency)
        self.walkthrough = plan_to_walkthrough(
            self.traj_data['plan']['high_pddl'])
        
        anns = self.traj_data['turk_annotations']['anns']
        self.task_desc = anns[0].get('task_desc', '')
        self.task_type = self.traj_data['task_type']
        
        self._parse_objects(trial_dir)
        
        self.current_step = 0
        self.done = False
        self.won = False
        
        obs = self._build_obs()
        cmds = self._get_commands()
        
        return obs, {
            'admissible_commands': cmds,
            'task_desc': self.task_desc,
            'task_type': self.task_type,
            'game_idx': self.current_game,
            'num_games': len(self.games),
            'walkthrough_len': len(self.walkthrough),
            'won': False, 'done': False,
        }
    
    def _parse_objects(self, trial_dir):
        trial_dir = Path(trial_dir)
        with open(trial_dir / 'initial_state.pddl') as f:
            state = f.read()
        self.receps = set()
        self.objects = set()
        for m in re.finditer(r'\(receptacleType\s+(\S+)', state):
            self.receps.add(m.group(1))
        for m in re.finditer(r'\(objectType\s+(\S+)', state):
            self.objects.add(m.group(1))
    
    def _build_obs(self) -> str:
        recep_shorts = []
        seen = set()
        for r in self.receps:
            s = shorten_name(r)
            if s not in seen:
                seen.add(s)
                recep_shorts.append(s)
        items = [f"a {s} {i+1}" for i, s in enumerate(recep_shorts)]
        obs = ("You are in the middle of a room. Looking quickly around you, "
               f"you see {', '.join(items)}.\n\n"
               f"Your task is to: {self.task_desc}")
        return obs
    
    def _get_commands(self) -> List[str]:
        base = ["look", "inventory", "help"]
        
        if self.current_step >= len(self.walkthrough):
            return base
        
        next_cmd = self.walkthrough[self.current_step]
        
        if next_cmd.startswith("go to"):
            rout = sorted(set(shorten_name(r) for r in self.receps))
            return [f"go to {s} 1" for s in rout] + base
        elif next_cmd.startswith("take"):
            return [next_cmd] + base
        elif next_cmd.startswith("put"):
            return [next_cmd] + base
        elif next_cmd.startswith("open"):
            return [next_cmd] + base
        elif next_cmd.startswith("close"):
            return [next_cmd] + base
        elif next_cmd.startswith("clean"):
            return [next_cmd] + base
        elif next_cmd.startswith("heat"):
            return [next_cmd] + base
        elif next_cmd.startswith("cool"):
            return [next_cmd] + base
        elif next_cmd.startswith("use"):
            return [next_cmd] + base
        elif next_cmd.startswith("slice"):
            return [next_cmd] + base
        
        return base
    
    def step(self, action: str) -> Tuple[str, dict]:
        action = action.strip()
        
        if self.done:
            return "Task already completed.", {
                'won': self.won, 'done': True, 'admissible_commands': []}
        
        if self.current_step >= len(self.walkthrough):
            self.done = True; self.won = True
            return "You won!", {
                'won': True, 'done': True, 'admissible_commands': []}
        
        expected = self.walkthrough[self.current_step].lower().strip()
        actual = action.lower().strip()
        
        # Accept: exact match
        if actual == expected:
            self.current_step += 1
            
            if self.current_step >= len(self.walkthrough):
                self.done = True; self.won = True
                return "You won!", {
                    'won': True, 'done': True, 'admissible_commands': []}
            
            obs = self._step_feedback()
            cmds = self._get_commands()
            return obs, {
                'won': False, 'done': False,
                'admissible_commands': cmds, 'step': self.current_step}
        
        return "That didn't work. Try something else.", {
            'won': False, 'done': False,
            'admissible_commands': self._get_commands()}
    
    def _step_feedback(self) -> str:
        if self.current_step <= 0:
            return self._build_obs()
        prev = self.walkthrough[self.current_step - 1].lower()
        
        if 'go to' in prev:
            target = prev.replace('go to ', '').replace(' 1', '')
            return (f"You arrive at loc {self.current_step}. "
                    f"On the {target}, you see some objects.")
        elif 'take' in prev:
            obj = prev.split(' from')[0].replace('take ', '').replace(' 1', '')
            return f"You pick up the {obj}."
        elif any(w in prev for w in ['put ', 'move ']):
            return "You place the object in/on the receptacle."
        elif 'open' in prev:
            target = prev.replace('open ', '').replace(' 1', '')
            return f"You open the {target}. In it, you see some objects."
        elif 'clean' in prev:
            return "You clean the object."
        elif 'heat' in prev:
            return "You heat the object."
        elif 'cool' in prev:
            return "You cool the object."
        elif 'use' in prev:
            return "You use the object."
        elif 'slice' in prev:
            return "You slice the object."
        return "OK."
    
    def get_stats(self) -> dict:
        task_types = defaultdict(int)
        for game_dir, trial_id in self.games:
            with open(Path(game_dir) / trial_id / 'traj_data.json') as f:
                d = json.load(f)
                task_types[d.get('task_type', 'unknown')] += 1
        return {
            'total_games': len(self.games),
            'task_types': dict(task_types),
        }


# ── Random Agent ─────────────────────────────────────────
def run_random_agent(env: ALFWorldLight, num_episodes: int = 10):
    results = []
    
    for ep in range(num_episodes):
        obs, info = env.reset()
        steps = 0
        won = False
        
        while steps < env.max_steps:
            cmds = info.get('admissible_commands', ['look'])
            action = random.choice(cmds)
            obs, info = env.step(action)
            steps += 1
            if info.get('done'):
                won = info.get('won', False)
                break
        
        results.append({
            'episode': ep,
            'task_type': env.task_type,
            'task_desc': env.task_desc,
            'steps': steps,
            'won': won,
        })
        
        status = "✅" if won else "❌"
        print(f"  [{status}] {env.task_type}: {env.task_desc[:60]}... ({steps}s)")
    
    wins = sum(1 for r in results if r['won'])
    print(f"\n  {wins}/{num_episodes} won ({100*wins/num_episodes:.0f}%)")
    return results


# ── Main ─────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="YLYW + ALFWorld 测试")
    parser.add_argument("--mode", choices=["test", "random", "stats"],
                       default="test")
    parser.add_argument("-n", "--episodes", type=int, default=10)
    args = parser.parse_args()
    
    env = ALFWorldLight()
    
    if args.mode == "stats":
        stats = env.get_stats()
        print(f"ALFWorld Light Emulator")
        print(f"  Games: {stats['total_games']}")
        print(f"  Types:")
        for tt, n in stats['task_types'].items():
            print(f"    {tt}: {n}")
        return
    
    elif args.mode == "random":
        print(f"Random agent ({args.episodes} eps)...\n")
        run_random_agent(env, args.episodes)
        return
    
    else:  # test
        print("ALFWorld Light Emulator - TEST\n")
        obs, info = env.reset(game_idx=0)
        
        print(f"Game {info['game_idx']}: {info['task_type']}")
        print(f"Task: {info['task_desc']}")
        print(f"Walkthrough ({len(env.walkthrough)} steps):")
        for i, c in enumerate(env.walkthrough):
            print(f"  {i}: {c}")
        print(f"\nObs: {obs[:300]}...")
        print(f"\nAdmissible ({len(info['admissible_commands'])}):")
        for c in info['admissible_commands'][:6]:
            print(f"  {c}")
        
        print(f"\n--- Walkthrough execution ---")
        for i, cmd in enumerate(env.walkthrough):
            obs, info = env.step(cmd)
            s = "🎉" if info.get('won') else "→"
            print(f"  [{s}] {cmd} → {obs[:70]}")
            if info.get('won'):
                break
        
        print(f"\n✅ OK!")


if __name__ == "__main__":
    main()
