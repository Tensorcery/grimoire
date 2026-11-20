# Ground rules for every roast agent

Your launch message gives you five values: `SKILL` (the skill's folder),
`RUN` (the run folder), `ROAST` (the script command), `AGENT` (your id) and
your assignment. Wherever these files say `SKILL`, `RUN`, `ROAST` or `AGENT`,
put in the value from your launch message. Then read your role file.

You are already inside a roast run. Do not start the roast skill, and launch
no agents.

## 1. Read the run first

Open `RUN/run.json`. It holds the targets and `focus`.

`focus` is the user's own instruction, in the user's language. It outranks
every checklist in these files. If it narrows the scope, stay inside it. If it
adds a concern (architecture, folder layout, maturity, anything), that concern
gets the same effort as defects do.

## 2. Where you work

- `RUN/sandbox/<target>/` is a copy of each target. Read it, run it, test it.
- `RUN/sandbox/_poc/AGENT/` is yours: scripts, scratch databases, output
  files. Create it when you need it.
- The copied target files stay as they are: other agents are reading and
  running the same copy at the same moment. To show what a change would do,
  copy the file into your `_poc` folder and change the copy. Build output
  that the target's own build writes into the copy is fine.
- The original paths listed under `targets` in `run.json` are read-only. Open
  them for one purpose only: reading version-control history (`git log`,
  `git show`, `git blame`). Run nothing there and write nothing there:
  even a test run leaves files behind, and the run checks at the end that the
  original is untouched.
- Nothing outside the sandbox is touched: no live hosts, no production
  services, no third-party APIs called with the target's credentials, no
  destructive commands, nothing installed outside the sandbox. Searching the
  web for information is fine, with generic queries only: nothing copied
  from the target goes into a query.

A path of a target file is always written as the script writes it: the
target's name, then the path inside it, for example `shop/src/refund.py`.
The same path under `RUN/sandbox/` is the copy you work on.

## 3. The clock

Every `ROAST` command prints the clock as its first line. There are two kinds
of line.

```
[roast] study: no clock
```

No clock means there is no time limit. Be complete: the work is finished when
your role file's list is done, not when it feels long enough. This holds for
the study, the verification and the judge.

```
[roast] attack: 12:45 left | CONTINUE
```

Only the attack is timed, and its end is soft. Obey the last word:

- `CONTINUE`: carry on.
- `OVERTIME`: the time is up, but the targets this run committed to are not
  all done. Carry on with them; the script hands out nothing else.
- `STOP`: the attack is over. Write what you have and hand back.

## 4. Text with quotes in it

Put free text in single quotes on the command line. If the text itself
contains a single quote, a backtick or a `$`, give `-` in its place and send
the text on standard input:

```
ROAST target add --run RUN --agent AGENT --piece auth --style input \
  --importance 85 --source shop/src/login.py:40 - <<'TEXT'
log in with the name `admin'--`; a defect if the reply isn't "wrong password"
TEXT
```

## 5. Disk first, then the hand-back

Only what is in the run folder exists. Write each result the moment you have
it, not at the end.

Your final message is the hand-back: the lines your role file gives and no
others. It carries ids and counts, not what you found: no titles, no
locations, no suspicions, no paths. The orchestrator must stay without an
opinion about the target, so that it does not steer the next agent; whoever
needs your results reads them from the run folder.

## 6. Stay in your role

Do the job of your role file and no other role's job.

## 7. The importance of a target

Every target on the shared list carries an importance from 0 to 100. The
pack takes the list from the top, and a run tries only as many targets as
its agents and minutes allow, so the number decides what is tried at all.
It answers one question: how bad is it if this breaks, and how likely does
the code make it?

| Importance | What belongs there |
|---|---|
| 90 to 100 | Breaking it loses money or data, or lets in someone who should be kept out, and the code shows no defence at that place |
| 70 to 89 | The same damage, but a defence exists that is narrower than the rule or has no test; or a stated rule with no enforcement where less is at stake |
| 40 to 69 | A weak spot with no promise behind it; wrong output that someone would notice and could work around |
| 0 to 39 | Cosmetic effects, unlikely conditions, guesses with no place in the code that supports them |

Use the whole scale. A list on which everything is 80 is sorted by nothing.
