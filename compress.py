#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Context Compressor: generate a compact session snapshot for AI handoff.
"""

import argparse
import fnmatch
import logging
import os
import subprocess
import datetime
from pathlib import Path
from typing import List

DEFAULT_WORKSPACE_DIR = Path("/Users/newmacbook/claude")
DEFAULT_OUT_DIR = Path("/Users/newmacbook/Desktop/办事材料")
DEFAULT_TIMEOUT = 30
DEFAULT_EXCLUDE = ["__pycache__", "*.pyc", "*.swp", ".DS_Store"]


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def run_cmd(cmd: List[str], cwd: Path = None, timeout: int = DEFAULT_TIMEOUT) -> str:
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            logging.warning("Command failed: %s", " ".join(cmd))
            if result.stderr:
                logging.warning("stderr: %s", result.stderr.strip())
            return ""
        return result.stdout.rstrip("\r\n")
    except subprocess.TimeoutExpired as exc:
        logging.error("Command timed out after %s seconds: %s", timeout, " ".join(cmd))
        if exc.stdout:
            logging.error("stdout: %s", exc.stdout.strip())
        if exc.stderr:
            logging.error("stderr: %s", exc.stderr.strip())
        return ""
    except FileNotFoundError:
        logging.error("Executable not found: %s", cmd[0])
        return ""
    except Exception as exc:
        logging.error("Unexpected error while running %s: %s", " ".join(cmd), exc)
        return ""


def is_noise_path(path: str, exclude_patterns: List[str]) -> bool:
    normalized = path.replace('\\', '/')
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(normalized, pattern) or pattern in normalized:
            return True
    return False


def parse_git_status_line(line: str, exclude_patterns: List[str]) -> str:
    if not line.strip():
        return ""
    status = line[:2].strip()
    path = line[2:].strip() if len(line) >= 3 else line[2:].strip()
    if not path or is_noise_path(path, exclude_patterns):
        return ""
    return f"- `[{status}]` {path}"


def get_git_changes(workspace_dir: Path, exclude_patterns: List[str]) -> str:
    if not workspace_dir.exists():
        return f"- No git workspace found at configured path: {workspace_dir}"

    status = run_cmd(["git", "status", "--porcelain"], cwd=workspace_dir)
    if not status:
        return "- Git status is clean (no uncommitted changes detected)."

    entries = []
    for line in status.splitlines():
        parsed = parse_git_status_line(line, exclude_patterns)
        if parsed:
            entries.append(parsed)

    if not entries:
        return "- Git status contains only excluded noise files."
    return "\n".join(entries)


def get_latest_commit(workspace_dir: Path) -> str:
    if not workspace_dir.exists():
        return "N/A"
    commit = run_cmd(["git", "log", "-1", "--oneline"], cwd=workspace_dir)
    return commit or "N/A"


def build_snapshot(timestamp: str, workspace_dir: Path, out_dir: Path, git_snapshot: str, last_commit: str) -> str:
    host_system = os.uname().sysname if hasattr(os, "uname") else "unknown"
    return f"""# SESSION CONTEXT COMPACTED (会话状态自动压缩层)
> **Generated on:** {timestamp} | **Host System:** {host_system}

## 1. 活动意图与最新变更记录
- **最后提交(Last Commit):** {last_commit}
- **暂存区与未提交的代码变更(Git Status):**
{git_snapshot}

## 2. 关键过滤规则
- 默认过滤：`__pycache__`、`*.pyc`、`*.swp`、`.DS_Store`
- 仅保留与当前开发上下文直接相关的变更，避免将无关缓存文件转化为 prompt 噪音。

## 3. 全局运行时状态
- **Active Workspace:** `{workspace_dir}`
- **输出目录:** `{out_dir}`

---
*Tip: 该文件用于在新会话中快速恢复开发状态。不要把它当作常规日志聚合器。*
"""


def write_snapshot(out_file: Path, content: str) -> bool:
    try:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(content, encoding="utf-8")
        logging.info("✅ Context snapshot saved to: %s", out_file)
        return True
    except Exception as exc:
        logging.error("Failed to write snapshot to %s: %s", out_file, exc)
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a compact session context snapshot for AI handoff."
    )
    parser.add_argument(
        "--workspace-dir",
        type=Path,
        default=DEFAULT_WORKSPACE_DIR,
        help="Git workspace root to inspect.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Directory where CONTEXT_SNAPSHOT.md will be written.",
    )
    parser.add_argument(
        "--out-file",
        type=Path,
        help="Explicit output file path. Overrides --out-dir.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="Timeout seconds for git command execution.",
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=DEFAULT_EXCLUDE,
        help="Glob patterns to exclude from git status output.",
    )
    parser.add_argument("--version", action="version", version="context-compressor 1.0.0")
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()

    workspace_dir = args.workspace_dir.expanduser()
    out_dir = args.out_dir.expanduser() if args.out_file is None else args.out_file.parent.expanduser()
    out_file = args.out_file.expanduser() if args.out_file else out_dir / "CONTEXT_SNAPSHOT.md"

    logging.info("Starting Context Compressor")
    logging.info("Workspace dir: %s", workspace_dir)
    logging.info("Output file: %s", out_file)
    logging.info("Command timeout: %s seconds", args.timeout)
    logging.info("Exclude patterns: %s", args.exclude)

    git_snapshot = get_git_changes(workspace_dir, args.exclude)
    last_commit = get_latest_commit(workspace_dir)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    snapshot = build_snapshot(timestamp, workspace_dir, out_dir, git_snapshot, last_commit)

    return 0 if write_snapshot(out_file, snapshot) else 1


if __name__ == "__main__":
    raise SystemExit(main())
