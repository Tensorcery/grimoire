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
  `make validate`, which is Claude Code's own check of the catalog and of
  every plugin, and `make commits` on the pull request's commits.
- CodeQL (`.github/workflows/codeql.yml`) reads the Python and the
  workflows on every pull request, on `main` and once a week; what it finds
  is in the repository's Security tab.

## Releasing

1. Start the workflow `prepare release` by hand. It raises the version by
   commitizen (in `pyproject.toml`, `uv.lock` and the plugin's manifest),
   writes `CHANGELOG.md` and opens a pull request from `release/v<next>`.
2. Read the pull request's description and edit it: it is the draft of the
   release's description. CodeRabbit writes a summary into it, as
   `.coderabbit.yaml` tells it to, above the changelog section. If CodeRabbit
   does not come, comment `@coderabbitai summary` on the pull request; if it
   is not installed, the draft is the changelog section alone.
3. Merge that pull request. On `main` the workflow `release` finds a version
   without a tag and creates the tag and the GitHub release, described by
   what the pull request said at the merge.

`CHANGELOG.md` is commitizen's alone; no model writes into it.

The first push to `main` is a release too: `pyproject.toml` says 0.1.0 and
no tag `v0.1.0` exists yet.

A pull request opened by a workflow does not start CI by itself: close and
reopen it to run the checks. The repository setting "Allow GitHub Actions to
create and approve pull requests" has to be on.

MIT, see [LICENSE](LICENSE).

| Folder | What is in it |
|---|---|
| `plugins/<name>/` | one plugin: its manifest, its agents, its skill, its tests |
| `docs/` | design notes |
| `.github/` | workflows, and the scripts they call |
