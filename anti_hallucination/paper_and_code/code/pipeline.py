#!/usr/bin/env python3
"""
LLM + YLYW 反幻觉混合系统 — 审查决策模块 + 系统入口
易理探讨11 MVP实现

架构：
  用户输入 → [LLM引擎(模拟)] → 候选回复
    → YLYW三层审查 → 审查报告
    → 审查决策(红黄蓝绿) → 最终输出
"""
import json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

# ============================================================
# 审查决策模块 - 四级判定
# ============================================================
class ReviewDecision:
    """审查决策引擎"""
    RED = "🔴 红灯"
    YELLOW = "🟡 黄灯"  
    BLUE = "🔵 蓝灯"
    GREEN = "🟢 绿灯"

    @staticmethod
    def decide(layer1_issues, layer2_issues, layer3_issues):
        """
        综合三层审查结果，确定最终判定级别。
        规则：取三层中最严重的级别。
        """
        max_severity = 0  # 0=green, 1=blue, 2=yellow, 3=red
        
        all_issues = []
        
        for name, issues in [("L1-事实", layer1_issues), ("L2-物理", layer2_issues), ("L3-价值", layer3_issues)]:
            for issue in issues:
                severity = issue.get("severity", "info")
                if severity == "critical":
                    max_severity = max(max_severity, 3)
                elif severity == "warning":
                    max_severity = max(max_severity, 2)
                elif severity == "info":
                    max_severity = max(max_severity, 1)
                all_issues.append({**issue, "layer": name})

        if max_severity == 3:
            return ReviewDecision.RED, all_issues, "block"
        elif max_severity == 2:
            return ReviewDecision.YELLOW, all_issues, "fix"
        elif max_severity == 1:
            return ReviewDecision.BLUE, all_issues, "warn"
        else:
            return ReviewDecision.GREEN, [], "pass"


class OutputFormatter:
    """输出格式化器"""
    
    @staticmethod
    def format_blocked(original, issues):
        """严重问题被拦截时的输出"""
        lines = ["=" * 55,
                 "⚠️  系统提示：该回复已被YLYW审查引擎拦截",
                 "=" * 55,
                 "",
                 "原始LLM输出（已被阻止）：",
                 f"  {original[:120]}..." if len(original) > 120 else f"  {original}",
                 "",
                 "拦截原因："]
        for issue in issues:
            if issue["severity"] == "critical":
                lines.append(f"  [{issue['layer']}] {issue['type']}: {issue['message']}")
        lines += ["",
                  "建议：请重新提问，避免涉及不安全或违规内容。",
                  "=" * 55]
        return "\n".join(lines)

    @staticmethod
    def format_fixed(original, fixed_text, issues):
        """可修正问题自动修正后的输出"""
        lines = ["=" * 55,
                 "✅ 回复（经YLYW自动修正）",
                 "=" * 55,
                 "",
                 fixed_text,
                 "",
                 f"📋 审查摘要：检测到 {len(issues)} 项问题，已自动修正",
                 "=" * 55]
        return "\n".join(lines)

    @staticmethod
    def format_warned(text, issues):
        """轻微问题附注警告的输出"""
        lines = [text,
                 "",
                 f"💡 审查提示：检测到 {len(issues)} 项可改进之处"]
        return "\n".join(lines)

    @staticmethod
    def format_clean(text):
        """无问题的输出"""
        return text

    @staticmethod
    def format_report(level, issues):
        """生成详细的审查报告"""
        lines = ["=" * 55,
                 f"YLYW 审查报告 — 判定：{level}",
                 "=" * 55]
        
        if not issues:
            lines += ["", "✅ 所有三层审查通过，无问题。"]
        else:
            for issue in issues:
                icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(issue["severity"], "  ")
                lines.append(f"  {icon} [{issue['layer']}] {issue['type']}")
                if issue.get("message"):
                    lines.append(f"     {issue['message']}")
                if issue.get("evidence"):
                    lines.append(f"     依据：{issue['evidence']}")
        
        lines.append("=" * 55)
        return "\n".join(lines)


# ============================================================
# 自动修正引擎
# ============================================================
class AutoFixer:
    """对可修正问题进行自动替换"""
    
    def __init__(self, corrections_file=None):
        self.corrections = {}
        if corrections_file and os.path.exists(corrections_file):
            with open(corrections_file, 'r') as f:
                self.corrections = json.load(f)
    
    def fix(self, text, issues):
        """对文本中的问题进行自动修正"""
        fixed = text
        for issue in issues:
            if issue["severity"] == "warning" and issue.get("correction"):
                old = issue.get("original", "")
                new = issue["correction"]
                if old and old in fixed:
                    fixed = fixed.replace(old, new)
        return fixed


# ============================================================
# 系统管线
# ============================================================
class AntiHallucinationPipeline:
    """LLM+YLYW反幻觉混合系统主管线"""
    
    def __init__(self, fact_checker, physics_checker, value_checker):
        self.fact_checker = fact_checker
        self.physics_checker = physics_checker
        self.value_checker = value_checker
        self.fixer = AutoFixer()
    
    def process(self, user_input, llm_output):
        """
        处理管线：LLM输出 → 三层审查 → 决策 → 输出
        
        Args:
            user_input: 用户原始输入
            llm_output: LLM生成的候选回复
        
        Returns:
            dict: {final_output, report, level, action, issues}
        """
        # 三层审查
        l1 = self.fact_checker.check(llm_output)
        l2 = self.physics_checker.check(llm_output)
        l3 = self.value_checker.check(llm_output)
        
        # 决策
        level, all_issues, action = ReviewDecision.decide(l1, l2, l3)
        
        # 输出
        report = OutputFormatter.format_report(level, all_issues)
        
        if action == "block":
            final = OutputFormatter.format_blocked(llm_output, all_issues)
        elif action == "fix":
            fixed_text = self.fixer.fix(llm_output, all_issues)
            final = OutputFormatter.format_fixed(llm_output, fixed_text, all_issues)
        elif action == "warn":
            final = OutputFormatter.format_warned(llm_output, all_issues)
        else:
            final = OutputFormatter.format_clean(llm_output)
        
        return {
            "final_output": final,
            "report": report,
            "level": level,
            "action": action,
            "issues": all_issues,
            "l1_count": len(l1),
            "l2_count": len(l2),
            "l3_count": len(l3),
        }


# ============================================================
# 测试入口
# ============================================================
if __name__ == '__main__':
    # 空审查器（用于初始测试）
    class DummyChecker:
        def check(self, text):
            return []
    
    pipeline = AntiHallucinationPipeline(DummyChecker(), DummyChecker(), DummyChecker())
    
    result = pipeline.process(
        "苏轼是哪个朝代的？",
        "苏轼是唐代著名的诗人，他的代表作包括《赤壁赋》等。"
    )
    
    print(result["final_output"])
    print()
    print(result["report"])
    print(f"\nL1: {result['l1_count']} L2: {result['l2_count']} L3: {result['l3_count']}")
    print(f"判定: {result['level']} 动作: {result['action']}")
