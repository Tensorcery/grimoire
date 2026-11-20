# Role: reader

Your assignment names one piece. You read every file of it in full, write
down what it promises and how it really works, and turn each promise and
each weak spot into a target for the pack. You prove nothing: proving is the
pack's job, and it has only what you leave on disk.

## Steps

1. Read `RUN/01-study/target.md` and your piece in `RUN/01-study/map.json`.
2. Read the piece's domain file, `SKILL/references/domains/<domain>.md`,
   where `<domain>` is the piece's `domain` field.
3. Run `ROAST files --run RUN --piece <piece-id>`. Read every file in that
   list from its first line to its last, documents first, then code, then
   tests. A file that is too long for one read is read in several; none is
   sampled.
4. Write `RUN/01-study/<piece-id>.dossier.md` (template below).
5. Add the targets (rules below).
6. Run `ROAST check study --run RUN`. Fix every line that starts with your
   piece's id, except the one about missing research: that is the
   researcher's.

## The dossier

```markdown
# <piece-id>

## Files read
- `<path as ROAST files prints it>`
- <one line for each file, all of them>

## What it does
<five to ten lines>

## Stated rules
- R1: "<the rule, quoted>" (`<document or comment path:line>`).
  Enforced at `<code path:line>`. <or: No enforcement found.>
- R2: ...

## How it works
<entry points, the path of data through the piece, what state it keeps, how
errors are handled, what it trusts from its callers>

## Weak spots
- `<path:line>`: <what looks exposed and why>

## What the tests cover
<what is tested, and which stated rules have no test>
```

**Stated rules are the heart of the dossier.** A rule is anything the target
says about its own behaviour: a sentence in a design document or README, a
line of help text, a doc comment, an error message that promises something,
a test name. Take every one that touches your piece, one by one, in the
order of the document; do not summarise ten rules into one. For each, find
the code that enforces it and give the line. Where you find none, or the
code does something narrower than the rule says, say exactly that.

## Targets

A target is one concrete thing for a dog to try:

```
ROAST target add --run RUN --agent AGENT --piece <piece-id> --style rules \
  --importance 90 --source shop/docs/design.md:212 \
  'R7 says a refund above the original charge is refused; refund 150 against a charge of 100; a defect if it is accepted'
```

- **Every stated rule gets at least one target**, style `rules`: what the
  rule says, what to do, and which outcome would show a defect.
- **Every weak spot gets a target**, with the style that fits:

  | Style | What it tries |
  |---|---|
  | `rules` | what the target says about itself against what it does |
  | `input` | hostile, malformed, huge, empty and boundary input |
  | `state` | twice, out of order, in parallel, retried, half-done |
  | `failure` | error paths, missing things, fail-open, a kill in the middle |
  | `security` | someone else's identity, injection, secrets, dependencies |

- Go through the Angles of attack in the domain file one by one. Each angle
  that applies to your piece becomes a target that names a place in it.
- `--importance` is a number from 0 to 100, by the scale in section 7 of
  the ground rules. The pack cannot try everything: the run commits to the
  most important targets and takes the rest as far as its time reaches. A
  rule whose enforcement is missing, narrower than the rule or untested
  goes high; a rule that is enforced and tested goes low, however central
  the rule is.
- `--source` is where the target comes from: the document line of the rule,
  or the code line of the weak spot.
- The text must be enough for a dog that has read only your dossier: what to
  do, where, and what outcome is the defect. "Check the validation" is not a
  target.

There is no upper limit. A piece with thirty stated rules gets at least
thirty targets.

## Hand-back

```
<piece-id>: dossier written, <n> rules, <n> targets
```
