# Domain: code-design

For pieces about structure, layout, maturity and production readiness. The
scout creates such a piece when the focus asks for these things.

Here the focus is the promise: if the user asks about readiness, an absent
safeguard is a defect, even though no document of the target promises it.

## Evidence

An item below becomes a finding only with one of these, plus the concrete
consequence:

- a command that fails, with its output;
- a search that shows absence, quoted with its result ("`grep -rn timeout
  src/` returns nothing; three outbound calls in `client.py`");
- the quoted lines with their locations.

"This is messy" is not evidence. Group by area: one finding for "outbound
calls have no timeout" that lists the calls, not one finding per call.
Severity follows `severity.md`: `high` only when the structure makes a stated
rule impossible to keep; an absent safeguard is usually `low` or `medium`.

## Architecture

- An import cycle, or a lower layer importing a higher one: quote both import
  lines.
- One module far larger or far more imported than the rest: give the counts.
- The same rule implemented in two places: quote both and give an input on
  which they differ.
- A symbol, route or flag with no reference anywhere.
- One kind of error handled in two different ways.
- Code more general than its use: an interface with one implementation, a
  configuration option nothing sets.

## Layout and documents

- A documented command that fails when run word for word.
- A setting the code reads but no document mentions, or the reverse.
- Configuration spread over several places with no single source.
- A file whose place hides what it does: business rules in a utilities
  folder, storage code in a handler.

## Maturity

- Does it build and do the tests pass from a clean copy with the documented
  commands?
- Do the tests run in the pipeline? Are there recent source changes with no
  test changes?
- Linter, type checker or compiler warnings: configured, and clean?
- Lockfile, version number, release notes.

## Production readiness

- Every outbound call has a timeout.
- Retries use backoff, apply only to calls that are safe to repeat, and
  happen at one layer only.
- The process handles the termination signal and finishes work in hand.
- Health and readiness checks exist.
- Configuration is validated at start, not at first use.
- Logs carry a request identifier and no secrets.
- Failures that users see are counted somewhere.
- Start it with a dependency down and watch what happens.
- Rollback and restore from backup are documented.
- Container images are pinned and do not run as root.
