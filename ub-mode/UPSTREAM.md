# Upstream provenance

This directory is a downstream distribution of the following sources. Commit IDs, rather than moving branch names, are the update baseline.

| Component | Repository | Commit |
| --- | --- | --- |
| Skill principles and license | https://github.com/unclebob/ub-mode | `3da62bf3fcfd2034de41f30d920d2739e566171f` |
| crapper | https://github.com/unclebob/crapper | `c757ec79a6c15dc815238bbd9c2f4601eb54d3cc` |
| dryer | https://github.com/unclebob/dryer | `66ff6d21a42c04afcad89c78a80066176d1294b0` |
| mutator | https://github.com/unclebob/mutator | `830ec7e9c39664d753f8699015bc796df67727b9` |

## Downstream changes

- Add C (`.c` and `.h`) support to crapper, dryer, and mutator.
- Vendor the three deterministic tools, including their tests and licenses.
- Add the cross-platform `scripts/ub_tool.py` launcher and DSH installation instructions.
- Keep uml-viewer external and optional.

## Updating from upstream

1. Compare each repository's new commit with the baseline above and review license changes.
2. Import the source snapshot without its `.git` directory; preserve the existing downstream C patches and launcher.
3. Run every tool's complete test suite, including the C behavior tests.
4. Run the skill validation and packaged-install smoke test.
5. Replace the affected commit IDs and adjust the downstream-change list if a change was merged upstream.
