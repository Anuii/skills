from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ub_tool.py"
SPEC = importlib.util.spec_from_file_location("ub_tool", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
ub_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ub_tool)


class LauncherTests(unittest.TestCase):
    def test_existing_environment_is_reused(self):
        with patch.object(Path, "is_file", return_value=True), patch("subprocess.run") as run:
            python = ub_tool.ensure_installed(Path("tool"))
        self.assertEqual(python, ub_tool.tool_python(Path("tool")))
        run.assert_not_called()

    def test_missing_environment_is_created_before_install(self):
        with patch.object(Path, "is_file", return_value=False), patch("subprocess.run") as run:
            ub_tool.ensure_installed(Path("tool"))
        self.assertEqual(run.call_count, 2)
        create = run.call_args_list[0].args[0]
        install = run.call_args_list[1].args[0]
        self.assertEqual(create[1:3], ["-m", "venv"])
        self.assertEqual(install[1:4], ["-m", "pip", "install"])

    def test_tool_arguments_and_exit_code_are_preserved(self):
        args = ["ub_tool.py", "crapper", "--changed", "src"]
        completed = subprocess.CompletedProcess([], 2)
        with patch.object(sys, "argv", args), patch.object(
            ub_tool, "ensure_installed", return_value=Path("python")
        ), patch("subprocess.run", return_value=completed) as run:
            result = ub_tool.main()
        self.assertEqual(result, 2)
        self.assertEqual(run.call_args.args[0][1:], ["-m", "crapper", "--changed", "src"])


if __name__ == "__main__":
    unittest.main()
