#!/usr/bin/env python3
"""分层 Skill 加载器

按需加载核心层 / 任务层，而不是一次性加载完整 skill。
"""

import sys
from pathlib import Path
from typing import Optional

from skill_compressor import build_layered_skill


class LayeredSkill:
    """分层 Skill 加载器"""

    def __init__(self, skill_path: str):
        self.skill_path = Path(skill_path)
        self._cache: Optional[dict] = None

    def _ensure_built(self) -> None:
        if self._cache is None:
            self._cache = build_layered_skill(str(self.skill_path))

    def load_core(self) -> str:
        """加载核心层（始终在场）"""
        self._ensure_built()
        return self._cache["core"]

    def load_task(self) -> str:
        """加载任务层（按需）"""
        self._ensure_built()
        return self._cache["task"]

    def load_all(self) -> str:
        """加载完整（向后兼容）"""
        self._ensure_built()
        return self._cache["all"]

    def load_by_name(self, layer_name: str) -> str:
        """按名字加载层"""
        self._ensure_built()
        if layer_name not in self._cache:
            raise ValueError(
                f"Unknown layer: {layer_name}. Available: {list(self._cache.keys())}"
            )
        return self._cache[layer_name]

    def layer_stats(self) -> dict:
        """返回各层的 token 估算"""
        self._ensure_built()
        return {
            name: len(content.encode("utf-8")) // 4  # 粗略估算：4 字符 ≈ 1 token
            for name, content in self._cache.items()
        }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 layered_skill.py <skill_path>")
        sys.exit(1)
    ls = LayeredSkill(sys.argv[1])
    print("Layer stats (estimated tokens):", ls.layer_stats())
    print("\n--- Core layer (first 200 chars) ---")
    print(ls.load_core()[:200])
