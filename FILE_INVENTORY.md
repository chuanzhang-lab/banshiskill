# Context-Compressor Skill 文件清单

## 文件架构

```
banshi2/
├── SKILL.md                    # Skill 定义文档（输入源）
├── skill_tree.json             # 解析后的结构化树（中间产物）
├── skill_compressed.xml        # 压缩后的 XML（输出）
├── chapter_hashes.json         # 章节级变更检测哈希（缓存）
├── skill_index.md              # 快速索引参考
│
├── parse_skill.py              # 核心解析器（四步提取管线）
├── skill_compressor.py         # XML 压缩器（结构化输出）
├── compress.py                 # 上下文压缩（快照生成）
├── skill_diff.py               # 版本对比工具
├── verify_completeness.py      # 语义完整性验证
├── test_compress.py            # 测试套件（27 个测试）
│
├── Makefile                    # 构建命令封装
├── .coveragerc                 # pytest-cov 配置
├── .pre-commit-config.yaml     # 预提交检查配置
├── .gitignore                  # Git 忽略配置
│
├── .github/workflows/
│   ├── ci.yml                  # 持续集成工作流
│   └── cd.yml                  # 持续部署工作流
│
├── prompts/
│   └── skill_executor.md        # Skill 执行器模板
│
└── .trae/
    ├── rules/
    │   └── project_rules.md    # 项目规范
    └── specs/                  # 规范文档
```

## 核心文件职责

### parse_skill.py — 四步提取管线

**职责：** 从 SKILL.md 解析出结构化树

**四步规则：**
- Rule A: 层级归属（heading → content 归属）
- Rule B: 顺序关系（兄弟节点的 next 边）
- Rule C: 因果关系（internal 类型边）
- Rule D: 约束关系（must/forbid 类型约束）

**输出：**
```json
{
  "meta": { "source", "version", "generated", "parser", "scheme" },
  "tree": { "id", "type", "label", "children", "input", "output", "precondition" },
  "relationships": { "hierarchical", "sequential", "causal", "constraints" },
  "fidelity": { "skeleton_preservation_rate", "flow_executability", "information_discard_rate" }
}
```

### skill_compressor.py — XML 压缩器

**职责：** 将结构化树转换为紧凑 XML

**输出结构：**
```xml
<skill name="..." type="operation">
  <framework>
    <node id="..." text="..." role="heading">...</node>
    <child id="..." next="..." />
  </framework>
  <sequence>
    <step id="..." text="...">
      <input>...</input>
      <output>...</output>
      <precondition>...</precondition>
    </step>
  </sequence>
  <constraints>
    <rule target="..." type="required" text="..." />
  </constraints>
</skill>
```

### compress.py — 上下文压缩

**职责：** 生成会话快照（CONTEXT_SNAPSHOT.md）

**功能：**
- Git 工作区变更提取
- 噪音文件过滤（__pycache__, *.pyc 等）
- 结构化快照生成

**输出：** CONTEXT_SNAPSHOT.md

### skill_diff.py — 版本对比

**职责：** 对比两个版本的 skill_tree.json

**功能：**
- 节点增删改检测
- 关系变更分析
- 变更摘要生成

### verify_completeness.py — 完整性验证

**职责：** 检查 Skill 的语义完整性

**检查项：**
- 步骤的 input/output 标记
- 前置条件（precondition）
- 约束规则完整性

### test_compress.py — 测试套件

**测试覆盖：**
- Rule A: 层级解析（3 个测试）
- Rule B: 顺序关系（2 个测试）
- Rule C: 因果关系（2 个测试）
- Rule D: 约束关系（2 个测试）
- XML 压缩（6 个测试）
- 上下文压缩（10 个测试）

**总计：27 个测试**

## 数据流

```
SKILL.md
    │
    ▼
parse_skill.py ────► skill_tree.json
    │                      │
    │                      ▼
    │              skill_diff.py（版本对比）
    │
    ▼
skill_compressor.py ────► skill_compressed.xml
    │
    ▼
compress.py ────► CONTEXT_SNAPSHOT.md
```

## 增量更新

章节级哈希（chapter_hashes.json）用于：
- 检测哪些章节发生变化
- 跳过未变更章节的重新解析
- 加速大型 Skill 的处理

## 保真度指标

| 指标 | 含义 | 当前值 |
|------|------|--------|
| skeleton_preservation_rate | 骨架保留率 | 0.2727 |
| flow_executability | 流程可执行性 | True |
| information_discard_rate | 信息丢弃率 | 0.7273 |
| info_compression_ratio | 压缩比 | ~1.0 |

## 命令速查

```bash
make install    # 安装依赖
make test       # 运行测试
make lint       # 运行 linter
make format     # 格式化代码
make skill      # 生成所有工件
make snapshot   # 生成上下文快照
make clean      # 清理生成文件
make ci         # CI 检查（test + lint）
```
