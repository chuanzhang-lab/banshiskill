#!/usr/bin/env python3

import copy
import hashlib
import json
import re
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional
from typing import Dict
from typing import List


DEFAULT_SKILL = Path.home() / "Desktop/banshi2/SKILL.md"
DEFAULT_JSON = Path.home() / "Desktop/banshi2/skill_tree.json"

REJECTED_SUGGESTIONS = {
    "剔除80%内容": "误伤率过高，改为分层保留+结构化输出",
    "关键词全局四四关联O(n²)": "输入输出双爆token，不可行",
    "自我打分(0-10分)": "主观性太强，无重现性",
    "仅保留因果关系(单独)": "丢三顺序=操作手册报废",
    "仅保留约束关系(单独)": "丢三层级和顺序=规则碎片化",
    "开新会话隔离": "用户明确否决，且破坏连续性",
}

ADOPTED_SUGGESTIONS = {
    "文件外化存储": "系统架构，解决上下文膨胀的根本手段",
    "主动前置压缩": "辅助手段，用于延缓自动压缩触发",
    "层级归属+因果+顺序": "核心框架，骨架+命脉+逻辑桥接齐全",
    "约束关系": "可选补充，提高保真度但非必需",
    "功能角色分类": "预处理手段，替代主观打分",
    "结构层全自动提取": "核心方案，基于文档格式而非语义",
}

CAUSAL_MARKERS = [
    "因为",
    "所以",
    "导致",
    "从而",
    "因而",
    "因此",
    "if",
    "then",
    "除非",
    "否则",
    "以至于",
    "使得",
]

CONSTRAINT_KEYWORDS = [
    "必须",
    "禁止",
    "严禁",
    "不要",
    "只能",
    "仅限于",
    "务必",
    "切勿",
    "应当",
]


def _node_id(counter: list) -> str:
    counter[0] += 1
    return f"N{counter[0]}"


def _detect_role(text: str) -> str:
    t = text.strip()
    if re.match(r"^\d+[\.\、]", t):
        return "step"
    if re.match(r"^[-*]\s", t):
        return "item"
    if any(
        kw in t
        for kw in (
            "必须",
            "禁止",
            "严禁",
            "不要",
            "只能",
            "仅限于",
            "务必",
            "切勿",
            "应当",
        )
    ):
        return "constraint"
    if any(kw in t for kw in ("如果", "若", "当", "除非", "否则")):
        return "conditional"
    if any(kw in t for kw in CAUSAL_MARKERS):
        return "causal"
    return "info"


def _has_causal_marker(text: str) -> bool:
    return any(marker in text for marker in CAUSAL_MARKERS)


def _has_constraint_keyword(text: str) -> bool:
    return any(kw in text for kw in CONSTRAINT_KEYWORDS)


def _extract_constraint_keywords(text: str) -> list:
    return [kw for kw in CONSTRAINT_KEYWORDS if kw in text]


def rule_a_parse_hierarchy(lines: list) -> dict:
    counter = [0]
    root = {"id": "root", "text": "", "role": "root", "children": [], "source_line": 0}
    heading_stack = [root]
    in_code_block = False
    pending_paragraphs = []

    def _flush_paragraphs(parent: dict):
        for pline, ptext in pending_paragraphs:
            nid = _node_id(counter)
            parent["children"].append(
                {
                    "id": nid,
                    "text": ptext,
                    "role": _detect_role(ptext),
                    "children": [],
                    "source_line": pline,
                }
            )
        pending_paragraphs.clear()

    for lineno, raw_line in enumerate(lines, start=1):
        stripped = raw_line.rstrip("\n")

        if stripped.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        m_heading = re.match(r"^(#{2,4})\s+(.*)", stripped)
        if m_heading:
            _flush_paragraphs(heading_stack[-1])
            level = len(m_heading.group(1))
            title = m_heading.group(2).strip()
            nid = _node_id(counter)
            node = {
                "id": nid,
                "text": title,
                "role": "heading",
                "children": [],
                "source_line": lineno,
            }
            while len(heading_stack) > 1 and heading_stack[-1]["role"] != "root":
                top = heading_stack[-1]
                top_level = _heading_level(top)
                if top_level >= level:
                    heading_stack.pop()
                else:
                    break
            heading_stack[-1]["children"].append(node)
            heading_stack.append(node)
            continue

        m_list = re.match(r"^(\s*)([-*]|\d+[\.\、])\s+(.*)", stripped)
        if m_list:
            _flush_paragraphs(heading_stack[-1])
            indent = len(m_list.group(1))
            text = m_list.group(3).strip()
            nid = _node_id(counter)
            node = {
                "id": nid,
                "text": text,
                "role": _detect_role(m_list.group(2) + " " + text),
                "children": [],
                "source_line": lineno,
                "_indent": indent,
            }
            parent = heading_stack[-1]
            if parent["children"]:
                last = parent["children"][-1]
                if last.get("_indent") is not None and last["_indent"] < indent:
                    parent = last
            parent["children"].append(node)
            continue

        stripped_text = stripped.strip()
        if stripped_text and stripped_text != "---":
            pending_paragraphs.append((lineno, stripped_text))
            continue

        if not stripped_text:
            _flush_paragraphs(heading_stack[-1])

    _flush_paragraphs(heading_stack[-1])
    return root


def _heading_level(node: dict) -> int:
    if node["role"] == "root":
        return 0
    if node["role"] == "heading":
        return 1
    return 999


def _clean_tree(node: dict):
    node.pop("_indent", None)
    for child in node.get("children", []):
        _clean_tree(child)


def rule_b_extract_sequential(tree: dict) -> list:
    edges = []

    def _walk(node: dict):
        children = node.get("children", [])
        for i in range(len(children) - 1):
            edges.append(
                {
                    "from": children[i]["id"],
                    "to": children[i + 1]["id"],
                    "type": "next",
                }
            )
        for child in children:
            _walk(child)

    _walk(tree)
    return edges


def rule_c_extract_causal(tree: dict, sequential_edges: list) -> list:
    causal_edges = []

    def _mark_causal_nodes(node: dict):
        if _has_causal_marker(node["text"]):
            node["has_internal_causality"] = True
            causal_object = None
            for pattern in [
                r"从而([^，,。！!]+)",
                r"因而([^，,。！!]+)",
                r"导致([^，,。！!]+)",
            ]:
                m = re.search(pattern, node["text"])
                if m:
                    causal_object = m.group(1).strip()
                    break
            if causal_object:
                node["causal_object"] = causal_object
            m_reason = re.search(r"因为([^，,。！!]+)", node["text"])
            if m_reason:
                node["causal_reason"] = m_reason.group(1).strip()
        for child in node.get("children", []):
            _mark_causal_nodes(child)

    _mark_causal_nodes(tree)

    def _walk(node: dict, parent: Optional[dict] = None):
        children = node.get("children", [])
        for i, child in enumerate(children):
            if child.get("has_internal_causality"):
                # 尝试找到因果目标：优先下一个兄弟节点，其次父节点
                target = None
                if i + 1 < len(children):
                    target = children[i + 1]["id"]
                elif parent is not None and parent.get("id") != "root":
                    target = parent["id"]
                # 只添加有意义的非自环边（允许与顺序边并存，表达不同语义）
                if target and target != child["id"]:
                    causal_edges.append(
                        {
                            "from": child["id"],
                            "to": target,
                            "type": "internal",
                        }
                    )
            _walk(child, node)

    _walk(tree)

    return causal_edges


def rule_d_extract_constraints(tree: dict) -> list:
    constraints = []

    def _find_nearest_step(node: dict, current_step: Optional[dict]) -> Optional[dict]:
        if node["role"] in ("step", "heading"):
            return node
        return current_step

    def _walk(node: dict, current_step: Optional[dict]):
        effective_step = _find_nearest_step(node, current_step)
        kws = _extract_constraint_keywords(node["text"])
        if kws:
            target = effective_step if effective_step else node
            constraints.append(
                {
                    "node": target["id"],
                    "constrained_by": node["id"],
                    "keywords": kws,
                    "text": node["text"],
                }
            )
        for child in node.get("children", []):
            _walk(child, effective_step)

    _walk(tree, None)
    return constraints


def _collect_nodes(tree: dict) -> list:
    nodes = []

    def _walk(node: dict):
        nodes.append(node)
        for child in node.get("children", []):
            _walk(child)

    _walk(tree)
    return nodes


def _build_hierarchical_edges(tree: dict) -> list:
    edges = []

    def _walk(node: dict):
        for child in node.get("children", []):
            edges.append(
                {
                    "parent": node["id"],
                    "child": child["id"],
                }
            )
            _walk(child)

    _walk(tree)
    return edges


def _extract_semantic_fields(text: str) -> dict:
    fields = {"input": [], "output": [], "precondition": []}

    input_patterns = [
        r"读取\s+[`'『』]?([^`'『』\n]+)[`'『』]?",
        r"获取\s+([^，。、！？；；：「」『』【】（）\n]+)",
        r"从\s+([^，。、！？；；：「」『』【】（）\n]+)\s*(?:获取|读取)",
        r"输入[：:]\s*([^，。、！？；；：「」『』【】（）\n]+)",
    ]
    for p in input_patterns:
        for m in re.finditer(p, text):
            val = m.group(1).strip()
            if val and val not in fields["input"] and len(val) > 1:
                fields["input"].append(val)

    output_patterns = [
        r"写入\s+[`'『』]?([^`'『』\n]+)[`'『』]?",
        r"输出[：:]\s*([^，。、！？；；：「」『』【】（）\n]+)",
        r"生成\s+([^，。、！？；；：「」『』【】（）\n]+)",
        r"保存\s+([^，。、！？；；：「」『』【】（）\n]+)",
    ]
    for p in output_patterns:
        for m in re.finditer(p, text):
            val = m.group(1).strip()
            if val and val not in fields["output"] and len(val) > 1:
                fields["output"].append(val)

    pre_patterns = [
        r"(?:前提[：:]|前提条件[：:])\s*([^，。、！？；；：「」『』【】（）\n]+)",
        r"(?:如果|若|当|确保)\s*([^，。、！？；；：「」『』【】（）\n]+)",
        r"必须先\s*([^，。、！？；；：「」『』【】（）\n]+)",
        r"在\s*([^，。、！？；；：「」『』【】（）\n]+)\s*之前",
    ]
    for p in pre_patterns:
        for m in re.finditer(p, text):
            val = m.group(1).strip()
            if val and val not in fields["precondition"] and len(val) > 2:
                fields["precondition"].append(val)

    return fields


def _build_output_tree(node: dict) -> dict:
    result: dict[str, object] = {
        "id": node["id"],
        "type": node["role"],
        "label": node["text"],
        "children": [_build_output_tree(c) for c in node.get("children", [])],
    }
    if node.get("has_internal_causality"):
        result["has_internal_causality"] = True
    if node.get("causal_object"):
        result["causal_object"] = node["causal_object"]
    if node.get("causal_reason"):
        result["causal_reason"] = node["causal_reason"]
    # 语义完整性：为 step 节点提取 input/output/precondition
    if node.get("role") == "step":
        semantic = _extract_semantic_fields(node["text"])
        if semantic["input"]:
            result["input"] = semantic["input"]
        if semantic["output"]:
            result["output"] = semantic["output"]
        if semantic["precondition"]:
            result["precondition"] = semantic["precondition"]
    return result


def _calc_fidelity(tree: dict, hierarchical: list, sequential: list) -> dict:
    all_nodes = _collect_nodes(tree)
    total = len(all_nodes)
    if total == 0:
        return {
            "skeleton_preservation_rate": 0.0,
            "flow_executability": False,
            "information_discard_rate": 0.0,
        }

    heading_count = sum(1 for n in all_nodes if n["role"] == "heading")
    step_count = sum(1 for n in all_nodes if n["role"] == "step")
    skeleton_count = heading_count + step_count
    skeleton_rate = skeleton_count / total if total else 0.0

    flow_ok = len(sequential) > 0 and step_count > 0

    information_discard_rate = 1.0 - (skeleton_count / total) if total else 0.0

    return {
        "skeleton_preservation_rate": round(skeleton_rate, 4),
        "flow_executability": flow_ok,
        "information_discard_rate": round(information_discard_rate, 4),
    }


def _compute_chapter_hash(title: str, content: str) -> str:
    raw = f"{title}\n{content}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _extract_chapters_from_lines(lines: list) -> Dict[str, str]:
    chapters: Dict[str, str] = {}
    current_title: Optional[str] = None
    current_content_lines: List[str] = []
    in_code_block = False

    for raw_line in lines:
        stripped = raw_line.rstrip("\n")

        if stripped.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        m_heading = re.match(r"^##\s+(.*)", stripped)
        if m_heading:
            if current_title is not None:
                chapters[current_title] = "\n".join(current_content_lines).strip()
            current_title = m_heading.group(1).strip()
            current_content_lines = []
            continue

        if current_title is not None:
            current_content_lines.append(stripped)

    if current_title is not None:
        chapters[current_title] = "\n".join(current_content_lines).strip()

    return chapters


def compute_chapter_hashes(skill_path: str) -> Dict[str, str]:
    with open(skill_path, encoding="utf-8") as f:
        lines = f.readlines()

    chapters = _extract_chapters_from_lines(lines)
    hashes: Dict[str, str] = {}
    for title, content in chapters.items():
        hashes[title] = _compute_chapter_hash(title, content)
    return hashes


def load_chapter_hashes(json_path: Path) -> Dict[str, str]:
    hash_file = json_path.parent / "chapter_hashes.json"
    if not hash_file.exists():
        return {}
    with open(hash_file, encoding="utf-8") as f:
        return json.load(f)


def save_chapter_hashes(hashes: Dict[str, str], json_path: Path) -> None:
    hash_file = json_path.parent / "chapter_hashes.json"
    with open(hash_file, "w", encoding="utf-8") as f:
        json.dump(hashes, f, ensure_ascii=False, indent=2)


def detect_changed_chapters(
    old_hashes: Dict[str, str], new_hashes: Dict[str, str]
) -> List[str]:
    changed: List[str] = []
    all_titles = set(old_hashes.keys()) | set(new_hashes.keys())

    for title in sorted(all_titles):
        old_hash = old_hashes.get(title)
        new_hash = new_hashes.get(title)
        if old_hash != new_hash:
            changed.append(title)

    return changed


def _find_heading_in_tree(tree: dict, heading_text: str) -> Optional[dict]:
    """在树中按 heading 文本查找第一个匹配的节点（深拷贝安全）"""
    for child in tree.get("children", []):
        if child.get("role") == "heading" and child.get("text") == heading_text:
            return child
    for child in tree.get("children", []):
        found = _find_heading_in_tree(child, heading_text)
        if found:
            return found
    return None


def _remap_tree_ids(node: dict, counter: list) -> dict:
    """深拷贝并重新分配树中所有节点的 id"""
    new_node = dict(node)
    new_node["id"] = _node_id(counter)
    new_node["children"] = [
        _remap_tree_ids(c, counter) for c in node.get("children", [])
    ]
    return new_node


def _split_lines_by_heading2(lines: list) -> list:
    """按 ## 二级标题切分行，返回 [(title, lines), ...]"""
    chapters: list = []
    current_title: Optional[str] = None
    current_lines: list = []

    for line in lines:
        m = re.match(r"^##\s+(.*)", line)
        if m:
            if current_title is not None:
                chapters.append((current_title, current_lines))
            current_title = m.group(1).strip()
            current_lines = [line]
        elif current_title is not None:
            current_lines.append(line)

    if current_title is not None:
        chapters.append((current_title, current_lines))

    return chapters


def _incremental_parse(lines: list, old_tree: dict, changed_chapters: list) -> dict:
    """章节级增量解析：未变更章节复用旧树子树，变更章节重新解析"""
    changed_set = set(changed_chapters)
    counter = [0]
    root = {"id": "root", "text": "", "role": "root", "children": [], "source_line": 0}

    # 提取 frontmatter + intro（第一个 ## 之前的所有内容）
    intro_lines = []
    chapter_start_idx = 0
    for i, line in enumerate(lines):
        if re.match(r"^##\s+", line):
            chapter_start_idx = i
            break
        intro_lines.append(line)

    if intro_lines:
        intro_root = rule_a_parse_hierarchy(intro_lines)
        _clean_tree(intro_root)
        # 只保留有意义的子节点（过滤 frontmatter 属性行等）
        for child in intro_root.get("children", []):
            if child.get("role") not in ("root",):
                root["children"].append(child)

    # 按章节解析
    chapters = _split_lines_by_heading2(lines[chapter_start_idx:])
    for title, chapter_lines in chapters:
        if title not in changed_set:
            old_subtree = _find_heading_in_tree(old_tree, title)
            if old_subtree:
                # 复用旧子树，但重新分配 id 以避免冲突
                new_subtree = _remap_tree_ids(copy.deepcopy(old_subtree), counter)
                root["children"].append(new_subtree)
                continue
        # 变更章节或旧树中找不到，重新解析
        ch_root = rule_a_parse_hierarchy(chapter_lines)
        _clean_tree(ch_root)
        # 重新分配 id
        for child in ch_root.get("children", []):
            if child.get("role") not in ("root",):
                _renumber_node_ids(child, counter)
                root["children"].append(child)

    return root


def _renumber_node_ids(node: dict, counter: list):
    """为已存在的树重新分配连续 id"""
    node["id"] = _node_id(counter)
    for child in node.get("children", []):
        _renumber_node_ids(child, counter)


def generate_skill_tree(
    skill_path: str,
    old_tree: Optional[dict] = None,
    changed_chapters: Optional[list] = None,
) -> dict:
    with open(skill_path, encoding="utf-8") as f:
        lines = f.readlines()

    if old_tree and changed_chapters:
        tree = _incremental_parse(lines, old_tree, changed_chapters)
    else:
        tree = rule_a_parse_hierarchy(lines)
        _clean_tree(tree)

    hierarchical = _build_hierarchical_edges(tree)
    sequential = rule_b_extract_sequential(tree)
    causal = rule_c_extract_causal(tree, sequential)
    constraints = rule_d_extract_constraints(tree)

    fidelity = _calc_fidelity(tree, hierarchical, sequential)

    output_tree = _build_output_tree(tree)

    return {
        "meta": {
            "source": skill_path,
            "version": "2.0.0",
            "generated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "parser": "rule-based-4step-pipeline",
            "scheme": "Skill强关联降维最小可行方案",
        },
        "scheme_verdict": {
            "rejected": REJECTED_SUGGESTIONS,
            "adopted": ADOPTED_SUGGESTIONS,
        },
        "tree": output_tree,
        "relationships": {
            "hierarchical": hierarchical,
            "sequential": sequential,
            "causal": causal,
            "constraints": constraints,
        },
        "fidelity": fidelity,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse SKILL.md to skill_tree.json")
    parser.add_argument("skill_path", nargs="?", default=DEFAULT_SKILL, type=Path)
    parser.add_argument("json_path", nargs="?", default=DEFAULT_JSON, type=Path)
    parser.add_argument(
        "--incremental", action="store_true", help="Enable incremental update mode"
    )
    args = parser.parse_args()

    skill_path = args.skill_path
    json_path = args.json_path

    if not skill_path.exists():
        print(f"错误: 文件不存在 {skill_path}", file=sys.stderr)
        sys.exit(1)

    if args.incremental:
        old_hashes = load_chapter_hashes(json_path)
        new_hashes = compute_chapter_hashes(str(skill_path))

        old_tree = None
        if json_path.exists():
            try:
                with open(json_path, encoding="utf-8") as f:
                    old_data = json.load(f)
                    old_tree = old_data.get("tree")
            except Exception:
                pass

        if not old_hashes:
            print("增量模式: 未找到历史 hash，执行全量解析")
            result = generate_skill_tree(str(skill_path))
        else:
            changed = detect_changed_chapters(old_hashes, new_hashes)
            if not changed:
                print("增量模式: 无章节变更，跳过解析")
                sys.exit(0)
            print("增量模式: 检测到以下章节发生变化:")
            for title in changed:
                print(f"  - {title}")
            if old_tree:
                print("增量模式: 复用未变更章节的子树")
                result = generate_skill_tree(
                    str(skill_path), old_tree=old_tree, changed_chapters=changed
                )
            else:
                print("增量模式: 未找到旧树，执行全量解析")
                result = generate_skill_tree(str(skill_path))

        save_chapter_hashes(new_hashes, json_path)
    else:
        result = generate_skill_tree(str(skill_path))
        new_hashes = compute_chapter_hashes(str(skill_path))
        save_chapter_hashes(new_hashes, json_path)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    n_h = len(result["relationships"]["hierarchical"])
    n_s = len(result["relationships"]["sequential"])
    n_c = len(result["relationships"]["causal"])
    n_x = len(result["relationships"]["constraints"])
    fid = result["fidelity"]

    print("✓ 生成 skill_tree.json")
    print(f"  来源: {skill_path}")
    print(f"  输出: {json_path}")
    print(f"  层级边: {n_h}  顺序边: {n_s}  因果边: {n_c}  约束边: {n_x}")
    print(
        f"  保真度: 骨架保留率={fid['skeleton_preservation_rate']}  流程可执行={fid['flow_executability']}  信息丢弃率={fid['information_discard_rate']}"
    )
