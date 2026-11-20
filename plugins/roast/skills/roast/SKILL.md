---
name: roast
description: "Use when the user asks to roast, tear apart, break or stress-test a code repository, a service or a library, and wants a pack of agents to study it in full and then attack it, with every defect proven by a script. A heavy tool for an occasional deep audit, not for everyday review. Typical requests: '/roast 5 20', 'roast this repo with 10 agents for 30 minutes', 'tear this service apart', 'прожарь этот проект'. Not for a quick review of a diff or a single question about the code."
---

# Roast

An adversarial review carried out by subagents in two halves. First the
target is studied in full, with no time limit: every file is read, the web
is searched, and each promise and weak spot becomes an entry in a shared
list of targets. Then a pack of dogs attacks from that list. After that the
script re-runs every proof, judges sort the findings, and the script
assembles the report.

The user gives two numbers: how many agents may work at once, and how long
the attack should take. The time is a wish, not a wall: from the two numbers
the script works out how many targets the pack can get through, commits the
run to that many, and lets the attack run over by up to half its length to
finish them.

You are the orchestrator. Your whole job is five actions: run the script,
launch an agent, continue an agent, read a hand-back, tell the user the
result.

The agents read the target, investigate, and write everything down. You do
none of that, for two reasons: your context has to last the whole run, and
an orchestrator with its own opinion of the target steers the agents towards
it. So you open no file of the target and no file of the run folder except
`REPORT.md` at the end. Everything else you know comes from what the script
prints. When something is broken, you send it back to the agent that made
it; you do not repair it.

Needs: Python 3.8 or newer, subagents, and a way to run a command in the
background. The run folder is created with the first target, as
`<target>/.roast/artifacts/<start time>/`: the study, the targets, the
findings, the proof scripts and the report stay with the project. The copy
of the target that is built and run is kept outside the project, under
`~/.cache/roast`, and needs the disk space of one full build until the run
is cleaned at the end. If the user names another place for the results, add
`--out <that folder>` to `start`.

`<SKILL>` below is the absolute path of the folder that holds this file,
`<RUN>` the absolute path of the run folder, and `ROAST` stands for
`python3 <SKILL>/scripts/roast.py`.

Read `references/harness.md` now, before the first command: it says how to
launch, continue and stop an agent, which agent type and model each role
gets, and how to run a command in the background in your harness.

## 1. Read the request

Take four things from the user's message. Ask nothing.

| What | How to recognise it | Default |
|---|---|---|
| agents | the first number: how many agents may work at once, in every phase | 5 |
| minutes | the second number: the wished length of the attack | 20 |
| targets | paths to folders or files | the current directory |
| focus | everything else the user wrote about what to look at | none |

The focus is passed on word for word, in the user's language. Do not
translate, shorten or interpret it.

## 2. Start

The focus goes in on standard input, so that no quoting can damage it:

```
ROAST start <agents> <minutes> <target> [<target> ...] --focus - <<'FOCUS'
<the focus, word for word>
FOCUS
ROAST sandbox --run <RUN>
```

With no focus, leave out `--focus -` and the lines after it.

## 3. Who to launch: `crew`

You never work out yourself which agents a step needs.

```
ROAST crew --run <RUN>
```

prints them, one per line, as `agent id | role | assignment`:

```
read-refunds | reader | Piece: refunds
```

Launch each line with exactly this message and nothing more. Your own
guesses about the target do not belong in it.

```
You are the <role> in a roast run. Do not start the roast skill yourself.
Read these two files now and follow them exactly:
  <SKILL>/references/ground-rules.md
  <SKILL>/references/roles/<role>.md
SKILL: <SKILL>
RUN: <RUN>
ROAST: python3 <SKILL>/scripts/roast.py
AGENT: <agent id>
Assignment: <assignment>
```

The agent type for each role is in `references/harness.md`.

**Never more agents at once than the user's first number.** When `crew`
prints more lines than that, launch that many, and launch the next line each
time one hands back. Agents launched together go into one message, so that
they run in parallel. Between a launch and a hand-back you do nothing; you
are woken by a hand-back or by `wait`. Do not poll.

## 4. Study

Nothing here is timed. The study is finished when the script says so, not
when it has taken long enough.

Repeat: run `crew`, launch what it prints, wait for the hand-backs. `crew`
moves on by itself: first the scout, then a reader for every piece, then
the researchers. When it prints lines that start with `map.json:`, continue
the scout with those lines, word for word.

When `crew` says the study has an agent for every piece:

```
ROAST check study --run <RUN>
```

Each line starts with the piece it is about. Continue that piece's reader
with the line, word for word; a line about missing research goes to the
researcher that had that piece. Repeat until the output ends in
`study: 0 problem(s)`.

Then tell the user, in the user's language and in a few lines, what is about
to happen: how many pieces and files were studied, how many targets are on
the list, how many of them this run commits to, how many dogs attack for
about how long. The numbers come from `ROAST status` and from the output of
the next command. Do not wait for an answer: go on.

## 5. Attack

```
ROAST phase attack --run <RUN>
ROAST crew --run <RUN>
```

`phase attack` starts the clock and says how many targets this run commits
to; the rest of the list is the reserve. `crew` prints the pack. Launch
every dog now, then start `ROAST wait --run <RUN>` in the background.

Every `ROAST` command now prints the clock first:

```
[roast] attack: 12:45 left | CONTINUE
```

`wait` sleeps and exits with an instruction. That it has exited tells you
nothing: it also exits every eight minutes with nothing changed. Read its
output first, then act on the last line:

| Last line of `wait` | What you do |
|---|---|
| `No checkpoint yet` | Nothing has changed. Start `wait` again |
| `The time is up but this run's list is not done` | The clock says `OVERTIME`: the pack finishes the list. Start `wait` again |
| `The attack is over` | The clock says `STOP`. Wait for the dogs to hand back |

Keep exactly one `wait` running at a time.

A dog leaves only when the script lets it: a proper hand-back is the three
lines that `ROAST leave` printed. Act on the last of them:

| Last line of the hand-back | What you do |
|---|---|
| `stopped by: relay` | The dog has done its share and its context has grown costly. If the clock does not say `STOP`, launch a fresh dog in its place: the same style, the next id (`A1` is followed by `A1-2`, then `A1-3`) |
| `stopped by: clock` | Nothing. The attack is over for this dog |
| `stopped by: nothing left to try` | Nothing |
| anything else, while the clock does not say `STOP` | The dog stopped too early. Continue the same dog with exactly: `The attack is still running. Run take again and go on. Hand back only the lines that ROAST leave gives you.` |

When the clock says `STOP` and every dog has handed back, go on. A dog still
running two minutes after `STOP` is stopped; what it filed is on disk.

## 6. Verify, judge, report

```
ROAST phase verify --run <RUN>
ROAST verify --run <RUN>          # in the background: it runs every proof again
```

`verify` puts the sandbox back to the original sources and runs each proof
once more. A proof that fails now marks its finding `unconfirmed`. No agent
is involved.

```
ROAST phase judge --run <RUN>
ROAST crew --run <RUN>
```

`crew` says how many judges the findings need and what each one gets.
Launch them as it says. When the last one has handed back, run `ROAST
finding list --run <RUN>`. If a finding is still `open`, continue the judge
that had it with the ids of those findings. If the last judge's
hand-back does not end in `summary: saved`, continue it with: `Save the
summary with ROAST summary, as your role file says.`

```
ROAST phase report --run <RUN>
ROAST report --run <RUN>
ROAST clean --run <RUN>
```

`clean` deletes the sandbox with its build and keeps the proof scripts.
Leave it out only if the user asked to keep the sandbox.

## 7. Tell the user

The closing summary has a fixed form. Fill it from two places only: the
block `Numbers for the closing summary` that `report` printed, and the
section `Summary by the judge` of `REPORT.md`. Write it in the user's
language, in plain words. The user reads this and nothing else, so say
"check" for a target and "defect" for a finding, and leave out every id.

```markdown
**<Target>: <the judge's verdict, two or three sentences>**

| From the list to the result | |
|---|---|
| Checks on the list | 281 |
| Run by the pack | 60 |
| ...of them broke the target | 42 |
| Distinct defects filed | 30 |
| Confirmed by the judge | 23 |
| Checks nobody ran | 220 |

Several checks often hit the same defect, and the judge throws out repeats
and what is not a defect: that is why 42 became 23.

Confirmed by level: critical 0, high 0, medium 13, low 10.

| Level | What goes wrong | What it costs | Where |
|---|---|---|---|
| medium | A refund above the charge is accepted | The shop pays out more than it took | `shop/src/refund.py:88` |

| Piece | Checks | Run | Broke the target | Nobody ran | Confirmed defects |
|---|---|---|---|---|---|
| refunds | 94 | 20 | 14 | 73 | 8 |

3 agents, 5 minutes asked, the attack took 5.1; 3 pieces and 86 files
studied; the whole run took 41 minutes. The original was not touched.

Full report: `<RUN>/REPORT.md`
To run the 220 checks that are left (15 of them important):
`/roast:roast more 5 <RUN>`, or `more 5 20 <RUN>` to cap it at 20 minutes.
```

- The first table is the lines `targets:` and `findings:`. The sentence
  under it uses the run's own two numbers; leave it out when they are equal.
- The levels line is `confirmed by level:`. Leave out `info` when it is 0.
- The defects table is the judge's table `What is broken`, translated, worst
  first, without the ids. If the judge added a line about further defects,
  keep it under the table.
- The pieces table is the lines under `pieces`.
- The last paragraph is the lines `attack round`, `studied:` and `source:`.
  If the source line says `CHANGED`, say so in bold as the first line of
  the whole summary, with what changed, from the report's last section.
- The two closing lines appear only when `report` printed `to finish`.

Add nothing else: no list of the agents, no account of the phases, no
advice of your own.

## 8. A finishing round

A run rarely tries its whole list: what did not fit stays on disk as targets
nobody has taken. The user can send the pack after them later, without a new
study. The request looks like `more 5`, `more 5 20` or "finish the rest of
that roast": the first number is the agents, the second, if there is one,
the minutes. If it names no run folder, take the newest folder under
`<target>/.roast/artifacts/`; its name is its start time.

```
ROAST more <agents> [<minutes>] --run <RUN>
ROAST crew --run <RUN>
```

Without minutes the round has no time limit: it commits to every target that
is left and ends when the last one is reported. With minutes it works like
the first attack: a budget and a soft end.

`crew` prints `scout | scout | rebuild` when the sandbox was cleaned after
the earlier round: launch it and wait for its hand-back. Then go on from
section 5, `phase attack`, to the end. Only the new findings are verified
and judged; the report covers the whole run, all rounds together.

## When something goes wrong

| What happened | What you do |
|---|---|
| A `ROAST` command exits with an error | Read its message; it names what was expected. Correct the command and run it again |
| `phase attack` refuses and prints lines | The study is not complete. Treat the lines as `check study` lines |
| An agent hands back but the script still reports its work missing | Continue the same agent with the script's line, word for word |
| A hand-back is not in the role's format | Go by what the script prints: `ROAST crew`, `ROAST status`, `ROAST finding list` |
| An agent dies or cannot be continued | Launch a fresh agent with the same launch message; under the assignment line add the last hand-back of the one it replaces |
| You have lost track of the run | `ROAST status --run <RUN>` shows the phase, the clock, the pieces, the targets and the findings; `ROAST crew --run <RUN>` shows who is still to be launched |
| The user's message has no usable target | `ROAST start` says which path does not exist; ask the user for the path, and nothing else |
| The same target was studied in an earlier run | Add `--study-from <that run folder>` to `start`. The script copies the study and drops the dossiers of the pieces whose files changed; `crew` then asks for those pieces only |
