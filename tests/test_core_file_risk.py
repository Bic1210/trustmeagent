import tempfile
import unittest
from pathlib import Path

from trust_me.detectors.core_file_risk import detect_core_file_risk
from tests.git_helpers import commit_files, init_repo, write_files


class CoreFileRiskDetectorTests(unittest.TestCase):
    def test_detect_core_file_risk_reports_missing_git_repo_for_working_tree_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = detect_core_file_risk(Path(tmp_dir))

        self.assertEqual(result["detector"], "core_file_risk")
        self.assertEqual(result["status"], "not_configured")
        self.assertIn("not a git repository", result["unverified"][0])

    def test_detect_core_file_risk_passes_when_no_files_changed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            patch_file = root / "empty.patch"
            patch_file.write_text("", encoding="utf-8")

            result = detect_core_file_risk(root, patch_path="empty.patch")

        self.assertEqual(result["status"], "passed")
        self.assertIn("no changed tracked files detected", result["verified"][0])

    def test_detect_core_file_risk_flags_risky_files_without_test_updates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            patch_file = root / "sample.patch"
            patch_file.write_text(
                "\n".join(
                    [
                        "diff --git a/trust_me/cli.py b/trust_me/cli.py",
                        "--- a/trust_me/cli.py",
                        "+++ b/trust_me/cli.py",
                        "@@ -1 +1 @@",
                        "-old",
                        "+new",
                    ]
                ),
                encoding="utf-8",
            )

            result = detect_core_file_risk(root, patch_path="sample.patch")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["evidence"]["risky_files"], ["trust_me/cli.py"])
        self.assertEqual(result["suspicious"], ["1 risky files changed without any nearby test file updates"])

    def test_detect_core_file_risk_passes_when_risky_files_change_with_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            patch_file = root / "sample.patch"
            patch_file.write_text(
                "\n".join(
                    [
                        "diff --git a/trust_me/parser.py b/trust_me/parser.py",
                        "--- a/trust_me/parser.py",
                        "+++ b/trust_me/parser.py",
                        "@@ -1 +1 @@",
                        "-old",
                        "+new",
                        "diff --git a/tests/test_parser.py b/tests/test_parser.py",
                        "--- a/tests/test_parser.py",
                        "+++ b/tests/test_parser.py",
                        "@@ -1 +1 @@",
                        "-old_test",
                        "+new_test",
                    ]
                ),
                encoding="utf-8",
            )

            result = detect_core_file_risk(root, patch_path="sample.patch")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["evidence"]["changed_test_files"], ["tests/test_parser.py"])
        self.assertIn("1 risky files changed alongside 1 test files", result["verified"])

    def test_detect_core_file_risk_reports_real_working_tree_risk_without_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            init_repo(
                root,
                {
                    "trust_me/cli.py": "print('v1')\n",
                    "tests/test_cli.py": "def test_cli():\n    assert True\n",
                },
            )
            write_files(root, {"trust_me/cli.py": "print('v2')\n"})

            result = detect_core_file_risk(root)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["evidence"]["source"], "working_tree")
        self.assertEqual(result["evidence"]["risky_files"], ["trust_me/cli.py"])
        self.assertEqual(result["evidence"]["changed_test_files"], [])
        self.assertIn("without any nearby test file updates", result["suspicious"][0])

    def test_detect_core_file_risk_passes_for_real_git_diff_range_with_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            init_repo(
                root,
                {
                    "trust_me/parser.py": "VALUE = 1\n",
                    "tests/test_parser.py": "def test_parser():\n    assert True\n",
                },
            )
            commit_files(
                root,
                {
                    "trust_me/parser.py": "VALUE = 2\n",
                    "tests/test_parser.py": "def test_parser():\n    assert 2 == 2\n",
                },
                "update parser and tests",
            )

            result = detect_core_file_risk(root, diff_range="HEAD~1")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["evidence"]["source"], "git_diff_range")
        self.assertEqual(result["evidence"]["risky_files"], ["trust_me/parser.py"])
        self.assertEqual(result["evidence"]["changed_test_files"], ["tests/test_parser.py"])
        self.assertIn("1 risky files changed alongside 1 test files", result["verified"])


if __name__ == "__main__":
    unittest.main()
