#!/usr/bin/env python3
"""
YLYW API 自测脚本
验证文档中的所有示例代码能否正常执行。
"""

import sys
sys.path.insert(0, '/home/lijinhan/MXL/科研/ylyw/experiment_phase1')
sys.path.insert(0, '/home/lijinhan/MXL/科研/ylyw')

import numpy as np
from ylyw_core import PriorManual, TrigramBase, YaoEncoder, HexagramRuleBase
from ylyw_core.yao_relations import YaoRelations, analyze_yao_relations

def test_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def ok(msg=""):
    print(f"  ✅ {msg}")

# ======================================================================
# Test 1: 最简调用
# ======================================================================
test_section("最简调用")
manual = PriorManual(verbose=False)
perception, strategy = manual.process({
    'stability': 0.8,
    'roll_tendency': 0.1,
    'strength_needed': 0.6,
    'fragility': 0.2,
    'task_priority': 0.7,
    'reachability': 0.9,
})
assert isinstance(strategy['type'], str)
assert 0 < strategy['force'] <= 1.0
ok(f"策略: {strategy['type']}, 力: {strategy['force']:.2f}")

# ======================================================================
# Test 2: 分步调用
# ======================================================================
test_section("分步调用")
manual2 = PriorManual(verbose=False)
cube = {
    'stability': 0.9, 'roll_tendency': 0.05,
    'strength_needed': 0.75, 'fragility': 0.1,
    'task_priority': 0.5, 'reachability': 0.95,
    'support_area': 0.9, 'occlusion': 0.0,
    'obstacle_density': 0.1, 'grasp_surface_quality': 0.8,
    'weight_ratio': 0.7,
}
perception = manual2.perceive_and_encode(cube)
assert 'yao_vector' in perception
assert 'best_hexagram' in perception
assert 'yao_relations' in perception
assert len(perception['yao_vector']) == 6
strategy2 = manual2.get_grasp_strategy(perception)
ok(f"yao_vector shape={perception['yao_vector'].shape}, 策略={strategy2['type']}")

# 查看推理链
explanation = manual2.explain_reasoning(perception)
assert len(explanation) > 100
ok(f"推理链长度: {len(explanation)} 字符")

# ======================================================================
# Test 3: L1 八卦映射（单独使用）
# ======================================================================
test_section("L1 八卦映射")
tb = TrigramBase()
features = {
    'stability': 0.2, 'roll_tendency': 0.9,
    'strength_needed': 0.3, 'deformability': 0.4,
    'visibility': 0.6, 'fragility': 0.5
}
memberships = tb.get_all_memberships(features)
assert len(memberships) == 8
dominant, score = tb.get_dominant_trigram(features)
ok(f"主导卦: {dominant.name}, 隶属度向量: {memberships.round(3)}")

# ======================================================================
# Test 4: L2 六爻编码（单独使用）
# ======================================================================
test_section("L2 六爻编码")
encoder = YaoEncoder()
features2 = {
    'stability': 0.3, 'roll_tendency': 0.7,
    'reachability': 0.8, 'occlusion': 0.2,
    'grasp_surface_quality': 0.6, 'strength_needed': 0.5,
    'weight_ratio': 0.4, 'fragility': 0.6,
    'task_priority': 0.7, 'obstacle_density': 0.1
}
yao = encoder.encode(features2)
assert len(yao) == 6
assert all(0 <= v <= 1 for v in yao)
ok(f"六爻: {yao.round(3)}")

interp = encoder.get_yao_interpretation(yao)
assert len(interp) == 6
ok(f"爻解读: {len(interp)} 条")

# ======================================================================
# Test 5: L3+ 爻位关系（单独使用）
# ======================================================================
test_section("L3+ 爻位关系")
rel = YaoRelations()
yao_test = np.array([0.7, 0.3, 0.8, 0.2, 0.6, 0.4], dtype=np.float32)
report = rel.analyze(yao_test)
assert report.dangwei_count <= 6
assert 0 <= report.score_overall <= 1
ok(f"当位: {report.dangwei_count}/6, 质量: {report.score_overall:.2f}, "
   f"修正: {report.strategy_modifier:.2f}")

# 测试便捷函数
report2 = analyze_yao_relations(yao_test)
assert report2.score_overall == report.score_overall
ok("便捷函数 analyze_yao_relations() 可用")

# 格式化报告
formatted = rel.format_report(yao_test, report)
assert len(formatted) > 50
ok(f"格式化报告: {len(formatted)} 字符")

# ======================================================================
# Test 6: 批量处理
# ======================================================================
test_section("批量处理")
objects = [
    {'stability': 0.1, 'roll_tendency': 0.95, 'strength_needed': 0.3,
     'fragility': 0.4, 'task_priority': 0.5, 'reachability': 0.8,
     'support_area': 0.05, 'occlusion': 0.0, 'obstacle_density': 0.0,
     'grasp_surface_quality': 0.6, 'weight_ratio': 0.3},
    {'stability': 0.9, 'roll_tendency': 0.05, 'strength_needed': 0.8,
     'fragility': 0.1, 'task_priority': 0.7, 'reachability': 0.95,
     'support_area': 0.9, 'occlusion': 0.0, 'obstacle_density': 0.1,
     'grasp_surface_quality': 0.9, 'weight_ratio': 0.8},
    {'stability': 0.3, 'roll_tendency': 0.7, 'strength_needed': 0.4,
     'fragility': 0.5, 'task_priority': 0.5, 'reachability': 0.7,
     'support_area': 0.3, 'occlusion': 0.1, 'obstacle_density': 0.2,
     'grasp_surface_quality': 0.5, 'weight_ratio': 0.4},
]
yao_batch = encoder.encode_batch(objects)
assert yao_batch.shape == (3, 6)
ok(f"批量爻向量形状: {yao_batch.shape}")

for i, obj in enumerate(objects):
    _, strat = manual.process(obj)
    ok(f"  物体{i+1}: {strat['type']}, 力={strat['force']:.2f}")

# ======================================================================
# Test 7: 确定性检查
# ======================================================================
test_section("确定性检查")
manual3 = PriorManual(verbose=False)
r1, _ = manual3.process(cube)
r2, _ = manual3.process(cube)
assert np.allclose(r1['yao_vector'], r2['yao_vector'])
ok("相同输入 → 相同输出（确定性） ✅")

# ======================================================================
# Test 8: 完整推理链
# ======================================================================
test_section("完整推理链（球体）")
sphere = {
    'stability': 0.1, 'roll_tendency': 0.95,
    'strength_needed': 0.3, 'fragility': 0.4,
    'task_priority': 0.5, 'reachability': 0.8,
    'support_area': 0.05, 'occlusion': 0.0,
    'obstacle_density': 0.0, 'grasp_surface_quality': 0.6,
    'weight_ratio': 0.3,
}
perception_s, strategy_s = manual3.process(sphere)
print(manual3.explain_reasoning(perception_s))

# ======================================================================
# Summary
# ======================================================================
test_section("全部测试通过")
print(f"""
  ✅ 最简调用      — PriorManual.process()
  ✅ 分步调用      — perceive_and_encode() + get_grasp_strategy()
  ✅ L1 八卦基元   — TrigramBase 隶属度计算
  ✅ L2 六爻编码   — YaoEncoder 编码 + 解读
  ✅ L3 卦象匹配   — HexagramRuleBase 64卦规则库
  ✅ L3+ 爻位关系  — YaoRelations 乘承比应当位得中
  ✅ 批量处理      — encode_batch()
  ✅ 确定性验证    — 相同输入始终相同输出
  ✅ 可解释推理链  — explain_reasoning()
""")
