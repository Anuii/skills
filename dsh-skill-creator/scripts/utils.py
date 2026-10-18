# Modified for DeepSeek Harness. Upstream: Anthropic's skill-creator (Apache-2.0, see LICENSE.txt).
"""Shared utilities for dsh-skill-creator scripts."""

import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path



def parse_skill_md(skill_path: Path) -> tuple[str, str, str]:
    """Parse a SKILL.md file, returning (name, description, full_content)."""
    content = (skill_path / "SKILL.md").read_text(encoding="utf-8")
    lines = content.split("\n")

    if lines[0].strip() != "---":
        raise ValueError("SKILL.md missing frontmatter (no opening ---)")

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        raise ValueError("SKILL.md missing frontmatter (no closing ---)")

    name = ""
    description = ""
    frontmatter_lines = lines[1:end_idx]
    i = 0
    while i < len(frontmatter_lines):
        line = frontmatter_lines[i]
        if line.startswith("name:"):
            name = line[len("name:"):].strip().strip('"').strip("'")
        elif line.startswith("description:"):
            value = line[len("description:"):].strip()
            # Handle YAML multiline indicators (>, |, >-, |-)
            if value in (">", "|", ">-", "|-"):
                continuation_lines: list[str] = []
                i += 1
                while i < len(frontmatter_lines) and (frontmatter_lines[i].startswith("  ") or frontmatter_lines[i].startswith("\t")):
                    continuation_lines.append(frontmatter_lines[i].strip())
                    i += 1
                description = " ".join(continuation_lines)
                continue
            else:
                description = value.strip('"').strip("'")
        i += 1

    return name, description, content


def resolve_dsh() -> list[str]:
    """Locate the DSH CLI and return the argv prefix that runs it.

    Checks DSH_CLI, then dsh on PATH, then the default Windows install path.
    Windows cannot launch a .cmd/.bat through CreateProcess, so those go
    through "cmd /c". "call" is required on top of it: cmd strips the first
    quote pair after /c, so as soon as another argument contains whitespace
    the script path is itself truncated at the space and the trailing
    arguments are lost. "call" keeps the quoting intact.
    """
    candidates: list[Path] = []
    override = os.environ.get("DSH_CLI")
    if override:
        candidates.append(Path(override))
    on_path = shutil.which("dsh")
    if on_path:
        candidates.append(Path(on_path))
    local_appdata = os.environ.get("LOCALAPPDATA")
    if os.name == "nt" and local_appdata:
        candidates.append(
            Path(local_appdata) / "Programs" / "DeepSeek Harness"
            / "resources" / "runtime" / "cli" / "bin" / "dsh.cmd"
        )

    for candidate in candidates:
        if not candidate.is_file():
            continue
        resolved = str(candidate)
        if resolved.lower().endswith((".cmd", ".bat")):
            return ["cmd", "/c", "call", resolved]
        return [resolved]

    raise FileNotFoundError(
        "Could not find the DSH CLI. Set DSH_CLI to the dsh executable, add "
        "dsh to PATH, or install DeepSeek Harness (Windows default path: "
        "%LOCALAPPDATA%\\Programs\\DeepSeek Harness\\resources\\runtime\\cli\\bin\\dsh.cmd)."
    )


def headless_argv(
    task: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    json_mode: bool = False,
    use_stdin: bool = False,
) -> list[str]:
    """Build the argv for one headless DSH run of "task".

    DSH has no --model flag: the model comes from the profile's
    agent-default-model, so an override is written to a temporary YAML file
    passed with --patch, which must come before the app arguments. Deleting
    that file is the caller's job.
    """
    if (provider is None) != (model is None):
        raise ValueError("provider and model must be given together or not at all")

    argv = resolve_dsh() + ["--profile", "headless"]
    if provider is not None and model is not None:
        patch_path = Path(tempfile.gettempdir()) / f"dsh-agent-default-model-{uuid.uuid4().hex[:8]}.yml"
        patch_path.write_text(
            "- id: agent-default-model\n"
            "  config:\n"
            f"    provider: {provider}\n"
            f"    model: {model}\n",
            encoding="utf-8",
        )
        argv.extend(["--patch", str(patch_path)])
    if json_mode:
        argv.append("--json")
    argv.append("-" if use_stdin else task)
    return argv


def safe_console() -> None:
    """Windows consoles default to cp936, and a redirected stream uses it too.

    Let an unencodable character degrade to '?' instead of killing the script:
    a report full of checkmarks still gets written, just not to a raw console.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass

