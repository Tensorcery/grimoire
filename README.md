# skills

Plugins for Claude Code.

| Plugin | What it does |
|---|---|
| [roast](plugins/roast/README.md) | An adversarial review by a pack of subagents: the target is studied in full, then attacked for a set time, and every defect in behaviour is proven by a script |

## Install

```
claude plugin marketplace add <this repository: a path or a git URL>
claude plugin install roast@roast-skills
```

Then, in a session: `/roast:roast 5 20`.

## Working on it

```
uv sync
uv run pre-commit install
python3 plugins/roast/tests/test_roast.py
```

- Commit messages follow Conventional Commits; a hook checks each one
  against `cz.toml`.
- The tests run before every push.
- `uv run cz bump` raises the version in `pyproject.toml` and in the
  plugin's manifest, and writes the changelog.

MIT, see [LICENSE](LICENSE).

| Folder | What is in it |
|---|---|
| `plugins/<name>/` | one plugin: its manifest, its agents, its skill, its tests |
| `docs/` | design notes |
