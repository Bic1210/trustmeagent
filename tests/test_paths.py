import tempfile
import unittest
from pathlib import Path

from trust_me.utils.paths import iter_files


class PathUtilsTests(unittest.TestCase):
    def test_iter_files_prunes_ignored_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app.py").write_text("print('ok')\n", encoding="utf-8")
            (root / ".venv").mkdir()
            (root / ".venv" / "ignored.py").write_text("print('skip')\n", encoding="utf-8")

            files = list(iter_files(root, ignored_parts={".venv"}, suffixes={".py"}))

        self.assertEqual(files, [root / "app.py"])


if __name__ == "__main__":
    unittest.main()
