# grimoire

Skills, agents and plugins for coding agents. So far it holds one plugin
for Claude Code.

| Plugin | What it does |
|---|---|
| [roast](plugins/roast/README.md) | An adversarial review by a pack of subagents: the target is studied in full, then attacked for a set time, and every defect in behaviour is proven by a script |

## Install

```
claude plugin marketplace add <this repository: a path or a git URL>
claude plugin install roast@tensorcery
```

Then, in a session: `/roast:roast 5 20`.

## Working on it

```
make install
make lint
make test
```

- `make lint` runs yamllint, shellcheck on the shell scripts, actionlint on
  the workflows, zizmor on everything GitHub runs, and jscpd, which fails
  on any copied block.
- Dependabot proposes new versions of the dev tools and of the actions the
  workflows pin, a week after each release.
- Commit messages follow Conventional Commits; a hook checks each one
  against `cz.toml`.
- The lint and the tests run before every push.
- CI (`.github/workflows/ci.yml`) runs the same targets on every pull
  request and on `main`: `make lint`, `make test` on Python 3.8 and 3.15,
  and `make commits` on the pull request's commits.
- `uv run cz bump` raises the version in `pyproject.toml` and in the
  plugin's manifest, and writes the changelog.

MIT, see [LICENSE](LICENSE).

| Folder | What is in it |
|---|---|
| `plugins/<name>/` | one plugin: its manifest, its agents, its skill, its tests |
| `docs/` | design notes |
| `.github/` | workflows, and the scripts they call |
