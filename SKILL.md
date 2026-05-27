---
name: context-compressor
description: "ALWAYS USE WHEN: 任何时候当智能体检测到会话卡顿、Token 数量过高、用户提到 '会话太长了'、'重新整理记忆'、'上下文满了'、'开始崩溃'，或者智能体自身检测到多轮迭代中出现记忆混乱、重复犯同类错误时，必须调用本技能生成紧凑的上下文压缩树。"
user-invocable: true
version: 1.0.0
---

# 上下文压缩与状态精简技能 (Context Compressor Skill)

当我们在深度开发或 AI 代理调试过程中，因对话历史累计、代码仓库变更或终端输出导致上下文窗口被耗尽时，直接丢弃上下文会让智能体遗忘关键决策、遗漏已验证的错误修复，以及重复出现已排除的问题。

本技能通过**结构化压缩 (Structured Compaction)**，将工作状态转化为一份“只保留骨干、去除噪音”的可复用状态快照。

---

## 1. 适用场景

* 当前会话出现“记忆碎片化”或“重复问题”时
* 需要从旧会话切换到新会话，但不希望丢失当前工作上下文
* 当前工作目录包含大量缓存、临时文件，导致 git 状态噪音过多
* 需要生成一份“可直接投喂新模型”的结构化状态汇总

## 2. 不适用场景

* 日常日志收集、普通调试输出归档
* 需要精确还原代码内容或全文记录历史时
* 只想追踪单个 bug 修复，而不是整个会话状态时

## 3. 核心功能

* 从 Git 工作区中提取当前变更和最新提交
* 自动过滤 `__pycache__`、`*.pyc`、`.swp`、`.DS_Store` 等噪音文件
* 生成 `CONTEXT_SNAPSHOT.md` 作为“新会话快速恢复文件”
* 支持参数化调用：可定制工作区路径、输出目录、命令超时和排除规则

## 4. 输出结果

该技能将生成一份结构化 Markdown 文件，包含：

1. 意图与最新变更记录
2. 过滤规则与噪音说明
3. 全局运行时状态

该文件的正确示例格式如下：

```markdown
# SESSION CONTEXT COMPACTED (会话状态自动压缩层)
> **Generated on:** 2026-05-27 20:09:32 | **Host System:** macOS

## 1. 活动意图与最新变更记录
- **最后提交(Last Commit):** 165692b ci: scope tests to deterministic smoke suite
- **暂存区与未提交的代码变更(Git Status):**
- `[[M]]` acp-protocol/openclaw_config_updated.json

## 2. 关键过滤规则
- 默认过滤：`__pycache__`、`*.pyc`、`*.swp`、`.DS_Store`

## 3. 全局运行时状态
- **Active Workspace:** `/Users/newmacbook/claude`
- **输出目录:** `/Users/newmacbook/Desktop/办事材料`
```

## 5. 使用示例

```bash
python3 compress.py --workspace-dir /Users/newmacbook/claude --out-dir /Users/newmacbook/Desktop/办事材料 --timeout 30
```

或显式指定输出文件：

```bash
python3 compress.py --workspace-dir /Users/newmacbook/claude --out-file /tmp/context_snapshot.md
```

## 6. 关键建议

* 该技能应在“会话上下文临近饱和”或“需要无缝切换到新会话”时触发。
* 不要把它当作实时日志收集工具；它是“状态快照”而非“全文日志”。
* 仅在当前工作目录中的有效代码变更被识别后，才将输出文件作为新会话的启动输入。

## 7. 触发规则

当智能体检测到以下任一情况，应优先调用本技能：

* “Token 数量过高”
* “上下文窗口被耗尽”
* “记忆碎片化”
* “存在大量缓存文件或临时文件噪音”

---

## 8. 版本与扩展

* Current Skill Version: `1.0.0`
* 下一步可扩展项：
  * 增加“会话意图提取”模块，自动从 prompt 中提取当前目标
  * 支持从多个工作区生成一份汇总状态
  * 集成 CI/CD 预览以生成可审阅的状态快照
