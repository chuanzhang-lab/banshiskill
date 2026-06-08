import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from parse_skill import (
    rule_a_parse_hierarchy,
    generate_skill_tree,
    REJECTED_SUGGESTIONS,
    ADOPTED_SUGGESTIONS,
    CAUSAL_MARKERS,
    CONSTRAINT_KEYWORDS,
)
from skill_compressor import (
    compress_to_xml,
    _constraint_type,
)
from compress import (
    run_cmd,
    is_noise_path,
    parse_git_status_line,
    get_git_changes,
    get_latest_commit,
    write_snapshot,
    calc_skeleton_preservation,
    verify_flow_executability,
    calc_compression_ratio,
)

SAMPLE_MD = """\
## 操作流程

### 触发条件

用户说"执行"

### 执行步骤

1. 发送元指令，从而重置上下文
2. ReadFile 读取 SKILL.md，导致获取执行依据
3. 执行结果写入 output.md
4. 回复简短确认

### 约束规则

- 必须先发送元指令
- 禁止直接注入文件内容
"""


class TestParseSkillRuleA(unittest.TestCase):
    def test_rule_a_heading_hierarchy(self):
        lines = ["## 标题1\n", "### 子标题\n", "内容\n"]
        tree = rule_a_parse_hierarchy(lines)
        heading1 = tree["children"][0]
        self.assertEqual(heading1["text"], "标题1")
        self.assertEqual(heading1["role"], "heading")
        sub = heading1["children"][0]
        self.assertEqual(sub["text"], "子标题")
        self.assertEqual(sub["role"], "heading")
        content = sub["children"][0]
        self.assertEqual(content["text"], "内容")

    def test_rule_a_list_indentation(self):
        lines = ["## 标题\n", "- 项目1\n", "  - 子项目\n"]
        tree = rule_a_parse_hierarchy(lines)
        heading = tree["children"][0]
        item1 = heading["children"][0]
        self.assertEqual(item1["text"], "项目1")
        sub_item = item1["children"][0]
        self.assertEqual(sub_item["text"], "子项目")

    def test_rule_a_paragraph_attribution(self):
        lines = ["## 标题\n", "段落文本\n"]
        tree = rule_a_parse_hierarchy(lines)
        heading = tree["children"][0]
        para = heading["children"][0]
        self.assertEqual(para["text"], "段落文本")


class TestParseSkillRuleB(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.md_path = os.path.join(self.tmp_dir, "test.md")
        with open(self.md_path, "w", encoding="utf-8") as f:
            f.write(SAMPLE_MD)
        self.result = generate_skill_tree(self.md_path)
        self.sequential = self.result["relationships"]["sequential"]
        self.nodes = {}
        self._collect(self.result["tree"])

    def _collect(self, node):
        self.nodes[node["id"]] = node
        for c in node.get("children", []):
            self._collect(c)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_rule_b_sequential_next(self):
        next_edges = [e for e in self.sequential if e["type"] == "next"]
        self.assertTrue(len(next_edges) > 0)
        step_nodes = [n for n in self.nodes.values() if n.get("type") == "step"]
        step_ids = [n["id"] for n in step_nodes]
        step_next = [
            (e["from"], e["to"])
            for e in next_edges
            if e["from"] in step_ids and e["to"] in step_ids
        ]
        self.assertTrue(len(step_next) > 0)
        for i in range(len(step_ids) - 1):
            self.assertIn((step_ids[i], step_ids[i + 1]), step_next)

    def test_rule_b_no_skip(self):
        next_edges = [e for e in self.sequential if e["type"] == "next"]
        edge_pairs = {(e["from"], e["to"]) for e in next_edges}
        step_nodes = [n for n in self.nodes.values() if n.get("type") == "step"]
        step_ids = [n["id"] for n in step_nodes]
        for i in range(len(step_ids)):
            for j in range(i + 2, len(step_ids)):
                self.assertNotIn((step_ids[i], step_ids[j]), edge_pairs)


class TestParseSkillRuleC(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.md_path = os.path.join(self.tmp_dir, "test.md")
        with open(self.md_path, "w", encoding="utf-8") as f:
            f.write(SAMPLE_MD)
        self.result = generate_skill_tree(self.md_path)
        self.causal = self.result["relationships"]["causal"]
        self.sequential = self.result["relationships"]["sequential"]
        self.nodes = {}
        self._collect(self.result["tree"])

    def _collect(self, node):
        self.nodes[node["id"]] = node
        for c in node.get("children", []):
            self._collect(c)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_rule_c_causal_markers(self):
        causal_nodes = [
            n for n in self.nodes.values() if n.get("has_internal_causality")
        ]
        self.assertTrue(len(causal_nodes) > 0)
        for n in causal_nodes:
            self.assertTrue(any(m in n["label"] for m in CAUSAL_MARKERS))

    def test_rule_c_has_internal_edges(self):
        internal_edges = [e for e in self.causal if e["type"] == "internal"]
        self.assertTrue(len(internal_edges) > 0)
        for e in internal_edges:
            self.assertIn("from", e)
            self.assertIn("to", e)
            self.assertIn("type", e)
            self.assertEqual(e["type"], "internal")


class TestParseSkillRuleD(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.md_path = os.path.join(self.tmp_dir, "test.md")
        with open(self.md_path, "w", encoding="utf-8") as f:
            f.write(SAMPLE_MD)
        self.result = generate_skill_tree(self.md_path)
        self.constraints = self.result["relationships"]["constraints"]

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_rule_d_constraint_keywords(self):
        self.assertTrue(len(self.constraints) > 0)
        for c in self.constraints:
            self.assertTrue(len(c["keywords"]) > 0)
            for kw in c["keywords"]:
                self.assertIn(kw, CONSTRAINT_KEYWORDS)

    def test_rule_d_constraint_attached_to_step(self):
        constraint_md = "## 标题\n1. 执行操作\n   - 必须先确认\n"
        path = os.path.join(self.tmp_dir, "constraint_test.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(constraint_md)
        result = generate_skill_tree(path)
        constraints = result["relationships"]["constraints"]
        self.assertTrue(len(constraints) > 0)
        all_nodes = []
        self._collect_list(result["tree"], all_nodes)
        step_ids = {n["id"] for n in all_nodes if n.get("type") == "step"}
        for c in constraints:
            self.assertIn(c["node"], step_ids)

    def _collect_list(self, node, out):
        out.append(node)
        for c in node.get("children", []):
            self._collect_list(c, out)


class TestParseSkillConstants(unittest.TestCase):
    def test_rejected_suggestions(self):
        self.assertEqual(len(REJECTED_SUGGESTIONS), 6)

    def test_adopted_suggestions(self):
        self.assertEqual(len(ADOPTED_SUGGESTIONS), 6)


class TestSkillCompressor(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.md_path = os.path.join(self.tmp_dir, "test.md")
        with open(self.md_path, "w", encoding="utf-8") as f:
            f.write(SAMPLE_MD)
        self.xml = compress_to_xml(self.md_path)
        self.result = generate_skill_tree(self.md_path)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_xml_has_hierarchy_structure(self):
        """测试：XML 包含显式层级结构（防错的盾牌）"""
        self.assertIn("<context_hierarchy>", self.xml)
        self.assertIn("<system_level", self.xml)
        self.assertIn("<skill_level", self.xml)
        self.assertIn("<user_level", self.xml)

    def test_xml_has_constraints(self):
        self.assertIn("<constraints>", self.xml)

    def test_xml_execution_flow_has_step_tags(self):
        """测试：执行步骤使用 step_1, step_2 等编号标签"""
        self.assertIn("step_1 ", self.xml)
        self.assertIn("step_2 ", self.xml)

    def test_xml_sequence_has_causal_structure(self):
        """测试：执行步骤包含因果结构（intent + effect）"""
        causes_md = "## 标题\n1. 从而触发子操作\n2. 步骤二\n"
        path = os.path.join(self.tmp_dir, "causes_test.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(causes_md)
        xml = compress_to_xml(path)
        self.assertIn("<intent>", xml)
        self.assertIn("<effect>", xml)

    def test_xml_sequence_has_semantic_fields(self):
        semantic_md = "## 标题\n1. ReadFile 读取 文件，输出 结果\n2. 步骤二\n"
        path = os.path.join(self.tmp_dir, "semantic_test.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(semantic_md)
        xml = compress_to_xml(path)
        self.assertTrue(
            "<input>" in xml or "<output>" in xml,
            "XML should contain input or output tags",
        )

    def test_constraint_type_mapping(self):
        self.assertEqual(_constraint_type(["禁止"]), "forbidden")
        self.assertEqual(_constraint_type(["必须"]), "required")
        self.assertEqual(_constraint_type(["只能"]), "exclusive")

    def test_xml_is_well_formed(self):
        """测试：XML 必须格式良好（无未转义双引号）"""
        import xml.etree.ElementTree as ET

        ET.fromstring(self.xml)  # 解析失败即测试失败

    def test_xml_skill_name_extracted(self):
        """测试：SKILL 根标签包含正确的名称"""
        import re

        m = re.search(r'<skill name="([^"]+)"', self.xml)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "操作流程")  # SAMPLE_MD 的第一个 heading

    def test_xml_hierarchy_has_priority(self):
        """测试：层级包含优先级属性"""
        self.assertIn('priority="critical"', self.xml)
        self.assertIn('priority="high"', self.xml)
        self.assertIn('priority="low"', self.xml)

    def test_xml_constraint_before_execution_flow(self):
        """测试：约束在执行步骤之前（先件后动）"""
        constraints_pos = self.xml.find("<constraints>")
        execution_flow_pos = self.xml.find("<execution_flow")
        self.assertLess(constraints_pos, execution_flow_pos)

    def test_xml_execution_flow_has_checkpoint(self):
        """测试：执行步骤包含检查点标签"""
        self.assertIn('checkpoint="[1]"', self.xml)
        self.assertIn('checkpoint="[2]"', self.xml)

    def test_xml_execution_flow_mode(self):
        """测试：执行步骤使用正确的标签名"""
        self.assertIn('<execution_flow mode="sequential">', self.xml)
        self.assertNotIn("<sequence>", self.xml)

    def test_xml_constraint_has_priority_attr(self):
        """测试：约束包含优先级属性"""
        self.assertIn('priority="', self.xml)


class TestDriftDetector(unittest.TestCase):
    """测试：L1 + L2 外部漂移检测（不依赖模型自检）"""

    def test_L1_detect_user_feedback(self):
        """L1: 检测用户反馈"""
        from drift_detector import DriftDetector

        d = DriftDetector()
        self.assertTrue(d.L1_user_feedback("不对，重来"))
        self.assertTrue(d.L1_user_feedback("自由发挥"))
        self.assertFalse(d.L1_user_feedback("请继续"))
        self.assertFalse(d.L1_user_feedback(""))

    def test_L2_detect_long_output(self):
        """L2: 检测超长输出"""
        from drift_detector import DriftDetector, MAX_OUTPUT_LENGTH

        d = DriftDetector()
        long_output = "x" * (MAX_OUTPUT_LENGTH + 100)
        rate = d.L2_output_features(long_output)
        self.assertGreater(rate, 0)

    def test_L2_detect_special_token_leak(self):
        """L2: 检测特殊 token 泄漏"""
        from drift_detector import DriftDetector

        d = DriftDetector()
        bad_output = "正常内容 <|endoftext|>" * 10
        rate = d.L2_output_features(bad_output)
        self.assertGreater(rate, 0)

    def test_L2_clean_output(self):
        """L2: 干净输出违规率为 0"""
        from drift_detector import DriftDetector

        d = DriftDetector()
        clean_output = "这是一个干净的输出"
        rate = d.L2_output_features(clean_output)
        self.assertEqual(rate, 0.0)

    def test_detect_comprehensive(self):
        """综合检测"""
        from drift_detector import DriftDetector

        d = DriftDetector()
        result = d.detect(user_input="不对", output="normal output")
        self.assertTrue(result["L1_user_feedback"])
        self.assertTrue(result["drift_detected"])


class TestCompress(unittest.TestCase):
    def test_run_cmd_success(self):
        output = run_cmd(["echo", "hello"])
        self.assertEqual(output, "hello")

    def test_run_cmd_failure(self):
        output = run_cmd(["false"])
        self.assertEqual(output, "")

    def test_is_noise_path(self):
        self.assertTrue(
            is_noise_path("__pycache__/module.pyc", ["__pycache__", "*.pyc"])
        )
        self.assertTrue(is_noise_path("module.pyc", ["__pycache__", "*.pyc"]))
        self.assertFalse(is_noise_path("src/main.py", ["__pycache__", "*.pyc"]))

    def test_parse_git_status_line(self):
        self.assertEqual(
            parse_git_status_line(
                " M __pycache__/module.cpython-313.pyc", ["__pycache__", "*.pyc"]
            ),
            "",
        )
        self.assertEqual(
            parse_git_status_line(" M src/app.py", ["__pycache__", "*.pyc"]),
            "- `[M]` src/app.py",
        )

    def test_git_snapshot_and_commit(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = Path(tmp_dir) / "repo"
            repo_dir.mkdir()
            subprocess.run(
                ["git", "init"], cwd=repo_dir, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=repo_dir,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "test"],
                cwd=repo_dir,
                check=True,
                capture_output=True,
            )
            file_path = repo_dir / "app.py"
            file_path.write_text("print('hello')\n", encoding="utf-8")
            subprocess.run(
                ["git", "add", "app.py"], cwd=repo_dir, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", "initial"],
                cwd=repo_dir,
                check=True,
                capture_output=True,
            )
            file_path.write_text("print('modified')\n", encoding="utf-8")
            status = get_git_changes(repo_dir, ["__pycache__", "*.pyc"])
            self.assertIn("app.py", status)
            self.assertNotEqual(get_latest_commit(repo_dir), "N/A")

    def test_write_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "CONTEXT_SNAPSHOT.md"
            content = "# test snapshot"
            self.assertTrue(write_snapshot(out_file, content))
            self.assertTrue(out_file.exists())
            self.assertEqual(out_file.read_text(encoding="utf-8"), content)

    def test_calc_skeleton_preservation(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_path = os.path.join(tmp_dir, "SKILL.md")
            with open(skill_path, "w", encoding="utf-8") as f:
                f.write("## 标题\n\n1. 步骤一\n2. 步骤二\n\n段落内容\n")
            rate = calc_skeleton_preservation(skill_path)
            self.assertGreater(rate, 0.0)
            self.assertLessEqual(rate, 1.0)

    def test_verify_flow_executability(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_path = os.path.join(tmp_dir, "SKILL.md")
            with open(skill_path, "w", encoding="utf-8") as f:
                f.write("## 流程\n\n1. 第一步\n2. 第二步\n3. 第三步\n")
            self.assertTrue(verify_flow_executability(skill_path))

    def test_calc_compression_ratio(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            original = os.path.join(tmp_dir, "original.md")
            compressed = os.path.join(tmp_dir, "compressed.md")
            with open(original, "w", encoding="utf-8") as f:
                f.write("A" * 100)
            with open(compressed, "w", encoding="utf-8") as f:
                f.write("B" * 50)
            ratio = calc_compression_ratio(original, compressed)
            self.assertAlmostEqual(ratio, 0.5)


class TestLayeredSkill(unittest.TestCase):
    """测试：分层 skill 加载器"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.skill_path = os.path.join(self.tmp_dir, "test_skill.md")
        with open(self.skill_path, "w", encoding="utf-8") as f:
            f.write(SAMPLE_MD)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_build_layered_skill_returns_three_layers(self):
        """build_layered_skill 应返回 3 个层"""
        from skill_compressor import build_layered_skill

        result = build_layered_skill(self.skill_path)
        self.assertIn("core", result)
        self.assertIn("task", result)
        self.assertIn("all", result)

    def test_core_layer_smaller_than_task(self):
        """核心层 < 任务层（核心层轻量）"""
        from skill_compressor import build_layered_skill

        result = build_layered_skill(self.skill_path)
        self.assertLess(len(result["core"]), len(result["task"]))

    def test_all_layer_equals_core_plus_task(self):
        """完整层应包含核心层和任务层的内容（向后兼容）"""
        from skill_compressor import build_layered_skill

        result = build_layered_skill(self.skill_path)
        self.assertIn("core", result["all"])
        self.assertIn("task", result["all"])

    def test_layered_skill_class_load_methods(self):
        """LayeredSkill 类的加载方法"""
        from layered_skill import LayeredSkill

        ls = LayeredSkill(self.skill_path)
        self.assertIn("<layer", ls.load_core())
        self.assertIn("<layer", ls.load_task())
        self.assertIn("<skill", ls.load_all())

    def test_layer_stats_returns_estimates(self):
        """layer_stats 返回 token 估算"""
        from layered_skill import LayeredSkill

        ls = LayeredSkill(self.skill_path)
        stats = ls.layer_stats()
        self.assertIn("core", stats)
        self.assertIn("task", stats)
        self.assertIn("all", stats)
        self.assertGreater(stats["task"], 0)


class TestStateLoader(unittest.TestCase):
    """测试：按需状态加载器"""

    def test_should_load_on_continue(self):
        """用户说"继续上次"应触发加载"""
        from state_loader import StateLoader

        s = StateLoader()
        self.assertTrue(s.should_load("继续上次"))
        self.assertTrue(s.should_load("接着"))
        self.assertTrue(s.should_load("resume"))

    def test_should_not_load_on_normal(self):
        """正常请求不应加载"""
        from state_loader import StateLoader

        s = StateLoader()
        self.assertFalse(s.should_load("请压缩"))
        self.assertFalse(s.should_load("分析一下"))

    def test_fresh_start_skips_load(self):
        """重新开始应跳过加载"""
        from state_loader import StateLoader

        s = StateLoader()
        self.assertFalse(s.should_load("重新开始"))
        self.assertFalse(s.should_load("fresh start"))

    def test_load_returns_none_when_no_file(self):
        """无状态文件时返回 None"""
        from state_loader import StateLoader

        s = StateLoader(state_file="/nonexistent/path.md")
        self.assertIsNone(s.load())


if __name__ == "__main__":
    unittest.main()
