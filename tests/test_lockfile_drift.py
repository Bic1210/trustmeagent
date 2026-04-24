import tempfile
import unittest
from pathlib import Path

from trust_me.detectors.lockfile_drift_check import detect_lockfile_drift


class LockfileDriftDetectorTests(unittest.TestCase):
    def test_detect_lockfile_drift_reports_missing_git_repo_for_working_tree_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = detect_lockfile_drift(Path(tmp_dir))

        self.assertEqual(result["detector"], "lockfile_drift_check")
        self.assertEqual(result["status"], "not_configured")
        self.assertIn("not a git repository", result["unverified"][0])

    def test_detect_lockfile_drift_passes_when_manifest_and_lockfile_change_together(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            patch_file = root / "sample.patch"
            patch_file.write_text(
                "\n".join(
                    [
                        "diff --git a/package.json b/package.json",
                        "--- a/package.json",
                        "+++ b/package.json",
                        "@@ -1 +1 @@",
                        '-{"dependencies":{"vite":"5.0.0"}}',
                        '+{"dependencies":{"vite":"5.1.0"}}',
                        "diff --git a/package-lock.json b/package-lock.json",
                        "--- a/package-lock.json",
                        "+++ b/package-lock.json",
                        "@@ -1 +1 @@",
                        '-{"lockfileVersion":3,"packages":{"":{"dependencies":{"vite":"5.0.0"}}}}',
                        '+{"lockfileVersion":3,"packages":{"":{"dependencies":{"vite":"5.1.0"}}}}',
                    ]
                ),
                encoding="utf-8",
            )

            result = detect_lockfile_drift(root, patch_path="sample.patch")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["evidence"]["source"], "patch_file")
        self.assertIn("package.json changed alongside package-lock.json", result["verified"])

    def test_detect_lockfile_drift_flags_existing_lockfile_that_was_not_updated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "Cargo.lock").write_text("# lock\n", encoding="utf-8")
            patch_file = root / "sample.patch"
            patch_file.write_text(
                "\n".join(
                    [
                        "diff --git a/Cargo.toml b/Cargo.toml",
                        "--- a/Cargo.toml",
                        "+++ b/Cargo.toml",
                        "@@ -1 +1 @@",
                        '-version = "0.1.0"',
                        '+version = "0.2.0"',
                    ]
                ),
                encoding="utf-8",
            )

            result = detect_lockfile_drift(root, patch_path="sample.patch")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["suspicious"], ["Cargo.toml changed without updating Cargo.lock"])
        self.assertIn("verify dependency lockfiles for Cargo.toml", result["action_items"])

    def test_detect_lockfile_drift_reports_manifest_without_known_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            patch_file = root / "sample.patch"
            patch_file.write_text(
                "\n".join(
                    [
                        "diff --git a/pyproject.toml b/pyproject.toml",
                        "--- a/pyproject.toml",
                        "+++ b/pyproject.toml",
                        "@@ -1 +1 @@",
                        '-requires-python = ">=3.10"',
                        '+requires-python = ">=3.11"',
                    ]
                ),
                encoding="utf-8",
            )

            result = detect_lockfile_drift(root, patch_path="sample.patch")

        self.assertEqual(result["status"], "partial")
        self.assertEqual(
            result["unverified"],
            ["pyproject.toml changed but no known lockfile was found for python dependencies"],
        )
        self.assertIn("add or verify lockfiles for pyproject.toml", result["action_items"])


if __name__ == "__main__":
    unittest.main()
