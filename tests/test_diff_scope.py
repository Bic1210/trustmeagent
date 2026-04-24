import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from trust_me.detectors.diff_scope_check import detect_diff_scope
from tests.git_helpers import commit_files, git_ok, init_repo, write_files


class DiffScopeDetectorTests(unittest.TestCase):
    def test_detect_diff_scope_reports_missing_git_repo_for_working_tree_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = detect_diff_scope(Path(tmp_dir))

        self.assertEqual(result["detector"], "diff_scope_check")
        self.assertEqual(result["status"], "not_configured")
        self.assertIn("not a git repository", result["unverified"][0])

    def test_detect_diff_scope_reads_patch_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            patch_file = root / "sample.patch"
            patch_file.write_text(
                "\n".join(
                    [
                        "diff --git a/app.py b/app.py",
                        "--- a/app.py",
                        "+++ b/app.py",
                        "@@ -1 +1,2 @@",
                        "-print('old')",
                        "+print('new')",
                        "+print('extra')",
                    ]
                ),
                encoding="utf-8",
            )

            result = detect_diff_scope(root, patch_path="sample.patch")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["evidence"]["source"], "patch_file")
        self.assertEqual(result["evidence"]["file_count"], 1)
        self.assertEqual(result["evidence"]["hunk_count"], 1)
        self.assertEqual(result["evidence"]["added_lines"], 2)
        self.assertEqual(result["evidence"]["removed_lines"], 1)
        self.assertIn("diff scope measured: 1 files, 1 hunks, +2/-1 lines", result["verified"])

    @patch(
        "trust_me.detectors.diff_scope_check.load_patch_text",
        return_value=(
            "\n".join(
                [
                    "diff --git a/src/app.py b/src/app.py",
                    "--- a/src/app.py",
                    "+++ b/src/app.py",
                    "@@ -1 +1 @@",
                    "-x = 1",
                    "+x = 2",
                    "diff --git a/src/util.py b/src/util.py",
                    "--- a/src/util.py",
                    "+++ b/src/util.py",
                    "@@ -1 +1,2 @@",
                    "-pass",
                    "+pass",
                    "+print('ok')",
                ]
            ),
            "git_diff_range",
            "",
            [],
        ),
    )
    def test_detect_diff_scope_reads_git_diff_range(self, _mock_load_patch_text: object) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = detect_diff_scope(Path(tmp_dir), diff_range="HEAD~1")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["evidence"]["source"], "git_diff_range")
        self.assertEqual(result["evidence"]["file_count"], 2)
        self.assertEqual(result["evidence"]["hunk_count"], 2)
        self.assertEqual(result["evidence"]["file_types"], {".py": 2})

    @patch(
        "trust_me.detectors.diff_scope_check.load_patch_text",
        return_value=(
            "\n".join(
                [
                    "diff --git a/app.py b/app.py",
                    "--- a/app.py",
                    "+++ b/app.py",
                    "@@ -1 +1 @@",
                    "-before",
                    "+after",
                ]
            ),
            "working_tree",
            "",
            ["1 untracked files are present and excluded from hunk counts"],
        ),
    )
    def test_detect_diff_scope_notes_untracked_files(
        self,
        _mock_load_patch_text: object,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = detect_diff_scope(Path(tmp_dir))

        self.assertEqual(result["status"], "passed")
        self.assertIn("1 untracked files are present and excluded from hunk counts", result["verified"])
        self.assertEqual(result["evidence"]["notes"], ["1 untracked files are present and excluded from hunk counts"])

    def test_detect_diff_scope_reads_real_working_tree_from_subdirectory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            init_repo(
                root,
                {
                    "src/app.py": "print('v1')\n",
                    "src/helper.py": "HELPER = 1\n",
                },
            )
            write_files(
                root,
                {
                    "src/app.py": "print('v2')\n",
                    "src/helper.py": "HELPER = 2\n",
                    "scratch.txt": "ignore me\n",
                },
            )
            git_ok(root, "add", "src/helper.py")

            result = detect_diff_scope(root / "src")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["evidence"]["source"], "working_tree")
        self.assertEqual(result["evidence"]["changed_files"], ["src/app.py", "src/helper.py"])
        self.assertEqual(result["evidence"]["file_count"], 2)
        self.assertIn("1 untracked files are present and excluded from hunk counts", result["evidence"]["notes"])

    def test_detect_diff_scope_reads_real_git_diff_range(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            init_repo(
                root,
                {
                    "src/app.py": "print('v1')\n",
                    "web/app.ts": "export const value = 1;\n",
                },
            )
            commit_files(
                root,
                {
                    "src/app.py": "print('v2')\n",
                    "web/app.ts": "export const value = 2;\n",
                },
                "update app and web",
            )

            result = detect_diff_scope(root, diff_range="HEAD~1")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["evidence"]["source"], "git_diff_range")
        self.assertEqual(result["evidence"]["changed_files"], ["src/app.py", "web/app.ts"])
        self.assertEqual(result["evidence"]["file_count"], 2)
        self.assertEqual(result["evidence"]["file_types"], {".py": 1, ".ts": 1})


if __name__ == "__main__":
    unittest.main()
