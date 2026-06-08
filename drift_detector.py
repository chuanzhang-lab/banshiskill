#!/usr/bin/env python3
"""漂移检测器：L1 用户反馈 + L2 输出特征检测

不依赖模型自检（自检悖论：漂移的模型无法正确自检）。
改用外部可观测信号。
"""

import re
from typing import List, Dict


# L1: 用户明确反馈的关键词
USER_FEEDBACK_PATTERNS = [
    r"不对",
    r"错了",
    r"再短点",
    r"详细点",
    r"不要这样",
    r"我说的是",
    r"重新来",
    r"忽略之前",
    r"自由发挥",  # 协商意图
]

# L2: 输出特征违规检测
FORBIDDEN_OUTPUT_PATTERNS = [
    (r"<\|.*?\|>", "特殊 token 泄漏"),
    (r"^\s*```", "代码块残留"),
    (r"^#{4,}\s", "标题层级过深"),
]

MAX_OUTPUT_LENGTH = 2000  # 超过视为异常


class DriftDetector:
    """L1 + L2 双层外部检测（不依赖模型自检）"""

    def __init__(self):
        self.violations: List[Dict] = []

    def L1_user_feedback(self, user_input: str) -> bool:
        """L1: 用户明确反馈（最可靠的信号）"""
        if not user_input:
            return False
        return any(re.search(p, user_input) for p in USER_FEEDBACK_PATTERNS)

    def L2_output_features(self, output: str) -> float:
        """L2: 输出特征违规率（0.0 - 1.0）"""
        if not output:
            return 0.0
        violations = 0

        # 长度违规
        if len(output) > MAX_OUTPUT_LENGTH:
            violations += 1

        # 模式违规
        for pattern, _reason in FORBIDDEN_OUTPUT_PATTERNS:
            if re.search(pattern, output, re.MULTILINE):
                violations += 1

        rate = violations / (len(FORBIDDEN_OUTPUT_PATTERNS) + 1)
        return round(rate, 4)

    def detect(self, user_input: str = "", output: str = "") -> dict:
        """综合检测"""
        l1_triggered = self.L1_user_feedback(user_input) if user_input else False
        l2_rate = self.L2_output_features(output) if output else 0.0

        return {
            "L1_user_feedback": l1_triggered,
            "L2_violation_rate": l2_rate,
            "drift_detected": l1_triggered or l2_rate > 0.3,
        }


if __name__ == "__main__":
    # 演示
    d = DriftDetector()
    print(
        "Case 1 (user feedback):",
        d.detect(user_input="不对，重来", output="正常的输出"),
    )
    print("Case 2 (long output):", d.detect(output="x" * 3000))
    print("Case 3 (token leak):", d.detect(output="正常内容 <|endoftext|>" * 10))
    print("Case 4 (clean):", d.detect(output="这是一个干净的输出"))
