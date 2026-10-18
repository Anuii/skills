# skills

A collection of skills for [DeepSeek Harness](https://github.com/deepseek-ai) (DSH).

## dsh-skill-creator

Create new skills, modify and improve existing skills, and measure skill performance.
Covers drafting a SKILL.md, running trigger evals against a real model, grading outputs,
benchmarking with variance analysis, opening a local review viewer, and optimizing a
skill description for triggering accuracy.

### Install

Copy the folder into a DSH skills root:

```
~/.dsh/skills/dsh-skill-creator/        # per-user, rank 400 (preferred)
~/.agents/skills/dsh-skill-creator/     # rank 500, shared with other harnesses
```

Discovery is one level deep: `<root>/dsh-skill-creator/SKILL.md` is found,
a nested `**/SKILL.md` is not.

### Requirements

- Python 3.12, standard library only (no PyYAML).
- `DEEPSEEK_API_KEY` in the environment when running the eval or optimization loop,
  which drives `dsh --profile headless`.

### License

A port of Anthropic's skill-creator. Licensed under the Apache License 2.0 - see
[dsh-skill-creator/LICENSE.txt](dsh-skill-creator/LICENSE.txt) and
[dsh-skill-creator/NOTICE](dsh-skill-creator/NOTICE).
