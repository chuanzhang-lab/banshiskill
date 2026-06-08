#!/usr/bin/env python3
"""状态加载器：用户显式触发才加载

不强制重注入、不自动加载、不污染对话。
只有用户说"继续上次"才加载。
"""

import re
from pathlib import Path
from typing import Optional


# 用户触发加载的关键词
LOAD_TRIGGERS = [
    r"继续上次",
    r"接着",
    r"回到上次",
    r"恢复状态",
    r"加载之前",
    r"resume",
    r"continue",
]

# 用户拒绝加载的关键词
SKIP_TRIGGERS = [
    r"重新开始",
    r"从零开始",
    r"不要之前",
    r"fresh start",
]


class StateLoader:
    """按需状态加载器（不自动）"""

    def __init__(self, state_file: str = "SESSION-STATE.md"):
        self.state_file = Path(state_file)

    def should_load(self, user_input: str, turn: int = 1) -> bool:
        """判断是否需要加载状态

        触发条件（满足任一即加载）：
          1. 用户说"继续上次"等明确加载指令

        不触发：
          - 用户说"重新开始"
          - 中间轮次（除非用户显式要求）
        """
        if not user_input:
            return False

        # 拒绝关键词优先
        for pattern in SKIP_TRIGGERS:
            if re.search(pattern, user_input, re.IGNORECASE):
                return False

        # 加载关键词
        for pattern in LOAD_TRIGGERS:
            if re.search(pattern, user_input, re.IGNORECASE):
                return True

        return False

    def load(self) -> Optional[str]:
        """加载状态文件"""
        if not self.state_file.exists():
            return None
        try:
            return self.state_file.read_text(encoding="utf-8")
        except OSError:
            return None

    def has_state(self) -> bool:
        """是否有状态文件"""
        return self.state_file.exists()


if __name__ == "__main__":
    s = StateLoader()
    print("Test 1 (continue):", s.should_load("继续上次"))
    print("Test 2 (normal):", s.should_load("请压缩"))
    print("Test 3 (fresh):", s.should_load("重新开始"))
    print("Test 4 (has state):", s.has_state())
