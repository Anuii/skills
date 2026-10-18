#!/usr/bin/env python3
# Modified for DeepSeek Harness. Upstream: Anthropic's skill-creator (Apache-2.0, see LICENSE.txt).
"""Run trigger evaluation for a skill description.

Tests whether a skill's description causes DSH to trigger (read the skill)
for a set of queries. Outputs results as JSON.
"""

import argparse
import json
import queue
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.utils import headless_argv, parse_skill_md, safe_console


def find_project_root() -> Path:
    """Find the project root by walking up from cwd looking for .git/.

    Mimics how DSH discovers its project root, so the skill directory we
    create ends up where dsh --profile headless will look for it. .git may
    be a file (worktree or submodule), so existence is the test.
    """
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    return current


def run_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    project_root: str,
    provider: str | None = None,
    model: str | None = None,
) -> bool:
    """Run a single query and return whether the skill was triggered.

    Creates a skill directory in .agents/skills/ so it appears in DSH's
    available skills, then runs dsh --profile headless with the raw query.
    The JSON event stream is read line by line on a worker thread, so a
    tool_call naming this skill is detected the moment it arrives instead of
    after the whole run finishes.
    """
    unique_id = uuid.uuid4().hex[:8]
    clean_name = f"{skill_name}-skill-{unique_id}"
    # DSH discovers skills one level deep only: <root>/<name>/SKILL.md.
    skill_dir = Path(project_root) / ".agents" / "skills" / clean_name
    skill_file = skill_dir / "SKILL.md"

    # The directory levels this run may create, shallow to deep. Cleanup
    # removes only levels that did not already exist, so a pre-existing
    # .agents/ (or .agents/skills/) is never deleted.
    created_dirs: list[Path] = []
    for level in [
        Path(project_root) / ".agents",
        Path(project_root) / ".agents" / "skills",
        skill_dir,
    ]:
        if not level.exists():
            created_dirs.append(level)

    try:
        skill_dir.mkdir(parents=True, exist_ok=True)
        # JSON string quoting is valid YAML double-quoting, so quotes and
        # newlines in the description cannot break the frontmatter.
        quoted_desc = json.dumps(skill_description)
        skill_content = (
            f"---\n"
            f"name: {clean_name}\n"
            f"description: {quoted_desc}\n"
            f"---\n\n"
            f"# {skill_name}\n\n"
            f"This skill handles: {skill_description}\n"
        )
        skill_file.write_text(skill_content, encoding="utf-8")

        cmd = headless_argv(
            query,
            provider=provider,
            model=model,
            json_mode=True,
        )
        # The model override rides in a temp file we must delete ourselves.
        patch_file = Path(cmd[cmd.index("--patch") + 1]) if "--patch" in cmd else None

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=project_root,
            )

            triggered = False
            # select() does not work on Windows pipes, so a worker thread
            # drains stdout and the main thread waits on the queue.
            lines: queue.Queue = queue.Queue()

            def _pump_stdout() -> None:
                try:
                    for raw_line in process.stdout:
                        lines.put(raw_line)
                finally:
                    lines.put(None)

            reader = threading.Thread(target=_pump_stdout, daemon=True)
            reader.start()

            deadline = time.time() + timeout
            try:
                while True:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        break
                    try:
                        raw_line = lines.get(timeout=remaining)
                    except queue.Empty:
                        break
                    if raw_line is None:
                        break

                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue

                    # DSH sends no stream_event/content_block_* events; the
                    # authoritative signal is a tool_call naming this skill.
                    # The marker fallback must also match JSON-escaped quotes.
                    marker = f'<skill_content name="{clean_name}"'
                    plain = line.replace('\\"', '"')
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        if marker in plain:
                            triggered = True
                            break
                        continue

                    if (
                        event.get("type") == "tool_call"
                        and event.get("tool") == "skill"
                        and (event.get("input") or {}).get("name") == clean_name
                    ):
                        triggered = True
                        break
                    if marker in plain:
                        triggered = True
                        break
            finally:
                # Clean up process on any exit path (return, exception, timeout)
                if process.poll() is None:
                    process.kill()
                    process.wait()

            return triggered
        finally:
            if patch_file is not None and patch_file.exists():
                patch_file.unlink()
    finally:
        if skill_file.exists():
            skill_file.unlink()
        # Only the directory we created, and only once it is empty; never a
        # recursive delete.
        if skill_dir.is_dir() and not any(skill_dir.iterdir()):
            skill_dir.rmdir()
        # Remove only the levels this run created, deepest first, and only
        # while empty; rmdir() fails on a non-empty directory, which is the
        # signal to leave it alone.
        for created in reversed(created_dirs):
            try:
                created.rmdir()
            except OSError:
                pass


def run_eval(
    eval_set: list[dict],
    skill_name: str,
    description: str,
    num_workers: int,
    timeout: int,
    project_root: Path,
    runs_per_query: int = 1,
    trigger_threshold: float = 0.5,
    provider: str | None = None,
    model: str | None = None,
) -> dict:
    """Run the full eval set and return results."""
    results = []

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_info = {}
        for item in eval_set:
            for run_idx in range(runs_per_query):
                future = executor.submit(
                    run_single_query,
                    item["query"],
                    skill_name,
                    description,
                    timeout,
                    str(project_root),
                    provider,
                    model,
                )
                future_to_info[future] = (item, run_idx)

        query_triggers: dict[str, list[bool]] = {}
        query_items: dict[str, dict] = {}
        for future in as_completed(future_to_info):
            item, _ = future_to_info[future]
            query = item["query"]
            query_items[query] = item
            if query not in query_triggers:
                query_triggers[query] = []
            try:
                query_triggers[query].append(future.result())
            except Exception as e:
                print(f"Warning: query failed: {e}", file=sys.stderr)
                query_triggers[query].append(False)

    for query, triggers in query_triggers.items():
        item = query_items[query]
        trigger_rate = sum(triggers) / len(triggers)
        should_trigger = item["should_trigger"]
        if should_trigger:
            did_pass = trigger_rate >= trigger_threshold
        else:
            did_pass = trigger_rate < trigger_threshold
        results.append({
            "query": query,
            "should_trigger": should_trigger,
            "trigger_rate": trigger_rate,
            "triggers": sum(triggers),
            "runs": len(triggers),
            "pass": did_pass,
        })

    passed = sum(1 for r in results if r["pass"])
    total = len(results)

    return {
        "skill_name": skill_name,
        "description": description,
        "results": results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
        },
    }


def main():
    safe_console()
    parser = argparse.ArgumentParser(description="Run trigger evaluation for a skill description")
    parser.add_argument("--eval-set", required=True, help="Path to eval set JSON file")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--description", default=None, help="Override description to test")
    parser.add_argument("--num-workers", type=int, default=10, help="Number of parallel workers")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout per query in seconds")
    parser.add_argument("--runs-per-query", type=int, default=3, help="Number of runs per query")
    parser.add_argument("--trigger-threshold", type=float, default=0.5, help="Trigger rate threshold")
    parser.add_argument("--provider", default=None, help="Provider for headless runs (default: the profile's agent-default-model)")
    parser.add_argument("--model", default=None, help="Model for headless runs (default: the profile's agent-default-model)")
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    args = parser.parse_args()

    if (args.provider is None) != (args.model is None):
        parser.error("--provider and --model must be given together or not at all")

    eval_set = json.loads(Path(args.eval_set).read_text(encoding="utf-8"))
    skill_path = Path(args.skill_path)

    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        sys.exit(1)

    name, original_description, content = parse_skill_md(skill_path)
    description = args.description or original_description
    project_root = find_project_root()

    if args.verbose:
        print(f"Evaluating: {description}", file=sys.stderr)

    output = run_eval(
        eval_set=eval_set,
        skill_name=name,
        description=description,
        num_workers=args.num_workers,
        timeout=args.timeout,
        project_root=project_root,
        runs_per_query=args.runs_per_query,
        trigger_threshold=args.trigger_threshold,
        provider=args.provider,
        model=args.model,
    )

    if args.verbose:
        summary = output["summary"]
        print(f"Results: {summary['passed']}/{summary['total']} passed", file=sys.stderr)
        for r in output["results"]:
            status = "PASS" if r["pass"] else "FAIL"
            rate_str = f"{r['triggers']}/{r['runs']}"
            print(f"  [{status}] rate={rate_str} expected={r['should_trigger']}: {r['query'][:70]}", file=sys.stderr)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
