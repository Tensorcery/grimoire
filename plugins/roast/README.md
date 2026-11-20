# roast

An adversarial review by a pack of subagents: the target is studied in full,
then attacked for a set time, and every defect in behaviour is proven by a
script before a judge sees it.

It is a heavy tool for an occasional deep audit of a repository, a service,
a library or a set of instructions for agents. It is not for reviewing a
diff or answering one question about the code.

## Use

```
/roast:roast 5 20
/roast:roast 3 5 path/to/project look at the refund flow first
/roast:roast more 5 path/to/project/.roast/artifacts/2026-11-21_01-17-33
```

| What you give | Meaning | Default |
|---|---|---|
| first number | how many agents may work at once, in every phase | 5 |
| second number | how long the attack should take, in minutes | 20 |
| paths | what to roast | the current directory |
| anything else | your focus, passed to every agent word for word | none |

The time is a wish, not a wall. From the two numbers the run works out how
many checks the pack can get through, commits to that many, the most
important first, and lets the attack run over by up to half its length to
finish them. Only the attack is timed: the study takes as long as it takes.

`more` sends the pack after the checks an earlier run did not get to,
without a new study. With no minutes it runs until the list is done.

## What you get

A closing summary in the chat: how many checks were on the list, how many
were run, how many broke the target, how many defects the judge confirmed,
and a table of what is broken with its level, its cost and its place.

A run folder inside the target, `.roast/artifacts/<start time>/`:

| File | What it holds |
|---|---|
| `REPORT.md` | the judge's summary, every finding, the coverage, the record of the attack |
| `04-findings/` | one file per finding: what is wrong, the impact, the output of its proof |
| `sandbox/_poc/` | the proof scripts; each exits 0 only while the defect is there |
| `01-study/` | what each piece of the target promises and how it works |
| `02-targets/` | the list of checks, each with its importance and its result |

Add `.roast/` to the target's `.gitignore`, or commit it, as you prefer.

## How it works

1. **Study, no clock.** A scout cuts the target into pieces and builds it.
   A reader per piece reads every file of it and writes down each rule the
   target states, with the code that enforces it. Researchers search the
   web for how things of this kind break. Each rule and each weak spot
   becomes a check on a shared list, with an importance from 0 to 100.
2. **Attack, on the clock.** A pack of dogs takes checks from the top of the
   list. A dog proves a defect with a script, and the script is run before
   the finding is accepted. "It held" is accepted only with the script that
   was run.
3. **Verify.** The copy is put back to the original sources and every proof
   is run again. A proof that fails now marks its finding unconfirmed. No
   model is involved.
4. **Judge.** A judge throws out what is not a defect, merges what is the
   same defect and sets the levels: critical, high, medium, low, info.
5. **Report.** The script assembles the report and the numbers of the
   summary.

| Role | Model | Does |
|---|---|---|
| scout, reader | Opus, medium effort | cut the target, read every file |
| researcher | Sonnet, medium | search the web |
| dog | Sonnet, medium | take checks, write proofs |
| judge | Opus, high | reject, merge, set levels, write the summary |

The session that runs the skill is the orchestrator. It only runs the
script and launches agents; it never looks into the target itself.

## What it can review

| Kind | What the readers look for | How a defect is shown |
|---|---|---|
| a program | broken rules, hostile input, races, error paths, access | a script |
| instructions for agents: skills, prompts, agent definitions | contradictions, steps that cannot be done, missing ways out, formats that do not match, rules nothing checks | a quotation, or a script where a run can show it |
| structure and readiness of a program, when the focus asks | missing safeguards, layout, maturity | a quotation or a command |

## The original stays untouched

Everything is built and run in a copy under `~/.cache/roast`, which is
deleted at the end. A link in the target is never copied as a link that
leads back into the original. The target is fingerprinted at the start and
compared at the end, and the summary says whether it changed. The one thing
a run writes into the target is its own `.roast/` folder. Web searches are
generic: nothing copied from the target goes into a query.

## What it costs

Most of the cost is the study, and the study does not depend on the minutes
you give. Two runs with 3 agents and 5 minutes:

| Target | Output tokens | Fresh input | Cache reads |
|---|---|---|---|
| 19 files, 4,000 lines, one piece | 0.17M | 0.74M | 13.9M |
| 262 files, three pieces | 0.28M | 1.15M | 22.7M |

The first of them took 21 minutes and launched 9 agents.

## Needs

- Claude Code with subagents.
- Python 3.8 or newer. The script uses the standard library only.
- git, if the target is a repository: ignored files then stay out of the
  copy. A target outside git works too.
- Disk space for one full build of the target, until the run is cleaned.

## Limits

- It reads instructions for agents; it does not run an agent under them to
  see what it does.
- Documents, spreadsheets and slide decks are not supported.
- The number of checks a run commits to rests on a rate measured on a
  handful of runs: three checks per agent and minute.
- It has been run in Claude Code only.

## Development

```
python3 plugins/roast/tests/test_roast.py
```

drives the script through whole runs without agents. The design, with what
the script enforces and why, is in `docs/roast-contract.md` of the
repository.
