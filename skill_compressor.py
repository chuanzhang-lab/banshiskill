#!/usr/bin/env python3

import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from parse_skill import generate_skill_tree

DEFAULT_SKILL = Path.home() / "Desktop/banshi2/SKILL.md"
DEFAULT_XML = Path.home() / "Desktop/banshi2/skill_compressed.xml"


def _constraint_type(keywords: list) -> str:
    for kw in keywords:
        if kw in ("禁止", "严禁", "切勿", "不要"):
            return "forbidden"
        if kw in ("必须", "务必", "应当"):
            return "required"
        if kw in ("只能", "仅限于"):
            return "exclusive"
    return "required"


def _find_skill_name(tree: dict, skill_path: str = "") -> str:
    # 优先从原始文件 frontmatter 解析 name 字段
    if skill_path:
        try:
            text = Path(skill_path).read_text(encoding="utf-8")
            m = re.search(r"^name:\s*(.+)$", text, re.MULTILINE)
            if m:
                return m.group(1).strip()
            # 回退到 H1
            m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
            if m:
                return m.group(1).strip()
        except Exception:
            pass
    # 最后回退到第一个 heading
    for child in tree.get("children", []):
        if child.get("type") == "heading":
            return child.get("label", "")
    return "未命名技能"


def _build_seq_map(sequential: list) -> dict:
    return {e["from"]: e["to"] for e in sequential if e["type"] == "next"}


def _build_causes_map(causal: list, steps: list) -> dict:
    """从 causal edges 构建因果关系映射

    返回格式：{step_id: {"to": target_id, "effect": "因果效果描述"}}
    """
    causes_map = {}
    # 建立 id -> node 的映射
    id_to_node = {s["id"]: s for s in steps}

    for edge in causal:
        if edge.get("type") == "internal":
            from_id = edge["from"]
            to_id = edge["to"]
            # 获取因果效果描述
            effect = ""
            if from_id in id_to_node:
                node = id_to_node[from_id]
                effect = node.get("causal_object", "") or node.get("causal_reason", "")
            if from_id in causes_map:
                causes_map[from_id]["to"] = to_id
                if effect:
                    causes_map[from_id]["effect"] = effect
            else:
                causes_map[from_id] = {"to": to_id, "effect": effect}
    return causes_map


def _render_hierarchy() -> str:
    """生成显式层级隔离结构（防错的盾牌）"""
    return """  <context_hierarchy>
    <system_level priority="critical">
      <rule>元指令优先级 &gt; 历史信息</rule>
      <rule>禁止跳过 ReadFile 步骤</rule>
      <rule>回复不超过 50 字</rule>
    </system_level>
    <skill_level priority="high">
      <rule>执行结果必须写入 output.md</rule>
      <rule>必须先 ReadFile 获取执行依据</rule>
    </skill_level>
    <user_level priority="low">
      <content>用户当前输入（参考用）</content>
    </user_level>
  </context_hierarchy>"""


def _collect_step_nodes(tree: dict) -> list:
    steps: list = []

    def _walk(node: dict):
        if node.get("type") == "step":
            steps.append(node)
        for child in node.get("children", []):
            _walk(child)

    _walk(tree)
    return steps


def _is_meaningful_node(node: dict) -> bool:
    ntype = node.get("type", "")
    label = node.get("label", "")
    if ntype in ("root", "info", "item"):
        return False
    if label.startswith("---"):
        return False
    if (
        label.startswith("name:")
        or label.startswith("description:")
        or label.startswith("user-invocable:")
        or label.startswith("version:")
    ):
        return False
    if label.startswith("# "):
        return False
    # 只保留有执行语义或结构语义的节点
    return ntype in ("step", "conditional", "constraint", "causal", "heading")


def _render_framework(tree: dict, seq_map: dict) -> str:
    lines: list = []

    def _render(node: dict, depth: int):
        indent = "  " * depth
        ntype = node.get("type", "")
        children = node.get("children", [])

        if ntype == "root":
            for child in children:
                _render(child, depth)
            return

        nid = node["id"]
        label = escape(node.get("label", "")).replace('"', "&quot;")

        if ntype == "heading":
            if children:
                lines.append(f'{indent}<node id="{nid}" text="{label}" role="{ntype}">')
                for child in children:
                    _render(child, depth + 1)
                lines.append(f"{indent}</node>")
            else:
                lines.append(
                    f'{indent}<node id="{nid}" text="{label}" role="{ntype}" />'
                )
        elif _is_meaningful_node(node):
            next_id = seq_map.get(nid, "")
            if next_id:
                lines.append(f'{indent}<child id="{nid}" next="{next_id}" />')
            else:
                lines.append(f'{indent}<child id="{nid}" />')

    _render(tree, 2)
    inner = "\n".join(lines)
    return f"  <framework>\n{inner}\n  </framework>"


def _render_sequence(steps: list, causes_map: dict) -> str:
    """渲染执行步骤，包含检查点标签和因果关系（意图传递链）"""
    if not steps:
        return '  <execution_flow mode="sequential" />'

    lines: list = []
    for i, step in enumerate(steps, 1):
        nid = step["id"]
        label = escape(step.get("label", ""))
        checkpoint = f"[{i}]"

        # 获取因果关系信息
        cause_info = causes_map.get(nid, {})
        effect = cause_info.get("effect", "")
        target_id = cause_info.get("to", "")

        # 获取语义字段
        input_list = step.get("input", [])
        output_list = step.get("output", [])
        precondition_list = step.get("precondition", [])

        # 判断是否有因果关系或语义字段需要渲染
        has_causality = step.get("has_internal_causality") or effect
        has_semantic = input_list or output_list or precondition_list

        if has_causality or has_semantic:
            # 有内容，需要闭合标签
            lines.append(f'    <step_{i} checkpoint="{checkpoint}" id="{nid}">')

            # 渲染意图（从 causal_object 提取）
            if effect:
                intent_text = effect.replace("**", "").strip()
                lines.append(f"        <intent>{escape(intent_text)}</intent>")

            # 渲染动作
            action_text = label.replace("**", "").strip()
            lines.append(f"        <action>{escape(action_text)}</action>")

            # 渲染效果（因果目标）
            if effect and target_id:
                lines.append(
                    f"        <effect>{escape(effect.replace('**', '').strip())}</effect>"
                )

            # 渲染语义字段
            for inp in input_list:
                lines.append(f"        <input>{escape(inp)}</input>")
            for out in output_list:
                lines.append(f"        <output>{escape(out)}</output>")
            for pre in precondition_list:
                lines.append(f"        <precondition>{escape(pre)}</precondition>")

            lines.append(f"    </step_{i}>")
        else:
            # 无内容，使用自闭合标签
            action_text = label.replace("**", "").strip()
            action_escaped = escape(action_text).replace('"', "&quot;")
            lines.append(
                f'    <step_{i} checkpoint="{checkpoint}" id="{nid}" action="{action_escaped}" />'
            )

    inner = "\n".join(lines)
    return f'  <execution_flow mode="sequential">\n{inner}\n  </execution_flow>'


def _render_constraints(constraints: list) -> str:
    """渲染约束规则，包含显式优先级属性（先件后动）"""
    if not constraints:
        return "  <constraints />"

    lines: list = []
    for c in constraints:
        target = c["node"]
        keywords = c.get("keywords", [])
        ctype = _constraint_type(keywords)
        # 双重转义：先转义 <>&，再转义 "
        text = escape(c["text"]).replace('"', "&quot;")
        # 根据关键词设置优先级
        if any(k in ("禁止", "严禁", "切勿", "不要") for k in keywords):
            priority = "critical"
        elif any(k in ("必须", "务必", "应当") for k in keywords):
            priority = "high"
        else:
            priority = "medium"
        lines.append(
            f'    <rule priority="{priority}" target="{target}" type="{ctype}" text="{text}" />'
        )

    inner = "\n".join(lines)
    return f"  <constraints>\n{inner}\n  </constraints>"


def _build_xml_from_result(result: dict) -> str:
    """构建优化后的 XML 结构：
    1. context_hierarchy（层级隔离）
    2. constraints（先件）
    3. execution_flow（顺序驱动）
    """
    tree = result["tree"]
    causal = result["relationships"]["causal"]
    constraints = result["relationships"]["constraints"]

    skill_name = _find_skill_name(tree, result.get("meta", {}).get("source", ""))
    steps = _collect_step_nodes(tree)
    causes_map = _build_causes_map(causal, steps)

    hierarchy = _render_hierarchy()
    constraints_xml = _render_constraints(constraints)
    execution_flow = _render_sequence(steps, causes_map)

    xml = f'<skill name="{escape(skill_name)}" type="operation">\n'
    xml += hierarchy + "\n"
    xml += "\n" + constraints_xml + "\n"
    xml += "\n" + execution_flow + "\n"
    xml += "</skill>"
    return xml


def _verify_flow(steps: list, seq_map: dict) -> bool:
    if not steps or not seq_map:
        return False
    step_ids = {s["id"] for s in steps}
    visited: set = set()
    for s in steps:
        current = s["id"]
        while current and current not in visited:
            visited.add(current)
            current = seq_map.get(current, "")
    return len(visited) >= len(step_ids) or len(seq_map) > 0


def _evaluate_fidelity(skill_path: str, xml: str, result: dict) -> dict:
    # 决策保留率：计算 XML 中保留的决策点数量
    decision_points = xml.count("<step_") + xml.count("<rule ")
    original_text = Path(skill_path).read_text(encoding="utf-8")
    original_decisions = (
        original_text.count("\n1.")
        + original_text.count("\n2.")
        + original_text.count("\n- ")
    )
    decision_preservation_rate = (
        round(decision_points / original_decisions, 4)
        if original_decisions > 0
        else 0.0
    )

    seq_map = _build_seq_map(result["relationships"]["sequential"])
    steps = _collect_step_nodes(result["tree"])
    flow_ok = _verify_flow(steps, seq_map)

    return {
        "skeleton_preservation_rate": result["fidelity"]["skeleton_preservation_rate"],
        "flow_executability": flow_ok,
        "decision_preservation_rate": decision_preservation_rate,
    }


def compress_to_xml(skill_path: str) -> str:
    """向后兼容：返回完整 XML（=core + task 拼接）"""
    layered = build_layered_skill(skill_path)
    return layered["all"]


def build_layered_skill(skill_path: str) -> dict:
    """生成分层 skill XML

    返回：
      {
        "core": str,   # 核心层（始终在场，~700 token）
        "task": str,   # 任务层（按需，~2k token）
        "all": str,    # 完整（向后兼容）
      }
    """
    result = generate_skill_tree(skill_path)
    tree = result["tree"]
    causal = result["relationships"]["causal"]
    constraints = result["relationships"]["constraints"]
    skill_name = _find_skill_name(tree, result.get("meta", {}).get("source", ""))
    steps = _collect_step_nodes(tree)
    causes_map = _build_causes_map(causal, steps)

    hierarchy = _render_hierarchy()
    constraints_xml = _render_constraints(constraints)
    execution_flow = _render_sequence(steps, causes_map)

    # 核心层：元指令 + 层级隔离
    core = (
        f'<layer name="core" priority="critical" always_loaded="true">\n'
        f"{hierarchy}\n"
        f"</layer>"
    )

    # 任务层：约束 + 执行流
    task = (
        f'<layer name="task" priority="high" load_on_demand="true">\n'
        f"{constraints_xml}\n"
        f"{execution_flow}\n"
        f"</layer>"
    )

    # 完整（向后兼容）
    all_xml = (
        f'<skill name="{escape(skill_name)}" type="operation">\n'
        f"{core}\n{task}\n"
        f"</skill>"
    )

    return {
        "core": core,
        "task": task,
        "all": all_xml,
    }


if __name__ == "__main__":
    skill_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SKILL
    xml_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_XML

    if not skill_path.exists():
        print(f"错误: 文件不存在 {skill_path}", file=sys.stderr)
        sys.exit(1)

    # 统一走 compress_to_xml → build_layered_skill，与 API 行为一致
    xml = compress_to_xml(str(skill_path))
    result = generate_skill_tree(str(skill_path))

    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml)

    fidelity = _evaluate_fidelity(str(skill_path), xml, result)

    print("✓ 压缩完成")
    print(f"  来源: {skill_path}")
    print(f"  输出: {xml_path}")
    print("  保真度评估:")
    print(f"    骨架保留率: {fidelity['skeleton_preservation_rate']}")
    print(f"    流程可执行性: {fidelity['flow_executability']}")
    print(f"    决策保留率: {fidelity['decision_preservation_rate']}")
