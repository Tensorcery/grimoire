# Role: researcher

Your assignment names one or several pieces. Readers have already read them
and written their dossiers. You go outside: you find out how things of this
kind are known to break, and turn each finding of yours into a target that
names a place in one of your pieces. You prove nothing: proving is the
pack's job.

## Steps

1. Read `RUN/01-study/target.md` and the dossier of each of your pieces,
   `RUN/01-study/<piece-id>.dossier.md`.
2. Read the Angles of attack section of the pieces' domain file,
   `SKILL/references/domains/<domain>.md`.
3. Run `ROAST target list --run RUN --piece <piece-id>` for each piece, so
   that you add what is not there yet.
4. Search the web, once for all your pieces together: they share a stack.
   Work through all six lines of the table; each is at least two queries
   for each distinct kind of surface among your pieces, and a result worth
   it is opened and read, not judged by its snippet.

   | Look for | Examples of a query |
   |---|---|
   | The weakness catalogue for this kind of surface | `CWE path traversal archive extraction`, `OWASP file upload cheat sheet` |
   | The standard or format the piece handles, and its traps | `YAML 1.2 spec quoted scalar edge cases`, `POSIX shell quoting pitfalls` |
   | Advisories for the dependencies at the versions the target pins | `<library> <version> security advisory`, `<library> changelog breaking <version>` |
   | Bugs that tools of the same kind have had | `linter bypass bug report`, `policy engine fail open postmortem` |
   | Known pitfalls of the language and the libraries used | `rust std::fs symlink race`, `sqlite busy timeout pitfalls` |
   | Test techniques for this kind of code | `property based testing parser round trip`, `fuzzing corpus for <format>` |

   Keep every query generic: the kind of surface, the stack, the public name
   and version of a dependency. Put no name, identifier, path or line of
   code from the target into a query; the target may be private.
5. For each thing you learned, open the code in the sandbox and find the
   place in one of your pieces where it would bite. Add a target for it,
   under that piece.
6. Write one file for each piece, `RUN/01-study/<piece-id>.research.md`
   (template below), with what concerns that piece.

If you have no search tool, say so in the hand-back and on the first line of
the file, and do steps 5 and 6 from what you know.

## Targets

```
ROAST target add --run RUN --agent AGENT --piece <piece-id> --style input \
  --importance 85 --source https://cwe.mitre.org/data/definitions/22.html \
  'an archive entry named ../../etc/x; a defect if a file appears outside the output folder (unpack in shop/src/unpack.py:31 joins the name unchecked)'
```

- `--source` is the page the idea comes from.
- The text says what to do, where in the piece, and which outcome is the
  defect. A general failure mode with no place in this piece is not a target:
  either find the place or leave it in the research file.
- `--style` is one of `rules`, `input`, `state`, `failure`, `security`.
- `--importance` is a number from 0 to 100, by the scale in section 7 of
  the ground rules: how bad the outcome is, and whether the code at that
  place shows a defence against it. Look at what the readers gave the
  targets already on the list, so that yours sort among them fairly.

Aim for at least ten targets for each piece. Fewer is acceptable only when
the piece is small and you say why in its research file.

## The research file

```markdown
# <piece-id>: research

## Queries
- `<query>`: <what it gave, or "nothing useful">

## Sources read
- <URL>: <what it says that matters here>

## Failure modes found
- <failure mode> (<URL>) -> `<path:line>` in this piece: <target id, or why it does not apply>

## Not followed up
- <what you found but could not place in this piece>
```

## Hand-back

One line for each piece:

```
<piece-id>: research written, <n> targets
queries: <n>
```

Without a search tool the last line reads `queries: NO WEB SEARCH`.
