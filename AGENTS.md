# Working in this repository

Read by coding agents that work here and by the reviewer of every pull
request. It says what holds in this project; where it says "flag", a
reviewer reports the thing as a defect.

## What this is

Skills, agents and plugins for coding agents. So far one plugin, `roast`,
for Claude Code. People install it straight from this repository, so `main`
is what they run.

| Path | What it is |
|---|---|
| `.claude-plugin/marketplace.json` | the catalog: which plugins this repository offers |
| `plugins/<name>/.claude-plugin/plugin.json` | one plugin's manifest |
| `plugins/<name>/agents/` | its agent definitions |
| `plugins/<name>/skills/<skill>/` | a skill: `SKILL.md`, `references/`, `scripts/` |
| `plugins/<name>/tests/` | its tests |
| `.github/` | workflows, and the scripts they call |

## Everywhere

- Everything is written in English: code, comments, skill texts, commit
  messages.
- Nothing personal goes in: no private e-mail address, no path of
  somebody's machine, nothing copied from a project a skill was run on.
- Every check has a `make` target (`lint`, `test`, `validate`, `commits`)
  and CI calls that target. Flag a check that exists only in a workflow.
- A block of text or code is written once. `make lint` fails on any copy;
  the agent definitions are the one exception, because an agent gets its own
  file and nothing else.

## Texts that an agent follows

`SKILL.md`, the files under `references/` and the agent definitions are
instructions. Their reader has that text, its tools and nothing else, and
cannot ask back. Review them as something that will be followed to the
letter:

- Flag two instructions that cannot both be followed, in one file or across
  the files one agent reads.
- Flag a step that cannot be done as written: a file, a command, a flag or
  a tool that does not exist or is named differently where it is defined.
- Flag a statement about what a script does, prints or refuses that the
  script does not do. The script is the authority; the text follows it.
- Flag a step with no instruction for the case where it fails or finds
  nothing.
- A rule that must hold is enforced by the script, not only stated. Flag a
  new "must" that nothing checks when skipping it is the easier way to look
  finished.
- The session that runs `roast` only runs the script and launches agents.
  Flag a text that has it read or judge the target itself.
- An agent definition stays a short opening that sends the agent to its
  role file. Its model and effort are part of the design: reader on Opus at
  medium, researcher and dog on Sonnet at medium, judge on Opus at high.
  Flag a change to them that the pull request does not explain.

Wording, tone and length are not defects. "Could be clearer" counts only
with a second reading that the text supports equally.

## The roast script

`plugins/roast/skills/roast/scripts/roast.py`:

- The standard library only, and Python 3.8 or newer. Flag an import of
  anything else and syntax newer than 3.8.
- It stays one file.
- Every change in what it does comes with a test in
  `plugins/roast/tests/test_roast.py` that fails without the change. The
  tests are plain `unittest` and drive the script as a command through
  whole runs. Flag a change in behaviour with no such test.
- The target of a run is read-only. The only thing the script writes into
  it is its own `.roast/` folder; everything is built and run in the copy
  under `sandbox/`. Flag any other write that can reach the original,
  a link in the copy that leads back to it included.
- A message the script prints is read by an agent, which acts on it. Flag a
  changed message whose old wording a skill text still quotes.

## Workflows and their scripts

- An action is pinned by its full commit, with the version in a comment.
- `permissions: {}` at the top of a workflow; each job asks for what it
  needs and says why when it asks for write access.
- No `${{ }}` inside `run:`. A value reaches a command through `env:`.
- `persist-credentials: false` on every checkout.
- No `pull_request_target`.
- A shell script starts with `set -euo pipefail` and passes shellcheck.

## Commits and versions

- Conventional Commits, checked against `cz.toml`: the subject at most 72
  characters, a body line at most 100.
- One change to a commit. A fix and an unrelated clean-up are two commits.
- No tool attribution in a message: no `Co-Authored-By` for an assistant,
  no "Generated with" line.
- The version is raised by the workflow `prepare release` only. Flag a
  version edited by hand in `pyproject.toml`, `uv.lock` or a plugin's
  manifest, and any hand edit of `CHANGELOG.md`.
