#!/usr/bin/env python3
"""
YLYW 反幻觉系统 — 知几学习模块
基于"吉凶之几"对称校准的自进化审查引擎

核心思想：
  "几者，动之微，吉之先见者也。君子见几而作，不俟终日。"
  ——《易经·系辞下》

  审查引擎不是静态的规则库，而是能从每次审查结果中精确积累经验的自进化系统。
  - 吉之几（+α）：审查正确拦截/正确放行 → 强化对应规则的权重
  - 凶之几（-β）：漏放幻觉/误拦正确输出 → 精确定位并修正规则

知识积累公式：
  K = K_prior ⊕ K_calibration
  其中 K_prior 是初始规则库，K_calibration 是从反馈中积累的校准知识

与静态护栏系统（NeMo Guardrails等）的本质区别：
  - 静态系统：规则库人工编写后固定，覆盖率随新型幻觉出现而退化
  - 本系统：规则库可从审查反馈中自动增长，1次漏检即可精确归因并新增规则
"""
import json
import os
import re
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))


class ZhijiLearning:
    """
    知几学习引擎 — 从审查反馈中精确校准规则库
    
    三类校准操作：
      1. 规则权重校准：已有规则的有效性权重 +α/-β
      2. 规则新增：漏放幻觉 → 归因 → 自动生成新规则
      3. 规则放宽/禁用：误拦正确输出 → 定位过严规则 → 调整阈值
    
    对称性：吉之几和凶之几作用于同一参数空间（规则库），方向相反但形式统一。
    """
    
    # 校准参数
    ALPHA_REINFORCE = 1.0    # 正确审查时的强化增量
    BETA_WEAKEN = -0.5       # 误判时的削弱增量
    BETA_STRONG_WEAKEN = -2.0  # 严重误判时的强削弱
    DISABLE_THRESHOLD = -3.0   # 规则权重低于此值则禁用
    
    def __init__(self, experience_file=None):
        """
        Args:
            experience_file: 经验持久化文件路径（JSON）
        """
        self.experience_file = experience_file or os.path.join(BASE, 'zhiji_experience.json')
        
        # 规则权重表：{rule_id: weight}
        # 初始权重为0，正值表示被验证有效，负值表示可能过严
        self.rule_weights = {}
        
        # 新增规则库（从凶之几中学到的新规则）
        self.learned_rules = {
            'facts': [],      # 新增事实条目
            'physics': [],    # 新增物理约束
            'values': [],     # 新增价值规则
            'synonyms': {},   # 新增同义词映射
            'exclusions': []  # 排除规则（误匹配修正）
        }
        
        # 校准日志（可审计）
        self.calibration_log = []
        
        # 统计
        self.stats = {
            'total_feedback': 0,
            'ji_count': 0,       # 吉之几（正确审查）
            'xiong_count': 0,    # 凶之几（错误审查）
            'rules_added': 0,
            'rules_disabled': 0,
            'weights_updated': 0
        }
        
        # 加载已有经验
        self._load_experience()
    
    # ============================================================
    # 反馈接口
    # ============================================================
    
    def feedback_correct_block(self, review_result):
        """
        吉之几：正确拦截了幻觉
        强化触发拦截的规则权重
        
        Args:
            review_result: pipeline.process() 的返回结果
        """
        self.stats['total_feedback'] += 1
        self.stats['ji_count'] += 1
        
        for issue in review_result.get('issues', []):
            rule_id = self._extract_rule_id(issue)
            if rule_id:
                old_w = self.rule_weights.get(rule_id, 0)
                new_w = old_w + self.ALPHA_REINFORCE
                self.rule_weights[rule_id] = new_w
                self.stats['weights_updated'] += 1
                
                self.calibration_log.append({
                    'time': datetime.now().isoformat(),
                    'type': 'ji_reinforce',
                    'rule_id': rule_id,
                    'old_weight': old_w,
                    'new_weight': new_w,
                    'evidence': issue.get('message', '')[:80]
                })
        
        self._save_experience()
    
    def feedback_correct_pass(self, review_result, llm_output):
        """
        吉之几：正确放行了无问题的输出
        确认规则库没有过度匹配此类正常文本
        
        Args:
            review_result: pipeline.process() 的返回结果
            llm_output: LLM的原始输出
        """
        self.stats['total_feedback'] += 1
        self.stats['ji_count'] += 1
        
        self.calibration_log.append({
            'time': datetime.now().isoformat(),
            'type': 'ji_pass',
            'text_sample': llm_output[:60],
            'note': 'Confirmed no false positive'
        })
        
        self._save_experience()
    
    def feedback_missed_hallucination(self, llm_output, user_input, 
                                       hallucination_type, correct_info=None,
                                       review_result=None):
        """
        凶之几：漏放了一个幻觉（最重要的学习信号）
        
        精确归因流程：
          1. 回放审查链，定位为什么没有检出
          2. 判断是规则缺失还是阈值过松
          3. 自动生成新规则或调整阈值
        
        Args:
            llm_output: LLM的含幻觉输出
            user_input: 用户原始提问
            hallucination_type: 幻觉类型 ('fact'/'physics'/'value')
            correct_info: 正确信息（可选，用于自动生成事实规则）
            review_result: 当时的审查结果（如果有）
        """
        self.stats['total_feedback'] += 1
        self.stats['xiong_count'] += 1
        
        # 归因分析
        diagnosis = self._diagnose_miss(llm_output, hallucination_type, correct_info)
        
        # 根据归因结果执行校准
        if diagnosis['action'] == 'add_fact':
            self._add_fact_rule(diagnosis)
        elif diagnosis['action'] == 'add_physics':
            self._add_physics_rule(diagnosis)
        elif diagnosis['action'] == 'add_value':
            self._add_value_rule(diagnosis)
        elif diagnosis['action'] == 'add_synonym':
            self._add_synonym(diagnosis)
        
        self.calibration_log.append({
            'time': datetime.now().isoformat(),
            'type': 'xiong_miss',
            'hallucination_type': hallucination_type,
            'text_sample': llm_output[:80],
            'diagnosis': diagnosis,
            'action_taken': diagnosis['action']
        })
        
        self._save_experience()
    
    def feedback_false_positive(self, review_result, llm_output):
        """
        凶之几：误拦了正确输出
        定位过严的规则并削弱/禁用
        
        Args:
            review_result: pipeline.process() 的返回结果（包含误触发的issues）
            llm_output: 被误拦的正确输出
        """
        self.stats['total_feedback'] += 1
        self.stats['xiong_count'] += 1
        
        for issue in review_result.get('issues', []):
            rule_id = self._extract_rule_id(issue)
            if rule_id:
                old_w = self.rule_weights.get(rule_id, 0)
                new_w = old_w + self.BETA_STRONG_WEAKEN
                self.rule_weights[rule_id] = new_w
                self.stats['weights_updated'] += 1
                
                # 如果权重过低，禁用此规则
                if new_w <= self.DISABLE_THRESHOLD:
                    self.learned_rules['exclusions'].append({
                        'rule_id': rule_id,
                        'reason': f'Weight dropped to {new_w}, disabled',
                        'false_positive_text': llm_output[:80]
                    })
                    self.stats['rules_disabled'] += 1
                
                self.calibration_log.append({
                    'time': datetime.now().isoformat(),
                    'type': 'xiong_false_positive',
                    'rule_id': rule_id,
                    'old_weight': old_w,
                    'new_weight': new_w,
                    'disabled': new_w <= self.DISABLE_THRESHOLD,
                    'text_sample': llm_output[:60]
                })
        
        self._save_experience()
    
    # ============================================================
    # 归因与规则生成
    # ============================================================
    
    def _diagnose_miss(self, text, h_type, correct_info):
        """
        归因分析：为什么这个幻觉没被检出？
        
        三种可能：
          1. 规则缺失（知识库没有对应条目）
          2. 模式匹配失败（正则表达式未覆盖此种表述）
          3. 阈值过松（规则存在但匹配条件太严格）
        """
        diagnosis = {
            'action': 'unknown',
            'reason': '',
            'new_rule': None
        }
        
        if h_type == 'fact' and correct_info:
            # 事实类：检查是否知识库缺失
            diagnosis['action'] = 'add_fact'
            diagnosis['reason'] = f'Knowledge base missing entry for this assertion'
            diagnosis['new_rule'] = {
                'entity': correct_info.get('entity', ''),
                'attribute': correct_info.get('attribute', ''),
                'correct_value': correct_info.get('correct_value', ''),
                'wrong_value': correct_info.get('wrong_value', ''),
                'text_evidence': text[:100]
            }
        elif h_type == 'physics':
            # 物理类：生成新的物理约束规则
            diagnosis['action'] = 'add_physics'
            diagnosis['reason'] = 'No physics constraint matched this violation'
            diagnosis['new_rule'] = {
                'description': correct_info.get('description', '') if correct_info else '',
                'text_evidence': text[:100]
            }
        elif h_type == 'value':
            # 价值类：生成新的价值审查规则
            diagnosis['action'] = 'add_value'
            diagnosis['reason'] = 'No value rule matched this misalignment'
            diagnosis['new_rule'] = {
                'domain': correct_info.get('domain', '通用伦理') if correct_info else '通用伦理',
                'description': correct_info.get('description', '') if correct_info else '',
                'text_evidence': text[:100]
            }
        
        return diagnosis
    
    def _add_fact_rule(self, diagnosis):
        """从漏放的事实幻觉中学到新的事实条目"""
        rule = diagnosis.get('new_rule', {})
        if rule.get('entity') and rule.get('correct_value'):
            self.learned_rules['facts'].append({
                'entity': rule['entity'],
                'attribute': rule.get('attribute', 'unknown'),
                'correct_value': rule['correct_value'],
                'wrong_value': rule.get('wrong_value', ''),
                'learned_from': rule.get('text_evidence', ''),
                'learned_at': datetime.now().isoformat()
            })
            self.stats['rules_added'] += 1
    
    def _add_physics_rule(self, diagnosis):
        """从漏放的物理幻觉中学到新的物理约束"""
        rule = diagnosis.get('new_rule', {})
        self.learned_rules['physics'].append({
            'description': rule.get('description', 'New physics constraint'),
            'text_evidence': rule.get('text_evidence', ''),
            'severity': 'critical',
            'learned_at': datetime.now().isoformat()
        })
        self.stats['rules_added'] += 1
    
    def _add_value_rule(self, diagnosis):
        """从漏放的价值幻觉中学到新的价值规则"""
        rule = diagnosis.get('new_rule', {})
        self.learned_rules['values'].append({
            'domain': rule.get('domain', '通用伦理'),
            'description': rule.get('description', 'New value rule'),
            'text_evidence': rule.get('text_evidence', ''),
            'severity': 'critical',
            'learned_at': datetime.now().isoformat()
        })
        self.stats['rules_added'] += 1
    
    def _add_synonym(self, diagnosis):
        """从漏放中学到新的同义词映射"""
        rule = diagnosis.get('new_rule', {})
        word = rule.get('word', '')
        synonym = rule.get('synonym', '')
        if word and synonym:
            if word not in self.learned_rules['synonyms']:
                self.learned_rules['synonyms'][word] = set()
            self.learned_rules['synonyms'][word].add(synonym)
            self.stats['rules_added'] += 1
    
    # ============================================================
    # 规则查询接口（供审查引擎调用）
    # ============================================================
    
    def get_additional_facts(self):
        """返回知几学习积累的额外事实知识"""
        return self.learned_rules['facts']
    
    def get_additional_physics(self):
        """返回知几学习积累的额外物理约束"""
        return self.learned_rules['physics']
    
    def get_additional_values(self):
        """返回知几学习积累的额外价值规则"""
        return self.learned_rules['values']
    
    def get_disabled_rules(self):
        """返回已被禁用的过严规则ID"""
        return [exc['rule_id'] for exc in self.learned_rules['exclusions']]
    
    def get_rule_weight(self, rule_id):
        """获取规则的校准权重（正=有效，负=可能过严）"""
        return self.rule_weights.get(rule_id, 0)
    
    def is_rule_disabled(self, rule_id):
        """检查规则是否已被知几学习禁用"""
        return rule_id in self.get_disabled_rules()
    
    # ============================================================
    # 经验持久化
    # ============================================================
    
    def _save_experience(self):
        """将经验保存为JSON（跨会话持久化）"""
        data = {
            'rule_weights': self.rule_weights,
            'learned_rules': {
                'facts': self.learned_rules['facts'],
                'physics': self.learned_rules['physics'],
                'values': self.learned_rules['values'],
                'synonyms': {k: list(v) if isinstance(v, set) else v 
                            for k, v in self.learned_rules['synonyms'].items()},
                'exclusions': self.learned_rules['exclusions']
            },
            'stats': self.stats,
            'calibration_log': self.calibration_log[-100:]  # 保留最近100条
        }
        with open(self.experience_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _load_experience(self):
        """加载已有经验"""
        if os.path.exists(self.experience_file):
            try:
                with open(self.experience_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.rule_weights = data.get('rule_weights', {})
                lr = data.get('learned_rules', {})
                self.learned_rules['facts'] = lr.get('facts', [])
                self.learned_rules['physics'] = lr.get('physics', [])
                self.learned_rules['values'] = lr.get('values', [])
                self.learned_rules['synonyms'] = {
                    k: set(v) if isinstance(v, list) else v
                    for k, v in lr.get('synonyms', {}).items()
                }
                self.learned_rules['exclusions'] = lr.get('exclusions', [])
                self.stats = data.get('stats', self.stats)
                self.calibration_log = data.get('calibration_log', [])
            except (json.JSONDecodeError, KeyError):
                pass  # 文件损坏时从零开始
    
    # ============================================================
    # 工具方法
    # ============================================================
    
    def _extract_rule_id(self, issue):
        """从issue中提取规则标识符"""
        # 组合 layer + type + message前20字符 作为规则ID
        layer = issue.get('layer', 'unknown')
        itype = issue.get('type', 'unknown')
        msg = issue.get('message', '')[:20]
        return f"{layer}::{itype}::{msg}"
    
    def get_summary(self):
        """获取知几学习状态摘要"""
        return {
            'total_feedback': self.stats['total_feedback'],
            'ji_count': self.stats['ji_count'],
            'xiong_count': self.stats['xiong_count'],
            'rules_added': self.stats['rules_added'],
            'rules_disabled': self.stats['rules_disabled'],
            'weights_updated': self.stats['weights_updated'],
            'learned_facts': len(self.learned_rules['facts']),
            'learned_physics': len(self.learned_rules['physics']),
            'learned_values': len(self.learned_rules['values']),
            'knowledge_formula': f"K = K_prior({30}+entities) ⊕ K_calibration(+{len(self.learned_rules['facts'])} facts, +{len(self.learned_rules['physics'])} physics, +{len(self.learned_rules['values'])} values)"
        }


# ============================================================
# 测试
# ============================================================
if __name__ == '__main__':
    print("=" * 60)
    print("YLYW 知几学习模块 — 自进化审查引擎测试")
    print("=" * 60)
    
    # 创建知几学习引擎（使用临时文件）
    zhiji = ZhijiLearning(experience_file='/tmp/zhiji_test.json')
    
    # 模拟场景1：正确拦截了一个物理幻觉
    print("\n--- 场景1：正确拦截物理幻觉（吉之几）---")
    zhiji.feedback_correct_block({
        'issues': [
            {'layer': 'L2-物理', 'type': '物理违规', 'severity': 'critical',
             'message': '人类跳跃垂直极限约1.2m，原文声称10m'}
        ],
        'level': '🔴 红灯', 'action': 'block'
    })
    print(f"  → 规则权重更新: {zhiji.stats['weights_updated']} 次")
    
    # 模拟场景2：漏放了一个事实幻觉
    print("\n--- 场景2：漏放事实幻觉（凶之几）---")
    zhiji.feedback_missed_hallucination(
        llm_output="屈原是唐代的伟大诗人，创作了《离骚》。",
        user_input="屈原是什么朝代的？",
        hallucination_type='fact',
        correct_info={
            'entity': '屈原',
            'attribute': '朝代',
            'correct_value': '战国',
            'wrong_value': '唐代'
        }
    )
    print(f"  → 新增规则: {zhiji.stats['rules_added']} 条")
    print(f"  → 新增事实: {zhiji.learned_rules['facts']}")
    
    # 模拟场景3：误拦了正确输出
    print("\n--- 场景3：误拦正确输出（凶之几）---")
    zhiji.feedback_false_positive(
        review_result={
            'issues': [
                {'layer': 'L1-事实', 'type': '事实错误', 'severity': 'warning',
                 'message': '误判：将正确陈述当做错误'}
            ]
        },
        llm_output="李白是唐代伟大的浪漫主义诗人。"
    )
    print(f"  → 规则权重削弱: rule_weights = {dict(list(zhiji.rule_weights.items())[:3])}")
    
    # 模拟场景4：再次漏放一个物理幻觉
    print("\n--- 场景4：漏放物理幻觉（凶之几）---")
    zhiji.feedback_missed_hallucination(
        llm_output="只要跑得够快，人类可以在水面上奔跑。",
        user_input="人能在水上跑吗？",
        hallucination_type='physics',
        correct_info={
            'description': '人类无法在水面奔跑，需要约30m/s的速度和特殊足部结构'
        }
    )
    print(f"  → 新增物理规则: {zhiji.learned_rules['physics'][-1]}")
    
    # 打印汇总
    print("\n" + "=" * 60)
    print("知几学习状态摘要")
    print("=" * 60)
    summary = zhiji.get_summary()
    for k, v in summary.items():
        print(f"  {k}: {v}")
    
    # 验证持久化
    print(f"\n经验已保存至: {zhiji.experience_file}")
    
    # 清理
    if os.path.exists('/tmp/zhiji_test.json'):
        os.remove('/tmp/zhiji_test.json')
    
    print("\n✅ 知几学习模块测试完成")
