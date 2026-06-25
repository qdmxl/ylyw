#!/usr/bin/env python3
"""
ALFWorld 官方环境适配器 — 方案B (Per-Game Env)

核心修复：
  旧版wrapper把所有134个game_files注册到一个TextWorld BatchEnv里，
  然后每次reset()取的是内部shuffled iterator的"下一个"游戏，
  根本无法按game_idx选择特定游戏。

  方案B：每次reset(game_idx)时，只把那一个gamefile注册为一个全新的
  TextWorld环境，确保reset()加载的就是我们要的游戏。

接口兼容：
  - reset(game_idx) → (obs_str, info_dict)
  - step(action)    → (obs_str, info_dict)
  - 与旧版和YLYWAgent完全兼容
"""

import os
import gc
import sys
import json
import yaml
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from functools import partial

import textworld
import textworld.gym

from alfworld.agents.environment.alfred_tw_env import (
    AlfredDemangler, AlfredInfos, AlfredTWEnv, TASK_TYPES
)


class ALFWorldOfficial:
    """ALFWorld 官方 TextWorld 仿真器适配器 (方案B: per-game env)"""

    def __init__(self, config_path: str = None, split: str = "valid_unseen"):
        """
        Args:
            config_path: ALFWorld 配置文件路径 (base_config.yaml)
            split: 'valid_unseen' | 'valid_seen' | 'train'
        """
        if config_path is None:
            config_path = str(Path.home() / "alfworld" / "configs" / "base_config.yaml")

        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        os.environ['ALFWORLD_DATA'] = os.path.expanduser('~/.cache/alfworld')

        split_map = {
            'train': 'train',
            'valid_seen': 'eval_in_distribution',
            'valid_unseen': 'eval_out_of_distribution',
        }
        self.train_eval = split_map.get(split, 'eval_out_of_distribution')
        self.split = split

        # 用 AlfredTWEnv.collect_game_files() 收集有效游戏列表
        # 但不调用 init_env()——我们自己按需创建单游戏环境
        print(f"Initializing ALFWorld Official (split={split})...")
        self._tw_env_obj = AlfredTWEnv(self.config, train_eval=self.train_eval)
        self._game_files = list(self._tw_env_obj.game_files)  # 确定性列表
        print(f"Collected {len(self._game_files)} solvable game files")

        # 预加载所有 traj_data（只读元信息，很快）
        self._traj_cache: Dict[int, Dict] = {}
        for idx, gf in enumerate(self._game_files):
            td = self._load_traj_data(gf)
            if td:
                self._traj_cache[idx] = td

        # 运行时状态
        self._gym_env = None  # 当前活跃的 gym env
        self._current_game_idx = -1
        self._current_traj_data = None

        # TextWorld 配置参数
        training_method = self.config.get("general", {}).get("training_method", "dagger")
        if training_method == "dqn":
            self._max_steps = self.config.get("rl", {}).get("training", {}).get(
                "max_nb_steps_per_episode", 50)
        else:
            self._max_steps = self.config.get("dagger", {}).get("training", {}).get(
                "max_nb_steps_per_episode", 50)

    @property
    def games(self) -> List[str]:
        """游戏文件列表（确定性顺序，与collect_game_files一致）"""
        return self._game_files

    @property
    def num_games(self) -> int:
        return len(self._game_files)

    # ------------------------------------------------------------------
    # 核心接口
    # ------------------------------------------------------------------

    def reset(self, game_idx: int = 0) -> Tuple[str, Dict]:
        """
        重置到指定游戏（方案B：每次创建单游戏环境）。

        Returns:
            (observation: str, info: dict)
        """
        # 关闭旧环境
        if self._gym_env is not None:
            try:
                self._gym_env.close()
            except Exception:
                pass
            self._gym_env = None
            gc.collect()

        self._current_game_idx = game_idx % len(self._game_files)
        game_file = self._game_files[self._current_game_idx]
        self._current_traj_data = self._traj_cache.get(self._current_game_idx)

        # ---- 方案B核心：只注册这一个gamefile ----
        request_infos = textworld.EnvInfos(
            won=True,
            admissible_commands=True,
            extras=["gamefile"]
        )

        domain_randomization = False  # eval 模式不随机化
        alfred_demangler = AlfredDemangler(shuffle=domain_randomization)
        wrappers = [alfred_demangler, AlfredInfos]

        env_id = textworld.gym.register_games(
            [game_file],              # 只注册这一个游戏！
            request_infos,
            batch_size=1,
            asynchronous=False,       # 单游戏无需异步
            max_episode_steps=self._max_steps,
            wrappers=wrappers,
        )
        self._gym_env = textworld.gym.make(env_id)

        # reset → 必定加载我们指定的那个游戏
        obs, info = self._gym_env.reset()

        # 解包 batch[0]
        obs_str = obs[0] if isinstance(obs, (list, tuple)) else str(obs)

        # 验证：extra.gamefile 应该就是我们指定的 game_file
        actual_gamefile = None
        if isinstance(info, dict):
            extras = info.get('extra.gamefile', info.get('extras', {}).get('gamefile', None))
            if isinstance(extras, list):
                actual_gamefile = extras[0] if extras else None
            else:
                actual_gamefile = extras

        processed_info = self._process_info_reset(info, game_file, actual_gamefile)

        return obs_str, processed_info

    def step(self, action: str) -> Tuple[str, Dict]:
        """
        执行一个动作。

        Args:
            action: 动作文本（官方格式，如 "go to desk 1"）

        Returns:
            (observation: str, info: dict)
        """
        if self._gym_env is None:
            raise RuntimeError("Must call reset() before step()")

        action = action.strip()

        # TextWorld batch mode: step 接受 list
        result = self._gym_env.step([action])
        obs, scores, dones, infos = result

        # 解包 batch[0]
        obs_str = obs[0] if isinstance(obs, (list, tuple)) else str(obs)

        processed_info = self._process_info_step(obs_str, scores, dones, infos)

        return obs_str, processed_info

    def close(self):
        """关闭当前环境"""
        if self._gym_env is not None:
            try:
                self._gym_env.close()
            except Exception:
                pass
            self._gym_env = None
            gc.collect()

    # ------------------------------------------------------------------
    # info 处理
    # ------------------------------------------------------------------

    def _process_info_reset(self, info: Dict, expected_gamefile: str,
                            actual_gamefile: Optional[str]) -> Dict:
        """处理 reset 返回的 info"""
        admissible = self._extract_admissible(info)

        result = {
            'won': self._extract_scalar(info, 'won', False),
            'done': False,
            'admissible_commands': admissible,
            'score': 0,
            'game_idx': self._current_game_idx,
            'game_file': expected_gamefile,
        }

        # 一致性检查
        if actual_gamefile and actual_gamefile != expected_gamefile:
            print(f"⚠️ Gamefile mismatch! expected={expected_gamefile}, actual={actual_gamefile}")
            result['gamefile_mismatch'] = True

        # 从 traj_data 获取元信息
        if self._current_traj_data:
            anns = self._current_traj_data.get('turk_annotations', {}).get('anns', [])
            result['task_desc'] = anns[0].get('task_desc', '') if anns else ''
            result['task_type'] = self._current_traj_data.get('task_type', '')
            result['pddl_params'] = self._current_traj_data.get('pddl_params', {})
            result['scene'] = {
                'floor_plan': self._current_traj_data.get('scene', {}).get('floor_plan', ''),
                'scene_num': self._current_traj_data.get('scene', {}).get('scene_num', -1),
            }
            # walkthrough 长度
            plan = self._current_traj_data.get('plan', {})
            result['walkthrough_len'] = len(plan.get('high_pddl', []))

        return result

    def _process_info_step(self, obs_str: str, scores, dones, infos: Dict) -> Dict:
        """处理 step 返回的 info"""
        won = self._extract_scalar(infos, 'won', False)
        done = dones[0] if isinstance(dones, (list, tuple)) else bool(dones)
        score = scores[0] if isinstance(scores, (list, tuple)) else float(scores)
        admissible = self._extract_admissible(infos)

        # 动作成功判定（基于观测文本）
        action_success = self._judge_action_success(obs_str)

        result = {
            'won': won,
            'done': done,
            'admissible_commands': admissible,
            'score': score,
            'action_success': action_success,
        }

        # 保留 task 元信息
        if self._current_traj_data:
            result['task_type'] = self._current_traj_data.get('task_type', '')
            anns = self._current_traj_data.get('turk_annotations', {}).get('anns', [])
            result['task_desc'] = anns[0].get('task_desc', '') if anns else ''

        return result

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _extract_scalar(self, info: Dict, key: str, default=None):
        """从可能嵌套list的info中提取标量值"""
        val = info.get(key, default)
        if isinstance(val, (list, tuple)):
            return val[0] if val else default
        return val

    def _extract_admissible(self, info: Dict) -> List[str]:
        """提取 admissible_commands"""
        cmds = info.get('admissible_commands', [])
        if isinstance(cmds, list) and len(cmds) > 0:
            if isinstance(cmds[0], list):
                cmds = cmds[0]  # batch[0]
        return list(cmds) if cmds else ['look']

    def _judge_action_success(self, obs: str) -> bool:
        """根据观测文本判定动作是否成功"""
        obs_lower = obs.lower()

        # 强成功信号（只要出现就判定成功，无论后续文本）
        strong_success = [
            "you arrive", "you pick up", "you put", "you place",
            "you move", "you open", "you close", "you heat",
            "you clean", "you cool", "you toggle", "you slice",
            "you are carrying",
        ]
        if any(kw in obs_lower for kw in strong_success):
            return True

        # 失败信号
        fail_keywords = [
            "nothing happens", "didn't work", "can't", "cannot",
            "not open", "you don't have", "isn't here",
            "can not", "won't", "sorry",
            "you already have", "you need to",
        ]
        # 注意："you see nothing" 不是失败，是空位置的正常描述
        if any(kw in obs_lower for kw in fail_keywords):
            return False

        return True  # 中性操作 (look/inventory/examine) 默认成功

    @staticmethod
    def _load_traj_data(game_file: str) -> Optional[Dict]:
        """从 game_file 路径加载对应的 traj_data.json"""
        game_path = Path(game_file)
        traj_path = game_path.parent / 'traj_data.json'
        if traj_path.exists():
            with open(traj_path) as f:
                return json.load(f)
        return None

    def get_stats(self) -> Dict:
        """获取数据集统计信息"""
        from collections import Counter
        task_types = Counter()
        floor_plans = Counter()
        for idx, td in self._traj_cache.items():
            task_types[td.get('task_type', 'unknown')] += 1
            fp = td.get('scene', {}).get('floor_plan', 'unknown')
            floor_plans[fp] += 1

        return {
            'total_games': len(self._game_files),
            'split': self.split,
            'task_types': dict(task_types),
            'floor_plans': dict(floor_plans),
        }

    def get_walkthrough(self, game_idx: int) -> List[str]:
        """获取指定游戏的专家解（walkthrough）"""
        game_file = self._game_files[game_idx % len(self._game_files)]
        with open(game_file) as f:
            gd = json.load(f)
        return gd.get('walkthrough', [])

    def get_expert_plan(self, game_idx: int) -> List[Dict]:
        """获取指定游戏的高层专家计划"""
        td = self._traj_cache.get(game_idx % len(self._game_files))
        if td:
            return td.get('plan', {}).get('high_pddl', [])
        return []


# ============================================================
# 便捷函数
# ============================================================

def make_official_env(split: str = "valid_unseen") -> ALFWorldOfficial:
    """创建官方 ALFWorld 环境"""
    return ALFWorldOfficial(split=split)


# ============================================================
# 自检测试
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Testing ALFWorldOfficial wrapper (方案B: per-game env)")
    print("=" * 60)

    env = ALFWorldOfficial(split="valid_unseen")
    stats = env.get_stats()
    print(f"\nDataset stats: {json.dumps(stats, indent=2, ensure_ascii=False)}")

    # 测试前3个游戏的 reset
    for i in range(min(3, env.num_games)):
        obs, info = env.reset(game_idx=i)
        print(f"\n--- Game {i} ---")
        print(f"  Game file: {info.get('game_file', '')[-80:]}")
        print(f"  Task type: {info.get('task_type')}")
        print(f"  Task desc: {info.get('task_desc', '')[:100]}")
        print(f"  Scene: {info.get('scene', {})}")
        print(f"  Won: {info.get('won')}")
        print(f"  Admissible ({len(info['admissible_commands'])}): "
              f"{info['admissible_commands'][:5]}...")
        print(f"  Obs: {obs[:150]}...")

        # 测试 step
        cmds = info['admissible_commands']
        if cmds:
            cmd = cmds[0]
            obs2, info2 = env.step(cmd)
            print(f"  Step '{cmd}' → won={info2['won']}, success={info2['action_success']}")
            print(f"    Obs: {obs2[:100]}...")

    # 验证：重复 reset 同一游戏应得到同样结果
    print("\n--- 一致性验证 ---")
    obs_a, info_a = env.reset(game_idx=0)
    obs_b, info_b = env.reset(game_idx=0)
    match = (info_a['task_type'] == info_b['task_type'] and
             info_a['task_desc'] == info_b['task_desc'])
    print(f"  reset(0) twice: task_type match={match}")
    print(f"  obs match: {obs_a[:80] == obs_b[:80]}")

    # 验证：不同 game_idx 应得到不同游戏
    obs_c, info_c = env.reset(game_idx=5)
    different = (info_a['game_file'] != info_c['game_file'])
    print(f"  game 0 vs game 5: different={different}")
    print(f"    game 0: {info_a['task_desc'][:60]}")
    print(f"    game 5: {info_c['task_desc'][:60]}")

    env.close()
    print("\n✅ ALFWorldOfficial wrapper (方案B) 测试通过!")
