import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from trust_me.detectors.import_check import detect_missing_import_risk
from trust_me.detectors.lint_check import detect_lint_status
from trust_me.detectors.test_check import detect_test_status
from trust_me.detectors.type_check import detect_type_status


class LintDetectorTests(unittest.TestCase):
    def test_detect_lint_status_skips_when_no_supported_source_files_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = detect_lint_status(Path(tmp_dir))

        self.assertEqual(result["detector"], "lint_check")
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["evidence"]["reason"], "no_supported_source_files")
        self.assertEqual(result["verified"], ["no supported source files found; lint check skipped"])
        self.assertEqual(result["unverified"], [])
        self.assertEqual(result["suspicious"], [])

    @patch("trust_me.detectors.lint_check.importlib.util.find_spec", return_value=None)
    @patch("trust_me.detectors.lint_check.shutil.which", return_value=None)
    def test_detect_lint_status_reports_missing_ruff(self, _mock_which: MagicMock, _mock_find_spec: MagicMock) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app.py").write_text("print('hello')\n", encoding="utf-8")

            result = detect_lint_status(root)

        self.assertEqual(result["detector"], "lint_check")
        self.assertEqual(result["status"], "not_configured")
        self.assertEqual(result["evidence"]["language_file_counts"]["python"], 1)
        self.assertEqual(result["verified"], [])
        self.assertEqual(result["suspicious"], [])
        self.assertEqual(result["unverified"], ["ruff is not installed; Python lint status unavailable"])
        self.assertIn("install ruff", result["action_items"][0])

    @patch("trust_me.detectors.lint_check.run_command", return_value=(0, "", ""))
    @patch("trust_me.detectors.lint_check.importlib.util.find_spec", return_value=object())
    def test_detect_lint_status_reports_success(self, _mock_find_spec: MagicMock, mock_run_command: MagicMock) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app.py").write_text("print('hello')\n", encoding="utf-8")
            (root / "worker.py").write_text("print('world')\n", encoding="utf-8")

            result = detect_lint_status(root)

        self.assertEqual(result["detector"], "lint_check")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["evidence"]["checks"][0]["exit_code"], 0)
        self.assertEqual(result["evidence"]["checks"][0]["file_count"], 2)
        self.assertEqual(result["verified"], ["ruff passed on 2 Python files"])
        self.assertEqual(result["unverified"], [])
        self.assertEqual(result["suspicious"], [])
        mock_run_command.assert_called_once()
        command = mock_run_command.call_args.args[0]
        self.assertNotIn(str(root), command)
        self.assertIn(str(root / "app.py"), command)
        self.assertIn(str(root / "worker.py"), command)

    @patch("trust_me.detectors.lint_check.run_command", return_value=(0, "", ""))
    @patch("trust_me.detectors.lint_check.importlib.util.find_spec", return_value=object())
    def test_detect_lint_status_limits_python_targets_in_changed_scope(
        self,
        _mock_find_spec: MagicMock,
        mock_run_command: MagicMock,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app.py").write_text("print('hello')\n", encoding="utf-8")
            (root / "worker.py").write_text("print('world')\n", encoding="utf-8")

            result = detect_lint_status(root, scope="changed", changed_files=["worker.py"])

        self.assertEqual(result["status"], "passed")
        command = mock_run_command.call_args.args[0]
        self.assertIn(str(root / "worker.py"), command)
        self.assertNotIn(str(root / "app.py"), command)

    @patch(
        "trust_me.detectors.lint_check.run_command",
        return_value=(1, "app.py:1:1: F401 imported but unused\n", ""),
    )
    @patch("trust_me.detectors.lint_check.importlib.util.find_spec", return_value=object())
    def test_detect_lint_status_reports_lint_findings(self, _mock_find_spec: MagicMock, _mock_run_command: MagicMock) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app.py").write_text("import os\n", encoding="utf-8")

            result = detect_lint_status(root)

        self.assertEqual(result["detector"], "lint_check")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["evidence"]["checks"][0]["exit_code"], 1)
        self.assertEqual(result["verified"], [])
        self.assertEqual(result["unverified"], [])
        self.assertEqual(result["suspicious"], ["ruff found lint issues across 1 Python files"])
        self.assertIn("app.py:1:1", result["action_items"][0])

    @patch("trust_me.detectors.lint_check.run_command", return_value=(0, "", ""))
    @patch("trust_me.detectors.lint_check.shutil.which", side_effect=lambda name: "/usr/bin/eslint" if name == "eslint" else None)
    @patch("trust_me.detectors.lint_check.importlib.util.find_spec", return_value=None)
    def test_detect_lint_status_reports_javascript_success(
        self,
        _mock_find_spec: MagicMock,
        _mock_which: MagicMock,
        mock_run_command: MagicMock,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src = root / "src"
            src.mkdir()
            (src / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
            (src / "helper.js").write_text("console.log('ok');\n", encoding="utf-8")

            result = detect_lint_status(root)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["verified"], ["eslint passed on 2 JavaScript/TypeScript files"])
        self.assertEqual(result["evidence"]["checks"][0]["tool"], "eslint")
        mock_run_command.assert_called_once()

    @patch("trust_me.detectors.lint_check.run_command", return_value=(0, "", ""))
    @patch("trust_me.detectors.lint_check.shutil.which", side_effect=lambda name: "/usr/bin/eslint" if name == "eslint" else None)
    @patch("trust_me.detectors.lint_check.importlib.util.find_spec", return_value=None)
    def test_detect_lint_status_reports_partial_when_python_and_javascript_have_mixed_configuration(
        self,
        _mock_find_spec: MagicMock,
        _mock_which: MagicMock,
        mock_run_command: MagicMock,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app.py").write_text("print('hello')\n", encoding="utf-8")
            web = root / "web"
            web.mkdir()
            (web / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

            result = detect_lint_status(root)

        self.assertEqual(result["status"], "partial")
        self.assertIn("ruff is not installed; Python lint status unavailable", result["unverified"])
        self.assertIn("eslint passed on 1 JavaScript/TypeScript files", result["verified"])
        self.assertEqual(len(result["evidence"]["checks"]), 2)
        self.assertEqual(mock_run_command.call_count, 1)


class TypeDetectorTests(unittest.TestCase):
    def test_detect_type_status_skips_when_no_supported_source_files_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = detect_type_status(Path(tmp_dir))

        self.assertEqual(result["detector"], "type_check")
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["evidence"]["reason"], "no_supported_source_files")
        self.assertEqual(result["verified"], ["no supported source files found; type check skipped"])
        self.assertEqual(result["unverified"], [])
        self.assertEqual(result["suspicious"], [])

    @patch("trust_me.detectors.type_check.importlib.util.find_spec", return_value=None)
    @patch("trust_me.detectors.type_check.shutil.which", return_value=None)
    def test_detect_type_status_reports_missing_type_checker(
        self,
        _mock_which: MagicMock,
        _mock_find_spec: MagicMock,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app.py").write_text("print('hello')\n", encoding="utf-8")

            result = detect_type_status(root)

        self.assertEqual(result["detector"], "type_check")
        self.assertEqual(result["status"], "not_configured")
        self.assertEqual(result["evidence"]["language_file_counts"]["python"], 1)
        self.assertEqual(result["verified"], [])
        self.assertEqual(result["suspicious"], [])
        self.assertEqual(result["unverified"], ["no mypy or pyright installation found; Python type status unavailable"])
        self.assertIn("install mypy or pyright", result["action_items"][0])

    @patch("trust_me.detectors.type_check.run_command", return_value=(0, "", ""))
    @patch("trust_me.detectors.type_check.importlib.util.find_spec", return_value=object())
    def test_detect_type_status_reports_success(self, _mock_find_spec: MagicMock, mock_run_command: MagicMock) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app.py").write_text("print('hello')\n", encoding="utf-8")
            (root / "worker.py").write_text("print('world')\n", encoding="utf-8")

            result = detect_type_status(root)

        self.assertEqual(result["detector"], "type_check")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["evidence"]["checks"][0]["tool"], "mypy")
        self.assertEqual(result["evidence"]["checks"][0]["exit_code"], 0)
        self.assertEqual(result["evidence"]["checks"][0]["file_count"], 2)
        self.assertEqual(result["verified"], ["mypy passed on 2 Python files"])
        self.assertEqual(result["unverified"], [])
        self.assertEqual(result["suspicious"], [])
        mock_run_command.assert_called_once()
        command = mock_run_command.call_args.args[0]
        self.assertNotIn(str(root), command)
        self.assertIn(str(root / "app.py"), command)
        self.assertIn(str(root / "worker.py"), command)

    @patch("trust_me.detectors.type_check.run_command", return_value=(0, "", ""))
    @patch("trust_me.detectors.type_check.importlib.util.find_spec", return_value=object())
    def test_detect_type_status_limits_python_targets_in_changed_scope(
        self,
        _mock_find_spec: MagicMock,
        mock_run_command: MagicMock,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app.py").write_text("print('hello')\n", encoding="utf-8")
            (root / "worker.py").write_text("print('world')\n", encoding="utf-8")

            result = detect_type_status(root, scope="changed", changed_files=["worker.py"])

        self.assertEqual(result["status"], "passed")
        command = mock_run_command.call_args.args[0]
        self.assertIn(str(root / "worker.py"), command)
        self.assertNotIn(str(root / "app.py"), command)

    @patch(
        "trust_me.detectors.type_check.run_command",
        return_value=(1, "app.py:1: error: Name 'x' is not defined\n", ""),
    )
    @patch("trust_me.detectors.type_check.importlib.util.find_spec", return_value=object())
    def test_detect_type_status_reports_type_findings(
        self,
        _mock_find_spec: MagicMock,
        _mock_run_command: MagicMock,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app.py").write_text("print(x)\n", encoding="utf-8")

            result = detect_type_status(root)

        self.assertEqual(result["detector"], "type_check")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["evidence"]["checks"][0]["tool"], "mypy")
        self.assertEqual(result["evidence"]["checks"][0]["exit_code"], 1)
        self.assertEqual(result["verified"], [])
        self.assertEqual(result["unverified"], [])
        self.assertEqual(result["suspicious"], ["mypy found type issues across 1 Python files"])
        self.assertIn("app.py:1:", result["action_items"][0])

    @patch("trust_me.detectors.type_check.run_command", return_value=(0, "", ""))
    @patch("trust_me.detectors.type_check.shutil.which", side_effect=lambda name: "/usr/bin/tsc" if name == "tsc" else None)
    @patch("trust_me.detectors.type_check.importlib.util.find_spec", return_value=None)
    def test_detect_type_status_reports_typescript_success(
        self,
        _mock_find_spec: MagicMock,
        _mock_which: MagicMock,
        mock_run_command: MagicMock,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "tsconfig.json").write_text("{}", encoding="utf-8")
            src = root / "src"
            src.mkdir()
            (src / "app.ts").write_text("export const value: number = 1;\n", encoding="utf-8")

            result = detect_type_status(root)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["verified"], ["tsc passed on 1 TypeScript files"])
        self.assertEqual(result["evidence"]["checks"][0]["tool"], "tsc")
        mock_run_command.assert_called_once()

    @patch("trust_me.detectors.type_check.importlib.util.find_spec", return_value=None)
    @patch("trust_me.detectors.type_check.shutil.which", return_value=None)
    def test_detect_type_status_reports_missing_tsconfig_for_typescript_sources(
        self,
        _mock_which: MagicMock,
        _mock_find_spec: MagicMock,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src = root / "src"
            src.mkdir()
            (src / "app.ts").write_text("export const value: number = 1;\n", encoding="utf-8")

            result = detect_type_status(root)

        self.assertEqual(result["status"], "not_configured")
        self.assertEqual(result["unverified"], ["tsconfig.json is missing; TypeScript type status unavailable"])
        self.assertIn("add tsconfig.json", result["action_items"][0])


class TestDetectorTests(unittest.TestCase):
    def test_detect_test_status_skips_when_no_tests_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = detect_test_status(Path(tmp_dir))

        self.assertEqual(result["detector"], "test_check")
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["evidence"]["reason"], "no_supported_test_files")
        self.assertEqual(result["verified"], [])
        self.assertEqual(result["unverified"], ["no supported tests discovered; test execution skipped"])
        self.assertEqual(result["suspicious"], [])

    @patch("trust_me.detectors.test_check.importlib.util.find_spec", return_value=None)
    @patch("trust_me.detectors.test_check.shutil.which", return_value=None)
    @patch("trust_me.detectors.test_check.run_command", return_value=(0, "", "Ran 3 tests in 0.01s\nOK\n"))
    def test_detect_test_status_runs_unittest_when_pytest_is_unavailable(
        self,
        mock_run_command: MagicMock,
        _mock_which: MagicMock,
        _mock_find_spec: MagicMock,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_sample.py").write_text("def test_example(): pass\n", encoding="utf-8")

            result = detect_test_status(root)

        self.assertEqual(result["detector"], "test_check")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["evidence"]["checks"][0]["runner"], "unittest")
        self.assertEqual(result["evidence"]["checks"][0]["test_count"], 3)
        self.assertEqual(result["verified"], ["3 tests passed via unittest for Python"])
        self.assertEqual(result["unverified"], [])
        self.assertEqual(result["suspicious"], [])
        mock_run_command.assert_called_once()

    @patch("trust_me.detectors.test_check.importlib.util.find_spec", return_value=None)
    @patch("trust_me.detectors.test_check.shutil.which", return_value=None)
    @patch("trust_me.detectors.test_check.run_command", return_value=(0, "", "Ran 1 tests in 0.01s\nOK\n"))
    def test_detect_test_status_runs_changed_python_test_modules_in_changed_scope(
        self,
        mock_run_command: MagicMock,
        _mock_which: MagicMock,
        _mock_find_spec: MagicMock,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_alpha.py").write_text("def test_alpha(): pass\n", encoding="utf-8")
            (tests_dir / "test_beta.py").write_text("def test_beta(): pass\n", encoding="utf-8")

            result = detect_test_status(root, scope="changed", changed_files=["tests/test_beta.py"])

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["evidence"]["scope"], "changed")
        self.assertEqual(
            mock_run_command.call_args.args[0],
            [sys.executable, "-m", "unittest", "-q", "-b", "tests.test_beta"],
        )

    @patch("trust_me.detectors.test_check.importlib.util.find_spec", return_value=None)
    @patch("trust_me.detectors.test_check.shutil.which", return_value=None)
    def test_detect_test_status_marks_python_unverified_when_no_changed_tests_exist(
        self,
        _mock_which: MagicMock,
        _mock_find_spec: MagicMock,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_sample.py").write_text("def test_example(): pass\n", encoding="utf-8")
            (root / "app.py").write_text("print('hello')\n", encoding="utf-8")

            result = detect_test_status(root, scope="changed", changed_files=["app.py"])

        self.assertEqual(result["status"], "partial")
        self.assertIn("no changed Python test files detected; Python test execution skipped in changed scope", result["unverified"])

    @patch(
        "trust_me.detectors.test_check.run_command",
        return_value=(1, "FAILED (failures=1)\n", "Ran 2 tests in 0.02s\n"),
    )
    @patch("trust_me.detectors.test_check.importlib.util.find_spec", return_value=object())
    def test_detect_test_status_reports_test_failures(
        self,
        _mock_find_spec: MagicMock,
        _mock_run_command: MagicMock,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_sample.py").write_text("def test_example(): pass\n", encoding="utf-8")

            result = detect_test_status(root)

        self.assertEqual(result["detector"], "test_check")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["evidence"]["checks"][0]["runner"], "pytest")
        self.assertEqual(result["evidence"]["checks"][0]["test_count"], 2)
        self.assertEqual(result["verified"], [])
        self.assertEqual(result["unverified"], [])
        self.assertEqual(result["suspicious"], ["2 tests failed or did not pass via pytest for Python"])
        self.assertIn("FAILED", result["action_items"][0])

    @patch("trust_me.detectors.test_check.run_command", return_value=(0, "Tests: 4 passed, 4 total\n", ""))
    @patch("trust_me.detectors.test_check.shutil.which", side_effect=lambda name: "/usr/bin/jest" if name == "jest" else None)
    @patch("trust_me.detectors.test_check.importlib.util.find_spec", return_value=None)
    def test_detect_test_status_reports_javascript_success(
        self,
        _mock_find_spec: MagicMock,
        _mock_which: MagicMock,
        mock_run_command: MagicMock,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src = root / "src"
            src.mkdir()
            (src / "app.test.ts").write_text("it('works', () => expect(1).toBe(1));\n", encoding="utf-8")

            result = detect_test_status(root)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["verified"], ["4 tests passed via jest for JavaScript/TypeScript"])
        self.assertEqual(result["evidence"]["checks"][0]["runner"], "jest")
        mock_run_command.assert_called_once()

    @patch("trust_me.detectors.test_check.importlib.util.find_spec", return_value=None)
    @patch("trust_me.detectors.test_check.shutil.which", return_value=None)
    def test_detect_test_status_reports_missing_javascript_runner(
        self,
        _mock_which: MagicMock,
        _mock_find_spec: MagicMock,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src = root / "src"
            src.mkdir()
            (src / "app.test.ts").write_text("it('works', () => expect(1).toBe(1));\n", encoding="utf-8")

            result = detect_test_status(root)

        self.assertEqual(result["status"], "not_configured")
        self.assertEqual(
            result["unverified"],
            ["no vitest, jest, or package test script found; JavaScript/TypeScript test status unavailable"],
        )
        self.assertIn("install vitest or jest", result["action_items"][0])

    @patch("trust_me.detectors.test_check.run_command", return_value=(0, "test result: ok. 3 passed; 0 failed;\n", ""))
    @patch("trust_me.detectors.test_check.shutil.which", side_effect=lambda name: "/usr/bin/cargo" if name == "cargo" else None)
    @patch("trust_me.detectors.test_check.importlib.util.find_spec", return_value=None)
    def test_detect_test_status_reports_rust_success(
        self,
        _mock_find_spec: MagicMock,
        _mock_which: MagicMock,
        mock_run_command: MagicMock,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "Cargo.toml").write_text("[package]\nname='demo'\nversion='0.1.0'\n", encoding="utf-8")
            src = root / "src"
            src.mkdir()
            (src / "lib.rs").write_text("pub fn add(a: i32, b: i32) -> i32 { a + b }\n", encoding="utf-8")

            result = detect_test_status(root)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["verified"], ["3 tests passed via cargo test for Rust"])
        self.assertEqual(result["evidence"]["checks"][0]["runner"], "cargo test")
        mock_run_command.assert_called_once()

    @patch("trust_me.detectors.test_check.run_command", return_value=(0, "ok   demo/pkg 0.012s\n", ""))
    @patch("trust_me.detectors.test_check.shutil.which", side_effect=lambda name: "/usr/bin/go" if name == "go" else None)
    @patch("trust_me.detectors.test_check.importlib.util.find_spec", return_value=None)
    def test_detect_test_status_reports_go_success(
        self,
        _mock_find_spec: MagicMock,
        _mock_which: MagicMock,
        mock_run_command: MagicMock,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "go.mod").write_text("module demo\n\ngo 1.22\n", encoding="utf-8")
            pkg = root / "pkg"
            pkg.mkdir()
            (pkg / "sum.go").write_text("package pkg\nfunc Sum(a int, b int) int { return a + b }\n", encoding="utf-8")
            (pkg / "sum_test.go").write_text("package pkg\nimport \"testing\"\nfunc TestSum(t *testing.T) {}\n", encoding="utf-8")

            result = detect_test_status(root)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["verified"], ["tests passed via go test for Go"])
        self.assertEqual(result["evidence"]["checks"][0]["runner"], "go test")
        self.assertEqual(result["evidence"]["checks"][0]["env_keys"], ["GOCACHE", "GOPATH"])
        mock_run_command.assert_called_once()


class ImportDetectorTests(unittest.TestCase):
    def test_detect_missing_import_risk_skips_when_no_supported_source_files_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = detect_missing_import_risk(Path(tmp_dir))

        self.assertEqual(result["detector"], "import_check")
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["evidence"]["reason"], "no_supported_source_files")
        self.assertEqual(result["verified"], ["no supported source files found; import scan skipped"])
        self.assertEqual(result["suspicious"], [])

    def test_detect_missing_import_risk_passes_for_local_and_stdlib_imports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            pkg = root / "pkg"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("", encoding="utf-8")
            (pkg / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
            (pkg / "module.py").write_text(
                "import pathlib\nfrom .helper import VALUE\n",
                encoding="utf-8",
            )

            result = detect_missing_import_risk(root)

        self.assertEqual(result["detector"], "import_check")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["evidence"]["missing_count"], 0)
        self.assertEqual(result["unverified"], [])
        self.assertEqual(result["suspicious"], [])
        self.assertEqual(result["verified"], ["no unresolved Python imports detected across 3 files"])

    def test_detect_missing_import_risk_passes_for_js_and_ts_imports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "package.json").write_text(
                '{"dependencies": {"react": "^18.0.0"}}',
                encoding="utf-8",
            )
            src = root / "src"
            src.mkdir()
            (src / "helper.ts").write_text("export const value = 1;\n", encoding="utf-8")
            (src / "app.ts").write_text(
                'import React from "react";\nimport { value } from "./helper";\nconsole.log(React, value);\n',
                encoding="utf-8",
            )

            result = detect_missing_import_risk(root)

        self.assertEqual(result["detector"], "import_check")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["evidence"]["missing_count"], 0)
        self.assertEqual(result["unverified"], [])
        self.assertIn("no unresolved JavaScript/TypeScript imports detected across 2 files", result["verified"])

    def test_detect_missing_import_risk_reports_missing_imports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app.py").write_text("import not_a_real_package\n", encoding="utf-8")

            result = detect_missing_import_risk(root)

        self.assertEqual(result["detector"], "import_check")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["evidence"]["missing_count"], 1)
        self.assertEqual(result["verified"], [])
        self.assertEqual(result["unverified"], [])
        self.assertEqual(result["suspicious"], ["found 1 unresolved import references across 1 Python files"])
        self.assertIn("not_a_real_package", result["action_items"][0])

    def test_detect_missing_import_risk_reports_missing_js_relative_imports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src = root / "src"
            src.mkdir()
            (src / "app.js").write_text('import "./missing";\n', encoding="utf-8")

            result = detect_missing_import_risk(root)

        self.assertEqual(result["detector"], "import_check")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["evidence"]["missing_count"], 1)
        self.assertIn("./missing", result["action_items"][0])

    def test_detect_missing_import_risk_marks_go_without_go_mod_not_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "main.go").write_text('package main\nimport "fmt"\n', encoding="utf-8")

            result = detect_missing_import_risk(root)

        self.assertEqual(result["detector"], "import_check")
        self.assertEqual(result["status"], "not_configured")
        self.assertEqual(result["evidence"]["language_file_counts"]["go"], 1)
        self.assertEqual(
            result["evidence"]["checks"],
            [{"tool": "go", "reason": "missing_go_mod", "file_count": 1}],
        )
        self.assertEqual(result["verified"], [])
        self.assertEqual(result["suspicious"], [])
        self.assertEqual(result["unverified"], ["go.mod is missing; Go import status unavailable"])
        self.assertEqual(result["action_items"], ["add go.mod so Go import resolution can be verified"])

    def test_detect_missing_import_risk_limits_python_scan_in_changed_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app.py").write_text("import os\n", encoding="utf-8")
            (root / "worker.py").write_text("import missing_dep\n", encoding="utf-8")

            result = detect_missing_import_risk(root, scope="changed", changed_files=["app.py"])

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["evidence"]["scope"], "changed")
        self.assertEqual(result["evidence"]["language_file_counts"]["python"], 1)
        self.assertEqual(result["verified"], ["no unresolved Python imports detected across 1 files"])

    def test_detect_missing_import_risk_skips_when_no_changed_supported_files_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app.py").write_text("import os\n", encoding="utf-8")
            (root / "README.md").write_text("docs\n", encoding="utf-8")

            result = detect_missing_import_risk(root, scope="changed", changed_files=["README.md"])

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["evidence"]["reason"], "no_changed_supported_source_files")


if __name__ == "__main__":
    unittest.main()
