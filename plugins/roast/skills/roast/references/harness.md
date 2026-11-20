# Harness

`SKILL.md` uses four verbs and three agent types. This file says what they
are in your harness.

| Verb | What it must do |
|---|---|
| launch an agent | Start a subagent with a message; get its final message back |
| continue an agent | Send a further message to the same subagent, with its context kept |
| stop an agent | End a subagent that is still running |
| run in the background | Start a shell command and be woken when it exits |

Each role wants a model that fits its work. Reading and judging need the
strongest model; searching and attacking need many cheap hands.

| Agent type | Roles | Model | Effort | Tools it needs |
|---|---|---|---|---|
| reader | `scout`, `reader` | strongest available | medium | read, search, shell, write |
| researcher | `researcher` | mid-tier | medium | the same, plus web search and web fetch |
| dog | `dog` | mid-tier | medium | read, search, shell, write |
| judge | `judge` | strongest available | high | read, search, shell, write |

## Claude Code

| Verb | Tool |
|---|---|
| launch an agent | `Agent`. Several `Agent` calls in one message run in parallel |
| continue an agent | `SendMessage` to the agent's id or name |
| stop an agent | `TaskStop` |
| run in the background | `Bash` with `run_in_background: true`. You are woken when the command exits; do not poll it |

Agent types, in this order of preference:

1. The roast plugin is installed: your list of agent types holds
   `roast:reader`, `roast:researcher`, `roast:dog` and `roast:judge`. Use
   them. Model, effort and tools are set in their definitions; pass no
   `model`.
2. Otherwise use `general-purpose` and pass `model` on every launch: `opus`
   for reader and judge, `sonnet` for researcher and dog. Never launch
   without `model`: the agent would inherit yours, which is the most
   expensive choice for a pack.

Give each agent its agent id as its name, so that you can continue it.

## Any other harness

Use its own subagent and background-command tools for the four verbs, and
its nearest models for the table above. Where something is missing:

| Missing | Do this instead |
|---|---|
| continue an agent | Launch a fresh agent with the same launch message, and add the previous hand-back of that agent under the assignment line |
| run in the background | Skip `wait`. Run `ROAST status --run RUN` after every hand-back and act on the clock's last word. Run `verify` in the foreground |
| stop an agent | Let it finish. It sees the clock and stops by itself |
| web search | Launch the researchers anyway. They write from what they know and say so; tell the user at the end that the research was done without the web |
| subagents altogether | Tell the user that roast needs subagents, and ask whether to run the roles one after another in this session instead. In that mode you follow each role file yourself, in the order of `SKILL.md` |
