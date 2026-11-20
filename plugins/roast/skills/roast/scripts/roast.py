#!/usr/bin/env python3
"""roast.py: run folder, target list, attack clock, proofs and findings for the roast skill.

Standard library only. Every command except `start` takes --run <dir> and
prints the clock line first. Only the attack phase has a clock:

    [roast] attack: 12:45 left | CONTINUE

The last word is an instruction: CONTINUE, OVERTIME (the time is up, the
targets this run committed to are not all done: the pack finishes them) or
STOP (the attack is over). Outside the attack the line reads
`[roast] study: no clock`.
"""
import argparse
import filecmp
import json
import os
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PHASES = ["study", "attack", "verify", "judge", "report"]
# ponytail: one number from one measured run (five dogs, twenty minutes, a 14,000-line target).
# Recalibrate from the attack record when runs on other targets come in.
RATE = 3  # targets one dog gets through in a minute
GRACE = 0.5  # share of the asked time by which the attack may run over to finish its list
RELAY_AFTER = int(os.environ.get("ROAST_RELAY_AFTER", 15))  # targets after which a dog hands over to a fresh one: a long context costs more each step
JUDGE_LOAD = int(os.environ.get("ROAST_JUDGE_LOAD", 40))  # findings one judge can read with their proofs before its context is full
NEAR = 5  # lines within which two findings in one file are taken for the same place
POLL = float(os.environ.get("ROAST_POLL", 5))  # seconds between looks at the list during overtime
STALL = float(os.environ.get("ROAST_STALL", 900))  # a round with no time limit ends after this long with no result
MAX_SLEEP = float(os.environ.get("ROAST_MAX_SLEEP", 480))  # some harnesses cut long commands
PROOF_TIMEOUT = float(os.environ.get("ROAST_PROOF_TIMEOUT", 180))  # seconds for one proof script

STYLES = {
    "rules": "what the target says about itself against what it does",
    "input": "hostile, malformed, huge, empty and boundary input",
    "state": "twice, out of order, in parallel, retried, half-done",
    "failure": "error paths, missing things, fail-open, a kill in the middle",
    "security": "someone else's identity, injection, secrets, dependencies",
}
RESULTS = ["hit", "miss", "skip"]

SEVERITIES = ["critical", "high", "medium", "low", "info"]
STATUSES = ["open", "confirmed", "unconfirmed", "rejected", "duplicate"]
VERDICTS = STATUSES[1:]
CATEGORIES = ["correctness", "security", "consistency", "data-loss",
              "performance", "design", "completeness", "clarity"]
NEED_PROOF = {"correctness", "security", "data-loss", "performance"}  # behaviour must be shown by a run
REQUIRED = ["id", "title", "severity", "status", "category", "piece", "location", "agent", "found_at"]

DOMAINS_DIR = Path(__file__).resolve().parent.parent / "references" / "domains"
VCS_DIRS = {".git", ".hg", ".svn"}
SKIP_IN_SANDBOX = VCS_DIRS | {"node_modules", ".venv", "venv", "__pycache__",
                              ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox"}
ID = r"[a-z0-9]+(-[a-z0-9]+)*"
OWN_DIR = ".roast"  # where a run keeps its results inside the target; never copied, studied or fingerprinted


def die(msg, code=2):
    print(f"roast.py: {msg}", file=sys.stderr)
    sys.exit(code)


def stamp(t=None):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t))


def mmss(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def one_line(text):
    return " ".join(str(text).split())


def stdin_text():
    """Text piped in. An agent that forgot the heredoc must get an error, not a command that hangs."""
    try:
        if sys.stdin.isatty() or not select.select([sys.stdin], [], [], 5)[0]:
            die("nothing arrived on standard input; pipe the text in with a heredoc: <<'EOF' ... EOF")
    except (OSError, ValueError):  # select cannot watch this kind of stdin: read it as it is
        pass
    return sys.stdin.read().strip()


def text_arg(value):
    """`-` means: take the text from standard input, where no shell quoting can mangle it."""
    return stdin_text() if value == "-" else value


def write_atomic(path, text):
    tmp = Path(f"{path}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def allocate(folder, prefix, suffix):
    """Create the next free `<prefix>-NNN<suffix>` file. O_EXCL makes it safe for parallel agents."""
    n = 1
    while True:
        path = Path(folder) / f"{prefix}-{n:03d}{suffix}"
        try:
            os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return path
        except FileExistsError:
            n += 1


# ---------------------------------------------------------------- run state

def load(run):
    state = read_json(Path(run) / "run.json")
    if state is None:
        die(f"no run.json in {run}; pass the run folder printed by `start`")
    state["_run"] = str(run)  # not saved: lets the clock look at the list
    return state


def save(run, state):
    kept = {k: v for k, v in state.items() if not k.startswith("_")}
    write_atomic(Path(run) / "run.json", json.dumps(kept, ensure_ascii=False, indent=2))


def budget(run):
    """Ids of the targets this run committed to finishing, chosen when the attack started."""
    return read_json(Path(run) / "02-targets" / "budget.json", [])


def budget_left(run):
    folder = Path(run) / "02-targets"
    return [i for i in budget(run) if not (folder / f"{i}.done.json").exists()]


def clock(state, now=None):
    """Return (line, instruction). Only the attack phase is timed, and its end is soft."""
    now = time.time() if now is None else now
    attack = state.get("attack")
    if state["phase"] != "attack" or not attack:
        return f"[roast] {state['phase']}: no clock", "CONTINUE"
    if attack["end"] is None:  # no time limit: the round ends when its list is done, or when nothing moves
        folder = Path(state["_run"]) / "02-targets"
        left = len(budget_left(state["_run"]))
        moved = max([attack["start"]] + [f.stat().st_mtime for f in folder.glob("T-*.claim")]
                    + [f.stat().st_mtime for f in folder.glob("T-*.done.json")])
        if left and now - moved < STALL:
            return f"[roast] attack: no time limit, {left} target(s) left | CONTINUE", "CONTINUE"
        return "[roast] attack: over | STOP", "STOP"
    if now < attack["end"]:
        return f"[roast] attack: {mmss(attack['end'] - now)} left | CONTINUE", "CONTINUE"
    left = len(budget_left(state["_run"])) if now < attack["hard_end"] and state.get("_run") else 0
    if left:
        return (f"[roast] attack: time is up, {left} target(s) of this run's list are not done, "
                f"{mmss(attack['hard_end'] - now)} to the hard stop | OVERTIME"), "OVERTIME"
    return "[roast] attack: over | STOP", "STOP"


def dog_lines(state):
    names = list(STYLES)
    return [f"A{i + 1}: {names[i % len(names)]}" for i in range(state["agents"])]


def imp(t):
    """Importance of a target, 0 to 100. Runs made before the scale existed had two priorities."""
    return t.get("importance", 80 if t.get("priority") == "high" else 50)


def pick_budget(items, size):
    """The targets a run commits to: the most important ones, as many as the pack can get through."""
    return [t["id"] for t in sorted(items, key=lambda t: (-imp(t), t["id"]))[:size]]


def split(names, groups):
    """Deal names into at most `groups` lists, in order."""
    groups = max(1, min(groups, len(names)))
    return [names[i::groups] for i in range(groups)]


# ------------------------------------------------------ files and fingerprint

def kept_files(path):
    """Files under a directory that git does not ignore, relative to it; None if git cannot say.

    Nearly every repository ignores its build output and dependency folders, so this keeps
    gigabytes out of the sandbox, and keeps a rebuild in the original from looking like a
    change to the source, without a list of folder names to maintain.
    """
    try:
        r = subprocess.run(["git", "-C", str(path), "ls-files", "-z", "--cached", "--others",
                            "--exclude-standard"], capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    names = {n for n in r.stdout.decode("utf-8", "surrogateescape").split("\0")
             if n and OWN_DIR not in Path(n).parts}
    # ponytail: a submodule is listed as one directory entry and is dropped here.
    # Walk into it if a target with submodules ever needs them in the sandbox.
    return sorted(n for n in names if (Path(path) / n).is_file() or (Path(path) / n).is_symlink())


def walked_files(path, skip):
    out = []
    for root, dirs, files in os.walk(path):
        dirs[:] = sorted(d for d in dirs if d not in skip and d != OWN_DIR)
        out += [str((Path(root) / name).relative_to(path)) for name in files]
    return sorted(out)


def sandbox_files(src):
    """(files of a directory target that belong in the sandbox, how they were chosen)."""
    names = kept_files(src)
    if names is None:
        return walked_files(src, SKIP_IN_SANDBOX), "all but dependency and cache folders"
    return names, "what git does not ignore"


def fingerprint(path):
    # ponytail: size + mtime, not content hashes. An edit that restores both
    # goes unnoticed. Switch to sha256 if that ever matters; it costs a full read.
    path = Path(path)
    if path.is_file():
        st = path.stat()
        return {path.name: [st.st_size, st.st_mtime_ns]}
    names = kept_files(path)
    if names is None:  # not a git work tree: everything except version-control internals
        names = walked_files(path, VCS_DIRS)
    out = {}
    for rel in names:
        try:
            st = (path / rel).lstat()
        except OSError:
            continue
        out[rel] = [st.st_size, st.st_mtime_ns]
    return out


def source_changes(run, state):
    before = read_json(Path(run) / "source-fingerprint.json", {})
    changes = []
    for target in state["targets"]:
        old = before.get(target["name"], {})
        if not Path(target["path"]).exists():
            changes.append(f"{target['name']}: target is gone")
            continue
        new = fingerprint(target["path"])
        for rel in sorted(set(old) | set(new)):
            if rel not in new:
                changes.append(f"{target['name']}: removed {rel}")
            elif rel not in old:
                changes.append(f"{target['name']}: added {rel}")
            elif old[rel] != new[rel]:
                changes.append(f"{target['name']}: changed {rel}")
    return changes


def source_files(run, state):
    """Every file of every target as it is addressed in the run: `<target name>/<relative path>`."""
    before = read_json(Path(run) / "source-fingerprint.json", {})
    out = []
    for target in state["targets"]:
        is_file = Path(target["path"]).is_file()
        for rel in before.get(target["name"], {}):
            out.append(target["name"] if is_file else f"{target['name']}/{rel}")
    return sorted(out)


def under(path, roots):
    return any(path == r.rstrip("/") or path.startswith(r.rstrip("/") + "/") for r in roots)


# -------------------------------------------------------------------- study

def read_map(run):
    """(pieces, skipped, problems) from 01-study/map.json."""
    path = Path(run) / "01-study" / "map.json"
    if not path.is_file():
        return [], [], ["map.json: 01-study/map.json does not exist"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        return [], [], [f"map.json: not valid JSON ({e})"]
    pieces = data.get("pieces") if isinstance(data, dict) else None
    if not isinstance(pieces, list) or not pieces or not all(isinstance(p, dict) for p in pieces):
        return [], [], ['map.json: must be an object with a non-empty list "pieces"']
    skipped = [s for s in data.get("skipped", []) if isinstance(s, dict) and isinstance(s.get("path"), str)]
    out, seen = [], set()
    domains = sorted(p.stem for p in DOMAINS_DIR.glob("*.md"))
    for i, p in enumerate(pieces, 1):
        pid = p.get("id")
        name = f"map.json: piece {i}" + (f" `{pid}`" if isinstance(pid, str) else "")
        if not isinstance(pid, str) or not re.fullmatch(ID, pid):
            out.append(f"{name}: `id` must be lowercase letters, digits and hyphens")
        elif pid in seen:
            out.append(f"{name}: `id` is used twice")
        seen.add(pid)
        for key in ("title", "why", "domain"):
            if not isinstance(p.get(key), str) or not p[key].strip():
                out.append(f"{name}: `{key}` is missing")
        where = p.get("where")
        if not isinstance(where, list) or not where or not all(isinstance(w, str) for w in where):
            out.append(f"{name}: `where` must be a list of paths")
        if domains and isinstance(p.get("domain"), str) and p["domain"].strip() and p["domain"] not in domains:
            out.append(f"{name}: no domain file for `{p['domain']}`; available: {', '.join(domains)}")
    for s in skipped:
        if not isinstance(s.get("why"), str) or not s["why"].strip():
            out.append(f"map.json: skipped `{s['path']}` has no `why`")
    return pieces, skipped, out


def piece_ids(pieces):
    return [p["id"] for p in pieces if isinstance(p.get("id"), str)]


def piece_files(piece, files):
    where = [w for w in piece.get("where", []) if isinstance(w, str)] if isinstance(piece.get("where"), list) else []
    return [f for f in files if under(f, where)]


def files_read(run, pid):
    """Paths listed under `## Files read` in a piece's dossier, or None if there is no dossier."""
    path = Path(run) / "01-study" / f"{pid}.dossier.md"
    if not path.is_file():
        return None
    listed = sections(path.read_text(encoding="utf-8")).get("Files read", "")
    return {re.sub(r"^[-*]\s*`?([^`\s]+)`?.*$", r"\1", line.strip()) for line in listed.splitlines() if line.strip()}


def few(items, n=8):
    items = list(items)
    return ", ".join(items[:n]) + (f" and {len(items) - n} more" if len(items) > n else "")


def study_problems(run, state):
    """What still stands between the study and the attack."""
    pieces, skipped, out = read_map(run)
    if not pieces:
        return out
    files = source_files(run, state)
    roots = [w for p in pieces if isinstance(p.get("where"), list) for w in p["where"] if isinstance(w, str)]
    loose = [f for f in files if not under(f, roots + [s["path"] for s in skipped])]
    if loose:
        out.append(f"map.json: {len(loose)} file(s) belong to no piece and are not under `skipped`: {few(loose)}")
    counts = {}
    for t in targets(run):
        counts[t.get("piece")] = counts.get(t.get("piece"), 0) + 1
    for p in pieces:
        pid = p.get("id")
        if not isinstance(pid, str):
            continue
        read = files_read(run, pid)
        if read is None:
            out.append(f"{pid}: no dossier at 01-study/{pid}.dossier.md")
            continue
        unread = [f for f in piece_files(p, files) if f not in read]
        if unread:
            out.append(f"{pid}: {len(unread)} file(s) of the piece are not under `## Files read` "
                       f"in its dossier: {few(unread)}")
        if not (Path(run) / "01-study" / f"{pid}.research.md").is_file():
            out.append(f"{pid}: no research at 01-study/{pid}.research.md")
        if not counts.get(pid):
            out.append(f"{pid}: no targets were added for this piece")
    return out


# ------------------------------------------------------------------ targets

def targets(run):
    """Every target on disk, each with its claim and its result if it has them."""
    out = []
    folder = Path(run) / "02-targets"
    for path in sorted(folder.glob("T-*.json")):
        if path.name.endswith(".done.json"):
            continue
        t = read_json(path)
        if not isinstance(t, dict):  # being written right now by another agent
            continue
        claim = folder / f"{path.stem}.claim"
        t["claimed_by"] = claim.read_text(encoding="utf-8").strip() if claim.is_file() else None
        t["done"] = read_json(folder / f"{path.stem}.done.json")
        out.append(t)
    return out


def show_target(t):
    print(f"{t['id']} | piece: {t['piece']} | style: {t['style']} | importance: {imp(t)}")
    print(f"source: {t['source']}")
    print(f"try: {t['text']}")


def claim(run, tid, agent):
    try:
        fd = os.open(Path(run) / "02-targets" / f"{tid}.claim", os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(agent)
    return True


# ----------------------------------------------------------------- findings

def read_finding(path):
    text = Path(path).read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n?(.*)", text, re.S)
    if not m:
        return {}, text
    head = {}
    for line in m.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            head[key.strip()] = value.strip()
    return head, m.group(2)


def write_finding(path, head, body):
    lines = "".join(f"{k}: {v}\n" for k, v in head.items())
    write_atomic(path, f"---\n{lines}---\n{body}")


def sections(body):
    out, name = {}, None
    for line in body.splitlines():
        if line.startswith("## "):
            name = line[3:].strip()
            out.setdefault(name, [])
        elif name is not None:
            out[name].append(line)
    return {k: re.sub(r"<!--.*?-->", "", "\n".join(v), flags=re.S).strip() for k, v in out.items()}


def findings(run):
    out = []
    for path in sorted((Path(run) / "04-findings").glob("F-*.md")):
        head, body = read_finding(path)
        out.append((path, head, body))
    return out


def add_note(body, status, note):
    headings = re.findall(r"^## (.+)$", body, re.M)
    if not headings or headings[-1].strip() != "Verification":
        body = body.rstrip("\n") + "\n\n## Verification\n"
    return body.rstrip("\n") + f"\n- {stamp()} {status}: {one_line(note)}\n"


def finding_problems(fid, head, body, ids, pieces):
    """What is wrong with one finding. `pieces` is the set of known piece ids, or None."""
    if not head:
        return [f"{fid}: no header"]
    out = []
    for key in REQUIRED:
        if not head.get(key):
            out.append(f"{fid}: missing `{key}`")
    if head.get("id") and head["id"] != fid:
        out.append(f"{fid}: header id is {head['id']}")
    for key, allowed in (("severity", SEVERITIES), ("status", STATUSES), ("category", CATEGORIES)):
        if head.get(key) and head[key] not in allowed:
            out.append(f"{fid}: {key} `{head[key]}` is not one of {', '.join(allowed)}")
    if pieces is not None and head.get("piece") and head["piece"] not in pieces:
        out.append(f"{fid}: piece `{head['piece']}` is not in map.json; pieces are: {', '.join(sorted(pieces))}")
    if head.get("status") == "duplicate" and head.get("duplicate_of") not in ids:
        out.append(f"{fid}: duplicate_of does not name an existing finding")
    filled = sections(body)
    needed = ["What is wrong"] + (["Evidence"] if head.get("proof", "none") == "none" else [])
    for name in needed:
        if not filled.get(name):
            out.append(f"{fid}: section `{name}` is empty")
    if head.get("status") in ("confirmed", "rejected") and not filled.get("Verification"):
        out.append(f"{fid}: status is {head['status']} but `Verification` is empty")
    return out


def problems(run, state):
    """Everything wrong with the map and the findings on disk, as a list of strings."""
    pieces, _, out = read_map(run)
    known = set(piece_ids(pieces)) if pieces else None
    items = findings(run)
    ids = {path.stem for path, _, _ in items}
    for path, head, body in items:
        out += finding_problems(path.stem, head, body, ids, known)
    return out


# ------------------------------------------------------------------- proofs

def proof_path(run, value):
    """A proof is a script the agent wrote under sandbox/_poc. Returns its absolute path."""
    run = Path(run).resolve()
    poc = run / "sandbox" / "_poc"
    path = Path(value)
    path = (path if path.is_absolute() else run / path).resolve()
    if poc.resolve() not in path.parents:  # the sandbox may be a link to a folder outside the run
        die(f"a proof must be a file under {poc}; got {value}")
    if not path.is_file():
        die(f"no such proof script: {path}")
    return poc / path.relative_to(poc.resolve())


def run_proof(run, path):
    """Run one proof the same way for its author and for `verify`. Returns (exit code, output tail)."""
    path = Path(path)
    if path.suffix == ".py":
        cmd = [sys.executable, str(path)]
    elif path.suffix == ".sh":
        cmd = ["sh", str(path)]
    else:
        cmd = [str(path)]
    sandbox = Path(run).resolve() / "sandbox"
    with tempfile.TemporaryDirectory(prefix="roast-proof-") as tmp:
        env = {**os.environ, "ROAST_SANDBOX": str(sandbox), "ROAST_TMP": tmp}
        try:
            r = subprocess.run(cmd, cwd=sandbox, env=env, capture_output=True, text=True,
                               errors="replace", timeout=PROOF_TIMEOUT)
        except subprocess.TimeoutExpired:
            return 124, f"timed out after {PROOF_TIMEOUT:g} s"
        except OSError as e:
            return 126, f"could not be run: {e}"
    return r.returncode, (r.stdout + r.stderr).strip()[-3000:]


def restore_sources(run, state):
    """Put back any target file the pack changed in the sandbox. Returns the paths restored."""
    restored = []
    for target in state["targets"]:
        src, dst = Path(target["path"]), Path(run) / "sandbox" / target["name"]
        pairs = [(src, dst)] if src.is_file() else [(src / rel, dst / rel) for rel in sandbox_files(src)[0]]
        for a, b in pairs:
            if not a.is_file() or a.is_symlink():
                continue
            if not b.is_file() or not filecmp.cmp(a, b, shallow=False):
                b.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(a, b)  # not copy2: a fresh mtime makes build tools rebuild from the clean file
                restored.append(str(b.relative_to(Path(run) / "sandbox")))
    return restored


# ----------------------------------------------------------------- commands

def cmd_start(a):
    if a.agents < 1:
        die("agents must be at least 1")
    if a.minutes <= 0:
        die("minutes must be positive")

    paths = [Path(t).expanduser().resolve() for t in (a.targets or ["."])]
    targets_, taken = [], set()
    for p in paths:
        if not p.exists():
            die(f"target does not exist: {p}")
        name, n = p.name or "root", 2
        while name in taken:
            name, n = f"{p.name}-{n}", n + 1
        taken.add(name)
        targets_.append({"name": name, "path": str(p)})

    if a.out:
        out = Path(a.out).expanduser().resolve()
        for p in paths:
            if p.is_dir() and (out == p or p in out.parents):
                die(f"the run folder would be inside the target {p}; the source is read-only. "
                    f"Leave --out away to keep the run in the target's own {OWN_DIR} folder")
        label = targets_[0]["name"] + (f"+{len(targets_) - 1}" if len(targets_) > 1 else "")
        run = out / f"{label}-{time.strftime('%Y%m%d-%H%M%S')}"
    else:  # with the project, named by the second the run started
        home = paths[0] if paths[0].is_dir() else paths[0].parent
        run = home / OWN_DIR / "artifacts" / time.strftime("%Y-%m-%d_%H-%M-%S")
    run.mkdir(parents=True, exist_ok=False)
    for sub in ("00-sources", "01-study", "02-targets", "03-attack", "04-findings", "05-verify"):
        (run / sub).mkdir()

    state = {"id": run.name, "started": stamp(), "agents": a.agents, "minutes": a.minutes,
             "targets": targets_, "focus": text_arg(a.focus) or "", "phase": "study", "attack": None, "rounds": []}
    save(run, state)
    prints = {x["name"]: fingerprint(x["path"]) for x in targets_}
    write_atomic(run / "source-fingerprint.json", json.dumps(prints))

    print(clock(state)[0])
    print(f"run folder: {run}")
    print(f"targets:    {', '.join(x['path'] for x in targets_)}")
    print(f"agents:     at most {a.agents} at once, in every phase")
    print(f"attack:     about {a.minutes:g} minutes with {a.agents} dog(s), on about "
          f"{round(a.agents * a.minutes * RATE)} targets. Study, verification and the report are not timed.")
    if state["focus"]:
        print(f"focus:      {state['focus']}")
    if a.study_from:
        reuse_study(Path(a.study_from).expanduser().resolve(), run, prints)
    print(f"next: `sandbox --run {run}`, then `crew --run {run}`")


def reuse_study(old, run, prints):
    """Carry the study of an earlier run over, and say which pieces touch files changed since."""
    if not (old / "01-study" / "map.json").is_file():
        die(f"no study to reuse in {old}")
    shutil.copytree(old / "01-study", run / "01-study", dirs_exist_ok=True)
    n = 0
    for path in sorted((old / "02-targets").glob("T-*.json")):
        if not path.name.endswith(".done.json"):
            shutil.copy2(path, run / "02-targets" / path.name)
            n += 1
    before = read_json(old / "source-fingerprint.json", {})
    changed = sorted(f"{name}/{rel}" for name, files in prints.items()
                     for rel in set(files) | set(before.get(name, {}))
                     if files.get(rel) != before.get(name, {}).get(rel))
    print(f"study reused from {old}: {n} targets, none of them tried yet in this run")
    if changed:
        pieces = read_map(run)[0]
        stale = [p["id"] for p in pieces if isinstance(p.get("id"), str) and piece_files(p, changed)]
        for pid in stale:  # their study is out of date: `crew` will ask for these pieces again
            for name in (f"{pid}.dossier.md", f"{pid}.research.md"):
                (run / "01-study" / name).unlink(missing_ok=True)
        print(f"{len(changed)} file(s) changed since that study: {few(changed)}")
        print(f"read again before the attack: {', '.join(stale) or 'no piece covers them; update map.json'}")


def place_sandbox(run):
    """Make RUN/sandbox. For a run kept inside its target it is a link to a folder outside.

    A copy that sits inside the original is not isolated: git, test runners and build tools
    look for their configuration in the folders above them and would reach the original.
    """
    box = Path(run).resolve() / "sandbox"
    if OWN_DIR not in box.parts:
        box.mkdir(exist_ok=True)
    elif box.is_symlink():
        Path(os.path.realpath(box)).mkdir(parents=True, exist_ok=True)  # the work folder may have been wiped
    else:
        parent = Path(os.environ.get("ROAST_WORK") or "~/.cache/roast").expanduser()
        parent.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix=f"{box.parent.name}-", dir=parent))
        if box.exists():  # the proof scripts `clean` left behind
            for child in box.iterdir():
                shutil.move(str(child), str(work / child.name))
            box.rmdir()
        box.symlink_to(work)
    return box


def copy_entry(src, dst, rel):
    """Copy one file of a target into its sandbox copy. False if it was left out.

    A link is never copied as it is: an absolute one would still lead into the original, and
    whatever the pack wrote through it in the sandbox would land there.
    """
    a, b = src / rel, dst / rel
    if not a.is_symlink():
        shutil.copy2(a, b)
        return True
    real = Path(os.path.realpath(a))
    if src in real.parents:  # it stays inside the target: the copy gets a link to its own file
        os.symlink(os.path.relpath(dst / real.relative_to(src), b.parent), b)
        return True
    if real.is_file():  # it leads out of the target: the copy gets the content, not the way out
        shutil.copy2(real, b)
        return True
    return False


def cmd_sandbox(a):
    state = load(a.run)
    print(clock(state)[0])
    box = place_sandbox(a.run)
    if box.is_symlink():
        print(f"the sandbox is kept outside the target, in {os.path.realpath(box)}")
    for target in state["targets"]:
        src, dst = Path(target["path"]), Path(a.run) / "sandbox" / target["name"]
        if dst.exists():
            print(f"exists: {dst}")
        elif src.is_dir():
            names, how = sandbox_files(src)
            dst.mkdir(parents=True)
            left_out = []
            for rel in names:
                (dst / rel).parent.mkdir(parents=True, exist_ok=True)
                if not copy_entry(src, dst, rel):
                    left_out.append(rel)
            print(f"copied: {dst} ({len(names) - len(left_out)} files, {how})")
            if left_out:
                print(f"left out: {len(left_out)} link(s) that lead out of the target to no file: {few(left_out)}")
        else:
            shutil.copy2(src, dst)
            print(f"copied: {dst}")
    (Path(a.run) / "sandbox" / "_poc").mkdir(exist_ok=True)
    print("Run builds, tests and proofs here only. The source stays read-only.")


def cmd_status(a):
    state = load(a.run)
    print(clock(state)[0])
    pieces, skipped, _ = read_map(a.run)
    files = source_files(a.run, state)
    asked = "no time limit" if state.get("minutes") is None else f"about {state['minutes']:g} min"
    print(f"phase: {state['phase']} | at most {state['agents']} agent(s) at once | attack: {asked}")
    print(f"study: {len(pieces)} piece(s), {len(files)} file(s) in the target(s), {len(skipped)} skipped path(s)")
    items = targets(a.run)
    by = lambda key, value: [t for t in items if t.get(key) == value]
    n = lambda result, group=items: sum(1 for t in group if t["done"] and t["done"].get("result") == result)
    print(f"targets: {len(items)} | tried {n('hit') + n('miss')} ({n('hit')} hit, {n('miss')} held) | "
          f"skipped {n('skip')} | in hand {sum(1 for t in items if t['claimed_by'] and not t['done'])} | "
          f"free {sum(1 for t in items if not t['claimed_by'])}")
    chosen = budget(a.run)
    if chosen:
        print(f"this round's list: {len(chosen)} target(s), {len(budget_left(a.run))} not done | "
              f"left outside it: {sum(1 for t in items if not t['done'] and t['id'] not in chosen)}")
    for style in STYLES:
        group = by("style", style)
        print(f"  {style:<9} {len(group):>4} target(s), {sum(1 for t in group if not t['claimed_by']):>4} free")
    for pid in piece_ids(pieces):
        group = by("piece", pid)
        print(f"  piece {pid}: {len(group)} target(s), {n('hit', group) + n('miss', group)} tried")
    found = findings(a.run)
    counts = {s: sum(1 for _, h, _ in found if h.get("status") == s) for s in STATUSES}
    print("findings: " + (", ".join(f"{n} {s}" for s, n in counts.items() if n) or "none"))
    print("pack: " + " | ".join(dog_lines(state)))


def cmd_crew(a):
    """Who to launch now: one line per agent, `id | role | assignment`."""
    state = load(a.run)
    print(clock(state)[0])
    n, study = state["agents"], Path(a.run) / "01-study"
    pieces, _, bad = read_map(a.run)
    ids = piece_ids(pieces)
    if state["phase"] == "study":
        if not pieces:
            print("Launch the scout:\nscout | scout | the whole target")
            return
        if bad:
            print("map.json has problems. Continue the scout with these lines:\n" + "\n".join(bad))
            return
        if state.get("rebuild"):
            print("The sandbox was cleaned after the last round and is a fresh copy now. Launch the scout to "
                  "build it again, then run `phase attack`:\nscout | scout | rebuild")
            return
        unread = [i for i in ids if not (study / f"{i}.dossier.md").is_file()]
        if unread:
            print(f"Launch the readers, at most {n} at once; launch the next when one hands back:")
            print("\n".join(f"read-{i} | reader | Piece: {i}" for i in unread))
            return
        bare = [i for i in ids if not (study / f"{i}.research.md").is_file()]
        if bare:
            print(f"Launch the researchers, at most {n} at once:")
            for k, group in enumerate(split(bare, max(1, n // 2)), 1):
                print(f"web-{k} | researcher | Pieces: {' '.join(group)}")
            return
        print("The study has an agent for every piece. Run `check study`, then `phase attack`.")
    elif state["phase"] == "attack":
        print(f"The pack, {n} at once. A dog that hands back `stopped by: relay` is replaced by a fresh one "
              f"with the same style and the next id (A1, A1-2, A1-3):")
        print("\n".join(f"{line.split(': ')[0]} | dog | Style: {line.split(': ')[1]}" for line in dog_lines(state)))
    elif state["phase"] == "judge":
        found = [f for f in findings(a.run) if not f[1].get("judged_at")]  # earlier rounds are judged already
        if not found:
            print("No findings wait for a verdict: no judge is needed. Run `phase report`.")
            return
        count = {}
        for _, head, _ in found:
            count[head.get("piece", "?")] = count.get(head.get("piece", "?"), 0) + 1
        judges = min(n, len(count), -(-len(found) // JUDGE_LOAD))
        if judges <= 1:
            print(f"{len(found)} finding(s). Launch one judge:\njudge | judge | all findings")
            return
        groups = [[] for _ in range(judges)]
        for piece in sorted(count, key=lambda x: -count[x]):  # the heaviest piece goes to the lightest judge
            min(groups, key=lambda g: sum(count[x] for x in g)).append(piece)
        print(f"{len(found)} finding(s). Launch {judges} judges together:")
        for k, group in enumerate(groups, 1):
            print(f"judge-{k} | judge | Pieces: {' '.join(group)}")
        print("When they have all handed back, launch one more:\njudge | judge | summary")
    else:
        print(f"No agents are launched in the {state['phase']} phase.")


def cmd_more(a):
    """Another round on the same study: the pack goes after what is still not tried."""
    state = load(a.run)
    if a.agents < 1:
        die("agents must be at least 1")
    if a.minutes is not None and a.minutes <= 0:
        die("minutes must be positive; leave them out for no time limit")
    if state["phase"] == "study" and not state.get("rounds"):
        die("this run has not had its first attack yet; go on with `crew`")
    if state["phase"] == "attack" and clock(state)[1] != "STOP":
        die("the attack is still running")
    folder = Path(a.run) / "02-targets"
    left = [t for t in targets(a.run) if not t["done"]]
    if not left:
        print(clock(state)[0])
        print("Every target on the list has been tried: nothing is left to finish.")
        return
    for t in left:  # a dog that never reported no longer holds its target
        (folder / f"{t['id']}.claim").unlink(missing_ok=True)
    cleaned = any(not (Path(a.run) / "sandbox" / t["name"]).exists() for t in state["targets"])
    state.update(agents=a.agents, minutes=a.minutes, phase="study", attack=None)
    if cleaned:
        state["rebuild"] = True
    save(a.run, state)
    cmd_sandbox(a)
    high = sum(1 for t in left if imp(t) >= 70)
    print(f"{len(left)} target(s) are left, {high} of them of importance 70 or more. This round: at most {a.agents} agent(s), "
          + ("no time limit, all of them." if a.minutes is None else f"about {a.minutes:g} minutes."))
    print(f"next: `crew --run {a.run}`")


def cmd_files(a):
    """The files the study has to account for, each with its size and the pieces that own it."""
    state = load(a.run)
    print(clock(state)[0])
    pieces, skipped, _ = read_map(a.run)
    shown = lines = 0
    for f in source_files(a.run, state):
        owners = [p["id"] for p in pieces if isinstance(p.get("id"), str) and piece_files(p, [f])]
        if a.piece and a.piece not in owners:
            continue
        try:
            n = (Path(a.run) / "sandbox" / f).read_bytes().count(b"\n")
        except OSError:
            n = 0  # not copied into the sandbox
        owner = ",".join(owners) or ("skipped" if under(f, [x["path"] for x in skipped]) else "NO PIECE")
        print(f"{n:>7}  {f}  [{owner}]")
        shown, lines = shown + 1, lines + n
    print(f"{shown} file(s), {lines} line(s)")


def cmd_check(a):
    state = load(a.run)
    print(clock(state)[0])
    found = (study_problems(a.run, state) if a.what == "study" else []) + \
            (problems(a.run, state) if a.what == "findings" else [])
    for p in found:
        print(p)
    print(f"{a.what}: {len(found)} problem(s)")
    sys.exit(1 if found else 0)


def cmd_phase(a):
    state = load(a.run)
    started = None
    if a.name == "attack" and state["phase"] != "attack":
        bad = study_problems(a.run, state)
        if bad:
            print(clock(state)[0])
            print("\n".join(bad))
            print("Still in study. Give each line to the agent it names, then run `phase attack` again.")
            sys.exit(1)
        items = [t for t in targets(a.run) if not t["done"]]
        minutes = state.get("minutes")
        # a target for every dog at least; with no time asked, everything that is left
        size = len(items) if minutes is None else max(state["agents"], round(state["agents"] * minutes * RATE))
        chosen = pick_budget(items, size)
        write_atomic(Path(a.run) / "02-targets" / "budget.json", json.dumps(chosen))
        now = time.time()
        state["attack"] = {"start": now, "end": None, "hard_end": None} if minutes is None else \
            {"start": now, "end": now + minutes * 60, "hard_end": now + minutes * 60 * (1 + GRACE)}
        state.setdefault("rounds", []).append({"agents": state["agents"], "minutes": minutes,
                                               "committed": len(chosen), "started": stamp(now)})
        state.pop("rebuild", None)
        started = (len(chosen), len(items))
    state["phase"] = a.name
    save(a.run, state)
    print(clock(state)[0])
    if a.name == "attack":
        attack = state["attack"]
        hhmm = lambda t: time.strftime("%H:%M:%S", time.localtime(t))
        if started and attack["end"] is None:
            print(f"This round's list: all {started[0]} target(s) that are left. There is no time limit: "
                  f"the attack runs until the list is done.")
        elif started:
            print(f"This round's list: {started[0]} of {started[1]} target(s) "
                  f"({state['agents']} dogs x {state['minutes']:g} min x {RATE} a minute); the rest is the reserve.")
        if attack["end"] is not None:
            print(f"The attack runs until {hhmm(attack['end'])}, and past it until the list is done, "
                  f"{hhmm(attack['hard_end'])} at the latest.")
        print("Run `crew` for the pack, launch it, then keep `wait` running in the background.")


def cmd_wait(a):
    state = load(a.run)
    attack = state.get("attack")
    if state["phase"] != "attack" or not attack:
        print(clock(state)[0])
        print("Nothing to wait for: only the attack has a clock.")
        return
    now = time.time()
    deadline = now + MAX_SLEEP
    unlimited = attack["end"] is None
    if not unlimited and now < attack["end"]:
        time.sleep(min(attack["end"] - now, MAX_SLEEP))
    while True:  # past the end, or with no end: look at the list until it is done, the hard stop comes, or the sleep cap
        state = load(a.run)  # the orchestrator may have moved on while this slept
        line, word = clock(state)
        watching = word == "OVERTIME" or (unlimited and word == "CONTINUE")
        if state["phase"] != "attack" or not watching or time.time() >= deadline:
            break
        time.sleep(POLL)
    print(line)
    if state["phase"] != "attack":
        print("The attack phase has been left. Do not run `wait` again.")
    elif word == "CONTINUE":
        print("No checkpoint yet: nothing has changed. Run `wait` again.")
    elif word == "OVERTIME":
        print("The time is up but this run's list is not done: the pack goes on. Run `wait` again.")
    else:
        print("The attack is over. When every dog has handed back, run `phase verify`.")


def cmd_target_add(a):
    state = load(a.run)
    print(clock(state)[0])
    pieces = read_map(a.run)[0]
    if pieces and a.piece not in piece_ids(pieces):
        die(f"piece `{a.piece}` is not in map.json; pieces are: {', '.join(piece_ids(pieces))}")
    text = one_line(text_arg(a.text))
    if len(text) < 15:
        die("the target text must say what to try and what would show a defect")
    if not 0 <= a.importance <= 100:
        die("importance is a number from 0 to 100")
    path = allocate(Path(a.run) / "02-targets", "T", ".json")
    target = {"id": path.stem, "piece": a.piece, "style": a.style, "importance": a.importance,
              "source": one_line(a.source), "text": text, "added_by": a.agent, "added_at": stamp()}
    write_atomic(path, json.dumps(target, ensure_ascii=False, indent=2))
    print(f"{path.stem} added ({a.piece}, {a.style}, importance {a.importance})")


def cmd_target_list(a):
    state = load(a.run)
    print(clock(state)[0])
    items = targets(a.run)
    if a.piece:
        items = [t for t in items if t["piece"] == a.piece]
    if not items:
        print("no targets yet")
    for t in sorted(items, key=lambda t: (-imp(t), t["id"])):
        state_ = (t["done"]["result"] if t["done"] else f"in hand ({t['claimed_by']})" if t["claimed_by"] else "free")
        print(f"{t['id']}  {state_:<14} {t['piece']:<18} {t['style']:<9} {imp(t):>3}  {t['text'][:110]}")


def cmd_take(a):
    state = load(a.run)
    line, word = clock(state)
    print(line)
    folder = Path(a.run) / "02-targets"

    if a.done:  # the result of the previous target comes in with the request for the next one
        if not a.result or not a.note:
            die("--done needs --result and --note")
        note = one_line(text_arg(a.note))
        claim_file = folder / f"{a.done}.claim"
        if not claim_file.is_file() or claim_file.read_text(encoding="utf-8").strip() != a.agent:
            die(f"{a.done} is not in the hands of {a.agent}")
        if a.result == "hit" and not (a.finding and (Path(a.run) / "04-findings" / f"{a.finding}.md").is_file()):
            die("a hit needs --finding with the id of the finding you filed for it")
        ran = None
        if a.result == "miss":
            if not a.proof:
                die("a miss needs --proof with the script you ran against this target. "
                    "Reading the code is not an attempt: run it, or report `skip` and say why it cannot be run.")
            ran = str(proof_path(a.run, a.proof).relative_to(Path(a.run).resolve()))
        done = {"agent": a.agent, "result": a.result, "note": note, "finding": a.finding, "proof": ran, "at": stamp()}
        write_atomic(folder / f"{a.done}.done.json", json.dumps(done, ensure_ascii=False))
        target = read_json(folder / f"{a.done}.json", {})
        with open(Path(a.run) / "03-attack" / f"{a.agent}.log.md", "a", encoding="utf-8") as f:
            f.write(f"- {time.strftime('%H:%M:%S')} | {a.done} | {target.get('piece', '-')} | {a.result} | {note}\n")
        print(f"{a.done} recorded: {a.result}")
        word = clock(state)[1]  # that result may have been the last one the list was waiting for

    if state["phase"] != "attack":
        print(f"No targets are handed out in the {state['phase']} phase. Hand back now.")
        return
    if word == "STOP":
        print("STOP: no new targets. Run `leave` and hand back what it prints.")
        return

    items = targets(a.run)
    held = [t for t in items if t["claimed_by"] == a.agent and not t["done"]]
    if held:  # one target in hand at a time: nothing is dropped on the floor
        print(f"You still hold {held[0]['id']}. Finish it and report it with --done before taking another:")
        return show_target(held[0])
    if sum(1 for t in items if t["done"] and t["done"].get("agent") == a.agent) >= RELAY_AFTER:
        print(f"RELAY: you have reported {RELAY_AFTER} targets. A fresh dog takes over from here: "
              f"run `leave` and hand back what it prints.")
        return
    chosen = set(budget(a.run))
    if a.target:
        if word == "OVERTIME" and a.target not in chosen:
            die("the time is up: only the targets of this run's list are still handed out")
        wanted = [t for t in items if t["id"] == a.target]
        if not wanted:
            die(f"no such target: {a.target}")
        if not claim(a.run, a.target, a.agent):
            die(f"{a.target} is already taken")
        return show_target(wanted[0])

    busy = {}
    for t in items:
        if t["claimed_by"]:
            busy[t["piece"]] = busy.get(t["piece"], 0) + 1
    free = sorted((t for t in items if not t["claimed_by"] and (word == "CONTINUE" or t["id"] in chosen)),
                  # the most important first; within ten points of importance a dog prefers its own style
                  key=lambda t: (t["id"] not in chosen, -(imp(t) // 10), t["style"] != a.style, -imp(t),
                                 busy.get(t["piece"], 0), t["id"]))
    for t in free:
        if claim(a.run, t["id"], a.agent):  # another dog may have taken it a moment ago
            return show_target(t)
    if word == "OVERTIME":
        print("Nothing is left to take: the rest of the list is in other dogs' hands. "
              "Run `leave` and hand back what it prints.")
    else:
        print("The list is empty. Make your own target from what has been found so far: "
              "`target add`, then `take --target <its id>`.")


def cmd_leave(a):
    """Tell a dog whether it may hand back, and give it the hand-back lines."""
    state = load(a.run)
    line, word = clock(state)
    print(line)
    items = targets(a.run)
    held = [t["id"] for t in items if t["claimed_by"] == a.agent and not t["done"]]
    mine = [t["done"] for t in items if t["done"] and t["done"].get("agent") == a.agent]
    count = lambda result: sum(1 for d in mine if d.get("result") == result)
    filed = [path.stem for path, head, _ in findings(a.run) if head.get("agent") == a.agent]
    chosen = set(budget(a.run))
    in_attack = state["phase"] == "attack"
    free = sum(1 for t in items if not t["claimed_by"] and (word == "CONTINUE" or t["id"] in chosen))
    relay = in_attack and word != "STOP" and len(mine) >= RELAY_AFTER
    running = in_attack and (word == "CONTINUE" or (word == "OVERTIME" and free))
    if held:
        print(f"STAY. You still hold {', '.join(held)}. Report each with `take --done` first, then run `leave` again.")
        return
    if running and not relay and not (a.nothing_left and not free):
        print(f"STAY. The attack is still running and {free} target(s) are free. Do not hand back.")
        print(f"Run `take --agent {a.agent} --style <your style>` now."
              + ("" if free else " The list is empty: add targets of your own with `target add` and take them."))
        return
    print("LEAVE. Hand back exactly these three lines and nothing else:")
    print(f"targets: {count('hit') + count('miss')} tried ({count('hit')} hit, {count('miss')} held), {count('skip')} skipped")
    print(f"findings: {' '.join(filed) or 'none'}")
    print(f"stopped by: {'relay' if relay else 'nothing left to try' if running else 'clock'}")


def cmd_summary(a):
    state = load(a.run)
    print(clock(state)[0])
    text = stdin_text()
    if len(text) < 200:
        die("the summary comes on standard input, the whole page")
    write_atomic(Path(a.run) / "SUMMARY.md", text + "\n")
    print(f"summary saved: {Path(a.run) / 'SUMMARY.md'}")


def cmd_finding_new(a):
    state = load(a.run)
    print(clock(state)[0])
    body = stdin_text()
    if not body:
        die("the body of the finding comes on standard input: `## What is wrong` and `## Impact`")
    pieces = read_map(a.run)[0]
    if pieces and a.piece not in piece_ids(pieces):
        die(f"piece `{a.piece}` is not in map.json; pieces are: {', '.join(piece_ids(pieces))}")
    place = lambda loc: (loc.rsplit(":", 1)[0], int(loc.rsplit(":", 1)[1])) if re.search(r":\d+$", loc) else (loc, None)
    here = place(one_line(a.location))
    for path, head, _ in findings(a.run):
        there = place(head.get("location", ""))
        close = here[0] == there[0] and (None in (here[1], there[1]) or abs(here[1] - there[1]) <= NEAR)
        if close and path.stem not in (a.other or []):
            print(f"{path.stem} is already filed at {head.get('location')}: {head.get('title')}")
            die(f"nothing was filed. The same defect: report your target with `--result hit --finding {path.stem}`. "
                f"A different defect at the same place: file again with `--not {path.stem}` added.", 1)
    proof, output = "none", ""
    if a.proof == "none":
        if a.category in NEED_PROOF:
            die(f"a `{a.category}` finding needs a proof script: behaviour is shown by running it. "
                f"`--proof none` is for {', '.join(sorted(set(CATEGORIES) - NEED_PROOF))}.")
    else:
        path = proof_path(a.run, a.proof)
        code, output = run_proof(a.run, path)
        if code != 0:
            print(output)
            die(f"the proof exited {code}, so nothing was filed. A proof exits 0 only when the defect is there.", 1)
        proof = str(path.relative_to(Path(a.run).resolve()))
        body += f"\n\n## Proof output\n\n```\n$ {proof}\n{output}\n```"

    path = allocate(Path(a.run) / "04-findings", "F", ".md")
    head = {"id": path.stem, "title": one_line(a.title), "severity": a.severity, "status": "open",
            "category": a.category, "piece": a.piece, "location": one_line(a.location),
            "agent": a.agent, "found_at": stamp(), "proof": proof,
            "proof_result": "passed" if proof != "none" else "none"}
    if a.target:
        head["target"] = a.target
    body = "\n" + body + "\n"
    write_finding(path, head, body)
    print(path)
    bad = finding_problems(path.stem, head, body, {path.stem}, set(piece_ids(pieces)) if pieces else None)
    if bad:
        print("\n".join(bad))
        print("The finding is saved. Edit that file now to fix the lines above.")


def cmd_finding_list(a):
    state = load(a.run)
    print(clock(state)[0])
    items = findings(a.run)
    if not items:
        print("no findings yet")
    for path, head, _ in items:
        print(f"{path.stem}  {head.get('status', '?'):<11} {head.get('severity', '?'):<8} "
              f"proof:{head.get('proof_result', '?'):<6} {head.get('piece', '?'):<16} "
              f"{head.get('location', '?')}  {head.get('title', '')}")


def cmd_verify(a):
    state = load(a.run)
    print(clock(state)[0])
    restored = restore_sources(a.run, state)
    if restored:
        print(f"{len(restored)} target file(s) had been changed in the sandbox and were put back: {few(restored)}")
    write_atomic(Path(a.run) / "05-verify" / "restored.txt", "\n".join(restored) + ("\n" if restored else ""))
    passed = failed = 0
    for path, head, body in findings(a.run):
        if head.get("status") != "open" or head.get("proof", "none") == "none":
            continue
        proof = Path(a.run).resolve() / head["proof"]
        code, output = run_proof(a.run, proof) if proof.is_file() else (127, "the proof script is gone")
        write_atomic(Path(a.run) / "05-verify" / f"{path.stem}.txt", f"exit {code}\n{output}\n")
        head["verified_at"] = stamp()
        if code == 0:
            head["proof_result"], passed = "passed", passed + 1
        else:
            head["proof_result"], head["status"], failed = "failed", "unconfirmed", failed + 1
            body = add_note(body, "unconfirmed", f"the proof exited {code} when re-run on clean sources; "
                                                 f"output in 05-verify/{path.stem}.txt")
        write_finding(path, head, body)
        print(f"{path.stem}: proof {'passed' if code == 0 else f'FAILED (exit {code})'}")
    print(f"{passed} proof(s) passed, {failed} failed. Findings without a proof go to the judge as they are.")


def cmd_clean(a):
    """Free the disk: drop the sandbox except the proof scripts the record points at."""
    state = load(a.run)
    print(clock(state)[0])
    run = Path(a.run).resolve()
    keep = {run / head["proof"] for _, head, _ in findings(run) if head.get("proof", "none") != "none"}
    keep |= {run / t["done"]["proof"] for t in targets(run) if t["done"] and t["done"].get("proof")}
    freed = removed = 0
    for root, dirs, files in os.walk(run / "sandbox", topdown=False):
        for name in files:
            path = Path(root) / name
            if path not in keep:
                freed, removed = freed + path.lstat().st_size, removed + 1
                path.unlink()
        for name in dirs:
            path = Path(root) / name
            if path.is_symlink():
                path.unlink()
            elif not any(path.iterdir()):
                path.rmdir()
    box = run / "sandbox"
    if box.is_symlink():  # bring what is left, the proof scripts, home to the run folder
        work = Path(os.path.realpath(box))
        box.unlink()
        if work.is_dir():
            shutil.move(str(work), str(box))
    print(f"removed {removed} file(s), {freed / 1e6:.0f} MB; kept {len(keep)} proof script(s). "
          f"To run a proof again, run `sandbox` first and build the target as 01-study/target.md says.")


def cmd_verdict(a):
    state = load(a.run)
    print(clock(state)[0])
    path = Path(a.run) / "04-findings" / f"{a.id}.md"
    if not path.is_file():
        die(f"no such finding: {a.id}")
    head, body = read_finding(path)
    if a.status == "duplicate":
        other = Path(a.run) / "04-findings" / f"{a.duplicate_of}.md"
        if not a.duplicate_of or a.duplicate_of == a.id or not other.is_file():
            die("duplicate needs --duplicate-of with the id of another existing finding")
        head["duplicate_of"] = a.duplicate_of
    if a.severity and a.severity != head.get("severity"):
        head["severity_was"], head["severity"] = head.get("severity", ""), a.severity
    head["status"], head["judged_at"] = a.status, stamp()
    note = text_arg(a.note)
    if note:
        body = add_note(body, a.status, note)
    write_finding(path, head, body)
    print(f"{a.id}: {a.status}, severity {head.get('severity')}")


def cmd_check_source(a):
    state = load(a.run)
    print(clock(state)[0])
    changes = source_changes(a.run, state)
    for c in changes:
        print(c)
    print("source unchanged" if not changes else f"SOURCE CHANGED: {len(changes)} difference(s)")
    sys.exit(1 if changes else 0)


def cmd_report(a):
    state = load(a.run)
    print(clock(state)[0])
    run = Path(a.run)
    items = sorted(findings(run), key=lambda x: (SEVERITIES.index(x[1]["severity"])
                   if x[1].get("severity") in SEVERITIES else len(SEVERITIES), x[0].stem))
    bad, changes = problems(run, state), source_changes(run, state)
    pieces = read_map(run)[0]
    tried = targets(run)

    def full(group):
        out = []
        for path, head, body in group:
            out.append(f"### {path.stem} [{head.get('severity', '?')}] {head.get('title', '')}\n")
            was = f" (was {head['severity_was']})" if head.get("severity_was") else ""
            out.append(f"- Status: {head.get('status', '?')}{was} | Proof: {head.get('proof_result', '?')}")
            out.append(f"- Location: `{head.get('location', '?')}`")
            out.append(f"- Piece: {head.get('piece', '?')} | Category: {head.get('category', '?')}"
                       f" | Found by: {head.get('agent', '?')} at {head.get('found_at', '?')}"
                       + (f" | Target: {head['target']}" if head.get("target") else "") + "\n")
            out.append(re.sub(r"^## ", "#### ", body.strip(), flags=re.M) + "\n")
        return out or ["None.\n"]

    by_status = lambda *names: [x for x in items if x[1].get("status") in names]
    md = [f"# Roast report: {state['id']}\n"]
    md.append(f"- Targets: {', '.join('`' + t['path'] + '`' for t in state['targets'])}")
    rounds = state.get("rounds") or [{"agents": state["agents"], "minutes": state.get("minutes"), "committed": 0}]
    md.append("- Attack rounds: " + "; ".join(
        f"{r['agents']} agents at once, " + ("no time limit" if r["minutes"] is None else f"about {r['minutes']:g} min")
        + f", {r['committed']} target(s) committed to" for r in rounds))
    md.append(f"- Focus: {state['focus'] or 'none'}")
    md.append(f"- Started: {state['started']} | Report assembled: {stamp()}\n")

    summary = run / "SUMMARY.md"
    if summary.is_file() and summary.read_text(encoding="utf-8").strip():
        md.append("## Summary by the judge\n")
        md.append(re.sub(r"^#", "###", summary.read_text(encoding="utf-8").strip(), flags=re.M) + "\n")

    md.append("## Findings in numbers\n")
    md.append("| Severity | " + " | ".join(STATUSES) + " | total |")
    md.append("|---|" + "---|" * (len(STATUSES) + 1))
    for sev in SEVERITIES:
        row = [sum(1 for _, h, _ in items if h.get("severity") == sev and h.get("status") == st)
               for st in STATUSES]
        md.append(f"| {sev} | " + " | ".join(map(str, row)) + f" | {sum(row)} |")
    md.append(f"\n{len(items)} finding(s) in total.\n")

    md.append("## Confirmed findings\n")
    md += full(by_status("confirmed"))
    md.append("## Not confirmed\n")
    md.append("Unconfirmed: the proof failed when re-run on clean sources. Open: the judge gave no verdict.\n")
    md += full(by_status("unconfirmed", "open"))
    md.append("## Rejected and duplicate findings\n")
    dropped = by_status("rejected", "duplicate")
    for path, head, _ in dropped:
        ref = f" of {head['duplicate_of']}" if head.get("duplicate_of") else ""
        md.append(f"- {path.stem} {head.get('status')}{ref}: {head.get('title', '')}")
    md.append("" if dropped else "None.\n")

    md.append("## Coverage\n")
    chosen = set(budget(run))
    if chosen:
        mine = [t for t in tried if t["id"] in chosen]
        got = lambda group, *res: sum(1 for t in group if t["done"] and t["done"].get("result") in res)
        rest = [t for t in tried if t["id"] not in chosen]
        md.append(f"The last round committed to {len(mine)} target(s): {got(mine, 'hit', 'miss')} were run, "
                  f"{got(mine, 'skip')} skipped, {len(mine) - got(mine, 'hit', 'miss', 'skip')} not finished. "
                  f"Outside that list, over all rounds: {got(rest, 'hit', 'miss')} run, {got(rest, 'skip')} skipped, "
                  f"{len(rest) - got(rest, 'hit', 'miss', 'skip')} never taken.\n")
    md.append("Hit: a defect was proven. Held: a script was run and the target behaved correctly. "
              "Skipped: taken but not run.\n")
    md.append("| Piece | Targets | Hit | Held | Skipped | Never taken | Findings |")
    md.append("|---|---|---|---|---|---|---|")
    names = piece_ids(pieces)
    for pid in names + sorted({t["piece"] for t in tried} - set(names)):
        group = [t for t in tried if t["piece"] == pid]
        done = [t for t in group if t["done"]]
        res = lambda r: sum(1 for t in done if t["done"].get("result") == r)
        md.append(f"| {pid} | {len(group)} | {res('hit')} | {res('miss')} | {res('skip')} | "
                  f"{len(group) - len(done)} | {sum(1 for _, h, _ in items if h.get('piece') == pid)} |")
    md.append("")

    md.append("## Attack record\n")
    md.append("Every target that was taken, in the order of the list.\n")
    for pid in names + sorted({t["piece"] for t in tried} - set(names)):
        done = [t for t in tried if t["piece"] == pid and t["done"]]
        if not done:
            continue
        md.append(f"### {pid}\n")
        for t in done:
            d = t["done"]
            ref = f" -> {d['finding']}" if d.get("finding") else ""
            md.append(f"- {t['id']} [{t['style']}] {d.get('result')}{ref} by {d.get('agent')}: "
                      f"{t['text'][:140]} | {str(d.get('note', ''))[:200]}")
        md.append("")
    row = lambda t: f"- {t['id']} [{t['piece']}, {t['style']}, importance {imp(t)}] {t['text'][:160]}"
    left = [t for t in tried if not t["done"] and t["id"] in chosen]
    md.append(f"## Committed to but not finished: {len(left)} target(s)\n")
    md += [row(t) for t in left] + [""]
    left = [t for t in tried if not t["done"] and t["id"] not in chosen]
    md.append(f"## Never taken: {len(left)} target(s)\n")
    md += [row(t) for t in left] + [""]

    md.append("## Source integrity\n")
    md.append("The targets match the fingerprint taken at start.\n" if not changes else
              "**The targets changed during the run:**\n\n" + "\n".join(f"- {c}" for c in changes) + "\n")
    restored = (run / "05-verify" / "restored.txt")
    if restored.is_file() and restored.read_text(encoding="utf-8").strip():
        md.append("Files of the sandbox copy that the pack had changed and that were put back before "
                  "the proofs were re-run:\n\n"
                  + "\n".join(f"- {r}" for r in restored.read_text(encoding="utf-8").split()) + "\n")
    if bad:
        md.append("## Validation problems\n")
        md += [f"- {p}" for p in bad] + [""]

    write_atomic(run / "REPORT.md", "\n".join(md))
    print(run / "REPORT.md")
    res = lambda r: sum(1 for t in tried if t["done"] and t["done"].get("result") == r)
    left = sum(1 for t in tried if not t["done"])
    print("Numbers for the closing summary:")
    print(f"targets: {len(tried)} on the list | {res('hit') + res('miss')} run "
          f"({res('hit')} broke the target, {res('miss')} held) | {res('skip')} skipped | {left} never tried")
    print("findings: " + ", ".join(f"{len(by_status(st))} {st}" for st in STATUSES if by_status(st))
          + f" | {len(items)} in all")
    print("confirmed by level: " + " | ".join(
        f"{sev} {sum(1 for _, h, _ in by_status('confirmed') if h.get('severity') == sev)}" for sev in SEVERITIES))
    print("pieces (targets | run | broke the target | never tried | confirmed findings):")
    for pid in names + sorted({t["piece"] for t in tried} - set(names)):
        group = [t for t in tried if t["piece"] == pid]
        got = lambda *r: sum(1 for t in group if t["done"] and t["done"].get("result") in r)
        print(f"  {pid}: {len(group)} | {got('hit', 'miss')} | {got('hit')} | "
              f"{sum(1 for t in group if not t['done'])} | "
              f"{sum(1 for _, h, _ in by_status('confirmed') if h.get('piece') == pid)}")
    seconds = lambda text: time.mktime(time.strptime(text, "%Y-%m-%dT%H:%M:%S"))
    ends = sorted(seconds(t["done"]["at"]) for t in tried if t["done"] and t["done"].get("at"))
    for n, r in enumerate(rounds, 1):
        asked = "no time limit" if r["minutes"] is None else f"asked {r['minutes']:g} min"
        took = ""
        if r.get("started"):  # a round lasts from its start to the last result reported before the next round
            later = seconds(rounds[n]["started"]) if n < len(rounds) and rounds[n].get("started") else float("inf")
            mine = [e for e in ends if seconds(r["started"]) <= e < later]
            took = f", took {(mine[-1] - seconds(r['started'])) / 60:.1f} min" if mine else ""
        print(f"attack round {n}: {r['agents']} agents at once, {asked}{took}, {r['committed']} target(s) committed to")
    print(f"studied: {len(names)} piece(s), {len(source_files(run, state))} file(s) | "
          f"whole run so far: {(time.time() - seconds(state['started'])) / 60:.0f} min")
    print(f"source: {'unchanged' if not changes else 'CHANGED'}")
    if left:
        print(f"to finish the {left} left ({sum(1 for t in tried if not t['done'] and imp(t) >= 70)} of them of "
              f"importance 70 or more): `more <agents> [<minutes>] --run {run}`; without minutes the pack "
              f"works until the list is done")


# --------------------------------------------------------------------- main

def agent_id(value):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise argparse.ArgumentTypeError("agent id: letters, digits, - and _ only")
    return value


def main():
    ap = argparse.ArgumentParser(prog="roast.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = argparse.ArgumentParser(add_help=False)
    run.add_argument("--run", required=True, help="run folder printed by `start`")

    p = sub.add_parser("start", help="create the run folder")
    p.add_argument("agents", type=int, help="how many agents may work at once, in every phase")
    p.add_argument("minutes", type=float, help="the wished length of the attack; nothing else is timed")
    p.add_argument("targets", nargs="*", help="paths; default is the current directory")
    p.add_argument("--focus", help="the user's own wishes, stored verbatim; `-` reads them from stdin")
    p.add_argument("--out", help="parent of the run folder; by default the run is kept with the "
                                 "first target, in .roast/artifacts/<start time>")
    p.add_argument("--study-from", help="an earlier run folder of the same target whose study is reused")
    p.set_defaults(fn=cmd_start)

    for name, fn, text in (
            ("sandbox", cmd_sandbox, "copy the targets into the run folder"),
            ("status", cmd_status, "phase, clock, targets and findings in numbers"),
            ("crew", cmd_crew, "which agents to launch now: id, role and assignment"),
            ("clean", cmd_clean, "free the disk: drop the sandbox, keep the proof scripts"),
            ("wait", cmd_wait, "during the attack: sleep until its end, then until the list is done"),
            ("verify", cmd_verify, "put changed sandbox files back and re-run every proof"),
            ("check-source", cmd_check_source, "fail if a target changed since start"),
            ("report", cmd_report, "assemble REPORT.md")):
        sub.add_parser(name, parents=[run], help=text).set_defaults(fn=fn)

    p = sub.add_parser("files", parents=[run], help="lines, path and owning pieces of every target file")
    p.add_argument("--piece", help="only the files of this piece")
    p.set_defaults(fn=cmd_files)

    p = sub.add_parser("more", parents=[run], help="another attack round on what is still not tried")
    p.add_argument("agents", type=int, help="how many agents may work at once")
    p.add_argument("minutes", type=float, nargs="?", help="the wished length; left out: until the list is done")
    p.set_defaults(fn=cmd_more)

    p = sub.add_parser("check", parents=[run], help="say what is missing or malformed")
    p.add_argument("what", choices=["study", "findings"])
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("phase", parents=[run], help="declare the phase; `attack` starts the clock")
    p.add_argument("name", choices=PHASES)
    p.set_defaults(fn=cmd_phase)

    t = sub.add_parser("target", help="add or list things to try").add_subparsers(dest="tcmd", required=True)
    p = t.add_parser("add", parents=[run])
    p.add_argument("--agent", required=True, type=agent_id)
    p.add_argument("--piece", required=True)
    p.add_argument("--style", required=True, choices=list(STYLES),
                   help="; ".join(f"{k}: {v}" for k, v in STYLES.items()))
    p.add_argument("--importance", required=True, type=int, metavar="0-100",
                   help="how much it matters that this is tried; the pack takes the list from the top")
    p.add_argument("--source", required=True, help="where it comes from: path:line in the target, or a URL")
    p.add_argument("text", help="what to try and what would show a defect; `-` reads it from stdin")
    p.set_defaults(fn=cmd_target_add)
    p = t.add_parser("list", parents=[run])
    p.add_argument("--piece")
    p.set_defaults(fn=cmd_target_list)

    p = sub.add_parser("take", parents=[run], help="report the last target and get the next one")
    p.add_argument("--agent", required=True, type=agent_id)
    p.add_argument("--style", required=True, choices=list(STYLES))
    p.add_argument("--done", help="id of the target you have just finished")
    p.add_argument("--result", choices=RESULTS,
                   help="hit: defect proven and filed; miss: you ran it and it held; skip: it cannot be run here")
    p.add_argument("--note", help="what you did and what happened, one line; `-` reads it from stdin")
    p.add_argument("--finding", help="with --result hit: the finding you filed")
    p.add_argument("--proof", help="with --result miss: the script under sandbox/_poc that you ran")
    p.add_argument("--target", help="take this target instead of the next one in line")
    p.set_defaults(fn=cmd_take)

    p = sub.add_parser("leave", parents=[run], help="a dog asks whether it may hand back")
    p.add_argument("--agent", required=True, type=agent_id)
    p.add_argument("--nothing-left", action="store_true",
                   help="the list is empty and you have no target of your own left to add")
    p.set_defaults(fn=cmd_leave)

    sub.add_parser("summary", parents=[run], help="the judge's page, on stdin").set_defaults(fn=cmd_summary)

    f = sub.add_parser("finding", help="file or list findings").add_subparsers(dest="fcmd", required=True)
    p = f.add_parser("new", parents=[run], help="body on stdin; the proof is run before anything is filed")
    p.add_argument("--agent", required=True, type=agent_id)
    p.add_argument("--piece", required=True)
    p.add_argument("--severity", required=True, choices=SEVERITIES)
    p.add_argument("--category", required=True, choices=CATEGORIES)
    p.add_argument("--location", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--proof", required=True,
                   help="a script under sandbox/_poc that exits 0 only when the defect is there, or `none`")
    p.add_argument("--target", help="the target this finding came from")
    p.add_argument("--not", dest="other", action="append", metavar="F-ID",
                   help="a finding already filed at this place that is a different defect; repeatable")
    p.set_defaults(fn=cmd_finding_new)
    f.add_parser("list", parents=[run]).set_defaults(fn=cmd_finding_list)

    p = sub.add_parser("verdict", parents=[run], help="the judge's decision on a finding")
    p.add_argument("id")
    p.add_argument("status", choices=VERDICTS)
    p.add_argument("--severity", choices=SEVERITIES)
    p.add_argument("--duplicate-of")
    p.add_argument("--note", help="the reason, one line; goes under Verification; `-` reads it from stdin")
    p.set_defaults(fn=cmd_verdict)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
