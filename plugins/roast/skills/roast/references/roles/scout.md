# Role: scout

You open the study. You cut the target into pieces so that every file gets
read in full by somebody, and you find out how the target is built and run.
You look for no defects.

If your assignment is `rebuild`, the study is already done and the sandbox
is a fresh copy: do step 3 only, with the commands in
`RUN/01-study/target.md`, correct that file if a command no longer works,
and hand back the `build:` line.

## Steps

1. Run `ROAST files --run RUN`. It lists every file of the target with its
   line count. This list, not your own walk of the tree, is what the study
   has to account for.
2. Read what the target says about itself: README, design documents,
   specifications, changelog, the manifest, the CI configuration, the help
   text of its commands. Skim the tree far enough to know what each folder
   is for.
3. Build the target and run its tests in the sandbox. Keep the exact
   commands that worked. The pack will reuse this build, so leave it in
   place.
4. Write `RUN/01-study/target.md` (template below).
5. Write `RUN/01-study/map.json` (rules below).
6. Run `ROAST files --run RUN` again. Every line must end in a piece id or
   in `[skipped]`. A line that ends in `[NO PIECE]` is a file you have not
   placed: place it. Then run `ROAST files --run RUN --piece <id>` for each
   piece and look at the total in its last line: merge the small ones.

## map.json

```json
{
  "pieces": [
    {
      "id": "refunds",
      "title": "Refund flow",
      "where": ["shop/src/refund.py", "shop/src/ledger/", "shop/tests/test_refund.py",
                "shop/docs/design.md", "shop/README.md"],
      "why": "moves money; the design document states six rules for it",
      "domain": "code"
    }
  ],
  "skipped": [
    {"path": "shop/poetry.lock", "why": "generated lockfile"},
    {"path": "shop/tests/fixtures", "why": "test data, opened when a test needs it"}
  ]
}
```

- `id`: lowercase letters, digits and hyphens.
- `where`: files and folders, written as `ROAST files` prints them. A folder
  covers everything under it.
- `domain`: the name of a file in `SKILL/references/domains/` without `.md`.
  Read the Surfaces section of `SKILL/references/domains/code.md` for the
  kinds of pieces worth their own entry.

How to cut:

- **As few pieces as the size allows.** One reader reads one piece in full,
  and every reader is a costly agent. Aim at 2,500 to 3,500 lines of a
  piece's own files; a document that sits in several pieces is not counted.
  A piece under 1,500 lines is merged with its nearest neighbour, and one
  over 4,000 is split: its reader would run out of room. A target of 14,000
  lines is four or five pieces, not three and not twelve.
- **Cut along responsibilities**, not by folder: a piece is a group of
  neighbouring things that can be wrong together (parsing and the data it
  produces; the command-line interface and its reports; fetching, caching
  and locking).
- **Rules travel with the code they govern.** A document that states rules
  for a piece goes into that piece's `where`, even when it then sits in
  several pieces: the reader of each of them must read it. A design document
  that governs everything sits in every piece.
- **Tests travel with the code they test.**
- **Every file is in a piece or under `skipped`.** `skipped` is for what
  nobody needs to read line by line: generated files, lockfiles, vendored
  code, binary assets, bulk test data. Give the reason. Source code and
  documents are never skipped.
- Order the pieces most dangerous first.

If the focus in `run.json` narrows the scope, cut only that scope into pieces
and put the rest under `skipped` with the reason `outside the focus`.

## target.md

```markdown
# <target name>

## What it is
<three to six lines: what it does, for whom, in what language and stack>

## Where its rules are written
- `<path>`: <what kind of promises this document makes>

## Build, run, test
<the exact commands that worked in the sandbox, with the folder to run them
in, how long they take, and where the built program ends up>

## What a proof script can rely on
<what is already built, how to call the program from a script, which
environment variables or scratch folders it needs>

## Stated limitations
<what the target's own documents say it does not do or does not guarantee,
each with its source; these are not defects>

## Leave alone
<anything that must not be run, and why: network calls, long jobs, publishing>
```

## Hand-back

```
pieces: <count>  skipped: <count>
build: <"works" or "fails">  tests: <"pass", "fail" or "none">
```
