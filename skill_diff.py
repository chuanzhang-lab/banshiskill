import json
import sys
import hashlib
from typing import Any


def generate_node_key(node: dict[str, Any]) -> str:
    text = node.get("label", "")
    node_type = node.get("type", "")
    content = f"{node_type}:{text}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def clean_node(node: dict[str, Any]) -> dict[str, Any]:
    cleaned = {
        "id": node.get("id", ""),
        "type": node.get("type", ""),
        "label": node.get("label", ""),
        "children": [],
    }
    if "children" in node:
        cleaned["children"] = [clean_node(child) for child in node["children"]]
    return cleaned


def flatten_tree(node: dict[str, Any]) -> list[dict[str, Any]]:
    result = [node.copy()]
    for child in node.get("children", []):
        result.extend(flatten_tree(child))
    return result


def load_skill_tree(json_path: str) -> dict[str, Any]:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "meta" in data:
        data["meta"].pop("generated", None)

    if "tree" in data:
        data["tree"] = clean_node(data["tree"])

    dynamic_fields = ["has_internal_causality"]
    for field in dynamic_fields:
        if field in data:
            del data[field]

    return data


def extract_nodes_by_key(
    tree: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    nodes: dict[str, dict[str, Any]] = {}
    root = tree.get("tree", {})
    flat_nodes = flatten_tree(root)
    for node in flat_nodes:
        key = generate_node_key(node)
        nodes[key] = node
    return nodes


def normalize_rel_key(rel: dict[str, Any], rel_type: str) -> tuple[str, str]:
    if rel_type == "hierarchical":
        return (rel["parent"], rel["child"])
    elif rel_type in ("sequential", "causal"):
        return (rel["from"], rel["to"])
    elif rel_type == "constraints":
        return (rel["node"], rel["constrained_by"])
    return ("", "")


def diff_nodes(
    old_tree: dict[str, Any], new_tree: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    old_nodes = extract_nodes_by_key(old_tree)
    new_nodes = extract_nodes_by_key(new_tree)

    old_keys = set(old_nodes.keys())
    new_keys = set(new_nodes.keys())

    added_keys = new_keys - old_keys
    removed_keys = old_keys - new_keys
    common_keys = old_keys & new_keys

    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    modified: list[dict[str, Any]] = []

    for key in added_keys:
        added.append(new_nodes[key])

    for key in removed_keys:
        removed.append(old_nodes[key])

    for key in common_keys:
        old_node = old_nodes[key]
        new_node = new_nodes[key]
        if old_node != new_node:
            modified.append({"old": old_node, "new": new_node})

    return {"added": added, "removed": removed, "modified": modified}


def diff_relationships(
    old_rels: dict[str, Any], new_rels: dict[str, Any]
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    rel_types = ["hierarchical", "sequential", "causal", "constraints"]
    result: dict[str, dict[str, list[dict[str, Any]]]] = {}

    for rel_type in rel_types:
        old_type_rels = old_rels.get(rel_type, [])
        new_type_rels = new_rels.get(rel_type, [])

        old_keys = set(normalize_rel_key(r, rel_type) for r in old_type_rels)
        new_keys = set(normalize_rel_key(r, rel_type) for r in new_type_rels)

        added_keys = new_keys - old_keys
        removed_keys = old_keys - new_keys
        common_keys = old_keys & new_keys

        added_rels: list[dict[str, Any]] = []
        removed_rels: list[dict[str, Any]] = []
        modified_rels: list[dict[str, Any]] = []

        old_rel_map = {normalize_rel_key(r, rel_type): r for r in old_type_rels}
        new_rel_map = {normalize_rel_key(r, rel_type): r for r in new_type_rels}

        for key in added_keys:
            added_rels.append(new_rel_map[key])

        for key in removed_keys:
            removed_rels.append(old_rel_map[key])

        for key in common_keys:
            old_r = old_rel_map[key]
            new_r = new_rel_map[key]
            if old_r != new_r:
                modified_rels.append({"old": old_r, "new": new_r})

        result[rel_type] = {
            "added": added_rels,
            "removed": removed_rels,
            "modified": modified_rels,
        }

    return result


def print_diff_report(diff_result: dict[str, Any]) -> None:
    node_diff = diff_result["nodes"]
    rel_diff = diff_result["relationships"]

    print("=" * 60)
    print("SKILL TREE DIFF REPORT")
    print("=" * 60)

    print("\n## Nodes")
    print("-" * 40)

    if node_diff["added"]:
        print(f"\n[+] Added ({len(node_diff['added'])}):")
        for node in node_diff["added"]:
            print(f"  {node.get('type', 'unknown')}: {node.get('label', '')[:60]}...")

    if node_diff["removed"]:
        print(f"\n[-] Removed ({len(node_diff['removed'])}):")
        for node in node_diff["removed"]:
            print(f"  {node.get('type', 'unknown')}: {node.get('label', '')[:60]}...")

    if node_diff["modified"]:
        print(f"\n[~] Modified ({len(node_diff['modified'])}):")
        for mod in node_diff["modified"]:
            old_label = mod["old"].get("label", "")[:40]
            new_label = mod["new"].get("label", "")[:40]
            print(f"  {mod['old'].get('type', 'unknown')}:")
            print(f"    - {old_label}...")
            print(f"    + {new_label}...")

    if not any(node_diff.values()):
        print("  No changes")

    print("\n## Relationships")
    print("-" * 40)

    for rel_type, changes in rel_diff.items():
        if any(changes.values()):
            print(f"\n### {rel_type.capitalize()}")
            if changes["added"]:
                print(f"  [+] Added: {len(changes['added'])}")
                for rel in changes["added"][:3]:
                    print(f"      {rel}")
                if len(changes["added"]) > 3:
                    print(f"      ... and {len(changes['added']) - 3} more")

            if changes["removed"]:
                print(f"  [-] Removed: {len(changes['removed'])}")
                for rel in changes["removed"][:3]:
                    print(f"      {rel}")
                if len(changes["removed"]) > 3:
                    print(f"      ... and {len(changes['removed']) - 3} more")

            if changes["modified"]:
                print(f"  [~] Modified: {len(changes['modified'])}")
                for mod in changes["modified"][:3]:
                    print(f"      {mod['old']} -> {mod['new']}")
                if len(changes["modified"]) > 3:
                    print(f"      ... and {len(changes['modified']) - 3} more")

    total_added = len(node_diff["added"])
    total_removed = len(node_diff["removed"])
    total_modified = len(node_diff["modified"])
    total_rel_changes = sum(
        len(changes["added"]) + len(changes["removed"]) + len(changes["modified"])
        for changes in rel_diff.values()
    )

    print("\n" + "=" * 60)
    print(
        f"Summary: +{total_added} -{total_removed} ~{total_modified} "
        f"relationships: {total_rel_changes}"
    )
    print("=" * 60)


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} old_tree.json new_tree.json")
        sys.exit(1)

    old_path = sys.argv[1]
    new_path = sys.argv[2]

    old_tree = load_skill_tree(old_path)
    new_tree = load_skill_tree(new_path)

    node_diff = diff_nodes(old_tree, new_tree)

    old_rels = old_tree.get("relationships", {})
    new_rels = new_tree.get("relationships", {})
    rel_diff = diff_relationships(old_rels, new_rels)

    diff_result = {"nodes": node_diff, "relationships": rel_diff}
    print_diff_report(diff_result)


if __name__ == "__main__":
    main()
