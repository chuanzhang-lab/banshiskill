# Context-Compressor Skill

> 一个用于压缩、解析和优化上下文的智能体技能，基于"层级隔离 + 顺序驱动 + 检查点验证"的设计原则。

> **v2.0 已完成 · 船坞出品 · 启航**

## 🚀 一键启动

无需关心当前目录：

```bash
bash setup.sh
```

**自动完成**：
1. 切到脚本所在目录（解决"找不到文件"问题）
2. 安装依赖（`python3 -m pip install -r requirements.txt`）
3. 生成所有工件（skill_tree.json / skill_compressed.xml / CONTEXT_SNAPSHOT.md）
4. 跑测试（47 passed）
5. Lint + Format 检查

**适用场景**：
- ✅ 第一次使用（推荐）
- ✅ 验证环境是否配置正确
- ✅ 跑一次完整冒烟测试

## 项目结构

```
banshi2/
├── SKILL.md                    # Skill 定义文档（输入）
├── README.md                   # 项目说明
├── skill_tree.json             # 解析树（中间产物）
├── skill_compressed.xml        # XML 压缩输出（v2.0 嵌套分层结构）
├── skill_index.md              # 快速索引
├── chapter_hashes.json         # 增量哈希（缓存）
├── CONTEXT_SNAPSHOT.md         # 上下文快照
├── FILE_INVENTORY.md           # 文件清单
│
├── parse_skill.py              # 四步提取管线（规则 A/B/C/D）
├── skill_compressor.py         # XML 压缩输出（核心层/任务层）
├── compress.py                 # 上下文压缩 + 保真度评估
├── verify_completeness.py      # 语义完整性验证
├── skill_diff.py               # 版本对比
├── drift_detector.py           # L1/L2 外部漂移检测（v2.0 新增）
├── layered_skill.py            # 分层 Skill 加载器（v2.0 新增）
├── state_loader.py             # 按需状态加载器（v2.0 新增）
├── deploy.py                   # 一键部署脚本
├── test_compress.py            # 测试（47 个测试用例）
│
├── prompts/                    # 执行模板
│   └── skill_executor.md
│
├── setup.sh                    # 一键启动脚本（推荐首次使用）
├── requirements.txt            # 依赖清单
├── Makefile                    # 构建脚本
├── .coveragerc                 # 覆盖率配置
├── .pre-commit-config.yaml     # pre-commit 钩子
└── .github/workflows/          # CI/CD 工作流
    ├── ci.yml
    └── cd.yml
```

## 快速开始

### 1. 安装依赖

推荐：用 requirements.txt（跨平台、版本固定）

```bash
python3 -m pip install -r requirements.txt
```

或者一行命令直接装：

```bash
python3 -m pip install ruff mypy types-python-dateutil pytest pytest-cov
```

也支持 make（如果系统装了 make）：

```bash
make install
```

**为什么用 `python3 -m pip` 而不是 `pip`？**
- `pip` 在 macOS 上可能指向 pip2（系统 Python）
- `python3 -m pip` 强制用当前 python3 的 pip
- 跨平台（macOS/Linux/Windows）通用

### 2. 生成工件

生成解析树：

```bash
python3 parse_skill.py
```

生成 XML 压缩文件（v2.0 嵌套分层结构）：

```bash
python3 skill_compressor.py
```

生成上下文快照（含保真度评估）：

```bash
python3 compress.py --skill-md SKILL.md
```

也支持 make：

```bash
make skill
```

```bash
make snapshot
```

### 3. 运行测试

```bash
python3 -m pytest test_compress.py -v
```

预期输出：47 passed in 0.32s

也支持 make：

```bash
make test
```

### 4. 代码质量

Lint 检查：

```bash
python3 -m ruff check .
```

预期输出：All checks passed!

格式化代码：

```bash
python3 -m ruff format .
```

预期输出：10 files left unchanged

也支持 make：

```bash
make lint
```

```bash
make format
```

### 5. v2.0 新功能（Python API）

分层加载（核心层 + 任务层）：

```python
from layered_skill import LayeredSkill
ls = LayeredSkill("SKILL.md")
print(ls.layer_stats())  # {'core': 148, 'task': 1605, 'all': 1769}
core = ls.load_core()    # ~700 token，始终在场
task = ls.load_task()    # ~2k token，按需加载
```

按需状态加载（用户说"继续上次"才加载）：

```python
from state_loader import StateLoader
s = StateLoader()
if s.should_load(user_input):  # "继续上次" → True
    state = s.load()
```

L1/L2 外部漂移检测：

```python
from drift_detector import DriftDetector
d = DriftDetector()
report = d.detect(user_input="不对", output="")
print(report["drift_detected"])  # True（L1 用户反馈触发）
```

### 6. 一键部署

端到端部署（lint/format/typecheck/test/build 全跑）：

```bash
python3 deploy.py
```

简化版（test + lint）：

```bash
make ci
```

### 7. 清理

```bash
make clean
```

### 完整命令对照表

| 任务 | Python 直接调用 | Make 封装 |
|------|-----------------|-----------|
| 安装依赖 | `python3 -m pip install -r requirements.txt` | `make install` |
| 生成 skill_tree.json | `python3 parse_skill.py` | `make skill-tree` |
| 生成 skill_compressed.xml | `python3 skill_compressor.py` | `make skill-xml` |
| 生成 CONTEXT_SNAPSHOT.md | `python3 compress.py --skill-md SKILL.md` | `make snapshot` |
| 运行测试 | `python3 -m pytest test_compress.py -v` | `make test` |
| Lint | `python3 -m ruff check .` | `make lint` |
| 格式化 | `python3 -m ruff format .` | `make format` |
| 端到端部署 | `python3 deploy.py` | - |
| 清理 | - | `make clean` |

## 生产化部署

### 一键部署

```bash
python3 deploy.py
```

执行步骤：
1. ✅ 验证 Python 环境
2. ✅ 安装依赖（ruff/mypy/pytest）
3. ✅ Lint 检查
4. ✅ Format 检查（自动修复）
5. ✅ Type Check
6. ✅ 测试（47 个用例）
7. ✅ 生成 Skill 工件
8. ✅ XML 结构验证
9. ✅ 打包发布文件

### CI/CD 流程

#### CI（持续集成）

触发条件：push / pull_request 到 main/master

**5 个独立 Job：**

| Job | 内容 | 严格度 |
|-----|------|--------|
| **lint** | ruff check + ruff format --check | 强制 |
| **typecheck** | mypy 静态类型检查 | 警告 |
| **test** | pytest + coverage gate (>=80%) | 强制 |
| **build-artifacts** | 生成 skill_tree.json + XML | 强制 + XML 验证 |
| **deploy** | 仅 main 分支：自动提交工件 | 强制 |

#### CD（持续部署）

触发条件：
- 推送 `v*.*.*` 标签 → 自动发布 GitHub Release
- 手动触发（workflow_dispatch）

**发布流程：**
1. 检出代码（完整历史）
2. 运行测试
3. 生成工件
4. 打包为 `release/` 目录
5. 创建 `.tar.gz` 压缩包
6. 创建 GitHub Release 并上传

### 发布新版本

```bash
# 1. 确保所有测试通过
make ci

# 2. 创建 tag
git tag v2.1.0
git push origin v2.1.0

# 3. GitHub Actions 自动触发 CD
#    - 打包 release/
#    - 创建 GitHub Release
#    - 生成变更日志
```

## XML 结构

生成的 `skill_compressed.xml` 采用 **v2.0 嵌套分层结构**（核心层 + 任务层）：

```xml
<skill name="context-compressor" type="operation">
  <layer name="core" priority="critical" always_loaded="true">    <!-- 核心层（始终在场） -->
    <context_hierarchy>           <!-- 1. 层级隔离 -->
      <system_level priority="critical">...</system_level>
      <skill_level priority="high">...</skill_level>
      <user_level priority="low">...</user_level>
    </context_hierarchy>
  </layer>

  <layer name="task" priority="high" load_on_demand="true">      <!-- 任务层（按需加载） -->
    <constraints>                 <!-- 2. 约束（先件） -->
      <rule priority="critical" type="forbidden" />
      <rule priority="high" type="required" />
    </constraints>

    <execution_flow mode="sequential">  <!-- 3. 执行（顺序） -->
      <step_4 checkpoint="[4]">
        <intent>重置上下文优先级</intent>
        <action>发送元指令...</action>
        <effect>重置上下文优先级</effect>
      </step_4>
    </execution_flow>
  </layer>
</skill>
```

| 结构 | 设计原则 | 作用 |
|------|----------|------|
| `<layer name="core">` | 始终在场 | 注入元指令 + 层级隔离 |
| `<layer name="task">` | 按需加载 | 注入约束 + 执行流 |
| `<context_hierarchy>` 在 core 层 | 层级隔离 | 防错 |
| `<constraints>` 在 `<execution_flow>` 之前 | 先件后动 | 顺序 |
| `<step_n checkpoint="[n]">` | 检查点机制 | 验证 |
| `<intent> + <action> + <effect>` | 意图传递链 | 因果 |

### 分层加载示例

```python
from layered_skill import LayeredSkill
from state_loader import StateLoader

ls = LayeredSkill("SKILL.md")
core = ls.load_core()   # ~700 token，始终在场
task = ls.load_task()   # ~2k token，按需加载
all_xml = ls.load_all() # ~2.7k token，完整（向后兼容）

s = StateLoader()
if s.should_load(user_input):  # 用户说"继续上次"才加载
    state = s.load()
```

## 不做的事（明确范围）

- ❌ **不做模型自检**（自检悖论：漂移的模型无法正确判断自己是否漂移）
- ❌ **不做自动重注入**（成本高、收益递减）
- ❌ **不做完美遵循**（接受 60-90% 概率遵循）
- ❌ **不做协商遵循**（保持强制遵循，因为对当前用户够用）

## 替代方案

- 检测漂移：使用 `drift_detector.py`（L1 用户反馈 + L2 输出特征）
- 跨会话：使用 `SESSION-STATE.md`（人工外化）
- 长对话：开启新会话而非重注入

## 开发指南

### 修改 SKILL.md 后重新生成

```bash
make skill
```

### 添加新测试

在 `test_compress.py` 添加测试用例，然后运行：

```bash
make test
```

### Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## 故障排查

### Lint 失败

```bash
make format  # 自动修复格式
```

### XML 验证失败

```bash
python3 -c "
import xml.etree.ElementTree as ET
ET.parse('skill_compressed.xml')
print('OK')
"
```

### 测试失败

```bash
python3 -m pytest test_compress.py -v --tb=long
```

## License

MIT
