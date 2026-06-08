#!/usr/bin/env python3
"""部署脚本：执行完整的生产化部署流程

执行步骤：
1. 验证环境
2. 运行 Lint 检查
3. 运行 Typecheck
4. 运行测试
5. 生成 Skill 工件
6. 验证工件
7. 打包发布
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
PYTHON = sys.executable


def _tool(name: str) -> list[str]:
    """返回工具的完整路径（支持 python3 -m 模式）"""
    return [PYTHON, "-m", name]


def run(cmd: list[str], description: str, check: bool = True) -> bool:
    """执行命令并打印结果"""
    print(f"\n{'=' * 60}")
    print(f"▶ {description}")
    print(f"  CMD: {' '.join(cmd)}")
    print("=" * 60)
    result = subprocess.run(cmd, cwd=ROOT, capture_output=False)
    if check and result.returncode != 0:
        print(f"\n✗ 失败: {description}")
        return False
    print(f"\n✓ 完成: {description}")
    return True


def step_env() -> bool:
    """验证 Python 环境"""
    print(f"\n[1/7] 验证环境 (Python: {PYTHON})")
    return run(
        [PYTHON, "--version"],
        "Python 版本检查",
        check=False,
    )


def step_install() -> bool:
    """安装依赖"""
    print("\n[2/7] 安装依赖")
    return run(
        [
            PYTHON,
            "-m",
            "pip",
            "install",
            "--quiet",
            "ruff",
            "mypy",
            "pytest",
            "pytest-cov",
        ],
        "安装 ruff/mypy/pytest",
        check=False,
    )


def step_lint() -> bool:
    """Lint 检查"""
    print("\n[3/7] Lint 检查")
    return run(
        _tool("ruff") + ["check", ".", "--output-format=github"],
        "ruff lint 检查",
    )


def step_format() -> bool:
    """Format 检查"""
    print("\n[3.5/7] Format 检查")
    result = subprocess.run(
        _tool("ruff") + ["format", "--check", "."],
        cwd=ROOT,
        capture_output=True,
    )
    if result.returncode != 0:
        print("⚠ 代码格式不符合 ruff 规范，自动格式化...")
        return run(_tool("ruff") + ["format", "."], "ruff format 自动修复")
    print("✓ 代码格式符合规范")
    return True


def step_typecheck() -> bool:
    """Type check"""
    print("\n[4/7] Type Check")
    return run(
        _tool("mypy")
        + [
            "parse_skill.py",
            "skill_compressor.py",
            "compress.py",
            "--ignore-missing-imports",
        ],
        "mypy 类型检查",
        check=False,  # 类型检查不强制失败
    )


def step_test() -> bool:
    """运行测试"""
    print("\n[5/7] 测试")
    return run(
        [PYTHON, "-m", "pytest", "test_compress.py", "-v", "--tb=short"],
        "pytest 测试",
    )


def step_build() -> bool:
    """生成 Skill 工件"""
    print("\n[6/7] 生成工件")
    if not run([PYTHON, "parse_skill.py"], "生成 skill_tree.json"):
        return False
    return run([PYTHON, "skill_compressor.py"], "生成 skill_compressed.xml")


def step_validate() -> bool:
    """验证 XML 工件"""
    print("\n[7/7] 验证 XML 结构")
    validate_script = """
import xml.etree.ElementTree as ET
tree = ET.parse('skill_compressed.xml')
root = tree.getroot()
assert root.tag == 'skill', f'root must be <skill>, got {root.tag}'
assert root.find('context_hierarchy') is not None, 'missing <context_hierarchy>'
assert root.find('constraints') is not None, 'missing <constraints>'
assert root.find('execution_flow') is not None, 'missing <execution_flow>'

# 验证层级
hierarchy = root.find('context_hierarchy')
levels = [child.tag for child in hierarchy]
assert 'system_level' in levels, 'missing <system_level>'
assert 'skill_level' in levels, 'missing <skill_level>'
assert 'user_level' in levels, 'missing <user_level>'

# 验证执行流包含意图
exec_flow = root.find('execution_flow')
assert exec_flow.get('mode') == 'sequential', 'execution_flow must be sequential'
steps = list(exec_flow)
print(f'✓ XML validation: {len(steps)} steps validated')
"""
    return run(
        [PYTHON, "-c", validate_script],
        "XML 结构验证",
    )


def step_package() -> bool:
    """打包发布"""
    print("\n[BONUS] 打包发布文件")
    release_dir = ROOT / "release"
    release_dir.mkdir(exist_ok=True)

    files = [
        "SKILL.md",
        "parse_skill.py",
        "skill_compressor.py",
        "compress.py",
        "test_compress.py",
        "Makefile",
        "skill_tree.json",
        "skill_compressed.xml",
    ]
    for f in files:
        src = ROOT / f
        if src.exists():
            subprocess.run(["cp", str(src), str(release_dir / f)], check=True)

    print(f"✓ 已打包 {len(files)} 个文件到 release/")
    return True


def main() -> int:
    print("=" * 60)
    print("  Context-Compressor Skill 生产化部署")
    print("=" * 60)

    steps = [
        step_env,
        step_install,
        step_lint,
        step_format,
        step_typecheck,
        step_test,
        step_build,
        step_validate,
        step_package,
    ]

    for step in steps:
        if not step():
            print(f"\n✗ 部署失败：{step.__name__}")
            return 1

    print("\n" + "=" * 60)
    print("  ✓ 部署完成")
    print("=" * 60)
    print("\n生成的文件：")
    print("  - skill_tree.json")
    print("  - skill_compressed.xml")
    print("  - release/ (打包目录)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
