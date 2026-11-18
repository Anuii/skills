#!/usr/bin/env python3
"""Run a bundled ub-mode quality tool in an isolated environment."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TOOLS = ("crapper", "dryer", "mutator")


def tool_python(tool_dir: Path) -> Path:
    scripts_dir = "Scripts" if sys.platform == "win32" else "bin"
    executable = "python.exe" if sys.platform == "win32" else "python"
    return tool_dir / ".venv" / scripts_dir / executable


def ensure_installed(tool_dir: Path) -> Path:
    python = tool_python(tool_dir)
    if not python.is_file():
        subprocess.run([sys.executable, "-m", "venv", str(tool_dir / ".venv")], check=True)
        subprocess.run(
            [str(python), "-m", "pip", "install", "-e", str(tool_dir)],
            check=True,
        )
    return python


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool", choices=TOOLS)
    parser.add_argument("args", nargs=argparse.REMAINDER)
    options = parser.parse_args()
    if sys.version_info < (3, 11):
        parser.error("ub-mode tools require Python 3.11 or newer")
    tool_dir = Path(__file__).resolve().parent.parent / "tools" / options.tool
    python = ensure_installed(tool_dir)
    completed = subprocess.run([str(python), "-m", options.tool, *options.args])
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
