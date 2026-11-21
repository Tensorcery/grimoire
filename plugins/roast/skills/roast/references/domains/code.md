# Domain: code

Who reads what: the scout reads Surfaces; the reader and the researcher read
Angles of attack; a dog reads Working method, Evidence, Not findings and
Sandbox practice; the judge reads Evidence and Not findings.

## Surfaces

Kinds of pieces worth their own entry in `map.json`:

- Entry points: HTTP routes, command-line arguments, message handlers, uploads.
- Identity and access: login, sessions, tokens; who may touch which object
  and which field of it.
- State that must add up: money, balances, counters, inventories, quotas.
- Concurrency: state reached from several threads, processes or requests.
- Storage: schema, queries, transactions, migrations, old code on new data.
- Error and cleanup paths: handlers, rollbacks, fallbacks, retries.
- Outbound calls: third-party APIs, webhooks, queues, fetching a URL the
  caller supplies.
- Parsers and encoders: serialisation, deserialisation, encodings, paths.
- Public contract: a library's exported API, command-line flags, the wire
  format, documented behaviour against actual behaviour.
- Background work: jobs, schedulers, consumers, startup and shutdown.
- Limits: paging, payload size, loops whose length the caller decides.
- Cryptography: tokens, randomness, hashing, keys.
- Time: clocks, zones, expiry, schedules.
- Configuration and secrets: defaults, environment, what ships in the tree.
- Dependencies and build: manifests, lockfiles, vendored code, the CI
  pipeline, release.
- Deployment: container files, manifests, infrastructure-as-code.
- Logging: what leaks and what goes unrecorded.
- Model or agent integration, where present: prompts built from untrusted
  text, what the tools are allowed to do.

Rank a piece higher when it takes input from outside, when it moves money or
changes state that cannot be undone, when the history shows recent bug fixes
in it, and when no test covers it.

Structure, layout, maturity and production readiness are a domain of their
own: `code-design`. Give a piece that domain when the focus asks for those.

Text that an agent or a model follows (skills, prompts, agent definitions,
role files) is a domain of its own too: `instructions`. Such files get a
piece of their own, apart from the program they come with.

## Angles of attack

Each one that applies to a piece becomes a target. "Look for" names the signal.

**Rules and contracts**
1. Stated rule. Take a rule from `target.md`, write the input or sequence
   that would break it, run it. Run every documented example word for word.
2. Two paths, one answer. Get the same fact two ways (a list and its total,
   single and batch, cached and fresh, API and command line). Look for any
   disagreement.
3. Invariant. Name what must always hold (parts sum to the whole, decoding an
   encoding gives the original, doing it twice equals doing it once). Run
   random sequences of operations and check after each one.

**Input**
4. Hostile values. At each entry point: negative, zero, huge, empty, missing,
   wrong type, wrong encoding, very long.
5. Sink first. Search for places where text becomes an instruction: a query
   built from strings, a shell or exec call, eval, a deserialiser, a path
   join, raw markup output, a fetch of a supplied URL. Walk back to an entry
   point and name every check on the way. Look for a route with none.
6. Size. Run with ten and a hundred times the usual input. Look for missing
   limits and for time or memory that grows faster than the input.

**Identity**
7. Someone else's object. Logged in as A, ask for B's object by id on every
   route that takes an id, the quiet ones too: lists, history, search, export.
8. Fields and functions. Send fields the caller must not set (role, owner,
   price, status). Look for fields in responses that should be hidden. Call a
   privileged operation as an ordinary user, and with no credentials at all.

**State and sequence**
9. Twice, skipped, out of order. Do each action twice, undo it twice, skip a
   step, try every action in every state.
10. In parallel. Run a sequential baseline first, then the same thing many
    times at once, and compare the totals. Look for read-then-write and
    check-then-act outside a transaction, and for two different operations
    racing on one record.
11. Retry. Perform a write, act as if the answer was lost, send it again.
    Look for the effect applied twice.

**Failure**
12. Error path. Search for empty catch blocks, catch-all handlers, ignored
    return values and TODO notes in handlers. Force that error and look at
    the state it leaves behind.
13. Missing object. Refer to something that does not exist, was deleted, or
    is in the wrong state. Look for an operation that half succeeds.
14. Fail open. Make the thing a check depends on fail or time out. Look for
    access granted or validation skipped.
15. Kill it. Stop the process in the middle of an operation, start it again,
    check the state.

**Numbers and time**
16. Money and rounding. Look for floating point used for money, rounding in
    a direction the rules do not state, per-line against total rounding, the
    smallest amounts, parts that do not sum to the whole.
17. Boundaries. First, last, empty, exactly at the limit, one past it; page
    N against page N+1 for a gap or an overlap.
18. Time. Another time zone, a daylight-saving change, month end, leap day;
    an expiry compared across zones.

**Configuration and supply**
19. Unsafe defaults. Start with an empty environment and no configuration.
    Look for a default secret, debug mode on, a check switched off. Search
    the tree and the history for secrets.
20. Dependencies and pipeline. Is there a lockfile and does it match the
    manifest? Do pinned versions have published advisories, and does this
    code reach the vulnerable call? Does the pipeline run text that an
    outsider controls, or use actions that are not pinned?
21. Leaks. Trigger errors and read the responses and the logs. Look for
    stack traces, secrets and personal data.

**Tests**
22. Weak tests. Read the tests for the piece and attack what they leave out.
    In a copy under `_poc`, flip one comparison or delete one line in
    critical code and run the tests: if they still pass, the test is weak.

## Working method

- Decide the proof before you run anything: write down which output would
  show the hypothesis is true. A result you have to argue for is not a proof.
- Several short, independent attempts beat one long trail.
- Plant a marker: put a unique value in the victim's data and show it in the
  attacker's output.
- Use the target's own tools for leads: compiler warnings, the type checker,
  the linter, a race detector. Their output is a lead, not a finding.
- After a hit, look for siblings. Search for the pattern you just proved,
  widen it one element at a time, and check each match. One finding lists
  every proven place; a place you did not check is listed as unchecked.
- Read the history for bug fixes, then look for call sites of the same kind
  that did not get the fix.

## Evidence

- Behaviour (`correctness`, `security`, `data-loss`): the command and its
  real output from the sandbox, with what should have happened and what did.
- Through the front door: the proof enters by something a real caller can
  reach (a route, a command, an exported function) with input a real caller
  can send. An internal function called with arguments nothing passes proves
  nothing.
- A missing check: say where you looked for it. Checks often live in
  middleware, decorators, base classes, route configuration, the data layer
  or database constraints.
- A race: the baseline run and "k of n parallel runs showed it".
- `performance`: measurements at two input sizes. Without them, `low`.
- A dependency advisory: `info` unless you show the vulnerable call is
  reached from this code.
- A mismatch (`consistency`, `completeness`): both quotations with their
  locations, for example the rule in the README and the line of code.
- A weak test: the change you made in the copy and the test run that passed.
- An error response alone (a 500, a stack trace) shows that something is
  wrong, not what. Dig until the output shows the consequence, or file what
  you really have at the severity it really supports.

## Not findings

- Style and formatting.
- Anything under `Stated limitations` in `target.md`.
- "Could be exploited if" with no path shown.
- A missing feature that no document promises and the focus does not ask for.
- A dangerous-looking call whose input never comes from outside.
- A check that is missing here but made somewhere else on the way.
- Code that runs only in tests, examples or a debug mode that is off by
  default.
- Advice to harden code that is already safe.
- Data that is meant to be public.
- A race in code that runs in a single thread.
- "No rate limit" or "could be slowed down" with no measured effect.

## Sandbox practice

- The sandbox holds what version control keeps: build output, dependency
  folders and the history are not copied. The first build therefore starts
  from nothing; build once and reuse it. If the tests need packages, install
  them inside the sandbox only (a virtual environment in your `_poc` folder).
  The same holds for a tool the target's checks call and the machine does
  not have: install it there and run the check.
- When a proof needs a whole copy of the target, take the sources only:
  `git clone -q RUN/sandbox/<target> RUN/sandbox/_poc/AGENT/src`. The copy
  in the sandbox is a git repository that holds the sources as they were
  copied, so the clone leaves the build output behind. The build output is
  gigabytes, and a copy of it fills the disk for the whole pack. Delete
  your clone when the target is reported.
- Use a fresh database or data directory for each proof.
- A proof that needs the service running starts it on a free local port and
  stops it at the end.
- A proof that needs changed code (a flipped comparison, an injected fault)
  changes a copy under `_poc`, and the finding says so.
