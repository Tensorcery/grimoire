# Domain: instructions

For pieces made of text that an agent or a model is meant to follow: skills,
system prompts, agent definitions, role files, prompt templates, files like
`AGENTS.md` or `CLAUDE.md`, tool descriptions, runbooks an agent works from.

Such text has one reader who cannot ask back. The agent that receives it has
this text, its tools and nothing else, and it will do something with every
sentence, the unclear ones too. Where two sentences disagree it picks one
without saying so. A defect here is a place where an agent that follows the
text as written does the wrong thing, cannot go on, or is left to guess.

Who reads what: the scout reads Surfaces; the reader reads In the dossier
and Angles of attack; the researcher reads Angles of attack; a dog reads
Working method, Evidence and Not findings; the judge reads Evidence and Not
findings.

## Surfaces

Kinds of pieces worth their own entry in `map.json`:

- The entry text: what starts the work and decides who does what (a skill's
  main file, an orchestrator's prompt).
- Role texts: what each agent is told, one role together with the shared
  rules it reads.
- The contract with a program: every place where the text says what a
  command does, prints or refuses.
- Hand-offs: the formats one agent or program writes and another reads.
- What selects the text and what it may use: a description, a trigger,
  frontmatter, a routing table, a list of tools.

Rank a piece higher when many agents read it, when it steers work that
cannot be undone, and when what it asks for is checked by nothing but the
agent's own word.

## In the dossier

- Under `Stated rules`, every instruction is a rule: what the agent must do,
  must not do, and in which order.
- `Enforced at` names what would notice if the agent did not follow it: a
  check in a program, a file the next step cannot do without, a format a
  parser refuses, another agent that looks at the result. A rule in a text
  is not a control. `No enforcement found` is common here and is not a
  target by itself; it becomes one where skipping the rule is the easier
  way to look finished (angle 19).
- Under `How it works`, trace one whole run: who reads which file when, what
  each one has in hand at that moment, what it passes on, and what tells it
  that it is finished.
- The styles of targets fit like this: `rules` for contradictions, broken
  references and text against program; `state` for order, long runs and
  hand-offs; `failure` for the ways out; `input` and `security` for text
  from outside and for tools.

## Angles of attack

Each one that applies to a piece becomes a target. "Look for" names the signal.

**The reader has only this text**
1. Cold read. Read the file as the agent that receives it, knowing nothing
   else. Look for a term, a file, a value or a tool that the text uses but
   neither defines nor hands over.
2. References. Take every path, command, flag, section name and tool name
   the text gives. Look for one that does not exist or is spelled another
   way where it is defined. Run each command word for word. Look also for a
   file the agent needs that no sentence tells it to read, or tells it to
   read too late.
3. Examples against rules. An agent copies an example before it obeys a
   rule. Look for an example that breaks a rule of the text around it.

**Rules against each other**
4. Contradiction. Look for an instruction that requires what another one
   forbids, in one file or across the files one agent reads. The agent will
   not report the conflict; it will follow one of them.
5. Who wins. List every source that tells this agent what to do: the launch
   message, its role text, the shared rules, the user's own words, the
   content it works on. Look for two that can disagree with no stated order
   between them.
6. Dead zone. Look for rules that are each sound and together leave no
   allowed way to do a step that is required.
7. Modes. Where a phase, a mode or a flag changes what applies, look for a
   base rule of which the text does not say whether it still holds there.
8. Names. Look for one thing under two names, and one name for two things.
9. Copies. Look for the same rule, limit or default written out in several
   places, in other files and in a program, and check that the copies still
   agree. Small differences in wording count.

**Steps that cannot be done**
10. Tools, both ways. Compare each step with the tools and permissions the
    agent is given. Look for a step that needs one it does not have, and
    for a tool that no step needs, above all one that deletes, sends or
    spends.
11. Order. Look for a step that needs the result of a later step, or a file
    that somebody else writes later.
12. Missing input. Look for a step that needs a value nobody gives.
13. A program's job. Look for a step that has to come out exact and is left
    to the agent's reading: counting, adding up, sorting, comparing two
    lists, picking the next free number, deciding by a threshold.

**The ways out**
14. No exit. For each step ask what the text says when the command fails,
    the file is missing, the result is empty, the time is up, or there is
    nothing to do. Look for a branch with no instruction: there the agent
    improvises.
15. No end. Look for what tells each agent that it is finished. Look for a
    loop with no stopping rule, for "until it is done" with no test for
    done, and for an agent that may launch agents with nothing that bounds
    how many.
16. Go on or ask. Look for a text that tells the agent both to carry on
    until the work is done and to check before it acts, and for one that
    never says in which case to stop and ask.
17. Soft exception. Look for a rule with a way out that swallows it
    ("unless needed", "where appropriate", "if possible"), and for a must
    that is written as a preference.
18. Nobody checks. For each result ask who looks at it and against what.
    Look for a result that only its author sees, and for a check that tests
    the form of an answer and not whether it is true.
19. The easier way. Ask where an agent could look finished without having
    done the work: report without running, skip for lack of time, fill a
    template with nothing behind it, change the check instead of the thing
    checked. Look for a rule that nothing checks on such a path.

**Long runs**
20. A rule said once. Look for a rule that is stated at the start and
    needed many steps later, after the agent's context has filled up or
    been cut down, and that nothing repeats where it applies.
21. Done twice. Ask how the agent knows what is already done when it is
    interrupted, continued or replaced by another. Look for work that would
    be repeated or lost because the state is in the agent's head and not on
    disk.

**Hand-offs**
22. Format. Where one side writes what another reads, compare the writer's
    template with the reader's parser or expectation. Look for a field, a
    name or a case in one that the other does not know, and for a result
    whose form is not stated at all.
23. What gets lost. Look for something the next reader needs and the
    hand-off leaves out or forbids.
24. Text from outside. Look for a place where content of the target, the
    output of a tool or a web page reaches the agent without being marked
    as data, in a position where it could be taken for an instruction.

**Reach and weight**
25. Selection. Read what decides that this text is used. Look for requests
    it would wrongly fire on, requests it would miss, and a summary of the
    procedure that lets the agent skip the text itself.
26. Role bleed. Look for an instruction that belongs to another role, and
    for a role that is told to do what a rule elsewhere forbids it.
27. Too much in one text. Look for one text that serves several readers or
    several jobs, so that each reader carries what it does not need, and
    for the one rule that matters buried under the rest.

**Text against the world**
28. Whatever the text says a program does, prints or refuses: run it and
    compare. Look for a promise the program does not keep and for behaviour
    the text does not mention but the agent will meet. The same holds for
    any other fact the text states about files, tools or the environment.

## Working method

- Read as the recipient. Open the files in the order the agent gets them,
  and nothing else, before you judge any sentence.
- Walk one run on paper: follow the text step by step with only the tools
  that agent has, and note the first place where you would have to guess.
- For a reference, search; for a command, run it in the sandbox; for a
  format, put the writer's example through the reader.
- For a contradiction, write down both sentences with their places before
  you decide that they collide: many pairs differ in scope, not in content.
- After a hit, look for siblings: the same gap in the other role files.

## Evidence

- What a run can show is shown by a run: a file that is not there, a
  command that fails, an example a parser refuses, a program that does
  something else than the text says. Write a proof script and use the
  category `correctness`.
- A contradiction or a mismatch (`consistency`): both quotations with their
  locations, and what an agent does if it follows the first and if it
  follows the second.
- A gap (`completeness`): the step, quoted, the situation it leaves open,
  and how that situation comes about in a normal run.
- An unclear sentence (`clarity`): the sentence and two readings that the
  text supports equally, with what each leads to. One reading and a wish
  for better words is not a finding.
- A rule that nothing checks is a finding only together with the easier way
  it leaves open and what is lost when an agent takes it.
- Severity goes by what the misled agent would do. `high`: following the
  text as written breaks a rule the same text states, or loses work.
  `medium`: the agent has to guess at a step that matters and one of the
  plausible guesses is wrong. `low`: a gap whose obvious filling is the
  right one. `info`: wording.

## Not findings

- Tone, length, formatting and the choice of one prompting technique over
  another.
- "Could be clearer" with no second reading.
- A typing mistake that changes no meaning.
- A missing rule for a situation that cannot come about.
- What the text itself lists as a limitation.
- A guess about how some model would behave, with nothing in the text that
  supports it.
