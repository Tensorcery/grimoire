#!/usr/bin/env python3
"""End-to-end checks of roast.py without any agents. Run: python3 plugins/roast/tests/test_roast.py"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROAST = Path(__file__).resolve().parent.parent / "skills" / "roast" / "scripts" / "roast.py"


def roast(*args, stdin=None, ok=True, env=None):
    r = subprocess.run([sys.executable, str(ROAST), *map(str, args)], input=stdin or "", capture_output=True,
                       text=True, env={**os.environ, **(env or {})})
    if ok is not None and (r.returncode == 0) != ok:
        raise AssertionError(f"{args}: exit {r.returncode}\n{r.stdout}{r.stderr}")
    return r.stdout + r.stderr


def run_folder(out):
    return Path(next(l.split(": ", 1)[1].strip() for l in out.splitlines() if l.startswith("run folder")))


def has(out, *needles):
    for needle in needles:
        if needle not in out:
            raise AssertionError(f"missing: {needle}\n{out}")


def write_map(run, pieces, skipped=()):
    data = {"pieces": [{"id": i, "title": i.title(), "where": where, "why": "can break", "domain": "code"}
                       for i, where in pieces.items()],
            "skipped": [{"path": p, "why": "vendored"} for p in skipped]}
    (run / "01-study" / "map.json").write_text(json.dumps(data))


def write_dossier(run, piece, files):
    listed = "".join(f"- `{f}` - read in full\n" for f in files)
    (run / "01-study" / f"{piece}.dossier.md").write_text(f"# {piece}\n\n## Files read\n{listed}\n## Stated rules\nNone.\n")
    (run / "01-study" / f"{piece}.research.md").write_text("## Queries\n- none\n")


def add_target(run, piece, style="rules", importance=50, text="call refund with a negative amount; a defect if accepted",
               agent="R1", **kw):
    return roast("target", "add", "--run", run, "--agent", agent, "--piece", piece, "--style", style,
                 "--importance", importance, "--source", "proj/app.py:1", text, **kw)


def taken(out):
    """Id of the target a `take` handed out, or None."""
    return next((l.split(" | ")[0] for l in out.splitlines() if l.startswith("T-") and " | piece: " in l), None)


BODY = "## What is wrong\nRefund accepts a negative amount.\n\n## Impact\nMoney is created.\n"
EVIDENCE = "\n## Evidence\n`proj/app.py:1` mixes transport and storage.\n"


def one_file_run(tmp, minutes):
    """A run on a single file with its study done, ready for `phase attack`."""
    src = tmp / "one.txt"
    src.write_text("x")
    run = run_folder(roast("start", 5, minutes, src, "--out", tmp / "roasts"))
    write_map(run, {"whole": ["one.txt"]})
    write_dossier(run, "whole", ["one.txt"])
    add_target(run, "whole"), add_target(run, "whole")
    roast("sandbox", "--run", run)
    (run / "sandbox" / "_poc" / "A1").mkdir()
    (run / "sandbox" / "_poc" / "A1" / "try.py").write_text("raise SystemExit(1)\n")
    return run


class RoastScript(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.tmp = Path(folder.name)

    def test_whole_run(self):
        tmp = self.tmp
        src = tmp / "proj"
        (src / ".git").mkdir(parents=True)
        (src / ".git" / "index").write_text("x")
        (src / "node_modules").mkdir()
        (src / "node_modules" / "dep.js").write_text("x")
        (src / "app.py").write_text("print(1)\n")
        (src / "lib.py").write_text("print(2)\n")

        # ---- start: the run folder may never be created inside a target
        has(roast("start", 5, 30, src, "--out", src / "out", ok=False), "read-only")
        has(roast("start", "low", 30, src, "--out", tmp / "roasts", ok=False), "invalid int value")
        focus = "ещё посмотри архитектуру и раскладку по папкам"
        # `-` takes the focus from stdin, so no shell quoting can damage it
        out = roast("start", 7, 30, src, "--focus", "-", "--out", tmp / "roasts", stdin=focus + "\n")
        has(out, "at most 7 at once", "on about 630 targets")
        run = run_folder(out)
        state = json.loads((run / "run.json").read_text(encoding="utf-8"))
        self.assertTrue(state['focus'] == focus and state['agents'] == 7 and (state['phase'] == 'study') and (state['attack'] is None))
        crew = lambda: roast("crew", "--run", run)
        has(crew(), "scout | scout | the whole target")
        self.assertEqual(out.splitlines()[0], '[roast] study: no clock', out)

        roast("sandbox", "--run", run)
        box = run / "sandbox" / "proj"
        self.assertTrue((box / 'app.py').is_file() and (not (box / '.git').exists()) and (not (box / 'node_modules').exists()))
        poc = run / "sandbox" / "_poc" / "A1"
        poc.mkdir(parents=True)

        # ---- the attack cannot start until the study is complete, and the script says what is missing
        has(roast("phase", "attack", "--run", run, ok=False), "does not exist", "Still in study")
        (run / "01-study" / "map.json").write_text(json.dumps({"pieces": [{"id": "Bad Id", "domain": "cobol"}]}))
        has(roast("phase", "attack", "--run", run, ok=False),
            "lowercase", "`title` is missing", "`where` must be", "no domain file for `cobol`")
        write_map(run, {"core": ["proj/app.py"]})
        has(roast("check", "study", "--run", run, ok=False), "2 file(s) belong to no piece", "core: no dossier")
        write_map(run, {"core": ["proj/app.py"], "lib": ["proj/lib.py"]}, skipped=["proj/node_modules"])
        has(crew(), "at most 7 at once", "read-core | reader | Piece: core", "read-lib | reader | Piece: lib")
        write_dossier(run, "core", ["proj/app.py"])
        (run / "01-study" / "core.research.md").unlink()
        self.assertNotIn('read-core', crew())
        write_dossier(run, "core", ["proj/app.py"])
        write_dossier(run, "lib", [])
        out = roast("check", "study", "--run", run, ok=False)
        has(out, "lib: 1 file(s) of the piece are not under `## Files read`", "core: no targets", "lib: no targets")
        self.assertTrue('belong to no piece' not in out and 'core: 1 file' not in out, out)
        write_dossier(run, "lib", ["proj/lib.py"])
        (run / "01-study" / "lib.research.md").unlink()
        has(roast("check", "study", "--run", run, ok=False), "lib: no research at 01-study/lib.research.md")
        has(crew(), "web-1 | researcher | Pieces: lib")
        write_dossier(run, "lib", ["proj/lib.py"])
        out = roast("files", "--run", run)
        has(out, "1  proj/app.py  [core]", "1  proj/lib.py  [lib]", "0  proj/node_modules/dep.js  [skipped]", "3 file(s), 2 line(s)")
        has(roast("files", "--run", run, "--piece", "lib"), "1 file(s), 1 line(s)")
        has(roast("take", "--run", run, "--agent", "A1", "--style", "rules"), "No targets are handed out in the study phase")

        # ---- targets: parallel agents never get the same id
        with ThreadPoolExecutor(10) as pool:
            outs = list(pool.map(lambda i: add_target(run, "core"), range(10)))
        ids = sorted(o.strip().splitlines()[-1].split()[0] for o in outs)
        self.assertEqual(ids, [f'T-{n:03d}' for n in range(1, 11)], ids)
        add_target(run, "lib", "security")
        has(add_target(run, "lib", "security", 101, ok=False), "from 0 to 100")
        add_target(run, "lib", "security", 90, "-", stdin="send `id` as the name; a defect if it isn't escaped: $HOME\n")
        self.assertIn("isn't escaped: $HOME", (run / '02-targets' / 'T-012.json').read_text(encoding='utf-8'))
        has(add_target(run, "nowhere", ok=False), "is not in map.json")
        has(add_target(run, "lib", text="try it", ok=False), "what would show a defect")
        has(roast("check", "study", "--run", run), "study: 0 problem(s)")

        # ---- the attack: the clock starts here and the pack is named
        has(crew(), "Run `check study`, then `phase attack`")
        out = roast("phase", "attack", "--run", run)
        self.assertTrue(out.splitlines()[0].startswith('[roast] attack: ') and out.splitlines()[0].endswith('CONTINUE'), out)
        has(out, "This round's list: 12 of 12 target(s)", "Run `crew` for the pack")
        has(crew(), "A1 | dog | Style: rules", "A5 | dog | Style: security", "A7 | dog | Style: input", "stopped by: relay")

        take = lambda agent, style, *more, **kw: roast("take", "--run", run, "--agent", agent, "--style", style, *more, **kw)
        (poc / "ok.py").write_text("print('defect shown')\n")
        (poc / "bad.py").write_text("import sys\nprint('held')\nsys.exit(3)\n")
        self.assertEqual(taken(take('A5', 'security')), 'T-012')  # the most important first
        has(take("A5", "security", "--done", "T-001", "--result", "miss", "--note", "x", ok=False), "not in the hands of A5")
        has(take("A5", "security", "--done", "T-012", "--result", "hit", "--note", "x", ok=False), "a hit needs --finding")
        # a miss is a script that was run, not a look at the code
        has(take("A5", "security", "--done", "T-012", "--result", "miss", "--note", "read it", ok=False), "a miss needs --proof")
        # one target in hand at a time: asking again shows the same one
        out = take("A5", "security")
        has(out, "You still hold T-012")
        self.assertEqual(taken(out), 'T-012')
        has(roast("leave", "--run", run, "--agent", "A5"), "STAY. You still hold T-012")
        has(roast("leave", "--run", run, "--agent", "A9"), "STAY. The attack is still running and 11 target(s) are free")
        out = take("A5", "security", "--done", "T-012", "--result", "miss", "--proof", poc / "bad.py", "--note", "-",
                   stdin="name isn't executed: `id` $HOME stays text\n")
        has(out, "T-012 recorded: miss")
        self.assertEqual(taken(out), 'T-011')
        has((run / "03-attack" / "A5.log.md").read_text(encoding="utf-8"), "| T-012 | lib | miss | name isn't executed: `id` $HOME")

        with ThreadPoolExecutor(10) as pool:  # ten dogs at once never get the same target
            got = sorted(taken(o) for o in pool.map(lambda i: take(f"D{i}", "rules"), range(10)))
        self.assertEqual(got, [f'T-{n:03d}' for n in range(1, 11)], got)
        has(take("A1", "rules"), "The list is empty")

        # a dog that runs dry adds its own target and takes it
        add_target(run, "lib", "input", agent="A1")
        self.assertEqual(taken(take('A1', 'input', '--target', 'T-013')), 'T-013')
        has(take("A2", "input", "--target", "T-013", ok=False), "already taken")
        has(take("A2", "input", "--target", "T-999", ok=False), "no such target")

        # ---- findings: behaviour is accepted only with a proof that exits 0
        (poc / "dirty.py").write_text("import os, sys\nsys.exit(0 if 'HACKED' in "
                                      "open(os.environ['ROAST_SANDBOX'] + '/proj/app.py').read() else 1)\n")
        (tmp / "evil.py").write_text("print(1)\n")
        new = lambda piece, category, proof, title="t", severity="high", *more, at=None, **kw: roast(
            "finding", "new", "--run", run, "--agent", "A1", "--piece", piece, "--severity", severity,
            "--category", category, "--location", f"proj/app.py:{at or 1}", "--title", title, "--proof", proof, *more, **kw)
        has(new("core", "correctness", "none", stdin=BODY, ok=False), "needs a proof script")
        has(new("core", "correctness", poc / "bad.py", stdin=BODY, ok=False), "held", "exited 3, so nothing was filed")
        has(new("core", "correctness", tmp / "evil.py", stdin=BODY, ok=False), "must be a file under")
        has(new("core", "correctness", poc / "ok.py", ok=False), "comes on standard input")
        self.assertFalse(list((run / '04-findings').iterdir()))

        with ThreadPoolExecutor(6) as pool:
            outs = list(pool.map(lambda i: new("core", "correctness", "sandbox/_poc/A1/ok.py", f"t{i}", at=1 + 100 * i, stdin=BODY), range(6)))
        ids = sorted(Path(o.strip().splitlines()[-1]).stem for o in outs)
        self.assertEqual(ids, [f'F-{n:03d}' for n in range(1, 7)], ids)
        has((run / "04-findings" / "F-001.md").read_text(), "## Proof output", "defect shown", "proof_result: passed")

        (box / "app.py").write_text("print('HACKED')\n")  # a dog leaves the sandbox dirty: the proof passes only for it
        # a second finding at the same place is refused until its author says it is another defect
        out = new("core", "security", poc / "dirty.py", "works only on a dirty sandbox", stdin=BODY, ok=False)
        has(out, "is already filed at proj/app.py:1", "--result hit --finding F-00", "--not F-00")
        others = [x for n in range(1, 10) for x in ("--not", f"F-{n:03d}")]
        new("core", "security", poc / "dirty.py", "works only on a dirty sandbox", "high", *others[:12], stdin=BODY)  # F-007
        out = new("lib", "design", "none", "layers: mixed", "low", *others[:14], stdin=BODY + EVIDENCE)  # F-008
        self.assertNotIn('is saved', out, out)
        has(new("lib", "design", "none", "no evidence", "high", *others[:16], stdin=BODY), "F-009: section `Evidence` is empty", "is saved")
        has(new("lib", "design", "none", "x", "huge", stdin=BODY, ok=False), "severity")
        has(take("A5", "security", "--done", "T-011", "--result", "hit", "--finding", "F-001", "--note", "escaped"),
            "T-011 recorded: hit")
        has(roast("check", "findings", "--run", run, ok=False), "findings: 1 problem(s)")
        has(roast("status", "--run", run), "targets: 13 | tried 2 (1 hit, 1 held) | skipped 0 | in hand 11 | free 0",
            "piece lib: 3 target(s), 2 tried", "9 open", "A7: input", "this round's list: 12 target(s), 10 not done | left outside it: 1")

        # a dog hands back only when the script lets it, with the lines the script gives
        has(roast("leave", "--run", run, "--agent", "A5"), "STAY", "The list is empty: add targets of your own")
        has(roast("leave", "--run", run, "--agent", "A1", "--nothing-left"), "STAY. You still hold T-013")
        has(roast("leave", "--run", run, "--agent", "A5", "--nothing-left"), "LEAVE.",
            "targets: 2 tried (1 hit, 1 held), 0 skipped", "findings: none", "stopped by: nothing left to try")

        # ---- verify: the sandbox is cleaned and every proof is run again
        roast("phase", "verify", "--run", run)
        has(take("A1", "rules"), "No targets are handed out in the verify phase")
        has(roast("leave", "--run", run, "--agent", "A1"), "STAY. You still hold T-013")
        has(take("A1", "input", "--done", "T-013", "--result", "skip", "--note", "needs a network the sandbox lacks"), "T-013 recorded: skip")
        has(roast("leave", "--run", run, "--agent", "A1"), "LEAVE.", "targets: 0 tried (0 hit, 0 held), 1 skipped",
            "findings: F-001 F-002 F-003 F-004 F-005 F-006 F-007 F-008 F-009", "stopped by: clock")
        out = roast("verify", "--run", run)
        has(out, "1 target file(s) had been changed", "proj/app.py", "F-001: proof passed",
            "F-007: proof FAILED (exit 1)", "6 proof(s) passed, 1 failed")
        self.assertEqual((box / 'app.py').read_text(), 'print(1)\n')
        has((run / "04-findings" / "F-007.md").read_text(), "status: unconfirmed", "proof_result: failed", "05-verify/F-007.txt")
        self.assertTrue((run / '05-verify' / 'F-007.txt').read_text().startswith('exit 1'))

        # ---- the judge
        roast("phase", "judge", "--run", run)
        has(crew(), "9 finding(s). Launch one judge:", "judge | judge | all findings")
        out = roast("crew", "--run", run, env={"ROAST_JUDGE_LOAD": "3"})  # too many for one judge: split by piece
        has(out, "Launch 2 judges together", "judge-1 | judge | Pieces: core", "judge-2 | judge | Pieces: lib", "judge | judge | summary")
        roast("verdict", "F-001", "confirmed", "--note", "the rule is stated in the README", "--run", run)
        has(roast("verdict", "F-002", "confirmed", "--severity", "medium", "--run", run), "severity medium")
        roast("verdict", "F-003", "duplicate", "--run", run, ok=False)
        roast("verdict", "F-003", "duplicate", "--duplicate-of", "F-001", "--run", run)
        roast("verdict", "F-004", "rejected", "--note", "-", "--run", run, stdin="by design: `x` isn't checked, see $HOME")
        has((run / "04-findings" / "F-004.md").read_text(encoding="utf-8"), "isn't checked, see $HOME")
        has(roast("summary", "--run", run, stdin="# Verdict\nTwo.\n", ok=False), "the whole page")
        has(roast("summary", "--run", run, stdin="# Verdict\nTwo real defects.\n" + "The refund flow pays out twice. " * 8), "summary saved")
        has(roast("finding", "list", "--run", run), "F-002  confirmed   medium", "F-007  unconfirmed", "layers: mixed")

        # ---- the report
        has(roast("check-source", "--run", run), "source unchanged")
        roast("phase", "report", "--run", run)
        has(roast("report", "--run", run), "targets: 13 on the list | 2 run (1 broke the target, 1 held) | 1 skipped | 10 never tried",
            "findings: 4 open, 2 confirmed, 1 unconfirmed, 1 rejected, 1 duplicate | 9 in all", "source: unchanged",
            "confirmed by level: critical 0 | high 1 |", "pieces (targets | run | broke the target",
            "attack round 1: 7 agents at once, asked 30 min", ", took ", "studied: 2 piece(s)",
            "to finish the 10 left (", "`more <agents> [<minutes>] --run")
        report = (run / "REPORT.md").read_text(encoding="utf-8")
        has(report, focus, "## Summary by the judge", "### Verdict", "Two real defects.", "### F-001 [high] t",
            "(was high)", "- F-003 duplicate of F-001", "- F-004 rejected", "### F-007 [high]", "Proof: failed",
            "| core | 10 | 0 | 0 | 0 | 10 | 7 |", "| lib | 3 | 1 | 1 | 1 | 0 | 2 |", "- T-011 [security] hit -> F-001 by A5",
            "- T-012 [security] miss by A5", "## Committed to but not finished: 10 target(s)", "- T-013 [input] skip by A1",
            "The last round committed to 12 target(s): 2 were run, 0 skipped, 10 not finished. "
            "Outside that list, over all rounds: 0 run, 1 skipped, 0 never taken.",
            "## Never taken: 0 target(s)", "Attack rounds: 7 agents at once, about 30 min, 12 target(s) committed to",
            "match the fingerprint", "put back before", "- proj/app.py", "## Validation problems", "#### Proof output")
        self.assertTrue(report.index('## Confirmed') < report.index('## Not confirmed') < report.index('## Rejected'))

        # ---- any change to the source is detected and lands in the report
        (src / "app.py").write_text("print(22)\n")
        (src / "new.py").write_text("")
        has(roast("check-source", "--run", run, ok=False), "changed app.py", "added new.py")
        roast("report", "--run", run)
        has((run / "REPORT.md").read_text(encoding="utf-8"), "targets changed during the run")

        # ---- a later run reuses the study and is told which pieces to read again
        out = roast("start", 5, 10, src, "--out", tmp / "again", "--study-from", run)
        has(out, "13 targets, none of them tried yet", "2 file(s) changed since that study",
            "read again before the attack: core")
        again = run_folder(out)
        self.assertTrue((again / '02-targets' / 'T-013.json').is_file() and (not list((again / '02-targets').glob('*.claim'))))
        self.assertTrue(not (again / '01-study' / 'core.dossier.md').exists() and (again / '01-study' / 'lib.dossier.md').is_file())
        has(roast("crew", "--run", again), "read-core | reader | Piece: core")
        has(roast("check", "study", "--run", again, ok=False), "1 file(s) belong to no piece", "proj/new.py")

        # ---- the disk is freed at the end; the scripts the record points at stay
        has(roast("clean", "--run", run), "kept 3 proof script(s)")
        self.assertTrue(not box.exists() and (poc / 'ok.py').is_file() and (poc / 'bad.py').is_file() and (poc / 'dirty.py').is_file())

        # ---- a later round finishes what is left; with no minutes it has no time limit
        has(roast("more", 0, "--run", run, ok=False), "at least 1")
        out = roast("more", 4, "--run", run)
        has(out, "copied:", "10 target(s) are left", "no time limit, all of them")
        has(crew(), "scout | scout | rebuild")  # the sandbox was cleaned: it has to be built again
        out = roast("phase", "attack", "--run", run)
        has(out, "[roast] attack: no time limit, 10 target(s) left | CONTINUE", "This round's list: all 10 target(s) that are left")
        has(crew(), "A4 | dog | Style: failure")
        self.assertTrue('A5' not in crew() and 'rebuild' not in crew())
        has(roast("status", "--run", run, env={"ROAST_STALL": "0"}), "[roast] attack: over | STOP")  # nothing moves: it ends
        out = take("X1", "rules")
        for n in range(1, 11):
            self.assertEqual(taken(out), f'T-{n:03d}', out)
            out = take("X1", "rules", "--done", f"T-{n:03d}", "--result", "skip", "--note", "needs a network")
        has(out, "T-010 recorded: skip", "STOP: no new targets")
        has(roast("wait", "--run", run, env={"ROAST_POLL": "0.1"}), "The attack is over")
        roast("phase", "verify", "--run", run), roast("verify", "--run", run), roast("phase", "judge", "--run", run)
        has(crew(), "5 finding(s). Launch one judge")  # only what has no verdict yet
        roast("phase", "report", "--run", run)
        out = roast("report", "--run", run)
        has(out, "targets: 13 on the list | 2 run (1 broke the target, 1 held) | 11 skipped | 0 never tried")
        self.assertNotIn('to finish', out, out)
        has((run / "REPORT.md").read_text(encoding="utf-8"),
            "12 target(s) committed to; 4 agents at once, no time limit, 10 target(s) committed to")
        has(roast("more", 4, "--run", run), "nothing is left to finish")

    def test_clock(self):
        tmp = self.tmp
        fast = {"ROAST_POLL": "0.1"}
        (tmp / "a").mkdir()
        run = one_file_run(tmp / "a", 0.1)  # asked for 6 s; the hard stop is at 9 s
        has(roast("wait", "--run", run), "[roast] study: no clock", "Nothing to wait for")
        has(roast("phase", "attack", "--run", run), "This round's list: 2 of 2 target(s)")
        t0 = json.loads((run / "run.json").read_text())["attack"]["start"]
        at = lambda: time.time() - t0
        take = lambda *more, **kw: roast("take", "--run", run, "--agent", "A1", "--style", "rules", *more, **kw)
        miss = lambda tid: take("--done", tid, "--result", "miss", "--proof", "sandbox/_poc/A1/try.py", "--note", "held")
        self.assertEqual(taken(take()), 'T-001')
        add_target(run, "whole", agent="A2")  # T-003: added during the attack, so it is reserve

        # the time is up but the list is not done: the pack goes on
        out = roast("wait", "--run", run, env={**fast, "ROAST_MAX_SLEEP": "6.2"})
        self.assertTrue(6.1 < at() < 6.8, at())
        has(out, "OVERTIME", "2 target(s) of this run's list are not done", "the pack goes on")
        out = miss("T-001")
        has(out, "T-001 recorded: miss")
        self.assertEqual(taken(out), 'T-002')  # what the run committed to is still handed out
        has(roast("take", "--run", run, "--agent", "A2", "--style", "rules", "--target", "T-003", ok=False),
            "only the targets of this run's list")
        has(roast("take", "--run", run, "--agent", "A2", "--style", "rules"), "Nothing is left to take")
        has(roast("leave", "--run", run, "--agent", "A2"), "LEAVE.", "stopped by: clock")
        has(roast("leave", "--run", run, "--agent", "A1"), "STAY. You still hold T-002")

        # the list is done before the hard stop: the attack is over at once
        has(miss("T-002"), "T-002 recorded: miss", "STOP: no new targets")
        out = roast("wait", "--run", run, env=fast)
        self.assertLess(at(), 8.8, at())
        has(out, "[roast] attack: over | STOP", "run `phase verify`")
        has(roast("finding", "list", "--run", run), "STOP")  # dogs see STOP on every command
        has(roast("leave", "--run", run, "--agent", "A1"), "LEAVE.", "targets: 2 tried (0 hit, 2 held), 0 skipped", "stopped by: clock")
        has(roast("phase", "verify", "--run", run), "[roast] verify: no clock")
        has(roast("wait", "--run", run), "Nothing to wait for")

        # a list that is never finished ends at the hard stop
        (tmp / "b").mkdir()
        run = one_file_run(tmp / "b", 0.02)  # asked for 1.2 s; the hard stop is at 1.8 s
        roast("phase", "attack", "--run", run)
        t0 = json.loads((run / "run.json").read_text())["attack"]["start"]
        out = roast("wait", "--run", run, env=fast)
        self.assertTrue(1.7 < at() < 2.4, at())
        has(out, "[roast] attack: over | STOP")
        has(roast("status", "--run", run), "this round's list: 2 target(s), 2 not done | left outside it: 0")

    def test_sleep_cap_and_relay(self):
        tmp = self.tmp
        run = one_file_run(tmp, 30)
        roast("phase", "attack", "--run", run)
        t0 = time.time()
        out = roast("wait", "--run", run, env={"ROAST_MAX_SLEEP": "0.5"})
        self.assertLess(time.time() - t0, 1.5)
        has(out, "No checkpoint yet")

        # after its share of targets a dog hands over to a fresh one
        one = {"ROAST_RELAY_AFTER": "1"}
        take = lambda agent, *more: roast("take", "--run", run, "--agent", agent, "--style", "rules", *more, env=one)
        self.assertEqual(taken(take('A1')), 'T-001')
        out = take("A1", "--done", "T-001", "--result", "skip", "--note", "needs a network")
        has(out, "T-001 recorded: skip", "RELAY: you have reported 1 targets")
        self.assertIsNone(taken(out))
        has(roast("leave", "--run", run, "--agent", "A1", env=one), "LEAVE.", "targets: 0 tried (0 hit, 0 held), 1 skipped", "stopped by: relay")
        self.assertEqual(taken(take('A1-2')), 'T-002')

    def test_git_target(self):
        """In a git repository only what git keeps is copied and fingerprinted."""
        tmp = self.tmp
        src = tmp / "repo"
        (src / "src").mkdir(parents=True)
        (src / "target").mkdir()
        (src / "src" / "main.rs").write_text("fn main() {}\n")
        (src / "target" / "big.bin").write_text("build output")
        (src / ".gitignore").write_text("/target/\n")
        subprocess.run(["git", "init", "-q", str(src)], check=True)
        run = run_folder(roast("start", 5, 30, src, "--out", tmp / "roasts"))
        has(roast("sandbox", "--run", run), "what git does not ignore")
        box = run / "sandbox" / "repo"
        self.assertTrue((box / 'src' / 'main.rs').is_file() and (box / '.gitignore').is_file())
        self.assertTrue(not (box / 'target').exists() and (not (box / '.git').exists()))

        # the study has to account for the kept files only
        write_map(run, {"all": ["repo"]})
        write_dossier(run, "all", ["repo/src/main.rs", "repo/.gitignore"])
        add_target(run, "all")
        has(roast("check", "study", "--run", run), "study: 0 problem(s)")

        # a rebuild in the original is not a change to the source; a new source file is
        (src / "target" / "big.bin").write_text("rebuilt")
        (src / "target" / "more.bin").write_text("x")
        has(roast("check-source", "--run", run), "source unchanged")
        (src / "src" / "new.rs").write_text("")
        has(roast("check-source", "--run", run, ok=False), "added src/new.rs")

    def test_run_inside_the_project(self):
        """By default the results live in <target>/.roast; the copy that is built and run lives outside it."""
        tmp = self.tmp
        src, work = tmp / "proj", tmp / "work"
        src.mkdir()
        (src / "app.py").write_text("def refund(x):\n    return x\n")
        env = {"ROAST_WORK": str(work)}
        has(roast("start", 2, 5, src, "--out", src / "elsewhere", ok=False), "inside the target")
        run = run_folder(roast("start", 2, 5, src, env=env))
        self.assertTrue(run.parent == src / '.roast' / 'artifacts' and len(run.name) == len('2026-11-21_01-07-04'), run)
        roast("sandbox", "--run", run, env=env)
        box = run / "sandbox"
        self.assertTrue(box.is_symlink() and work in box.resolve().parents, box.resolve())
        self.assertTrue((box / 'proj' / 'app.py').is_file() and (not (box / 'proj' / '.roast').exists()))

        # the run's own files are neither source to study nor a change to the source
        write_map(run, {"all": ["proj"]})
        write_dossier(run, "all", ["proj/app.py"])
        add_target(run, "all")
        has(roast("check", "study", "--run", run), "study: 0 problem(s)")
        has(roast("check-source", "--run", run), "source unchanged")

        # a proof is found through the link, and survives the cleaning inside the project
        roast("phase", "attack", "--run", run)
        target = taken(roast("take", "--run", run, "--agent", "A1", "--style", "rules"))
        poc = box / "_poc" / "A1"
        poc.mkdir(parents=True)
        (poc / "p.py").write_text("print('refund accepted -5')\n")
        (poc / "scratch.db").write_text("x")
        has(roast("finding", "new", "--run", run, "--agent", "A1", "--piece", "all", "--severity", "high",
                  "--category", "correctness", "--location", "proj/app.py:1", "--title", "negative refund accepted",
                  "--proof", "sandbox/_poc/A1/p.py", "--target", target, stdin=BODY), "F-001")
        has(roast("clean", "--run", run), "kept 1 proof script(s)")
        self.assertTrue(not box.is_symlink() and (box / '_poc' / 'A1' / 'p.py').is_file() and (not (box / 'proj').exists()))
        self.assertFalse(any(work.iterdir()), list(work.iterdir()))

        # a finishing round moves the copy out again and keeps the proof
        roast("sandbox", "--run", run, env=env)
        self.assertTrue(box.is_symlink() and (box / '_poc' / 'A1' / 'p.py').is_file() and (box / 'proj' / 'app.py').is_file())
        has(roast("check-source", "--run", run), "source unchanged")


    def test_links_do_not_lead_back_to_the_original(self):
        tmp = self.tmp.resolve()
        src = tmp / "proj"
        src.mkdir()
        (src / "real.txt").write_text("original")
        (tmp / "outside.txt").write_text("outside")
        os.symlink(src / "real.txt", src / "inside.txt")  # an absolute link into the target itself
        os.symlink(tmp / "outside.txt", src / "out.txt")  # a link out of the target, to a file
        os.symlink(tmp / "nowhere", src / "dangling.txt")
        run = run_folder(roast("start", 2, 5, src, "--out", tmp / "roasts"))
        has(roast("sandbox", "--run", run), "left out: 1 link")
        box = run / "sandbox" / "proj"
        (box / "inside.txt").write_text("changed")
        (box / "out.txt").write_text("changed")
        self.assertEqual((box / "real.txt").read_text(), "changed")  # the link leads to the copy's own file
        self.assertEqual((src / "real.txt").read_text(), "original")
        self.assertEqual((tmp / "outside.txt").read_text(), "outside")
        self.assertFalse(os.path.lexists(box / "dangling.txt"))
        has(roast("check-source", "--run", run), "source unchanged")


    def test_verify_runs_proofs_on_clean_sources(self):
        """What the pack added to the copy is gone before a proof is run again; build output stays."""
        tmp = self.tmp
        src = tmp / "proj"
        (src / "pkg").mkdir(parents=True)
        (src / "pkg" / "app.py").write_text("print(1)\n")
        (src / ".gitignore").write_text("/build/\n")
        subprocess.run(["git", "init", "-q", str(src)], check=True)
        run = run_folder(roast("start", 2, 5, src, "--out", tmp / "roasts"))
        roast("sandbox", "--run", run)
        box = run / "sandbox" / "proj"
        (box / "planted.flag").write_text("x")
        (box / "build").mkdir()
        (box / "build" / "out.bin").write_text("built")
        (box / "pkg" / "app.py").unlink()
        (box / "pkg" / "app.py").mkdir()  # a folder where the file was
        has(roast("verify", "--run", run), "1 target file(s)", "put back: proj/pkg/app.py",
            "1 file(s) the target does not have were removed from the sandbox: proj/planted.flag")
        self.assertEqual((box / "pkg" / "app.py").read_text(), "print(1)\n")
        self.assertFalse((box / "planted.flag").exists())
        self.assertTrue((box / "build" / "out.bin").is_file())


if __name__ == "__main__":
    unittest.main()
