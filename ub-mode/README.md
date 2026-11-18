# ub-mode

`ub-mode` is an agent skill that enforces disciplined software engineering principles when writing or changing code. This distribution keeps the upstream principles, adds C support, and bundles the deterministic quality-gate tools so installation does not require separate tool checkouts.

1. **First Make it Work** — Laziness Protocol, Foundational Thinking, TDD, Redesign From First Principles, Attack the Premise, Subtract Before You Add, Outcome-Oriented Execution, Build the Lever, and Architecture.
2. **Then Make it Right** — Fix Root Causes, Sequence Work into Verifiable Units, Test Behavior (Not Implementation), Crapper, Dryer, Mutator, and Refactoring.
3. **Practice** — Keep a Log, Guard the Context Window, Worktree Cleanup, and Commit and Push in small ordered commits.

## Installation

Copy the complete `ub-mode` directory into a DSH skills root:

```text
~/.dsh/skills/ub-mode/       # preferred
~/.agents/skills/ub-mode/    # shared with other harnesses
```

Invoke `/ub-mode`, or ask for the reduced principles. Keep `tools/` and `scripts/` beside `SKILL.md`; installing only `SKILL.md` omits the quality gates.

## Bundled tools

Run a tool from the target project root, replacing `<skill-directory>` with the installed skill path:

```bash
python <skill-directory>/scripts/ub_tool.py crapper --help
python <skill-directory>/scripts/ub_tool.py dryer --help
python <skill-directory>/scripts/ub_tool.py mutator --help
```

The launcher requires Python 3.11 or newer. On the first run for each tool it creates `tools/<tool>/.venv` and installs that tool's Python dependencies, so the first run needs network access. Later runs reuse the environment. Language-specific compilers, test runners, and coverage tools remain project requirements.

| Tool | Purpose |
| --- | --- |
| crapper | Cyclomatic complexity, coverage, and CRAP scores |
| dryer | Structural duplication candidates |
| mutator | Coverage-aware mutation testing |

C source and header files (`.c` and `.h`) are supported alongside the upstream languages. C++ is outside this change. See each bundled tool's `README.md` for its analysis rules and command overrides.

C projects must describe their own build and test pipeline: provide LCOV through `--coverage-command` or `--use-existing-coverage`, and pass mutator a `--test-command` that rebuilds the mutated sources before running tests. The tools do not assume a C build system.

[uml-viewer](https://github.com/unclebob/uml-viewer) remains an optional external visualization tool; it is not required by the three quality gates.

## Provenance and license

See [UPSTREAM.md](UPSTREAM.md) for exact source commits and the update procedure. The upstream skill license is in [LICENSE](LICENSE); each bundled tool retains its own license.
