import subprocess
import tempfile
import unittest
from pathlib import Path
from compress import run_cmd, is_noise_path, parse_git_status_line, get_git_changes, get_latest_commit, write_snapshot


class TestCompress(unittest.TestCase):

    def test_run_cmd_success(self):
        output = run_cmd(["echo", "hello"])
        self.assertEqual(output, "hello")

    def test_run_cmd_failure(self):
        output = run_cmd(["false"])
        self.assertEqual(output, "")

    def test_is_noise_path(self):
        self.assertTrue(is_noise_path("__pycache__/module.pyc", ["__pycache__", "*.pyc"]))
        self.assertTrue(is_noise_path("module.pyc", ["__pycache__", "*.pyc"]))
        self.assertFalse(is_noise_path("src/main.py", ["__pycache__", "*.pyc"]))

    def test_parse_git_status_line_excludes_noise(self):
        self.assertEqual(parse_git_status_line(" M __pycache__/module.cpython-313.pyc", ["__pycache__", "*.pyc"]), "")
        self.assertEqual(parse_git_status_line(" M src/app.py", ["__pycache__", "*.pyc"]), "- `[M]` src/app.py")

    def test_git_snapshot_and_commit(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = Path(tmp_dir) / "repo"
            repo_dir.mkdir()
            subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
            file_path = repo_dir / "app.py"
            file_path.write_text("print('hello')\n", encoding="utf-8")
            subprocess.run(["git", "add", "app.py"], cwd=repo_dir, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, check=True, capture_output=True)

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


if __name__ == "__main__":
    unittest.main()
