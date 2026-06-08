#!/usr/bin/env python3
import json
import sys
import re
from pathlib import Path
from typing import Any


def check_step_input(step_text: str) -> dict[str, Any]:
    input_keywords = ["读取", "获取", "从", "输入", "source", "read", "load", "fetch"]
    matched = [kw for kw in input_keywords if kw in step_text.lower()]

    path_patterns = [r"~/", r"/path/", r"[A-Za-z]:\\"]
    for pattern in path_patterns:
        if re.search(pattern, step_text):
            matched.append(f"path_pattern:{pattern}")

    return {"has_input": len(matched) > 0, "matched": matched}


def check_step_output(step_text: str) -> dict[str, Any]:
    output_keywords = [
        "写入",
        "输出",
        "生成",
        "保存",
        "输出到",
        "write",
        "save",
        "output",
        "generate",
    ]
    matched = [kw for kw in output_keywords if kw in step_text.lower()]

    path_patterns = [r"~/", r"/path/", r"[A-Za-z]:\\"]
    for pattern in path_patterns:
        if re.search(pattern, step_text):
            matched.append(f"path_pattern:{pattern}")

    return {"has_output": len(matched) > 0, "matched": matched}


def check_step_prerequisite(
    step_id: str, constraints: list[str], steps: list[dict]
) -> dict[str, Any]:
    prerequisite_keywords = [
        "必须先",
        "在...之前",
        "before",
        "prior",
        "after",
        "在之前",
    ]

    for constraint in constraints:
        for keyword in prerequisite_keywords:
            if keyword in constraint:
                return {"has_prerequisite": True, "prerequisite_text": constraint}

    for step in steps:
        if step.get("id") == step_id:
            continue
        step_text = json.dumps(step, ensure_ascii=False).lower()
        for keyword in prerequisite_keywords:
            if keyword in step_text:
                return {
                    "has_prerequisite": True,
                    "prerequisite_text": f"Found '{keyword}' dependency reference",
                }

    return {"has_prerequisite": False, "prerequisite_text": ""}


def verify_completeness(skill_tree: dict[str, Any]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    steps = skill_tree.get("steps", [])

    for step in steps:
        step_id = step.get("id", "unknown")
        step_text = step.get("text", "")
        constraints = step.get("constraints", [])

        input_check = check_step_input(step_text)
        output_check = check_step_output(step_text)
        prerequisite_check = check_step_prerequisite(step_id, constraints, steps)

        results.append(
            {
                "step_id": step_id,
                "text_preview": step_text[:80] + "..."
                if len(step_text) > 80
                else step_text,
                "input": input_check,
                "output": output_check,
                "prerequisite": prerequisite_check,
                "is_complete": input_check["has_input"] and output_check["has_output"],
            }
        )

    return {"steps": results}


def generate_completeness_report(result: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("SKILL COMPLETENESS VERIFICATION REPORT")
    lines.append("=" * 70)

    steps = result.get("steps", [])
    total_steps = len(steps)
    complete_steps = sum(1 for s in steps if s.get("is_complete", False))

    completeness_score = (
        int((complete_steps / total_steps * 100)) if total_steps > 0 else 0
    )

    lines.append(f"\nTotal Steps: {total_steps}")
    lines.append(f"Complete Steps: {complete_steps}")
    lines.append(f"Completeness Score: {completeness_score}/100")
    lines.append("")

    lines.append("-" * 70)
    lines.append("STEP-BY-STEP ANALYSIS")
    lines.append("-" * 70)

    warnings: list[str] = []

    for step in steps:
        step_id = step.get("step_id", "unknown")
        lines.append(f"\n[Step {step_id}]")
        lines.append(f"  Text: {step.get('text_preview', '')}")

        input_check = step.get("input", {})
        output_check = step.get("output", {})
        prerequisite_check = step.get("prerequisite", {})

        lines.append(
            f"  Input:  {'✓' if input_check.get('has_input') else '✗'} {input_check.get('matched', [])}"
        )
        lines.append(
            f"  Output: {'✓' if output_check.get('has_output') else '✗'} {output_check.get('matched', [])}"
        )
        lines.append(
            f"  Prerequisite: {'✓' if prerequisite_check.get('has_prerequisite') else '✗'}"
        )

        if not input_check.get("has_input"):
            warnings.append(f"Step {step_id}: Missing input information")
        if not output_check.get("has_output"):
            warnings.append(f"Step {step_id}: Missing output information")

    lines.append("\n" + "-" * 70)
    lines.append("WARNINGS")
    lines.append("-" * 70)

    if warnings:
        for warning in warnings:
            lines.append(f"  ⚠ {warning}")
    else:
        lines.append("  No warnings found.")

    lines.append("\n" + "=" * 70)

    return "\n".join(lines)


def parse_skill_file(file_path: str) -> dict[str, Any]:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if path.suffix == ".json":
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    elif path.suffix == ".md":
        skill_tree: dict[str, Any] = {"steps": []}
        lines = path.read_text(encoding="utf-8").split("\n")

        step_pattern = re.compile(r"^(\d+)\.\s+(.+)")
        current_step: dict[str, Any] = {}

        for line in lines:
            match = step_pattern.match(line.strip())
            if match:
                if current_step:
                    skill_tree["steps"].append(current_step)
                step_id = match.group(1)
                step_text = match.group(2)
                current_step = {"id": step_id, "text": step_text, "constraints": []}
            elif current_step and line.strip().startswith("- "):
                current_step["constraints"].append(line.strip()[2:])

        if current_step:
            skill_tree["steps"].append(current_step)

        return skill_tree
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python3 verify_completeness.py <SKILL.md|skill_tree.json>")
        return 1

    file_path = sys.argv[1]

    try:
        skill_tree = parse_skill_file(file_path)
        result = verify_completeness(skill_tree)
        report = generate_completeness_report(result)
        print(report)
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except ValueError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
